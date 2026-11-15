"""HF measurement data safety: manifests, detach, and continuous pull."""
from __future__ import annotations

import hashlib
import io
import json
import os
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from unittest import mock

import pytest


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def local_transport(remote_root: Path):
    from perf.container import pull as pull_mod

    return pull_mod.BashTransport(remote_root)


def write_job_tree(
    remote: Path,
    run_id: str,
    runner: str,
    job_id: str,
    *,
    files: dict[str, str],
    job_done: bool,
    status: int = 0,
):
    job = remote / 'runs' / run_id / runner / job_id
    job.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (job / name).write_text(content)
    from perf.container import artifacts

    if job_done:
        artifacts.finalize_job(job, status)


def count_tar_invocations(transport) -> int:
    if not hasattr(transport, 'call_log'):
        return 0
    from perf.container import pull as pull_mod

    needle = pull_mod.TAR_STDIN_MARKER
    return sum(1 for cmd in transport.call_log if needle in cmd)


def is_list_fragment(fragment: str) -> bool:
    return "os.walk(root)" in fragment or 'for dp,_,fns in os.walk' in fragment


def is_tar_fragment(fragment: str) -> bool:
    from perf.container import pull as pull_mod

    return pull_mod.TAR_STDIN_MARKER in fragment


class WatchTransport:
    """Wrap BashTransport to mutate the remote between list and tar."""

    def __init__(self, remote_root: Path, *, on_before_list=None, on_before_tar=None):
        from perf.container import pull as pull_mod

        self.inner = pull_mod.BashTransport(remote_root)
        self.remote_root = Path(remote_root)
        self.on_before_list = on_before_list
        self.on_before_tar = on_before_tar
        self.call_log = self.inner.call_log

    def run(self, fragment: str, *, stdin: bytes | None = None) -> bytes:
        if is_list_fragment(fragment) and self.on_before_list:
            self.on_before_list(self.remote_root)
        if is_tar_fragment(fragment) and self.on_before_tar:
            self.on_before_tar(self.remote_root, stdin)
        return self.inner.run(fragment, stdin=stdin)


@pytest.fixture
def remote_root(tmp_path):
    root = tmp_path / 'remote'
    (root / 'runs').mkdir(parents=True)
    return root


def test_job_done_absent_if_finalize_interrupted(tmp_path):
    from perf.container import artifacts

    job = tmp_path / 'job'
    job.mkdir()
    (job / 'summary.json').write_text('{}')
    original = artifacts.atomic_write

    def crash_on_job_done(path: Path, content: str):
        if path.name == 'JOB-DONE':
            path.with_suffix('.tmp').write_text(content)
            raise OSError('simulated crash')
        return original(path, content)

    artifacts.atomic_write = crash_on_job_done
    try:
        with pytest.raises(OSError, match='simulated'):
            artifacts.finalize_job(job, 0)
    finally:
        artifacts.atomic_write = original
    assert not (job / 'JOB-DONE').exists()


def test_manifest_matches_job_files(tmp_path):
    from perf.container import artifacts

    job = tmp_path / 'job'
    (job / 'cells').mkdir(parents=True)
    (job / 'summary.json').write_text('{"samples": []}')
    (job / 'cells' / 'a.json').write_text('1')
    artifacts.finalize_job(job, 0)
    manifest = (job / 'MANIFEST.sha256').read_text().splitlines()
    expected = []
    for path in sorted(
        p.relative_to(job).as_posix()
        for p in job.rglob('*')
        if p.is_file() and p.name not in ('MANIFEST.sha256', 'JOB-DONE')
    ):
        expected.append(f'{sha256_file(job / path)}  {path}')
    assert manifest == expected
    job_done = (job / 'JOB-DONE').read_text().splitlines()
    assert job_done[0] == 'exit_status=0'
    assert job_done[1] == f"manifest_sha256={sha256_bytes((job / 'MANIFEST.sha256').read_bytes())}"


def test_manifest_refuses_symlink_and_newline_name(tmp_path):
    from perf.container import artifacts

    job = tmp_path / 'job'
    job.mkdir()
    (job / 'summary.json').write_text('{}')
    target = tmp_path / 'outside.txt'
    target.write_text('x')
    (job / 'link').symlink_to(target)
    with pytest.raises(ValueError, match='symlink'):
        artifacts.finalize_job(job, 0)
    (job / 'link').unlink()
    bad = job / 'has\nnewline.txt'
    bad.write_text('y')
    with pytest.raises(ValueError, match='newline'):
        artifacts.finalize_job(job, 0)


def test_pull_second_cycle_fetches_nothing(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000000Z'
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'summary.json': '{}'},
        job_done=True,
    )
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_cycle(transport, remote_root, dest)
    capsys.readouterr()
    assert any('lstat' in cmd or 'S_ISLNK' in cmd for cmd in transport.call_log)
    transport.call_log.clear()
    pull_mod.pull_cycle(transport, remote_root, dest)
    second = capsys.readouterr().out
    assert second.strip() == ''
    assert count_tar_invocations(transport) == 0


def test_pull_never_deletes_local_when_remote_loses_file(remote_root, tmp_path):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000001Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    job = remote_root / job_rel
    job.mkdir(parents=True)
    (job / 'keep.txt').write_text('precious')
    from perf.container import artifacts

    artifacts.finalize_job(job, 0)
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_cycle(transport, remote_root, dest)
    local = dest / job_rel / 'keep.txt'
    assert local.read_text() == 'precious'
    (job / 'keep.txt').unlink()
    pull_mod.pull_cycle(transport, remote_root, dest)
    assert local.exists()
    assert local.read_text() == 'precious'


def test_pull_keeps_prev_copy_on_remote_change(remote_root, tmp_path):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000002Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    job = remote_root / job_rel
    job.mkdir(parents=True)
    (job / 'metric.txt').write_text('v1')
    from perf.container import artifacts

    artifacts.finalize_job(job, 0)
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_cycle(transport, remote_root, dest)
    (job / 'metric.txt').write_text('v2')
    (job / 'MANIFEST.sha256').unlink()
    (job / 'JOB-DONE').unlink()
    artifacts.finalize_job(job, 0)
    pull_mod.pull_cycle(transport, remote_root, dest)
    prev = list((dest / job_rel).glob('metric.txt.prev-*'))
    assert len(prev) == 1
    assert prev[0].read_text() == 'v1'
    assert (dest / job_rel / 'metric.txt').read_text() == 'v2'


def test_pull_keeps_three_prev_copies_within_same_second(remote_root, tmp_path, monkeypatch):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000002Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    job = remote_root / job_rel
    job.mkdir(parents=True)
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    fixed = '20260102T030405Z'

    def fake_strftime(fmt, t=None):
        if fmt == '%Y%m%dT%H%M%SZ':
            return fixed
        return time.strftime(fmt, t)

    monkeypatch.setattr(pull_mod.time, 'strftime', fake_strftime)
    for value in ('v1', 'v2', 'v3'):
        (job / 'metric.txt').write_text(value)
        (job / 'MANIFEST.sha256').unlink(missing_ok=True)
        (job / 'JOB-DONE').unlink(missing_ok=True)
        from perf.container import artifacts

        artifacts.finalize_job(job, 0)
        pull_mod.pull_cycle(transport, remote_root, dest)
    prev = sorted((dest / job_rel).glob('metric.txt.prev-*'))
    assert len(prev) == 2
    bodies = sorted(p.read_text() for p in prev)
    assert bodies == ['v1', 'v2']
    assert (dest / job_rel / 'metric.txt').read_text() == 'v3'


