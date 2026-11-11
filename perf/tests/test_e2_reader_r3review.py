"""Adversarial review r3reader: probes turned into regression tests (2026-11-11)."""
import json
import sys
from pathlib import Path

import pytest

from build import perf_e2_tables as report
from perf.analysis import e2_cells as cells
from perf.runner.browser_run import schedule

DISTINCTIVE_MEDIAN = 54321.987
DISTINCTIVE_FRAME = 777.77


def _summary(run_id, seed, order=None, **extra):
    base = dict(
        run_id=run_id,
        seed=seed,
        execution_profile='dedicated_publish',
        host_class='shared_guarded',
        publishable=True,
        order=order if order is not None else [[i, 'plate'] for i in range(30)],
        host=dict(cpu_model='fixture CPU', cpu_cores_logical=16, os='Linux', os_version='fixture',
                  power_source='ac', container=True, cpu_quota=8),
        rendering=dict(headless=True, browser_version='130', playwright_version='1.64',
                       vendor='Google Inc.', renderer='SwiftShader'),
        versions=dict(tools=dict(playwright='1.64'), editors=dict(plate=dict(pin='p'))),
    )
    base.update(extra)
    return base


def _trial(samples, *, tree='tree-a', criterion='C07', editor='plate', interval=16.7, workload=None):
    row = dict(
        editor_id=editor,
        criterion_id=criterion,
        outcome='measured',
        publishable=True,
        refusal_code=None,
        layer='browser_visible',
        boundary='input_to_next_paint',
        environment=dict(host_class='shared_guarded', execution_profile='dedicated_publish', editor_id=editor),
        samples_ms=samples,
        sub_frame_samples=[False] * len(samples),
        diagnostic=dict(frame_interval_ms=interval),
        host_provenance=dict(host_build='production', publishable=True, tree_sha256=tree),
    )
    if workload:
        row['workload_id'] = workload
    return row


def _write_job(root: Path, runner: str, job_id: str, seed, reps, tree='tree-a', *,
               summary=None, values=None, editor='plate', criterion='C07', launches=None):
    job = root / 'runs' / 'camp' / runner / job_id
    order = [[rep, editor] for rep in reps]
    (job / 'cells').mkdir(parents=True, exist_ok=True)
    payload = summary if summary is not None else _summary(job_id, seed, order=order)
    if payload is not None:
        (job / 'summary.json').write_text(json.dumps(payload))
    for rep in (launches if launches is not None else reps):
        cell = job / 'cells' / ('%04d-%s' % (rep, editor)) / 'attempts'
        cell.mkdir(parents=True, exist_ok=True)
        value = (values or {}).get(rep, 20.0)
        (cell / (criterion.lower() + '.json')).write_text(
            json.dumps(_trial([value], tree=tree, criterion=criterion, editor=editor)))
    return root / 'runs' / 'camp'


# BLOCKER 1


def test_block_rerun_of_same_launches_is_not_published(tmp_path):
    roots = []
    for space, job_id, seed, reps in (
        ('space-a', 'j1', 1, range(0, 15)),
        ('space-a', 'j2', 1, range(15, 30)),
        ('space-b', 'j9', 1, range(15, 30)),
        ('space-c', 'j3', 2, range(30)),
    ):
        root = _write_job(tmp_path / space, 'benchmark_input', job_id, seed, reps)
        if root not in roots:
            roots.append(root)
    pooled = cells.read_criterion_cell(roots, 'plate', 'C07')
    assert pooled['published'] is False
    assert (pooled['reason'] or '').count('seed') >= 1


def test_duplicate_pull_same_job_counts_once(tmp_path):
    roots = [
        _write_job(tmp_path / 'space-a', 'benchmark_input', 'j1', 1, range(30)),
        _write_job(tmp_path / 'space-b', 'benchmark_input', 'j1', 1, range(30)),
        _write_job(tmp_path / 'space-c', 'benchmark_input', 'j2', 2, range(30)),
    ]
    pooled = cells.read_criterion_cell(roots, 'plate', 'C07')
    assert pooled['published'] is True
    assert [g['stats']['n'] for g in pooled['groups']] == [30, 30]


# BLOCKER 3


