"""Results reach the Storage Bucket through a Space volume mount (issue #164).

No Hugging Face token belongs in the container. The bucket is attached to
each Space as a volume at /data; the existing verified copy to
HF_MIRROR_ROOT (default /data/e2) is the bucket write. The copy carries
generated data only, and check_host refuses a Space without the mount.
"""
from __future__ import annotations

import json
from pathlib import Path

from perf.tests.test_bucket_upload import _isolate_space, _quiet_host, _run_check, _write_proc1, seal_job


def _mount(monkeypatch, tmp_path, *, mounted: bool) -> Path:
    from perf.container import mirror
    data = tmp_path / 'data'
    data.mkdir(exist_ok=True)
    root = data / 'e2'
    monkeypatch.setenv('HF_MIRROR_ROOT', str(root))
    monkeypatch.setattr(mirror, '_is_mount', lambda p: mounted and Path(p) == data)
    return root


class TestMirrorCopiesGeneratedDataOnly:
    def test_excluded_files_never_reach_the_mirror_root(self, tmp_path, monkeypatch):
        from perf.container import mirror
        monkeypatch.delenv('HF_BUCKET_TOKEN', raising=False)
        monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(tmp_path / 'absent'))
        root = _mount(monkeypatch, tmp_path, mounted=True)
        remote = tmp_path / 'remote'
        files = {
            'summary.json': '{}',
            'logs/run.log': 'ok',
            'builds/plate/dist/index.js': 'x',
            'builds/plate/node_modules/a/b.js': 'x',
            'fixtures/prose-500w.docx': 'x',
            'out/edited.docx': 'x',
            'repos/plate/README.md': 'x',
        }
        job = seal_job(remote, 'camp-1', 'runner_a', 'camp-1-000', files)
        run_log = remote / 'runs' / 'camp-1' / 'RUN.log'
        mirror.mirror_job_directory('camp-1', 'runner_a', 'camp-1-000', job, run_log)
        dest = root / 'camp-1' / 'runner_a' / 'camp-1-000'
        copied = sorted(p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file())
        assert 'summary.json' in copied and 'logs/run.log' in copied
        assert 'MIRROR-OK' in copied and 'JOB-DONE' in copied and 'MANIFEST.sha256' in copied
        assert not [c for c in copied if c.endswith('.docx') or c.startswith(('builds/', 'fixtures/', 'repos/'))]
        text = run_log.read_text() if run_log.exists() else ''
        assert 'MIRROR-ERROR' not in text

    def test_no_token_is_the_normal_state_and_logs_nothing(self, tmp_path, monkeypatch):
        from perf.container import mirror
        monkeypatch.delenv('HF_BUCKET_TOKEN', raising=False)
        monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(tmp_path / 'absent'))
        _mount(monkeypatch, tmp_path, mounted=True)
        remote = tmp_path / 'remote'
        job = seal_job(remote, 'camp-2', 'runner_a', 'camp-2-000', {'summary.json': '{}'})
        campaign = remote / 'runs' / 'camp-2'
        run_log = campaign / 'RUN.log'
        mirror.mirror_job_directory('camp-2', 'runner_a', 'camp-2-000', job, run_log)
        mirror.mirror_campaign_tail(campaign, 'camp-2', run_log)
        text = run_log.read_text() if run_log.exists() else ''
        assert 'BUCKET-SKIP' not in text and 'BUCKET-ERROR' not in text and 'MIRROR-ERROR' not in text


class TestMountStatus:
    def test_mounted_writable_root_is_ready(self, tmp_path, monkeypatch):
        from perf.container import mirror
        _mount(monkeypatch, tmp_path, mounted=True)
        assert mirror.mirror_mount_status() == 'mounted'

    def test_writable_root_without_a_mount_is_not_ready(self, tmp_path, monkeypatch):
        from perf.container import mirror
        _mount(monkeypatch, tmp_path, mounted=False)
        assert mirror.mirror_mount_status() == 'not_mounted'

    def test_unwritable_root_is_not_ready(self, tmp_path, monkeypatch):
        from perf.container import mirror
        blocker = tmp_path / 'file'
        blocker.write_text('x')
        monkeypatch.setenv('HF_MIRROR_ROOT', str(blocker / 'e2'))
        assert mirror.mirror_mount_status() == 'not_writable'

    def test_root_filesystem_is_not_a_bucket_mount(self, tmp_path, monkeypatch):
        from perf.container import mirror
        monkeypatch.setenv('HF_MIRROR_ROOT', str(tmp_path / 'e2'))
        monkeypatch.setattr(mirror, '_is_mount', lambda p: str(p) == '/')
        assert mirror.mirror_mount_status() == 'not_mounted'


class TestCheckHostMount:
    def test_space_without_mount_refuses(self, monkeypatch, tmp_path, capsys):
        _quiet_host(monkeypatch)
        _isolate_space(monkeypatch, tmp_path)
        _mount(monkeypatch, tmp_path, mounted=False)
        monkeypatch.setenv('SPACE_ID', 'arthrod/e2-publish')
        message = _run_check()
        payload = json.loads(capsys.readouterr().out)
        assert message is not None and 'no_bucket_mount' in message
        assert payload['bucket']['expected'] is True
        assert payload['bucket']['ready'] is False
        assert payload['bucket']['mount'] == 'not_mounted'
        assert 'no_bucket_mount' in payload['quiet_machine_check']['reasons']

    def test_space_with_mount_and_no_token_passes(self, monkeypatch, tmp_path, capsys):
        _quiet_host(monkeypatch)
        path = _isolate_space(monkeypatch, tmp_path)
        _write_proc1(path, {'SPACE_ID': 'arthrod/e2-publish'})
        _mount(monkeypatch, tmp_path, mounted=True)
        message = _run_check()
        payload = json.loads(capsys.readouterr().out)
        assert message is None
        assert payload['bucket']['expected'] is True
        assert payload['bucket']['ready'] is True
        assert payload['bucket']['mount'] == 'mounted'
        assert payload['bucket']['blocking'] == []
        assert 'token' not in payload['bucket']

    def test_flag_requires_the_mount_off_a_space(self, monkeypatch, tmp_path, capsys):
        _quiet_host(monkeypatch)
        _isolate_space(monkeypatch, tmp_path)
        _mount(monkeypatch, tmp_path, mounted=False)
        monkeypatch.setenv('HF_BUCKET_REQUIRED', '1')
        message = _run_check()
        assert message is not None and 'no_bucket_mount' in message

    def test_zero_flag_does_not_waive_the_mount_on_a_space(self, monkeypatch, tmp_path, capsys):
        _quiet_host(monkeypatch)
        _isolate_space(monkeypatch, tmp_path)
        _mount(monkeypatch, tmp_path, mounted=False)
        monkeypatch.setenv('SPACE_ID', 'arthrod/e2-publish')
        monkeypatch.setenv('HF_BUCKET_REQUIRED', '0')
        message = _run_check()
        assert message is not None and 'no_bucket_mount' in message

    def test_not_expected_off_a_space(self, monkeypatch, tmp_path, capsys):
        _quiet_host(monkeypatch)
        _isolate_space(monkeypatch, tmp_path)
        _mount(monkeypatch, tmp_path, mounted=False)
        message = _run_check()
        payload = json.loads(capsys.readouterr().out)
        assert message is None
        assert payload['bucket']['expected'] is False
        assert payload['quiet_machine_check']['reasons'] == []