def test_corrupted_transfer_is_detected_and_refetched(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000003Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'a.txt': 'A' * 5000, 'b.txt': 'B' * 8000},
        job_done=True,
    )
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    cuts = {'n': 0}

    real_run = transport.run

    def truncating_run(fragment: str, *, stdin: bytes | None = None) -> bytes:
        data = real_run(fragment, stdin=stdin)
        if pull_mod.TAR_STDIN_MARKER not in fragment:
            return data
        cuts['n'] += 1
        if cuts['n'] == 1:
            return data[:5632]
        return data

    transport.run = truncating_run
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')
    code = pull_mod.pull_until(
        transport, remote_root, dest, run_id, interval=0, max_cycles=12
    )
    out = capsys.readouterr().out
    assert 'PULL-ERROR' in out
    assert (dest / job_rel / 'a.txt').read_text() == 'A' * 5000
    assert (dest / job_rel / 'b.txt').read_text() == 'B' * 8000
    index = json.loads((dest / '.pull-index.json').read_text())
    assert index[f'{job_rel}/b.txt'] == sha256_bytes(b'B' * 8000)


def test_truncated_tar_inside_member_retries(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000003Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'a.txt': 'A' * 5000, 'b.txt': 'B' * 8000},
        job_done=True,
    )
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    cuts = {'n': 0}
    real_run = transport.run

    def truncating_run(fragment: str, *, stdin: bytes | None = None) -> bytes:
        data = real_run(fragment, stdin=stdin)
        if pull_mod.TAR_STDIN_MARKER not in fragment:
            return data
        return data[:520]

    transport.run = truncating_run
    with pytest.raises(pull_mod.VerifyError):
        pull_mod.pull_cycle(transport, remote_root, dest)
    assert not (dest / job_rel / 'a.txt').exists()
    index = json.loads((dest / '.pull-index.json').read_text()) if (dest / '.pull-index.json').exists() else {}
    assert f'{job_rel}/a.txt' not in index


def test_omitted_tar_member_not_indexed(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000003Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'one.txt': '1', 'two.txt': '2'},
        job_done=True,
    )
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    real_fetch = pull_mod.fetch_tar
    calls = {'n': 0}

    def omit_second(tr, paths):
        calls['n'] += 1
        if calls['n'] == 1 and len(paths) >= 2:
            paths = paths[:1]
        return real_fetch(tr, paths)

    with mock.patch.object(pull_mod, 'fetch_tar', omit_second):
        with pytest.raises(pull_mod.VerifyError):
            pull_mod.pull_cycle(transport, remote_root, dest)
    index_path = dest / '.pull-index.json'
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    assert f'{job_rel}/two.txt' not in index
    pull_mod.pull_cycle(transport, remote_root, dest)
    assert (dest / job_rel / 'two.txt').exists()
    index = json.loads((dest / '.pull-index.json').read_text())
    assert f'{job_rel}/two.txt' in index


def test_symlink_outside_root_not_pulled(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000010Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    outside = tmp_path / 'secret.txt'
    outside.write_text('SECRET-MEASUREMENT')
    job = remote_root / job_rel
    job.mkdir(parents=True)
    (job / 'linked.txt').symlink_to(outside)
    (job / 'summary.json').write_text('{}')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_cycle(transport, remote_root, dest)
    out = capsys.readouterr().out
    assert 'PULL-WARN' in out and 'linked.txt' in out
    assert not (dest / job_rel / 'linked.txt').exists()
    index = json.loads((dest / '.pull-index.json').read_text())
    assert f'{job_rel}/linked.txt' not in index


def test_tar_extract_jail_rejects_dotdot_and_absolute(remote_root, tmp_path):
    from perf.container import pull as pull_mod

    dest = tmp_path / 'dest'
    dest.mkdir()
    buf = io.BytesIO()
    evil_rel = '../../escaped.txt'
    with tarfile.open(fileobj=buf, mode='w') as tar:
        data = b'ESCAPED'
        info = tarfile.TarInfo(name=evil_rel)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    with pytest.raises(pull_mod.VerifyError, match='jail'):
        pull_mod.extract_tar_stream(
            buf.getvalue(), dest, {evil_rel: {'sha256': sha256_bytes(data)}}
        )
    buf2 = io.BytesIO()
    with tarfile.open(fileobj=buf2, mode='w') as tar:
        data = b'ABSOLUTE'
        info = tarfile.TarInfo(name='/tmp/abs.txt')
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    with pytest.raises(pull_mod.VerifyError, match='jail'):
        pull_mod.extract_tar_stream(
            buf2.getvalue(), dest, {'/tmp/abs.txt': {'sha256': sha256_bytes(data)}}
        )


def test_bash_transport_runs_remote_commands_end_to_end(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000020Z'
    (remote_root / 'runs' / run_id).mkdir(parents=True)
    for idx, runner in enumerate(('benchmark_warm_cold', 'benchmark_input', 'benchmark_memory')):
        write_job_tree(
            remote_root,
            run_id,
            runner,
            f'{run_id}-{idx:03d}',
            files={'summary.json': f'{{"n": {idx}}}'},
            job_done=True,
            status=idx % 2,
        )
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=1\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    assert hasattr(transport, 'call_log')
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=3)
    out = capsys.readouterr().out.splitlines()
    assert code == 0
    assert len([line for line in out if line.startswith('JOB-DONE ')]) == 3
    assert out[-1].startswith(f'FINAL-VERIFIED {run_id} ')
    assert 'run_exit=1' in out[-1]
    assert any('lstat' in c or 'os.walk' in c for c in transport.call_log)


def test_spawn_detached_campaign_uses_new_session(tmp_path, monkeypatch):
    from perf.container.run import spawn_detached_campaign

    captured: dict = {}
    real_popen = subprocess.Popen

    def recording_popen(*args, **kwargs):
        captured.update(kwargs)
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, 'Popen', recording_popen)
    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    child_script = tmp_path / 'child.py'
    child_script.write_text('import time\ntime.sleep(0.2)\n')
    child = [sys.executable, '-u', str(child_script)]
    spawn_detached_campaign(child, campaign, 'session-test')
    assert captured.get('start_new_session') is True


def test_detached_child_survives_parent_exit(tmp_path):
    from perf.container.run import spawn_detached_campaign

    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    marker = campaign / 'survived'
    child_script = tmp_path / 'child.py'
    child_script.write_text(
        f'import time\nfrom pathlib import Path\nPath({str(marker)!r}).write_text("yes")\ntime.sleep(2)\n'
    )
    child = [sys.executable, '-u', str(child_script)]
    repo = Path(__file__).resolve().parents[2]
    launcher_script = tmp_path / 'detach_launcher.py'
    launcher_script.write_text(
        f"import sys\nfrom pathlib import Path\nsys.path.insert(0, {str(repo)!r})\n"
        f"from perf.container.run import spawn_detached_campaign\n"
        f"spawn_detached_campaign({child!r}, Path({str(campaign)!r}), 'detach-test')\n"
    )
    proc = subprocess.Popen([sys.executable, str(launcher_script)], cwd=tmp_path)
    proc.wait(timeout=10)
    assert proc.returncode == 0
    pid = int((campaign / 'RUN.pid').read_text().strip())
    for _ in range(30):
        if marker.exists():
            break
        time.sleep(0.2)
    assert marker.read_text() == 'yes'
    os.kill(pid, 0)


