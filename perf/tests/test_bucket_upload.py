"""Storage Bucket upload of every sealed job (issue #162, r3bucket).

A fake in-memory bucket client is injected through mirror.BUCKET_CLIENT_FACTORY;
no test touches the network.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


class FakeBucketClient:
    """Stand-in for the HfApi calls mirror.py uses."""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.calls: list[tuple] = []
        self.fail_on_batch = False
        self.fail_on_list = False
        self.drop_dests: set[str] = set()

    def list_bucket_tree(self, bucket_id, prefix=None, *, recursive=None, token=None):
        self.calls.append(('list', prefix))
        if self.fail_on_list:
            raise RuntimeError('simulated list failure')
        for path in sorted(self.files):
            if prefix is None or path.startswith(prefix):
                data = self.files[path]
                yield SimpleNamespace(type='file', path=path, size=len(data))

    def batch_bucket_files(self, bucket_id, *, add=None, copy=None, delete=None, token=None):
        self.calls.append(('batch', sorted(dest for _s, dest in (add or []))))
        if self.fail_on_batch:
            raise RuntimeError('simulated upload failure')
        for src, dest in add or []:
            if dest in self.drop_dests:
                continue
            self.files[dest] = Path(src).read_bytes()


def seal_job(remote: Path, run_id: str, runner: str, job_id: str, files: dict[str, str], status: int = 0) -> Path:
    job = remote / 'runs' / run_id / runner / job_id
    job.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = job / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    from perf.container import artifacts

    artifacts.finalize_job(job, status)
    return job


@pytest.fixture
def bucket_env(tmp_path, monkeypatch):
    from perf.container import mirror

    client = FakeBucketClient()
    monkeypatch.setattr(mirror, 'BUCKET_CLIENT_FACTORY', lambda token: client)
    monkeypatch.setenv('HF_BUCKET_TOKEN', 'unit-test-token')
    monkeypatch.setenv('SPACE_ID', 'arthrod/e2-publish')
    monkeypatch.setenv('HF_MIRROR_ROOT', str(tmp_path / 'mirror'))
    monkeypatch.delenv('HF_BUCKET_ID', raising=False)
    return client


def campaign_root(remote: Path, run_id: str) -> Path:
    return remote / 'runs' / run_id


def bucket_lines(run_log: Path, job: str | None = None):
    lines = [
        line for line in run_log.read_text().splitlines()
        if line.startswith(('BUCKET-OK ', 'BUCKET-ERROR '))
    ]
    if job is not None:
        lines = [line for line in lines if line.split(' ', 2)[1] == job]
    return lines


class TestUploadOnSeal:
    def test_sealed_job_uploads_under_space_run_prefix(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-1'
        job_dir = seal_job(
            remote, run_id, 'benchmark_warm_cold', f'{run_id}-000',
            {'summary.json': '{"samples": []}', 'cells/c1/attempts/a.json': '{}'},
        )
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        mirror.mirror_job_directory(run_id, 'benchmark_warm_cold', f'{run_id}-000', job_dir, run_log)
        prefix = 'runs/arthrod/e2-publish/camp-1/benchmark_warm_cold/camp-1-000'
        for name in ('summary.json', 'cells/c1/attempts/a.json', 'MANIFEST.sha256', 'JOB-DONE'):
            assert bucket_env.files[f'{prefix}/{name}'] == (job_dir / name).read_bytes(), name

    def test_campaign_level_files_upload_to_run_prefix(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-2'
        campaign = campaign_root(remote, run_id)
        job_dir = seal_job(remote, run_id, 'benchmark_input', f'{run_id}-000', {'summary.json': '{}'})
        run_log = campaign / 'RUN.log'
        run_log.write_text('first line\n')
        (campaign / 'RUN-DONE').write_text('exit_status=0\n')
        out_dir = campaign / 'out'
        out_dir.mkdir()
        (out_dir / 'e2-publication.json').write_text('{"runs": []}')
        mirror.mirror_job_directory(run_id, 'benchmark_input', f'{run_id}-000', job_dir, run_log)
        prefix = 'runs/arthrod/e2-publish/camp-2'
        assert (run_log.read_bytes()) == bucket_env.files[f'{prefix}/RUN.log']
        assert bucket_env.files[f'{prefix}/RUN-DONE'] == b'exit_status=0\n'
        assert bucket_env.files[f'{prefix}/out/e2-publication.json'] == b'{"runs": []}'

    def test_tail_uploads_jobs_and_campaign_files(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-3'
        campaign = campaign_root(remote, run_id)
        seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{}'})
        run_log = campaign / 'RUN.log'
        run_log.write_text('tail\n')
        (campaign / 'RUN-DONE').write_text('exit_status=0\n')
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        prefix = f'runs/arthrod/e2-publish/{run_id}'
        assert f'{prefix}/runner_a/{run_id}-000/summary.json' in bucket_env.files
        assert f'{prefix}/runner_b/{run_id}-001/summary.json' in bucket_env.files
        assert bucket_env.files[f'{prefix}/RUN-DONE'] == b'exit_status=0\n'
        assert bucket_env.files[f'{prefix}/RUN.log'] == run_log.read_bytes()

    def test_space_name_falls_back_to_hostname(self, tmp_path, bucket_env, monkeypatch):
        import socket

        from perf.container import mirror

        monkeypatch.delenv('SPACE_ID')
        monkeypatch.setattr(socket, 'gethostname', lambda: 'mac-box-9')
        remote = tmp_path / 'remote'
        run_id = 'camp-4'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir,
                                    campaign_root(remote, run_id) / 'RUN.log')
        assert f'runs/mac-box-9/{run_id}/runner_a/{run_id}-000/summary.json' in bucket_env.files

    def test_unsealed_job_is_not_uploaded(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-5'
        campaign = campaign_root(remote, run_id)
        inflight = campaign / 'runner_a' / f'{run_id}-000'
        inflight.mkdir(parents=True)
        (inflight / 'summary.json').write_text('{"partial": true}')
        run_log = campaign / 'RUN.log'
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        assert not any(f'{run_id}-000' in path for path in bucket_env.files)


class TestExclusions:
    def test_exclusion_constant_matches_only_non_generated_paths(self):
        from perf.container import mirror

        for rel in (
            'fixtures/w1-abcdef0123456789.docx', 'cells/c1/fixtures/in.docx',
            'builds/plate/abc123/dist/assets/index.js', 'builds/plate/abc123/build.json',
            'benchmark_input/job/builds/editor/x.js',
            'dist/app.js', 'job/dist/app.js',
            'node_modules/pkg/index.js', 'job/node_modules/pkg/index.js',
            'repos/plate/README.md', 'a/repos/x',
            'input.docx', 'cells/c1/input.docx', 'fixtures/nested/dir/in.docx',
        ):
            assert mirror.bucket_excluded(rel), rel
        for rel in (
            'summary.json', 'cells/c1/attempts/a.json', 'samples/s1.json',
            'evidence/e.json', 'rejected-evidence/r/cell/x.json',
            'MANIFEST.sha256', 'JOB-DONE', 'campaign-meta.json',
            'out/e2-publication.json', 'RUN.log', 'RUN-DONE', 'RUN.pid',
            'traces/t1.zip', 'distance.txt',
        ):
            assert not mirror.bucket_excluded(rel), rel

    def test_fixture_build_dist_and_docx_files_never_upload(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-6'
        campaign = campaign_root(remote, run_id)
        job_dir = seal_job(
            remote, run_id, 'runner_a', f'{run_id}-000',
            {
                'summary.json': '{}',
                'fixtures/w1-aaaa.docx': 'INPUT-DOCX',
                'input.docx': 'INPUT-DOCX-2',
                'builds/plate/abc/dist/app.js': 'CODE',
                'node_modules/pkg/index.js': 'CODE',
                'repos/plate/f.py': 'CODE',
                'evidence/e.json': '{}',
            },
        )
        dist = campaign / 'builds' / 'plate' / 'abc' / 'dist'
        dist.mkdir(parents=True)
        (dist / 'index.js').write_text('CODE')
        (campaign / 'builds' / 'plate' / 'abc' / 'build.json').write_text('{}')
        run_log = campaign / 'RUN.log'
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        leaked = [
            path for path, data in bucket_env.files.items()
            if data in (b'INPUT-DOCX', b'INPUT-DOCX-2', b'CODE')
        ]
        assert leaked == []
        prefix = f'runs/arthrod/e2-publish/{run_id}'
        assert not any('builds/' in path or 'fixtures/' in path or 'node_modules/' in path
                       or '/repos/' in path or path.endswith('.docx') or '/dist/' in path
                       for path in bucket_env.files)
        assert f'{prefix}/runner_a/{run_id}-000/evidence/e.json' in bucket_env.files


class TestVerifyAndLogLines:
    def test_bucket_ok_line_counts_files_and_bytes(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-10'
        job_dir = seal_job(
            remote, run_id, 'runner_a', f'{run_id}-000',
            {'summary.json': '12345', 'cells/c1/attempts/a.json': 'x' * 20},
        )
        run_log = campaign_root(remote, run_id) / 'RUN.log'
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        expected = 4  # summary.json, cells/..., MANIFEST.sha256, JOB-DONE
        manifest_bytes = (job_dir / 'MANIFEST.sha256').stat().st_size
        done_bytes = (job_dir / 'JOB-DONE').stat().st_size
        total = 5 + 20 + manifest_bytes + done_bytes
        assert bucket_lines(run_log, 'runner_a/camp-10-000') == [
            f'BUCKET-OK runner_a/{run_id}-000 {expected} {total}'
        ]

    def test_upload_failure_logs_one_error_line_and_returns(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-11'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        run_log = campaign_root(remote, run_id) / 'RUN.log'
        bucket_env.fail_on_batch = True
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        lines = bucket_lines(run_log, f'runner_a/{run_id}-000')
        assert len(lines) == 1 and lines[0].startswith('BUCKET-ERROR ')
        assert 'simulated upload failure' in lines[0]

    def test_remote_mismatch_after_upload_logs_error(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-12'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        run_log = campaign_root(remote, run_id) / 'RUN.log'
        prefix = f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000'
        bucket_env.drop_dests.add(f'{prefix}/summary.json')
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        lines = bucket_lines(run_log, f'runner_a/{run_id}-000')
        assert len(lines) == 1
        assert lines[0].startswith('BUCKET-ERROR ') and 'mismatch' in lines[0]

    def test_failed_upload_retried_on_the_next_seal(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-13'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job1 = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{"a": 1}'})
        bucket_env.fail_on_batch = True
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job1, run_log)
        assert bucket_lines(run_log, f'runner_a/{run_id}-000')[0].startswith('BUCKET-ERROR ')
        assert f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000/summary.json' not in bucket_env.files
        bucket_env.fail_on_batch = False
        job2 = seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{"b": 2}'})
        mirror.mirror_job_directory(run_id, 'runner_b', f'{run_id}-001', job2, run_log)
        prefix = f'runs/arthrod/e2-publish/{run_id}'
        assert f'{prefix}/runner_a/{run_id}-000/summary.json' in bucket_env.files
        ok_lines = [
            line for line in bucket_lines(run_log)
            if line.startswith('BUCKET-OK ')
        ]
        assert f'BUCKET-OK runner_a/{run_id}-000 3 {sum(p.stat().st_size for p in job1.rglob("*") if p.is_file())}' in ok_lines
        assert any(line.startswith(f'BUCKET-OK runner_b/{run_id}-001 ') for line in ok_lines)

    def test_tail_rechecks_every_job_and_logs_one_line_each(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-14'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        jobs = [
            seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'}),
            seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{}'}),
        ]
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        for job in jobs:
            rel = job.relative_to(campaign).as_posix()
            assert len(bucket_lines(run_log, rel)) == 1
            assert bucket_lines(run_log, rel)[0].startswith('BUCKET-OK ')

    def test_tail_reuploads_files_missing_from_remote(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-15'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': 'data'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        gone = f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000/summary.json'
        del bucket_env.files[gone]
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        assert bucket_env.files[gone] == b'data'
        assert bucket_lines(run_log, f'runner_a/{run_id}-000')[-1].startswith('BUCKET-OK ')

    def test_unexpected_remote_file_is_a_verify_mismatch(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-16'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        bucket_env.files[f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000/stale.txt'] = b'x'
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        last = bucket_lines(run_log, f'runner_a/{run_id}-000')[-1]
        assert last.startswith('BUCKET-ERROR ') and 'mismatch' in last

    def test_seal_pass_does_not_relog_complete_jobs(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-17'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job1 = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job1, run_log)
        job2 = seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_b', f'{run_id}-001', job2, run_log)
        assert len(bucket_lines(run_log, f'runner_a/{run_id}-000')) == 1
        assert len(bucket_lines(run_log, f'runner_b/{run_id}-001')) == 1


class TestToken:
    def test_no_token_logs_bucket_skip_once_per_run(self, tmp_path, monkeypatch):
        from perf.container import mirror

        monkeypatch.delenv('HF_BUCKET_TOKEN', raising=False)
        monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(tmp_path / 'absent-environ'))
        client = FakeBucketClient()
        monkeypatch.setattr(mirror, 'BUCKET_CLIENT_FACTORY', lambda token: client)
        remote = tmp_path / 'remote'
        run_id = 'camp-20'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job1 = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job1, run_log)
        job2 = seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_b', f'{run_id}-001', job2, run_log)
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        text = run_log.read_text() if run_log.exists() else ''
        assert text.count('BUCKET-SKIP no_token') == 1
        assert 'BUCKET-OK' not in text and 'BUCKET-ERROR' not in text
        assert client.files == {} and not any(c[0] == 'batch' for c in client.calls)

    def test_proc1_environ_supplies_token_when_env_missing(self, tmp_path, monkeypatch):
        from perf.container import mirror

        environ = tmp_path / 'environ'
        environ.write_bytes(b'PATH=/usr/bin\0HF_BUCKET_TOKEN=proc1-test-token\0OTHER=1\0')
        monkeypatch.delenv('HF_BUCKET_TOKEN', raising=False)
        monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(environ))
        assert mirror._bucket_token() == 'proc1-test-token'

    def test_env_token_wins_over_proc1_environ(self, tmp_path, monkeypatch):
        from perf.container import mirror

        environ = tmp_path / 'environ'
        environ.write_bytes(b'HF_BUCKET_TOKEN=proc1-test-token\0')
        monkeypatch.setenv('HF_BUCKET_TOKEN', 'env-test-token')
        monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(environ))
        assert mirror._bucket_token() == 'env-test-token'

    def test_unreadable_proc1_environ_means_no_token(self, tmp_path, monkeypatch):
        from perf.container import mirror

        monkeypatch.delenv('HF_BUCKET_TOKEN', raising=False)
        monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(tmp_path / 'not-there'))
        assert mirror._bucket_token() is None

    def test_upload_runs_on_proc1_token(self, tmp_path, bucket_env, monkeypatch):
        from perf.container import mirror

        environ = tmp_path / 'environ'
        environ.write_bytes(b'HF_BUCKET_TOKEN=proc1-test-token\0')
        monkeypatch.delenv('HF_BUCKET_TOKEN')
        monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(environ))
        remote = tmp_path / 'remote'
        run_id = 'camp-21'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir,
                                    campaign_root(remote, run_id) / 'RUN.log')
        assert f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000/summary.json' in bucket_env.files

    def test_missing_library_logs_skip_once(self, tmp_path, monkeypatch):
        from perf.container import mirror

        monkeypatch.setenv('HF_BUCKET_TOKEN', 'test-token-x')
        monkeypatch.setattr(mirror, 'BUCKET_CLIENT_FACTORY', None)
        monkeypatch.setitem(sys.modules, 'huggingface_hub', None)
        remote = tmp_path / 'remote'
        run_id = 'camp-22'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job1 = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job1, run_log)
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        text = run_log.read_text() if run_log.exists() else ''
        assert text.count('BUCKET-SKIP no_huggingface_hub') == 1

    def test_token_never_appears_in_log_stderr_or_run_files(self, tmp_path, monkeypatch, capsys):
        from perf.container import mirror

        token = 'test-token-neverlogged-0001'
        monkeypatch.setenv('HF_BUCKET_TOKEN', token)

        def leaky_batch(bucket_id, *, add=None, copy=None, delete=None, token=None):
            raise RuntimeError(f'401 Unauthorized: token {token} rejected')

        client = FakeBucketClient()
        client.batch_bucket_files = leaky_batch
        monkeypatch.setattr(mirror, 'BUCKET_CLIENT_FACTORY', lambda t: client)
        remote = tmp_path / 'remote'
        run_id = 'camp-23'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        text = run_log.read_text()
        assert token not in text
        assert 'BUCKET-ERROR' in text and '<redacted>' in text
        for path in campaign.rglob('*'):
            if path.is_file():
                assert token.encode() not in path.read_bytes(), path
        captured = capsys.readouterr()
        assert token not in captured.out and token not in captured.err

    def test_mirror_main_sanitizes_token_in_exception_text(self, tmp_path, monkeypatch, capsys):
        from perf.container import mirror

        token = 'test-token-in-exc-0002'
        monkeypatch.setenv('HF_BUCKET_TOKEN', token)

        def boom(run_log, line):
            raise RuntimeError(f'log append failed with {token}')

        monkeypatch.setattr(mirror, '_append_run_log', boom)
        remote = tmp_path / 'remote'
        run_id = 'camp-24'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        rc = mirror.main(['job', run_id, 'runner_a', f'{run_id}-000', str(job_dir), str(run_log)])
        captured = capsys.readouterr()
        assert token not in captured.err and token not in captured.out
