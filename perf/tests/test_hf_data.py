"""HF measurement data safety: manifests, detach, and continuous pull."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def local_transport(remote_root: Path):
    from perf.container.pull import BashTransport
    return BashTransport(remote_root)


def write_job_tree(remote: Path, run_id: str, runner: str, job_id: str, *, files: dict[str, str], job_done: bool, status: int = 0):
    job = remote / 'runs' / run_id / runner / job_id
    job.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (job / name).write_text(content)
    from perf.container import artifacts
    if job_done:
        artifacts.finalize_job(job, status)


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
    for path in sorted(p.relative_to(job).as_posix() for p in job.rglob('*') if p.is_file()
                       and p.name not in ('MANIFEST.sha256', 'JOB-DONE')):
        expected.append(f"{sha256_file(job / path)}  {path}")
    assert manifest == expected
    job_done = (job / 'JOB-DONE').read_text().splitlines()
    assert job_done[0] == 'exit_status=0'
    assert job_done[1] == f"manifest_sha256={sha256_bytes((job / 'MANIFEST.sha256').read_bytes())}"


def test_pull_second_cycle_fetches_nothing(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000000Z'
    write_job_tree(remote_root, run_id, 'benchmark_warm_cold', f'{run_id}-000',
                   files={'summary.json': '{}'}, job_done=True)
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    pull_mod.pull_cycle(transport, remote_root, dest)
    capsys.readouterr()
    pull_mod.pull_cycle(transport, remote_root, dest)
    second = capsys.readouterr().out
    assert second.strip() == ''


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


def test_corrupted_transfer_is_detected_and_refetched(remote_root, tmp_path, monkeypatch):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000003Z'
    write_job_tree(remote_root, run_id, 'benchmark_warm_cold', f'{run_id}-000',
                   files={'summary.json': '{"ok": true}'}, job_done=True)
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    real_extract = pull_mod.extract_tar_stream
    attempts = {'n': 0}

    def flaky_extract(stream, dest_root, expected):
        attempts['n'] += 1
        if attempts['n'] == 1:
            altered = {path: {**meta, 'sha256': '0' * 64} for path, meta in expected.items()}
            with pytest.raises(pull_mod.VerifyError):
                real_extract(stream, dest_root, altered)
            raise pull_mod.VerifyError('injected mismatch')
        return real_extract(stream, dest_root, expected)

    monkeypatch.setattr(pull_mod, 'extract_tar_stream', flaky_extract)
    announced = set()
    with pytest.raises(pull_mod.VerifyError):
        pull_mod.pull_cycle(transport, remote_root, dest, announce=announced)
    assert not announced
    monkeypatch.setattr(pull_mod, 'extract_tar_stream', real_extract)
    pull_mod.pull_cycle(transport, remote_root, dest)
    assert (dest / f'runs/{run_id}/benchmark_warm_cold/{run_id}-000' / 'summary.json').read_text() == '{"ok": true}'


def test_detached_child_survives_parent_exit(tmp_path):
    from perf.container.run import spawn_detached_campaign

    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    marker = campaign / 'survived'
    child_script = tmp_path / 'child.py'
    child_script.write_text(
        f'import time\nfrom pathlib import Path\nPath({str(marker)!r}).write_text("yes")\ntime.sleep(2)\n'
    )
    child = [sys.executable, str(child_script)]
    launcher_script = tmp_path / 'detach_launcher.py'
    repo = Path(__file__).resolve().parents[2]
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


def test_until_run_prints_jobs_and_exits_on_run_done(remote_root, tmp_path, capsys):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000004Z'
    (remote_root / 'runs' / run_id).mkdir(parents=True)
    write_job_tree(remote_root, run_id, 'benchmark_warm_cold', f'{run_id}-000',
                   files={'summary.json': '{}'}, job_done=True)
    write_job_tree(remote_root, run_id, 'benchmark_input', f'{run_id}-001',
                   files={'summary.json': '{}'}, job_done=True, status=1)
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=1\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=2)
    out = capsys.readouterr().out.splitlines()
    assert code == 1
    assert len([line for line in out if line.startswith('JOB-DONE ')]) == 2
    assert out[-1] == f'RUN-DONE {run_id} exit_status=1'


def test_transport_failure_prints_pull_error_and_recovers(remote_root, tmp_path, capsys, monkeypatch):
    from perf.container import pull as pull_mod

    run_id = '20260101T000000000005Z'
    write_job_tree(remote_root, run_id, 'benchmark_warm_cold', f'{run_id}-000',
                   files={'summary.json': '{}'}, job_done=True)
    (remote_root / 'runs' / run_id / 'RUN-DONE').write_text('exit_status=0\n')
    dest = tmp_path / 'dest'
    transport = local_transport(remote_root)
    real_fetch = pull_mod.fetch_tar
    calls = {'n': 0}

    def flaky_fetch(tr, paths):
        calls['n'] += 1
        if calls['n'] == 1:
            raise pull_mod.TransportError('broken pipe')
        return real_fetch(tr, paths)

    monkeypatch.setattr(pull_mod, 'fetch_tar', flaky_fetch)
    code = pull_mod.pull_until(transport, remote_root, dest, run_id, interval=0, max_cycles=4)
    out = capsys.readouterr().out
    assert 'PULL-ERROR broken pipe' in out
    assert code == 0
    assert (dest / f'runs/{run_id}/benchmark_warm_cold/{run_id}-000' / 'summary.json').exists()