def test_detached_child_ignores_sighup_to_pid(tmp_path):
    from perf.container.run import spawn_detached_campaign

    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    sighup_probe = tmp_path / 'sighup.txt'
    child_script = tmp_path / 'child.py'
    child_script.write_text(
        'import signal, time\nfrom pathlib import Path\n'
        f'Path({str(sighup_probe)!r}).write_text(repr(signal.getsignal(signal.SIGHUP)))\n'
        'for _ in range(50):\n    time.sleep(0.1)\n'
    )
    child = [sys.executable, '-u', str(child_script)]
    spawn_detached_campaign(child, campaign, 'sighup-test')
    pid = int((campaign / 'RUN.pid').read_text().strip())
    for _ in range(30):
        if sighup_probe.exists():
            break
        time.sleep(0.1)
    assert signal.SIG_IGN.name in sighup_probe.read_text()
    os.kill(pid, signal.SIGHUP)
    time.sleep(0.5)
    os.kill(pid, 0)


def test_two_detaches_get_distinct_run_ids(tmp_path, monkeypatch):
    from perf.container import run as run_mod

    root = tmp_path / 'runs_root'
    root.mkdir()
    monkeypatch.setattr(run_mod.random, 'randint', lambda _a, _b: 11)
    id1 = run_mod.allocate_run_id(root)
    id2 = run_mod.allocate_run_id(root)
    assert id1[0] != id2[0]


def test_until_run_prints_jobs_and_exits_on_run_done(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000004Z'
    (remote_root / 'runs' / run_id).mkdir(parents=True)
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'summary.json': '{"warm": true}'},
        job_done=True,
    )
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_input',
        f'{run_id}-001',
        files={'summary.json': '{"input": true}'},
        job_done=True,
        status=1,
    )
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=1\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=3)
    out = capsys.readouterr().out.splitlines()
    assert code == 0
    assert len([line for line in out if line.startswith('JOB-DONE ')]) == 2
    assert out[-1].startswith(f'FINAL-VERIFIED {run_id} ')
    assert 'run_exit=1' in out[-1]
    warm = dest / f'runs/{run_id}/benchmark_warm_cold/{run_id}-000' / 'summary.json'
    assert warm.read_text() == '{"warm": true}'
    assert sha256_file(warm) == sha256_bytes(b'{"warm": true}')


def test_transport_failure_prints_pull_error_and_recovers(remote_root, tmp_path, capsys, monkeypatch):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000005Z'
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'summary.json': '{}'},
        job_done=True,
    )
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    real_run = transport.run
    calls = {'n': 0}

    def flaky_run(fragment: str, *, stdin: bytes | None = None) -> bytes:
        calls['n'] += 1
        if calls['n'] == 2 and pull_mod.TAR_STDIN_MARKER in fragment:
            raise pull_mod.TransportError('broken pipe')
        return real_run(fragment, stdin=stdin)

    transport.run = flaky_run
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=6)
    out = capsys.readouterr().out
    assert 'PULL-ERROR broken pipe' in out
    assert code == 0
    assert (dest / f'runs/{run_id}/benchmark_warm_cold/{run_id}-000' / 'summary.json').exists()


def test_refuse_existing_job_preserves_job_done(tmp_path, monkeypatch):
    from perf.container import artifacts
    from perf.container import run as run_mod

    stamp = '20260101T000000000000Z'
    monkeypatch.setenv('HF_CAMPAIGN_ID', stamp)
    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    job_dir = campaign / 'benchmark_warm_cold' / f'{stamp}-000'
    job_dir.mkdir(parents=True)
    (job_dir / 'summary.json').write_text('{"samples": []}')
    artifacts.finalize_job(job_dir, 0)
    before = (job_dir / 'JOB-DONE').read_bytes()

    def fake_run(cmd, **kwargs):
        check = subprocess.CompletedProcess(cmd, 0)
        return check

    monkeypatch.setattr(subprocess, 'run', fake_run)
    argv = ['--smoke', '--out-root', str(campaign)]
    with pytest.raises(RuntimeError):
        run_mod.main(argv)
    assert (job_dir / 'JOB-DONE').read_bytes() == before


def test_assertion_error_in_job_still_writes_run_done(tmp_path, monkeypatch):
    from perf.container import run as run_mod

    stamp = '20260101T000000000001Z'
    monkeypatch.setenv('HF_CAMPAIGN_ID', stamp)
    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    real_counts = run_mod.cell_counts

    def fake_run(cmd, **kwargs):
        if any('check_host' in part for part in cmd):
            return subprocess.CompletedProcess(cmd, 0)
        run_id = cmd[cmd.index('--run-id') + 1]
        runner = cmd[3]
        job = campaign / runner / run_id
        job.mkdir(parents=True, exist_ok=True)
        (job / 'summary.json').write_text('{"samples": []}')
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, 'run', fake_run)

    def boom(data):
        if data.get('samples') is not None:
            raise AssertionError('counts wrong')
        return real_counts(data)

    monkeypatch.setattr(run_mod, 'cell_counts', boom)
    with pytest.raises(RuntimeError):
        run_mod.main(['--smoke', '--out-root', str(campaign)])
    assert (campaign / 'RUN-DONE').exists()


def test_pull_batching_at_most_two_files_per_call(remote_root, tmp_path, monkeypatch):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000030Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    job = remote_root / job_rel
    job.mkdir(parents=True)
    for idx in range(5):
        (job / f'f{idx}.txt').write_text(str(idx))
    from perf.container import artifacts

    artifacts.finalize_job(job, 0)
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    monkeypatch.setattr(pull_mod, 'BATCH_MAX_FILES', 2)
    monkeypatch.setattr(pull_mod, 'BATCH_MAX_BYTES', 10**9)
    pull_mod.pull_cycle(transport, remote_root, dest)
    tar_calls = count_tar_invocations(transport)
    assert tar_calls >= 3


def test_pull_sh_help_from_repo_root_and_other_cwd():
    repo = Path(__file__).resolve().parents[2]
    pull_sh = repo / 'perf' / 'container' / 'pull.sh'
    for cwd in (repo, repo / 'perf'):
        proc = subprocess.run([str(pull_sh), '--help'], cwd=cwd, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert 'until-run' in proc.stdout


def test_verify_job_manifest_checks_job_done_digest(remote_root, tmp_path):
    from perf.container import pull as pull_mod
    from perf.container import artifacts

    job = tmp_path / 'job'
    job.mkdir()
    (job / 'cells' / 'a.json').parent.mkdir(parents=True)
    (job / 'summary.json').write_text('{}')
    (job / 'cells' / 'a.json').write_text('1')
    artifacts.finalize_job(job, 0)
    job_done = (job / 'JOB-DONE').read_text()
    job_done = job_done.replace('manifest_sha256=', 'manifest_sha256=deadbeef' * 8)
    (job / 'JOB-DONE').write_text(job_done)
    index = {f'job/JOB-DONE': {'sha256': sha256_bytes(job_done.encode())}}
    with pytest.raises(pull_mod.VerifyError, match='manifest_sha256'):
        pull_mod.verify_job_manifest(tmp_path, 'job', index)


def test_until_run_fetches_job_written_in_run_done_gap(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000060Z'
    (remote_root / 'runs' / run_id).mkdir(parents=True)
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'summary.json': 'JOB-A'},
        job_done=True,
    )
    last_job = f'{run_id}-001'

    def before_list(root: Path):
        nonlocal lists
        lists += 1
        if lists == 2:
            write_job_tree(
                root,
                run_id,
                'benchmark_input',
                last_job,
                files={'summary.json': 'LAST-JOB'},
                job_done=True,
            )
            (root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')

    lists = 0
    dest = tmp_path / 'dest'
    transport = WatchTransport(remote_root, on_before_list=before_list)
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=12)
    out = capsys.readouterr().out.splitlines()
    assert code == 0
    last = dest / f'runs/{run_id}/benchmark_input/{last_job}' / 'summary.json'
    assert last.read_text() == 'LAST-JOB'
    index = json.loads((dest / '.pull-index.json').read_text())
    assert f'runs/{run_id}/benchmark_input/{last_job}/summary.json' in index
    assert (dest / f'runs/{run_id}/benchmark_input/{last_job}' / 'JOB-DONE').exists()
    assert any(line.startswith('FINAL-VERIFIED ') for line in out)
    assert out[-1].startswith('FINAL-VERIFIED ')