def _classic_roots(tmp_path, primary_extra=None):
    def write(root, run_id, seed, extra=None, interval=DISTINCTIVE_FRAME, value=DISTINCTIVE_MEDIAN):
        root.mkdir(parents=True, exist_ok=True)
        payload = _summary(run_id, seed)
        payload.update(extra or {})
        (root / 'summary.json').write_text(json.dumps(payload))
        for i in range(30):
            cell = root / 'cells' / ('%04d-plate' % i) / 'attempts'
            cell.mkdir(parents=True)
            (cell / 'c07.json').write_text(json.dumps(_trial([value], interval=interval)))

    primary, repro = tmp_path / 'primary', tmp_path / 'repro'
    write(primary, 'a', 1, primary_extra)
    write(repro, 'b', 2)
    return primary, repro


def test_blocked_cell_does_not_leak_frame_interval(tmp_path):
    primary, repro = _classic_roots(tmp_path, primary_extra=dict(
        shakedown=True, publishable=False,
        publication_block_reason='shakedown: few repetitions to find bugs; never a publication run'))
    facts = report.facts_from_runs(primary, repro)
    assert str(DISTINCTIVE_FRAME) not in json.dumps(facts)


def test_under_n_cell_does_not_leak_frame_interval(tmp_path):
    primary, repro = _classic_roots(tmp_path)
    for i in range(25):
        (primary / 'cells' / ('%04d-plate' % i) / 'attempts' / 'c07.json').unlink()
    facts = report.facts_from_runs(primary, repro)
    assert str(DISTINCTIVE_FRAME) not in json.dumps(facts)


# BLOCKER 4


def _write_typing_job(root: Path, job_id, seed, sessions=12, *, editor='plate', cps=5000.0):
    def session(load=100.0):
        return dict(
            schema='perf.typing/2', editor_id=editor, criterion_id='TYPING', session_kind='throughput',
            outcome='measured', publishable=True, refusal_code=None, execution_profile='dedicated_publish',
            host_class='dedicated', isolation='fresh_process', values_per_session=1, cadence_ms=0, budget_s=3600,
            fixture_sha256='fix' * 10, typed_text_sha256='txt' * 10, fixture_words=12805, words_typed=12805,
            session_wall_s=120.0, load_ms=load, throughput_chars_s=cps,
            host_provenance=dict(host_build='production', publishable=True, tree_sha256='tree-a'),
        )

    job = root / 'runs' / 'camp' / 'benchmark_typing' / job_id
    (job / 'cells').mkdir(parents=True, exist_ok=True)
    (job / 'summary.json').write_text(
        json.dumps(_summary(job_id, seed, order=[[i, editor] for i in range(sessions)])))
    for i in range(sessions):
        cell = job / 'cells' / ('%04d-%s' % (i, editor)) / 'attempts'
        cell.mkdir(parents=True)
        (cell / 'typing.json').write_text(json.dumps(session()))
    return root / 'runs' / 'camp'


def test_typing_table_with_two_campaign_roots(tmp_path):
    roots = [
        _write_typing_job(tmp_path / 'space-a', 't1', 1),
        _write_typing_job(tmp_path / 'space-b', 't2', 2),
    ]
    facts = report.facts_from_roots(roots)
    assert 'perf.e2' in json.dumps(facts)


# MAJOR 1


def _classic_typing_roots(tmp_path, cps_a=1111.0, cps_b=9999.0):
    roots = []
    for name, run_id, seed, cps in (('primary', 'a', 1, cps_a), ('repro', 'b', 2, cps_b)):
        root = tmp_path / name
        root.mkdir(parents=True, exist_ok=True)
        (root / 'summary.json').write_text(json.dumps(_summary(run_id, seed, order=[[i, 'plate'] for i in range(12)])))
        for i in range(12):
            cell = root / 'cells' / ('%04d-plate' % i) / 'attempts'
            cell.mkdir(parents=True)
            row = dict(
                schema='perf.typing/2', editor_id='plate', criterion_id='TYPING', session_kind='throughput',
                outcome='measured', publishable=True, execution_profile='dedicated_publish', host_class='dedicated',
                isolation='fresh_process', values_per_session=1, cadence_ms=0, budget_s=3600,
                fixture_sha256='fix' * 10, typed_text_sha256='txt' * 10, fixture_words=12805, words_typed=12805,
                session_wall_s=120.0, load_ms=100.0, throughput_chars_s=cps,
                host_provenance=dict(host_build='production', publishable=True, tree_sha256='tree-a'),
            )
            (cell / 'typing.json').write_text(json.dumps(row))
        roots.append(root)
    return roots


