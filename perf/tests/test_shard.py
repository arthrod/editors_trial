"""Split the publication jobs across Spaces by whole jobs (Arthur, 2026-11-11).

Each job keeps all nine editors on one machine; shards keep the global job
index in the run id so results from every Space merge without collisions.
"""
import pytest

from perf.container import run


def _dry(capsys, *extra):
    assert run.main(['--publish', '--dry-run', '--host-class', 'shared_guarded',
                     '--seed', '1', '--seed2', '2', *extra]) in (0, None)
    return [line for line in capsys.readouterr().out.splitlines() if '--run-id DRY-RUN-' in line]


def _index(line):
    return int(line.split('--run-id DRY-RUN-')[1].split()[0])


def test_shards_partition_every_job_once(capsys):
    full = _dry(capsys)
    assert len(full) == 594
    seen = []
    for i in range(8):
        part = _dry(capsys, '--shard', f'{i}/8')
        assert part, i
        assert all(_index(line) % 8 == i for line in part)
        seen += part
    assert sorted(seen, key=_index) == full


@pytest.mark.parametrize('bad', ['8/8', '-1/8', '1/0', 'x', '1/'])
def test_bad_shard_is_refused(capsys, bad):
    with pytest.raises(SystemExit):
        run.main(['--publish', '--dry-run', '--host-class', 'shared_guarded',
                  '--seed', '1', '--seed2', '2', '--shard', bad])


def test_out_of_shard_jobs_are_not_reported_as_not_run(tmp_path, monkeypatch):
    import subprocess

    campaign = tmp_path / 'campaign'
    started = []

    def fake_run(cmd, *a, **k):
        if any('check_host' in part for part in cmd):
            return subprocess.CompletedProcess(cmd, 0)
        run_id = cmd[cmd.index('--run-id') + 1]
        started.append(int(run_id.rsplit('-', 1)[1]))
        job = campaign / cmd[2].rsplit('.', 1)[1] / run_id
        job.mkdir(parents=True, exist_ok=True)
        (job / 'summary.json').write_text('{"samples": []}')
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    monkeypatch.setattr(run, 'run_mirror_tail', lambda *a, **k: None)
    monkeypatch.setattr(run, 'pin_to_quota', lambda: 'cpu_affinity_pinned=none', raising=False)
    try:
        run.main(['--publish', '--host-class', 'shared_guarded', '--seed', '1', '--seed2', '2',
                  '--shard', '3/8', '--out-root', str(campaign)])
    except (SystemExit, RuntimeError):
        pass
    assert started and all(index % 8 == 3 for index in started)
    done = (campaign / 'RUN-DONE').read_text()
    assert 'job_not_run' not in done, [line for line in done.splitlines() if 'job_not_run' in line][:3]