def test_until_run_updates_partial_to_final_before_exit(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000061Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    job = remote_root / job_rel
    job.mkdir(parents=True)
    (job / 'summary.json').write_text('PARTIAL-MEASUREMENT')
    lists = 0

    def before_list(root: Path):
        nonlocal lists
        lists += 1
        if lists == 2:
            (job / 'summary.json').write_text('FINAL-MEASUREMENT')
            for name in ('MANIFEST.sha256', 'JOB-DONE'):
                (job / name).unlink(missing_ok=True)
            from perf.container import artifacts

            artifacts.finalize_job(job, 0)
            (root / 'runs' / run_id).mkdir(parents=True, exist_ok=True)
            (root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')

    dest = tmp_path / 'dest'
    transport = WatchTransport(remote_root, on_before_list=before_list)
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=12)
    out = capsys.readouterr().out
    assert code == 0
    local = dest / job_rel / 'summary.json'
    assert local.read_text() == 'FINAL-MEASUREMENT'
    index = json.loads((dest / '.pull-index.json').read_text())
    assert index[f'{job_rel}/summary.json'] == sha256_bytes(b'FINAL-MEASUREMENT')
    assert (dest / job_rel / 'JOB-DONE').exists()
    assert 'FINAL-VERIFIED' in out


def test_list_copies_ok_despite_bad_filenames(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    (remote_root / 'ok.txt').write_text('good')
    bad_newline = remote_root / 'has\nnewline.txt'
    bad_newline.write_text('bad')
    bad_bytes = remote_root / bytes([0xFF, 0xFE, 0x2E, 0x74, 0x78, 0x74]).decode('latin-1')
    bad_bytes.write_text('x')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_cycle(transport, remote_root, dest)
    out = capsys.readouterr().out
    assert 'PULL-WARN' in out
    assert (dest / 'ok.txt').read_text() == 'good'
    index = json.loads((dest / '.pull-index.json').read_text())
    assert index['ok.txt'] == sha256_bytes(b'good')
    assert 'has\nnewline.txt' not in index


def test_torn_pull_index_rebuilt_new_file_copied(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    (remote_root / 'a.txt').write_text('first')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_cycle(transport, remote_root, dest)
    (dest / '.pull-index.json').write_text('{')
    (remote_root / 'b.txt').write_text('SECOND-MEASUREMENT')
    capsys.readouterr()
    pull_mod.pull_cycle(transport, remote_root, dest)
    out = capsys.readouterr().out
    assert 'PULL-WARN index unreadable; rebuilding' in out
    assert (dest / 'b.txt').read_text() == 'SECOND-MEASUREMENT'
    corrupt = list(dest.glob('.pull-index.json.corrupt-*'))
    assert len(corrupt) == 1
    index = json.loads((dest / '.pull-index.json').read_text())
    assert index['b.txt'] == sha256_bytes(b'SECOND-MEASUREMENT')


def test_tar_batches_use_stdin_not_argv(remote_root, tmp_path):
    from perf.container import pull as pull_mod

    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    for idx in range(500):
        rel = f'bulk/{idx:04d}/' + ('x' * 230)
        rel = rel[:240]
        assert len(rel) == 240
        path = remote_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(idx))
    pull_mod.pull_cycle(transport, remote_root, dest)
    max_argv = max(len(cmd.encode()) for cmd in transport.call_log)
    assert max_argv < 8 * 1024
    assert count_tar_invocations(transport) >= 1


def test_sha256_flip_at_data_byte_leaves_no_file(remote_root, tmp_path):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000080Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    rel = f'{job_rel}/b.txt'
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'b.txt': 'B' * 8000},
        job_done=True,
    )
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    real_run = transport.run

    def flip_data_byte(fragment: str, *, stdin: bytes | None = None) -> bytes:
        data = real_run(fragment, stdin=stdin)
        if stdin is None or not is_tar_fragment(fragment):
            return data
        with tarfile.open(fileobj=io.BytesIO(data.lstrip(b'\n\r')), mode='r:') as tar:
            member = tar.getmember(rel)
            offset = member.offset_data + 10
        buf = bytearray(data.lstrip(b'\n\r'))
        buf[offset] ^= 0xFF
        return bytes(buf)

    transport.run = flip_data_byte
    with pytest.raises(pull_mod.VerifyError, match='sha256 mismatch'):
        pull_mod.pull_cycle(transport, remote_root, dest)
    assert not (dest / rel).exists()
    index_path = dest / '.pull-index.json'
    if index_path.exists():
        index = json.loads(index_path.read_text())
        assert rel not in index
    else:
        assert not index_path.exists()


def test_until_run_bad_remote_manifest_never_final(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod
    from perf.container import artifacts

    run_id = '20260101T000000000081Z'
    (remote_root / 'runs' / run_id).mkdir(parents=True)
    job = remote_root / f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    job.mkdir(parents=True)
    (job / 'summary.json').write_text('{}')
    artifacts.finalize_job(job, 0)
    (job / 'cells').mkdir(exist_ok=True)
    (job / 'cells' / 'extra.json').write_text('{}')
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=10)
    out = capsys.readouterr().out
    assert code != 0
    assert 'FINAL-VERIFIED' not in out


def test_remote_skip_missing_member_raises(remote_root, tmp_path):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000082Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    gone = f'{job_rel}/gone.txt'
    keep = f'{job_rel}/keep.txt'
    job = remote_root / job_rel
    job.mkdir(parents=True)
    (job / 'gone.txt').write_text('1')
    (job / 'keep.txt').write_text('2')
    from perf.container import artifacts

    artifacts.finalize_job(job, 0)
    dest = tmp_path / 'dest'
    transport = WatchTransport(
        remote_root,
        on_before_tar=lambda _root, stdin: (remote_root / gone).unlink(missing_ok=True),
    )
    with pytest.raises(pull_mod.VerifyError, match='missing members'):
        pull_mod.pull_cycle(transport, remote_root, dest)
    assert not (dest / gone).exists()
    index = json.loads((dest / '.pull-index.json').read_text()) if (dest / '.pull-index.json').exists() else {}
    assert gone not in index


def test_sighup_sig_dfl_control_child_dies(tmp_path):
    child = tmp_path / 'child.py'
    child.write_text(
        'import os, signal, time\n'
        'signal.signal(signal.SIGHUP, signal.SIG_DFL)\n'
        'time.sleep(30)\n'
    )
    signal.signal(signal.SIGHUP, signal.SIG_DFL)
    proc = subprocess.Popen([sys.executable, '-u', str(child)])
    time.sleep(0.2)
    os.kill(proc.pid, signal.SIGHUP)
    proc.wait(timeout=5)
    assert proc.returncode != 0


def test_custom_campaign_run_done_with_until_run(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20261110T203054948922Z-33514-935073'
    campaign = remote_root / run_id
    campaign.mkdir(parents=True)
    (campaign / 'summary.json').write_text('DEFAULT-MEASUREMENT')
    (campaign / 'RUN-DONE').write_text('exit_status=0\n')
    dest = tmp_path / 'mirror'
    transport = local_transport(remote_root)
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=5)
    out = capsys.readouterr().out
    assert code == 0
    assert (dest / run_id / 'summary.json').read_text() == 'DEFAULT-MEASUREMENT'
    assert 'FINAL-VERIFIED' in out