def test_not_reproduced_typing_leaks_no_session_figures(tmp_path):
    roots = _classic_typing_roots(tmp_path)
    facts = {}
    report.typing_table(facts, roots, 'plate', 'throughput')
    blob = json.dumps(facts)
    assert '9999' not in blob and '1111' not in blob
    assert facts['perf.e2.plate.TYPING.throughput.reproduced'] is False


# MAJOR 2


def test_roots_config_missing_path_fails_loud(fs):
    from build import facts as generator

    config = Path('/report_e2_runs.json')
    config.write_text(json.dumps({'roots': ['/no-such-space']}))
    with pytest.raises((FileNotFoundError, ValueError, OSError)):
        generator.perf_e2_facts(config, {})


def test_roots_config_empty_list_fails_loud(fs):
    from build import facts as generator

    config = Path('/report_e2_runs.json')
    config.write_text(json.dumps({'roots': []}))
    with pytest.raises((ValueError, IndexError)):
        generator.perf_e2_facts(config, {})


def test_roots_config_non_list_fails_loud(fs):
    from build import facts as generator

    config = Path('/report_e2_runs.json')
    config.write_text(json.dumps({'roots': '/one/path'}))
    with pytest.raises((TypeError, ValueError)):
        generator.perf_e2_facts(config, {})


# MAJOR 3


def test_shakedown_on_unrelated_job_does_not_block_other_seed(tmp_path):
    roots = [
        _write_job(tmp_path / 'space-a', 'benchmark_input', 'j1', 1, range(30)),
        _write_job(
            tmp_path / 'space-a', 'benchmark_input', 'jx', 2, range(0),
            summary=_summary('jx', 2, order=[], shakedown=True, publishable=False,
                             publication_block_reason='shakedown: few repetitions; never a publication run'),
            launches=[0],
        ),
        _write_job(tmp_path / 'space-b', 'benchmark_input', 'j2', 2, range(30)),
    ]
    pooled = cells.read_criterion_cell(roots, 'plate', 'C07')
    assert pooled['groups'][0]['stats']['n'] == 30
    assert 'shakedown' not in (pooled['groups'][0].get('block_reason') or '')
    assert pooled['groups'][1].get('blocked')


# MAJOR 4


def test_inconsistent_block_repetitions_block_seed(tmp_path):
    job1 = [item for item in schedule(['plate'], 40, 5) if 0 <= item[0] < 20]
    job2 = [item for item in schedule(['plate'], 30, 5) if 15 <= item[0] < 30]
    roots = [
        _write_job(
            tmp_path / 'a', 'benchmark_input', 'j1', 1,
            [r for r, _e in job1],
            summary=_summary('j1', 1, order=job1, block={'index': 1, 'of': 2, 'repetitions': 20}),
        ),
        _write_job(
            tmp_path / 'b', 'benchmark_input', 'j2', 1,
            [r for r, _e in job2],
            summary=_summary('j2', 1, order=job2, block={'index': 2, 'of': 2, 'repetitions': 15}),
        ),
        _write_job(tmp_path / 'c', 'benchmark_input', 'j3', 2, range(30)),
    ]
    pooled = cells.read_criterion_cell(roots, 'plate', 'C07')
    assert pooled['published'] is False
    assert pooled['reason']


# NIT 1


def test_two_trees_within_one_seed_names_build_drift(tmp_path):
    roots = [
        _write_job(tmp_path / 'space-a', 'benchmark_input', 'j1', 1, range(15), tree='tree-a'),
        _write_job(tmp_path / 'space-b', 'benchmark_input', 'j2', 1, range(15, 30), tree='tree-b'),
        _write_job(tmp_path / 'space-c', 'benchmark_input', 'j3', 2, range(30), tree='tree-a'),
    ]
    pooled = cells.read_criterion_cell(roots, 'plate', 'C07')
    assert pooled['published'] is False
    assert 'first seed' in (pooled['reason'] or '')
    assert 'build' in (pooled['reason'] or '').casefold()
