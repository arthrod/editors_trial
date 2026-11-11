"""One editor per job, stable global job ids, and a balanced plan (Arthur, 2026-11-11).

Every publication job names exactly one editor, so jobs are independent and can
run on any Space. A job's index is its place in the full job list, whatever
filter selects it, so results from every Space merge without collisions.
"""
from collections import Counter

import pytest

from perf.container import plan, policy, run

EDITORS = ['plate', 'docxodus', 'superdoc', 'genoffice', 'canvas', 'docen', 'wordcraft', 'eigenpal', 'folio']
BASE = ['--publish', '--dry-run', '--host-class', 'shared_guarded', '--seed', '1', '--seed2', '2']


def _jobs():
    return policy.publication_jobs(EDITORS, 1, 2, 'shared_guarded')


def _dry(capsys, *extra):
    assert run.main([*BASE, *extra]) in (0, None)
    return [line for line in capsys.readouterr().out.splitlines() if '--run-id DRY-RUN-' in line]


def _index(line):
    return int(line.split('--run-id DRY-RUN-')[1].split()[0])


def test_every_job_names_exactly_one_editor():
    jobs = _jobs()
    assert all(policy.job_editor(options) in EDITORS for _name, options in jobs)
    per_editor = Counter(policy.job_editor(options) for _name, options in jobs)
    # per seed: warm/cold 5, document 5+C14, input 5, C10 5, typing 2 kinds, memory 5, resources 5
    assert set(per_editor.values()) == {2 * (5 + 6 + 5 + 5 + 2 + 5 + 5)}
    assert len(jobs) == 9 * 66


def test_every_cell_runs_under_both_seeds():
    keys = Counter(policy.job_key(name, options) for name, options in _jobs())
    assert set(keys.values()) == {2}


def test_global_index_is_stable_under_filters(capsys):
    full = {_index(line): line for line in _dry(capsys)}
    picked = _dry(capsys, '--runners', 'benchmark_memory', '--editors', 'wordcraft')
    assert len(picked) == 10
    for line in picked:
        assert full[_index(line)] == line


def test_jobs_flag_selects_exact_global_indices(capsys):
    picked = _dry(capsys, '--jobs', '3,17,500')
    assert sorted(_index(line) for line in picked) == [3, 17, 500]


@pytest.mark.parametrize('bad', ['x', '3,,4', '-1', '594', '3,3'])
def test_bad_jobs_flag_is_refused(bad):
    with pytest.raises(SystemExit):
        run.main([*BASE, '--jobs', bad])


def test_plan_assigns_every_job_once_and_balances():
    jobs = _jobs()
    costs = [plan.estimate(name, options) for name, options in jobs]
    spaces = plan.assign(jobs, costs, 20)
    flat = sorted(i for space in spaces for i in space)
    assert flat == list(range(len(jobs)))
    loads = [sum(costs[i] for i in space) for space in spaces]
    lower = max(sum(costs) / 20, max(costs))
    assert max(loads) <= lower * 4 / 3 + max(costs)


def test_plan_puts_the_two_seeds_of_a_cell_on_different_spaces():
    jobs = _jobs()
    costs = [plan.estimate(name, options) for name, options in jobs]
    spaces = plan.assign(jobs, costs, 20)
    where = {i: s for s, space in enumerate(spaces) for i in space}
    by_key = {}
    for i, (name, options) in enumerate(jobs):
        by_key.setdefault(policy.job_key(name, options), []).append(where[i])
    assert all(len(set(found)) == 2 for found in by_key.values())


def test_detach_refuses_a_bad_filter_before_spawning(monkeypatch):
    spawned = []
    monkeypatch.setattr(run, 'allocate_run_id', lambda root: spawned.append('allocated') or ('X', root))
    monkeypatch.setattr(run, 'spawn_detached_campaign', lambda *a, **k: spawned.append('spawned'))
    monkeypatch.delenv('HF_RUN_CHILD', raising=False)
    with pytest.raises(SystemExit) as exc:
        run.main(['--publish', '--detach', '--host-class', 'shared_guarded', '--seed', '1', '--seed2', '2',
                  '--editors', 'wordcraf'])
    assert exc.value.code == 2
    assert spawned == []


def test_repeated_editors_flags_accumulate(capsys):
    lines = _dry(capsys, '--runners', 'benchmark_memory', '--editors', 'wordcraft', '--editors', 'plate')
    assert len(lines) == 20


def test_run_done_and_publication_record_the_selection(tmp_path, monkeypatch):
    import json
    import subprocess

    campaign = tmp_path / 'campaign'

    def fake_run(cmd, *a, **k):
        if any('check_host' in part for part in cmd):
            return subprocess.CompletedProcess(cmd, 0)
        run_id = cmd[cmd.index('--run-id') + 1]
        job = campaign / cmd[2].rsplit('.', 1)[1] / run_id
        job.mkdir(parents=True, exist_ok=True)
        (job / 'summary.json').write_text('{"samples": []}')
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    monkeypatch.setattr(run, 'run_mirror_tail', lambda *a, **k: None)
    monkeypatch.setattr(run, 'pin_to_quota', lambda: 'cpu_affinity_pinned=none', raising=False)
    try:
        run.main(['--publish', '--host-class', 'shared_guarded', '--seed', '1', '--seed2', '2',
                  '--jobs', '17,3', '--out-root', str(campaign)])
    except (SystemExit, RuntimeError):
        pass
    done = (campaign / 'RUN-DONE').read_text().splitlines()
    assert 'selected_jobs=3,17' in done and 'total_jobs=594' in done
    publication = json.loads((campaign / 'out' / 'e2-publication.json').read_text())
    assert publication['selection'] == {'jobs': [3, 17], 'total_jobs': 594}


def test_empty_selection_is_refused():
    with pytest.raises(SystemExit):
        run.main([*BASE, '--runners', 'adversarial_c10_scroll', '--jobs', '0'])


def test_shakedown_estimates_are_short_and_still_balanced():
    jobs = _jobs()
    full = [plan.estimate(name, options) for name, options in jobs]
    short = [plan.estimate(name, options, shakedown=2) for name, options in jobs]
    assert all(s < f for s, f in zip(short, full))
    assert max(s for (name, _o), s in zip(jobs, short) if name == 'benchmark_typing') <= 20
    spaces = plan.assign(jobs, short, 20)
    loads = [sum(short[i] for i in space) for space in spaces]
    assert max(loads) <= max(sum(short) / 20, max(short)) * 4 / 3 + max(short)