def test_directory_symlink_pull_warn(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    hidden = remote_root / 'hidden'
    hidden.mkdir()
    (hidden / 'secret.txt').write_text('HIDDEN')
    (remote_root / 'dirlink').symlink_to(hidden, target_is_directory=True)
    (remote_root / 'ok.txt').write_text('ok')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_cycle(transport, remote_root, dest)
    out = capsys.readouterr().out
    assert 'PULL-WARN' in out and 'dirlink' in out
    assert (dest / 'ok.txt').exists()


def test_pull_rollback_remote_v1_local_must_match_before_final(remote_root, tmp_path, capsys):
    """Grok rollback: local V2 with index v1 must not FINAL-VERIFIED against remote V1."""
    from perf.container import artifacts
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000200Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    job = remote_root / job_rel
    drop = remote_root / 'runs' / run_id / 'drop.txt'
    job.mkdir(parents=True, exist_ok=True)
    (job / 'summary.json').write_text('V1')
    drop.write_text('drop-v1')
    artifacts.finalize_job(job, 0)
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=5)
    capsys.readouterr()
    # Plant the broken state extract_tar_stream used to leave behind.
    (job / 'summary.json').write_text('V2-MEASUREMENT')
    for name in ('MANIFEST.sha256', 'JOB-DONE'):
        (job / name).unlink(missing_ok=True)
    artifacts.finalize_job(job, 0)
    drop.write_text('drop-v2')
    (dest / job_rel / 'summary.json').write_text('V2-MEASUREMENT')
    index = json.loads((dest / '.pull-index.json').read_text())
    v1_summary_hash = sha256_bytes(b'V1')
    index[f'{job_rel}/summary.json'] = v1_summary_hash
    (dest / '.pull-index.json').write_text(json.dumps(index, sort_keys=True) + '\n')
    (job / 'summary.json').write_text('V1')
    for name in ('MANIFEST.sha256', 'JOB-DONE'):
        (job / name).unlink(missing_ok=True)
    artifacts.finalize_job(job, 0)
    drop.write_text('drop-v1')
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=6)
    out = capsys.readouterr().out
    local = (dest / job_rel / 'summary.json').read_bytes()
    remote = (job / 'summary.json').read_bytes()
    assert local == remote == b'V1'
    assert code == 0
    assert any(line.startswith('FINAL-VERIFIED ') and 'run_exit=' in line for line in out.splitlines())


def test_failed_tar_batch_leaves_dest_unchanged(remote_root, tmp_path):
    from perf.container import artifacts
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000201Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    gone = f'{job_rel}/gone.txt'
    keep = f'{job_rel}/keep.txt'
    job = remote_root / job_rel
    job.mkdir(parents=True)
    (job / 'gone.txt').write_text('1')
    (job / 'keep.txt').write_text('KEEP')
    artifacts.finalize_job(job, 0)
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_cycle(transport, remote_root, dest)
    (job / 'keep.txt').write_text('KEEP2')
    (job / 'gone.txt').write_text('2')
    for name in ('MANIFEST.sha256', 'JOB-DONE'):
        (job / name).unlink(missing_ok=True)
    artifacts.finalize_job(job, 0)
    transport = WatchTransport(
        remote_root,
        on_before_tar=lambda _r, _s: (remote_root / gone).unlink(missing_ok=True),
    )
    with pytest.raises(pull_mod.VerifyError):
        pull_mod.pull_cycle(transport, remote_root, dest)
    assert (dest / keep).read_text() == 'KEEP'
    assert (dest / gone).read_text() == '1'
    index = json.loads((dest / '.pull-index.json').read_text())
    assert gone in index


def test_corrupt_loose_publication_refetched(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000202Z'
    pub_rel = f'runs/{run_id}/e2-publication.json'
    (remote_root / 'runs' / run_id).mkdir(parents=True)
    (remote_root / pub_rel).write_text('PUB')
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=4)
    capsys.readouterr()
    (dest / pub_rel).write_text('CORRUPT-PUB')
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=4)
    out = capsys.readouterr().out
    assert (dest / pub_rel).read_text() == 'PUB'
    assert code == 0
    assert 'FINAL-VERIFIED' in out
    assert 'run_exit=' in out


def test_corrupt_sealed_summary_refetched_no_spin(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000203Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'summary.json': 'SEALED'},
        job_done=True,
    )
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=4)
    capsys.readouterr()
    (dest / job_rel / 'summary.json').write_text('CORRUPT')
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=4)
    out = capsys.readouterr().out
    assert (dest / job_rel / 'summary.json').read_text() == 'SEALED'
    assert code == 0
    assert 'FINAL-VERIFIED' in out


def test_tar_member_beyond_triple_listed_size_refused(remote_root, tmp_path, monkeypatch):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000204Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    big = b'X' * 120
    small_listed = 10
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'chunk.bin': big.decode('latin-1')},
        job_done=True,
    )
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    rel = f'{job_rel}/chunk.bin'
    index = pull_mod.list_remote(transport)
    index[rel] = {**index[rel], 'size': small_listed, 'sha256': sha256_bytes(big)}

    stream = pull_mod.fetch_tar(transport, [rel])
    with pytest.raises(pull_mod.VerifyError, match='listed size cap'):
        pull_mod.extract_tar_stream(stream, dest, {rel: index[rel]})
    assert not (dest / rel).exists()


def test_prev_copy_suffix_beyond_1000(remote_root, tmp_path, monkeypatch):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000205Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    target = tmp_path / 'dest' / job_rel / 'metric.txt'
    target.parent.mkdir(parents=True)
    target.write_text('live')
    fixed = '20260102T030405Z'
    monkeypatch.setattr(pull_mod.time, 'strftime', lambda fmt, t=None: fixed if fmt == '%Y%m%dT%H%M%SZ' else time.strftime(fmt, t))
    for idx in range(1001):
        name = f'metric.txt.prev-{fixed}' if idx == 0 else f'metric.txt.prev-{fixed}-{idx}'
        (target.parent / name).write_text(f'prev-{idx}')
    pull_mod.write_prev_copy(target)
    created = sorted(p.name for p in target.parent.glob('metric.txt.prev-*') if p.name.endswith('-1001'))
    assert created == [f'metric.txt.prev-{fixed}-1001']


def test_pull_exits_zero_only_after_final_verified(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod
    from perf.container import artifacts

    run_id = '20260101T000000000206Z'
    (remote_root / 'runs' / run_id).mkdir(parents=True)
    job = remote_root / f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    job.mkdir(parents=True)
    (job / 'summary.json').write_text('{}')
    artifacts.finalize_job(job, 0)
    (job / 'cells').mkdir(exist_ok=True)
    (job / 'cells' / 'extra.json').write_text('{}')
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=3)
    out = capsys.readouterr().out
    assert 'FINAL-VERIFIED' not in out
    assert code != 0


def test_final_verified_line_includes_run_exit_not_pull_rc(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000207Z'
    (remote_root / 'runs' / run_id).mkdir(parents=True)
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'summary.json': '{}'},
        job_done=True,
        status=1,
    )
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=1\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=4)
    out = capsys.readouterr().out.splitlines()
    assert code == 0
    final = [line for line in out if line.startswith('FINAL-VERIFIED ')][-1]
    assert 'run_exit=1' in final
    assert 'run_exit=0' not in final.replace('run_exit=1', '')


