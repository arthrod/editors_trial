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

    needle = 'json.loads(base64.b64decode(sys.argv[1]))'
    return sum(1 for cmd in transport.call_log if needle in cmd)


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

    def truncating_run(fragment: str) -> bytes:
        data = real_run(fragment)
        if 'base64.b64decode(sys.argv[1])' not in fragment:
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

    def truncating_run(fragment: str) -> bytes:
        data = real_run(fragment)
        if 'base64.b64decode(sys.argv[1])' not in fragment:
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
    assert code == 1
    assert len([line for line in out if line.startswith('JOB-DONE ')]) == 3
    assert out[-1] == f'RUN-DONE {run_id} exit_status=1'
    assert any('lstat' in c or 'os.walk' in c for c in transport.call_log)


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
    child_script = tmp_path / 'child.py'
    child_script.write_text('import time\nfor _ in range(50):\n    time.sleep(0.1)\n')
    child = [sys.executable, '-u', str(child_script)]
    spawn_detached_campaign(child, campaign, 'sighup-test')
    pid = int((campaign / 'RUN.pid').read_text().strip())
    time.sleep(0.3)
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
    assert code == 1
    assert len([line for line in out if line.startswith('JOB-DONE ')]) == 2
    assert out[-1] == f'RUN-DONE {run_id} exit_status=1'
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

    def flaky_run(fragment: str) -> bytes:
        calls['n'] += 1
        if calls['n'] == 2 and 'base64.b64decode(sys.argv[1])' in fragment:
            raise pull_mod.TransportError('broken pipe')
        return real_run(fragment)

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
