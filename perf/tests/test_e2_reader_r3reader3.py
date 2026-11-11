"""Second adversarial review (r3reader2) — probes with fixed-behavior assertions."""
import json
from pathlib import Path

import pytest

from build import perf_e2_tables as report
from perf.analysis import e2_cells as cells
from perf.analysis import e2_resources
from perf.analysis import e2_typing

DISTINCTIVE_MEDIAN = 54321.987
DISTINCTIVE_FRAME = 777.77
DISTINCTIVE_CPU = 987654.321
DISTINCTIVE_CPS = 1357.911
DISTINCTIVE_LOAD = 2468.111
DISTINCTIVE_WALL = 975.222
DISTINCTIVE_ELAPSED = 9753.222
DISTINCTIVE_K2P = 8642.333


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


def _trial(samples, *, tree='tree-a', criterion='C07', editor='plate', interval=16.7):
    return dict(
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


def _write_resource_job(root: Path, job_id, seed, launches=10, *, editor='plate',
                        workload='prose-500w', tree='tree-a', summary=None, cpu=100, reps=None):
    job = root / 'runs' / 'camp' / 'benchmark_resources' / job_id
    (job / 'cells').mkdir(parents=True, exist_ok=True)
    names = list(reps) if reps is not None else list(range(launches))
    order = [[i, editor] for i in names]
    payload = summary if summary is not None else _summary(job_id, seed, order=order)
    if payload is not None:
        (job / 'summary.json').write_text(json.dumps({**payload, 'runner': 'benchmark_resources',
                                                      'hosts': {editor: {'tree_sha256': tree}}}))
    for i in names:
        cell = job / 'cells' / ('%04d-%s' % (i, editor))
        cell.mkdir(parents=True, exist_ok=True)
        (cell / 'resource.json').write_text(json.dumps(dict(
            record_kind='browser_resources', editor_id=editor, workload_id=workload,
            outcome='measured', edit_oracle=dict(status='verified'), edit_cpu_publication='published',
            execution_profile='dedicated_publish', host_class='dedicated',
            load_cpu_ms=cpu, open_settle_cpu_ms=cpu, edit_cpu_ms=cpu, quiescence_cpu_ms=cpu,
            peak_ram_bytes=1000, peak_js_heap_used_bytes=500, load_network_encoded_bytes=200)))
    return root / 'runs' / 'camp'


def _write_typing_job(root: Path, job_id, seed, sessions=12, *, kind='throughput', summary=None,
                      cps=DISTINCTIVE_CPS, load=DISTINCTIVE_LOAD, wall=DISTINCTIVE_WALL,
                      fixture='fix' * 10, launches=None, progress_rows=(), tree='tree-a'):
    job = root / 'runs' / 'camp' / 'benchmark_typing' / job_id
    (job / 'cells').mkdir(parents=True, exist_ok=True)
    order = [[i, 'plate'] for i in range(sessions)]
    payload = summary if summary is not None else _summary(job_id, seed, order=order,
                                                           hosts={'plate': {'tree_sha256': tree}})
    if payload is not None:
        (job / 'summary.json').write_text(json.dumps(payload))
    for i in (launches if launches is not None else range(sessions)):
        cell = job / 'cells' / ('%04d-plate' % i) / 'attempts'
        cell.mkdir(parents=True, exist_ok=True)
        row = dict(
            schema='perf.typing/2', editor_id='plate', criterion_id='TYPING', session_kind=kind,
            outcome='measured', publishable=True, refusal_code=None, failure_reason=None,
            publication_block_reason=None, execution_profile='dedicated_publish', host_class='dedicated',
            isolation='fresh_process', values_per_session=1, cadence_ms=0, budget_s=3600,
            correctness_oracle='dom_document_text',
            fixture_sha256=fixture, typed_text_sha256='txt' * 10, fixture_words=12805, words_typed=12805,
            session_wall_s=wall, load_ms=load, throughput_chars_s=cps, characters_typed=77031,
            host_provenance=dict(host_build='production', publishable=True, tree_sha256=tree),
        )
        if i in progress_rows:
            row.update(failure_reason='budget_exceeded', outcome='failed', publishable=False,
                       throughput_chars_s=None,
                       progress={'characters_typed': 424242, 'elapsed_s': DISTINCTIVE_ELAPSED})
        (cell / 'typing.json').write_text(json.dumps(row))
    return root / 'runs' / 'camp'


# MAJOR A


def test_sameroot_full_rerun_without_block_is_refused(tmp_path):
    root = tmp_path / 'space-a'
    _write_job(root, 'benchmark_input', 'j1', 1, range(30), summary=_summary('j1', 1))
    _write_job(root, 'benchmark_input', 'j1r', 1, range(30),
               summary=_summary('j1r', 1), values={i: 80.0 for i in range(30)})
    seed2 = _write_job(tmp_path / 'space-b', 'benchmark_input', 'j2', 2, range(30))
    pooled = cells.read_criterion_cell([root / 'runs' / 'camp', seed2], 'plate', 'C07')
    assert pooled['published'] is False, pooled['reason']
    stats = pooled['groups'][0].get('stats') or {}
    assert stats.get('n', 0) <= 30


# MAJOR B


def test_of10_with_only_9_blocks_refuses_criterion_and_b8(tmp_path):
    roots = []
    for index in range(1, 10):
        reps = range((index - 1) * 3, index * 3)
        roots.append(_write_job(
            (tmp_path / ('space-%02d' % index)), 'benchmark_input', 'j%d' % index, 1, reps,
            summary=_summary('j%d' % index, 1,
                             block={'index': index, 'of': 10, 'repetitions': 3})))
    seed2 = _write_job(tmp_path / 'space-seed2', 'benchmark_input', 'j2', 2, range(30))
    roots.append(seed2)
    pooled = cells.read_criterion_cell(roots, 'plate', 'C07')
    assert pooled['published'] is False
    assert 'missing blocks 10' in (pooled['reason'] or '')

    rroots = []
    for index in range(1, 10):
        reps = range((index - 1) * 3, index * 3)
        rroots.append(_write_resource_job(
            (tmp_path / ('rb-%02d' % index)), 'r%d' % index, 1, reps=reps,
            summary=_summary('r%d' % index, 1, order=[[r, 'plate'] for r in reps],
                             block={'index': index, 'of': 10, 'repetitions': 3})))
    rroots.append(_write_resource_job(tmp_path / 'rb-seed2', 'r2', 2, launches=10))
    cell = e2_resources.read_cell(rroots, 'plate', 'prose-500w')
    assert cell['published'] is False, cell['reason']
    assert 'missing blocks 10' in (cell['reason'] or '')


# MAJOR C


def test_same_run_id_different_content_blocks_not_order_dependent(tmp_path):
    def pull(space, values, job_id='j1'):
        return _write_job(tmp_path / space, 'benchmark_input', job_id, 1, range(30),
                          summary=_summary('run-same', 1), values=values)

    seed2 = _write_job(tmp_path / 'space-c', 'benchmark_input', 'j2', 2, range(30))
    a = pull('space-a', {i: 20.0 for i in range(30)})
    b = pull('space-b', {i: 80.0 for i in range(30)})
    first = cells.read_criterion_cell([a, b, seed2], 'plate', 'C07')
    second = cells.read_criterion_cell([b, a, seed2], 'plate', 'C07')
    assert first['published'] is False and second['published'] is False
    assert first['reason'] == second['reason']
    assert 'duplicate' in (first['reason'] or '').casefold()


def test_same_run_id_partial_copy_blocks_regardless_of_order(tmp_path):
    partial = _write_job(tmp_path / 'space-a', 'benchmark_input', 'j1', 1, range(5),
                         summary=_summary('run-same', 1, order=[[i, 'plate'] for i in range(30)]))
    complete = _write_job(tmp_path / 'space-b', 'benchmark_input', 'j1', 1, range(30),
                          summary=_summary('run-same', 1))
    seed2 = _write_job(tmp_path / 'space-c', 'benchmark_input', 'j2', 2, range(30))
    partial_first = cells.read_criterion_cell([partial, complete, seed2], 'plate', 'C07')
    complete_first = cells.read_criterion_cell([complete, partial, seed2], 'plate', 'C07')
    assert partial_first['published'] is False and complete_first['published'] is False
    assert partial_first['reason'] == complete_first['reason']


def test_block_rerun_with_same_run_id_is_refused(tmp_path):
    j1 = _write_job(tmp_path / 'space-a', 'benchmark_input', 'j1', 1, range(0, 15))
    j2 = _write_job(tmp_path / 'space-b', 'benchmark_input', 'j2', 1, range(15, 30))
    j9 = _write_job(tmp_path / 'space-c', 'benchmark_input', 'j9', 1, range(15, 30),
                    values={i: 80.0 for i in range(15, 30)})
    seed2 = _write_job(tmp_path / 'space-d', 'benchmark_input', 'j3', 2, range(30))
    pooled = cells.read_criterion_cell([j1, j2, j9, seed2], 'plate', 'C07')
    assert pooled['published'] is False, pooled['reason']

    j9_same = _write_job(tmp_path / 'space-e', 'benchmark_input', 'j9b', 1, range(15, 30),
                         summary=_summary('j2', 1), values={i: 80.0 for i in range(15, 30)})
    seed2b = _write_job(tmp_path / 'space-d', 'benchmark_input', 'j3', 2, range(30))
    pooled_same = cells.read_criterion_cell([j1, j2, j9_same, seed2b], 'plate', 'C07')
    assert pooled_same['published'] is False, pooled_same['reason']


def test_missing_run_id_duplicate_pull_same_verdict_criterion_and_b8(tmp_path):
    def job_input(space, values=None):
        summary = _summary(None, 1)
        summary.pop('run_id')
        return _write_job(tmp_path / space, 'benchmark_input', 'j1', 1, range(30),
                          summary=summary, values=values)

    def job_res(space, cpu=100):
        summary = _summary(None, 1)
        summary.pop('run_id')
        return _write_resource_job(space, 'r1', 1, summary=summary, cpu=cpu)

    a, b = job_input('space-a'), job_input('space-b', {i: 80.0 for i in range(30)})
    seed2 = _write_job(tmp_path / 'space-c', 'benchmark_input', 'j2', 2, range(30))
    pooled = cells.read_criterion_cell([a, b, seed2], 'plate', 'C07')
    assert pooled['published'] is False
    assert 'duplicate' in (pooled['reason'] or '').casefold()

    a, b = job_res(tmp_path / 'ra'), job_res(tmp_path / 'rb', cpu=500)
    seed2 = _write_resource_job(tmp_path / 'rc', 'r2', 2)
    cell = e2_resources.read_cell([a, b, seed2], 'plate', 'prose-500w')
    assert cell['published'] is False
    assert 'duplicate' in (cell['reason'] or '').casefold()


# MAJOR D


def test_typing_refuses_two_editor_builds_in_one_root(tmp_path):
    camp = tmp_path / 'space-a' / 'runs' / 'camp'
    _write_typing_job(tmp_path / 'space-a', 't1', 1, tree='tree-a')
    _write_typing_job(tmp_path / 'space-a', 't2', 2, tree='tree-b')
    facts = {}
    text = report.typing_table(facts, [camp], 'plate', 'throughput')
    assert facts['perf.e2.plate.TYPING.throughput.reproduced'] is False, text
    assert 'different editor builds' in text


# MAJOR E


def test_existing_empty_directory_root_fails_loud(tmp_path):
    empty = tmp_path / 'typo-space'
    empty.mkdir()
    with pytest.raises(ValueError, match='no measured jobs'):
        report.facts_from_roots([empty])


def test_junk_directory_root_fails_loud(tmp_path):
    junk = tmp_path / 'extract-gone-wrong'
    (junk / 'runs' / 'empty-campaign').mkdir(parents=True)
    with pytest.raises(ValueError, match='no measured jobs'):
        report.facts_from_roots([junk])


# NIT G


def test_typing_refused_session_progress_withheld_from_facts(tmp_path):
    roots = [
        _write_typing_job(tmp_path / 'space-a', 't1', 1, progress_rows=(0, 1, 2)),
        _write_typing_job(tmp_path / 'space-b', 't2', 2),
    ]
    facts = report.facts_from_roots(roots)
    assert facts['perf.e2.plate.TYPING.throughput.reproduced'] is False
    assert str(DISTINCTIVE_ELAPSED) not in json.dumps(facts)