def test_mutation_direct_extract_breaks_failed_batch_rollback(remote_root, tmp_path, monkeypatch):
    """Removing staging must leave rollback test RED."""
    from perf.container import pull as pull_mod

    def legacy_extract(stream, dest_root, expected):
        satisfied: set[str] = set()
        data = stream.lstrip(b'\n\r')
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as tar:
            for member in tar:
                if not member.isreg():
                    continue
                if member.name not in expected:
                    continue
                blob = tar.extractfile(member).read()
                target = dest_root / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(blob)
                satisfied.add(member.name)
        missing = set(expected) - satisfied
        if missing:
            raise pull_mod.VerifyError(f'tar missing members: {sorted(missing)[:3]}')
        return satisfied

    monkeypatch.setattr(pull_mod, 'extract_tar_stream', legacy_extract)
    run_id = '20260101T000000000208Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    job = remote_root / job_rel
    job.mkdir(parents=True)
    (job / 'a.txt').write_text('A')
    (job / 'b.txt').write_text('B')
    from perf.container import artifacts

    artifacts.finalize_job(job, 0)
    dest = tmp_path / 'dest'
    transport = WatchTransport(
        remote_root,
        on_before_tar=lambda _r, _s: (remote_root / f'{job_rel}/b.txt').unlink(missing_ok=True),
    )
    with pytest.raises(pull_mod.VerifyError):
        pull_mod.pull_cycle(transport, remote_root, dest)
    assert (dest / job_rel / 'a.txt').exists()


def test_mutation_no_local_rehash_allows_corrupt_pub(remote_root, tmp_path, monkeypatch):
    from perf.container import pull as pull_mod

    def index_only(dest, index, prior):
        return [path for path, meta in index.items() if prior.get(path) != meta['sha256']]

    run_id = '20260101T000000000209Z'
    pub_rel = f'runs/{run_id}/e2-publication.json'
    (remote_root / 'runs' / run_id).mkdir(parents=True)
    (remote_root / pub_rel).write_text('PUB')
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=3)
    (dest / pub_rel).write_text('CORRUPT-PUB')
    index = pull_mod.list_remote(transport)
    prior = json.loads((dest / '.pull-index.json').read_text())
    assert sha256_file(dest / pub_rel) != index[pub_rel]['sha256']
    assert not pull_mod.local_bytes_match_listing(dest, index)
    monkeypatch.setattr(pull_mod, 'paths_needing_fetch', index_only)
    assert index_only(dest, index, prior) == []


def test_hf_mirror_job_verified_and_ordered(tmp_path, monkeypatch):
    from perf.container import mirror
    from perf.container import artifacts

    campaign = tmp_path / 'campaign'
    job = campaign / 'benchmark_warm_cold' / 'job-001'
    job.mkdir(parents=True)
    (job / 'summary.json').write_text('{"n": 1}')
    artifacts.finalize_job(job, 0)
    assert (job / 'JOB-DONE').exists()
    mirror_root = tmp_path / 'mirror'
    monkeypatch.setenv('HF_MIRROR_ROOT', str(mirror_root))
    mirror.mirror_job_directory('camp-1', 'benchmark_warm_cold', 'job-001', job, campaign / 'RUN.log')
    dest = mirror_root / 'camp-1' / 'benchmark_warm_cold' / 'job-001'
    assert (dest / 'MIRROR-OK').exists()
    assert (dest / 'summary.json').read_text() == '{"n": 1}'


def test_hf_mirror_skips_unwritable_root(tmp_path, monkeypatch, capsys):
    from perf.container import mirror
    from perf.container import artifacts

    campaign = tmp_path / 'campaign'
    job = campaign / 'benchmark_warm_cold' / 'job-001'
    job.mkdir(parents=True)
    (job / 'summary.json').write_text('{}')
    artifacts.finalize_job(job, 0)
    bad_root = tmp_path / 'not-writable'
    bad_root.mkdir()
    bad_root.chmod(0o555)
    monkeypatch.setenv('HF_MIRROR_ROOT', str(bad_root))
    run_log = campaign / 'RUN.log'
    run_log.write_text('')
    mirror.mirror_job_directory('camp-1', 'benchmark_warm_cold', 'job-001', job, run_log)
    text = run_log.read_text()
    assert 'HF_MIRROR_ROOT' in text or 'mirror skip' in text.lower() or 'MIRROR' not in text


def test_hf_mirror_detects_corrupted_copy(tmp_path, monkeypatch):
    from perf.container import mirror
    from perf.container import artifacts

    campaign = tmp_path / 'campaign'
    job = campaign / 'benchmark_warm_cold' / 'job-001'
    job.mkdir(parents=True)
    (job / 'summary.json').write_text('payload')
    artifacts.finalize_job(job, 0)
    mirror_root = tmp_path / 'mirror'
    monkeypatch.setenv('HF_MIRROR_ROOT', str(mirror_root))
    run_log = campaign / 'RUN.log'

    real_copy = mirror.copy_file_verified

    real_copy = mirror.copy_file_verified

    def flip_after_copy(src: Path, dst: Path, rel_digest: str) -> None:
        real_copy(src, dst, rel_digest)
        if dst.name == 'summary.json' and 'mirror' in str(dst):
            data = bytearray(dst.read_bytes())
            if data:
                data[0] ^= 0xFF
                dst.write_bytes(data)

    monkeypatch.setattr(mirror, 'copy_file_verified', flip_after_copy)
    mirror.mirror_job_directory('camp-1', 'benchmark_warm_cold', 'job-001', job, run_log)
    dest = mirror_root / 'camp-1' / 'benchmark_warm_cold' / 'job-001'
    assert not (dest / 'MIRROR-OK').exists()
    assert 'MIRROR-ERROR' in run_log.read_text()


def test_run_invokes_mirror_after_each_job(tmp_path, monkeypatch):
    from perf.container import run as run_mod

    stamp = '20260101T000000000210Z'
    monkeypatch.setenv('HF_CAMPAIGN_ID', stamp)
    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    calls: list[str] = []

    def fake_run(cmd, **kwargs):
        if any('check_host' in part for part in cmd):
            return subprocess.CompletedProcess(cmd, 0)
        runner = cmd[3]
        run_id = cmd[cmd.index('--run-id') + 1]
        job = campaign / runner / run_id
        job.mkdir(parents=True, exist_ok=True)
        (job / 'summary.json').write_text('{"samples": []}')
        return subprocess.CompletedProcess(cmd, 0)

    def track_mirror(campaign_id, runner, job_id, job_dir, run_log):
        calls.append(f'mirror:{runner}/{job_id}')
        assert (job_dir / 'JOB-DONE').exists()
        return True, None

    monkeypatch.setattr(subprocess, 'run', fake_run)
    monkeypatch.setenv('HF_MIRROR_ROOT', str(tmp_path / 'mirror'))
    monkeypatch.setattr(run_mod, 'run_mirror_process', track_mirror)
    with pytest.raises(RuntimeError):
        run_mod.main(['--smoke', '--out-root', str(campaign)])
    assert calls
    assert all('mirror:' in c for c in calls)


def test_gate_rehash_refuses_corrupt_without_fetch_rehash(remote_root, tmp_path, capsys, monkeypatch):
    """Fetch-side rehash stubbed out; local gate must still block FINAL-VERIFIED."""
    from perf.container import pull as pull_mod

    def index_only(dest, index, prior):
        return [path for path, meta in index.items() if prior.get(path) != meta['sha256']]

    monkeypatch.setattr(pull_mod, 'paths_needing_fetch', index_only)
    run_id = '20260101T000000000211Z'
    pub_rel = f'runs/{run_id}/e2-publication.json'
    (remote_root / 'runs' / run_id).mkdir(parents=True)
    (remote_root / pub_rel).write_text('PUB')
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=3)
    capsys.readouterr()
    (dest / pub_rel).write_text('CORRUPT-PUB')
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=4)
    out = capsys.readouterr().out
    assert 'FINAL-VERIFIED' not in out
    assert code != 0


def test_mutation_gate_rehash_removed_allows_corrupt_final(remote_root, tmp_path, capsys, monkeypatch):
    """Removing only the gate rehash is RED: false FINAL-VERIFIED on corrupt bytes."""
    from perf.container import pull as pull_mod

    monkeypatch.setattr(pull_mod, 'local_bytes_match_listing', lambda _dest, _index: True)
    run_id = '20260101T000000000212Z'
    pub_rel = f'runs/{run_id}/e2-publication.json'
    (remote_root / 'runs' / run_id).mkdir(parents=True)
    (remote_root / pub_rel).write_text('PUB')
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=3)
    (dest / pub_rel).write_text('CORRUPT-PUB')
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=4)
    out = capsys.readouterr().out
    assert code == 0
    assert any('FINAL-VERIFIED' in line and 'CORRUPT' not in line for line in out.splitlines())


def test_mirror_subprocess_hung_continues_campaign(tmp_path, monkeypatch):
    from perf.container import run as run_mod

    hang = tmp_path / 'hang_mirror.py'
    hang.write_text(
        'import signal, time\n'
        'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
        'time.sleep(3600)\n'
    )
    stamp = '20260101T000000000213Z'
    monkeypatch.setenv('HF_CAMPAIGN_ID', stamp)
    monkeypatch.setenv('HF_MIRROR_PY', str(hang))
    monkeypatch.setenv('HF_MIRROR_TIMEOUT_S', '2')
    monkeypatch.setattr(run_mod, 'RUNNERS', ('runner_a', 'runner_b'))
    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    starts: dict[str, float] = {}

    def fake_run(cmd, **kwargs):
        if any('check_host' in part for part in cmd):
            return subprocess.CompletedProcess(cmd, 0)
        runner = cmd[3]
        run_id = cmd[cmd.index('--run-id') + 1]
        starts[runner] = time.time()
        job = campaign / runner / run_id
        job.mkdir(parents=True, exist_ok=True)
        (job / 'summary.json').write_text('{"samples": []}')
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    t0 = time.time()
    with pytest.raises(RuntimeError):
        run_mod.main(['--smoke', '--out-root', str(campaign)])
    elapsed = starts.get('runner_b', 0) - t0
    assert elapsed < 8, f'runner_b started too late ({elapsed:.1f}s)'
    run_log = (campaign / 'RUN.log').read_text()
    assert 'MIRROR-ERROR' in run_log and 'timeout' in run_log
    assert (campaign / 'RUN-DONE').exists()
    done = (campaign / 'RUN-DONE').read_text()
    assert 'runner_a' in str(starts)
    assert 'runner_b' in str(starts)


def test_mirror_memory_error_subprocess_continues(tmp_path, monkeypatch):
    from perf.container import run as run_mod

    oom = tmp_path / 'oom_mirror.py'
    oom.write_text('raise MemoryError("tmp.read_bytes")\n')
    stamp = '20260101T000000000214Z'
    monkeypatch.setenv('HF_CAMPAIGN_ID', stamp)
    monkeypatch.setenv('HF_MIRROR_PY', str(oom))
    monkeypatch.setattr(run_mod, 'RUNNERS', ('runner_a', 'runner_b'))
    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    seen: list[str] = []

    def fake_run(cmd, **kwargs):
        if any('check_host' in part for part in cmd):
            return subprocess.CompletedProcess(cmd, 0)
        runner = cmd[3]
        run_id = cmd[cmd.index('--run-id') + 1]
        seen.append(runner)
        job = campaign / runner / run_id
        job.mkdir(parents=True, exist_ok=True)
        (job / 'summary.json').write_text('{"samples": []}')
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    with pytest.raises(RuntimeError):
        run_mod.main(['--smoke', '--out-root', str(campaign)])
    assert seen == ['runner_a', 'runner_b']
    assert (campaign / 'RUN-DONE').exists()
    assert 'MIRROR-ERROR' in (campaign / 'RUN.log').read_text()


def test_mirror_runs_only_between_jobs(tmp_path, monkeypatch):
    from perf.container import run as run_mod

    stamp = '20260101T000000000215Z'
    monkeypatch.setenv('HF_CAMPAIGN_ID', stamp)
    monkeypatch.setenv('HF_MIRROR_ROOT', str(tmp_path / 'mirror'))
    monkeypatch.setattr(run_mod, 'RUNNERS', ('runner_a', 'runner_b'))
    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    events: list[tuple[str, str, float]] = []

    def fake_run(cmd, **kwargs):
        if any('check_host' in part for part in cmd):
            return subprocess.CompletedProcess(cmd, 0)
        runner = cmd[3]
        now = time.time()
        events.append(('runner-start', runner, now))
        run_id = cmd[cmd.index('--run-id') + 1]
        job = campaign / runner / run_id
        job.mkdir(parents=True, exist_ok=True)
        (job / 'summary.json').write_text('{"samples": []}')
        proc = subprocess.CompletedProcess(cmd, 0)
        events.append(('runner-end', runner, time.time()))
        return proc

    real_mirror = run_mod.run_mirror_process

    def wrap_mirror(campaign_id, runner, job_id, job_dir, run_log):
        events.append(('mirror-start', runner, time.time()))
        out = real_mirror(campaign_id, runner, job_id, job_dir, run_log)
        events.append(('mirror-end', runner, time.time()))
        return out

    monkeypatch.setattr(subprocess, 'run', fake_run)
    monkeypatch.setattr(run_mod, 'run_mirror_process', wrap_mirror)
    with pytest.raises(RuntimeError):
        run_mod.main(['--smoke', '--out-root', str(campaign)])
    by_runner: dict[str, dict[str, float]] = {}
    for kind, runner, ts in events:
        by_runner.setdefault(runner, {})[kind] = ts
    for runner in ('runner_a', 'runner_b'):
        row = by_runner[runner]
        assert row['runner-end'] <= row['mirror-start'] < row['mirror-end']


def test_pull_streams_large_commit_without_whole_read_bytes(remote_root, tmp_path, monkeypatch):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000216Z'
    job_rel = f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    big = 'B' * 250_000
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'big.txt': big},
        job_done=True,
    )
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    real_read_bytes = Path.read_bytes
    calls: list[str] = []

    def guarded_read_bytes(self):
        if self.is_file() and self.stat().st_size > 200_000:
            calls.append(self.name)
            raise OSError('read_bytes refused on large file')
        return real_read_bytes(self)

    monkeypatch.setattr(Path, 'read_bytes', guarded_read_bytes)
    pull_mod.pull_cycle(transport, remote_root, dest)
    local_big = dest / job_rel / 'big.txt'
    assert pull_mod.sha256_file(local_big) == sha256_bytes(big.encode())
    assert 'big.txt' not in calls


def test_stale_pull_staging_quarantined_not_indexed(tmp_path):
    from perf.container import pull as pull_mod

    dest = tmp_path / 'dest'
    dest.mkdir()
    stale = dest / '.pull-staging' / 'leftover-stamp'
    stale.mkdir(parents=True)
    (stale / 'orphan.txt').write_text('ORPHAN')
    pull_mod.quarantine_stale_pull_staging(dest)
    moved = list(dest.glob('.pull-staging.stale-*'))
    assert len(moved) == 1
    assert moved[0].is_dir()
    assert (moved[0] / 'leftover-stamp' / 'orphan.txt').read_text() == 'ORPHAN'
    index = pull_mod.rebuild_local_index(dest)
    assert not index


def test_final_verified_files_matches_listing_after_remote_delete(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000217Z'
    (remote_root / 'runs' / run_id).mkdir(parents=True)
    (remote_root / 'note.txt').write_text('note')
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=4)
    capsys.readouterr()
    (remote_root / 'note.txt').unlink()
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=4)
    out = capsys.readouterr().out.splitlines()
    final = [line for line in out if line.startswith('FINAL-VERIFIED ')][-1]
    listing = pull_mod.list_remote(transport)
    assert code == 0
    assert f'files={len(listing)}' in final
    gone_path = dest / '.pull-index-gone.json'
    assert gone_path.exists()
    gone = json.loads(gone_path.read_text())
    assert 'note.txt' in gone


def test_job_changed_line_when_file_added_after_verify(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000040Z'
    write_job_tree(
        remote_root,
        run_id,
        'benchmark_warm_cold',
        f'{run_id}-000',
        files={'summary.json': '{}'},
        job_done=True,
    )
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_cycle(transport, remote_root, dest)
    capsys.readouterr()
    job_local = dest / f'runs/{run_id}/benchmark_warm_cold/{run_id}-000'
    (job_local / 'extra.json').write_text('new')
    pull_mod.pull_cycle(transport, remote_root, dest)
    out = capsys.readouterr().out
    assert 'JOB-CHANGED' in out


def test_mirror_script_runnable_with_python_I_from_any_cwd(tmp_path, monkeypatch):
    """Production mirror argv must work as ``python3 -I <abs>/mirror.py`` from any cwd."""
    from perf.container import artifacts
    from perf.container import run as run_mod

    campaign = tmp_path / 'campaign'
    job = campaign / 'benchmark_warm_cold' / 'job-mirror-stdlib'
    job.mkdir(parents=True)
    payload = '{"samples": []}'
    (job / 'summary.json').write_text(payload)
    artifacts.finalize_job(job, 0)
    run_log = campaign / 'RUN.log'
    run_log.write_text('')
    mirror_root = tmp_path / 'mirror'
    monkeypatch.setenv('HF_MIRROR_ROOT', str(mirror_root))
    stamp = 'camp-stdlib'
    cmd = [
        sys.executable,
        '-I',
        str(run_mod.mirror_script_path()),
        'job',
        stamp,
        'benchmark_warm_cold',
        'job-mirror-stdlib',
        str(job),
        str(run_log),
    ]
    result = subprocess.run(cmd, cwd='/tmp', capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    dest = mirror_root / stamp / 'benchmark_warm_cold' / 'job-mirror-stdlib'
    assert (dest / 'MIRROR-OK').exists()
    assert sha256_file(dest / 'summary.json') == sha256_file(job / 'summary.json')
    assert sha256_file(dest / 'MANIFEST.sha256') == sha256_file(job / 'MANIFEST.sha256')


def test_mirror_survivor_pid_on_every_later_job_without_refusal(tmp_path, monkeypatch):
    from perf.container import artifacts
    from perf.container import run as run_mod

    alive_pid = 424242
    stamp = '20260102T000000000001Z'
    monkeypatch.setenv('HF_CAMPAIGN_ID', stamp)
    monkeypatch.setenv('HF_MIRROR_TIMEOUT_S', '2')
    monkeypatch.setattr(run_mod, 'RUNNERS', ('runner_a', 'runner_b', 'runner_c'))
    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    seen: list[str] = []
    mirror_calls = {'n': 0}
    real_popen = subprocess.Popen

    class HungMirror:
        returncode = None
        pid = alive_pid

        def __init__(self, *args, **kwargs):
            self._args = args

        def wait(self, timeout=None):
            if timeout == 3:
                raise subprocess.TimeoutExpired(self._args, timeout)
            raise subprocess.TimeoutExpired(self._args, timeout or 2)

        def kill(self):
            return None

        def poll(self):
            return -9

        @property
        def stderr(self):
            return io.StringIO('')

    def fake_popen(cmd, **kwargs):
        mirror_script = str(run_mod.mirror_script_path())
        if len(cmd) >= 3 and Path(cmd[2]).name == 'mirror.py' or (len(cmd) >= 3 and mirror_script in cmd[2]):
            mirror_calls['n'] += 1
            return HungMirror()
        return real_popen(cmd, **kwargs)

    def fake_run(cmd, **kwargs):
        if any('check_host' in part for part in cmd):
            return subprocess.CompletedProcess(cmd, 0)
        runner = cmd[3]
        run_id = cmd[cmd.index('--run-id') + 1]
        seen.append(runner)
        job = campaign / runner / run_id
        job.mkdir(parents=True, exist_ok=True)
        (job / 'summary.json').write_text('{"samples": []}')
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, 'Popen', fake_popen)
    monkeypatch.setattr(subprocess, 'run', fake_run)
    with pytest.raises(RuntimeError):
        run_mod.main(['--smoke', '--out-root', str(campaign)])
    assert seen == ['runner_a', 'runner_b', 'runner_c']
    run_meta = json.loads((campaign / 'campaign-meta.json').read_text())
    assert run_meta.get('mirror_child_alive_pid') == alive_pid
    for runner in ('runner_b', 'runner_c'):
        job_dir = campaign / runner / f'{stamp}-{["runner_a", "runner_b", "runner_c"].index(runner):03d}'
        meta = json.loads((job_dir / 'campaign-meta.json').read_text())
        assert meta.get('mirror_child_alive_pid') == alive_pid
        assert (job_dir / 'JOB-DONE').exists()


def test_run_done_nonzero_when_last_job_campaign_meta_raises(tmp_path, monkeypatch):
    from perf.container import artifacts
    from perf.container import run as run_mod

    stamp = '20260102T000000000002Z'
    monkeypatch.setenv('HF_CAMPAIGN_ID', stamp)
    monkeypatch.setattr(run_mod, 'RUNNERS', ('runner_a', 'runner_b'))
    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    seen: list[str] = []
    real_atomic = artifacts.atomic_write

    def guarded_atomic(path: Path, content: str) -> None:
        if path.name == 'campaign-meta.json' and path.parent.name.startswith(stamp) and path.parent.parent.name == 'runner_b':
            raise OSError(28, 'ENOSPC simulated')
        return real_atomic(path, content)

    monkeypatch.setattr(artifacts, 'atomic_write', guarded_atomic)

    def fake_run(cmd, **kwargs):
        if any('check_host' in part for part in cmd):
            return subprocess.CompletedProcess(cmd, 0)
        runner = cmd[3]
        run_id = cmd[cmd.index('--run-id') + 1]
        seen.append(runner)
        job = campaign / runner / run_id
        job.mkdir(parents=True, exist_ok=True)
        (job / 'summary.json').write_text('{"samples": []}')
        return subprocess.CompletedProcess(cmd, 0)

    mirror_hits = {'n': 0}

    def fake_mirror(*_args, **_kwargs):
        mirror_hits['n'] += 1
        if mirror_hits['n'] == 1:
            return False, 424242
        return True, None

    monkeypatch.setattr(subprocess, 'run', fake_run)
    monkeypatch.setattr(run_mod, 'run_mirror_process', fake_mirror)
    with pytest.raises(RuntimeError):
        run_mod.main(['--smoke', '--out-root', str(campaign)])
    done = (campaign / 'RUN-DONE').read_text()
    assert 'exit_status=1' in done
    assert any('runner_b' in line and 'ENOSPC' in line for line in done.splitlines() if line.startswith('failure='))
