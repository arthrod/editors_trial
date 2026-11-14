"""Review B of the refused cells (2026-11-13): one cause, three labels.

The warm/cold lane writes a criterion's ``not_applicable`` (or ``not_run``)
row at one cache state only. The other measure of the same launch then took
the launch-level code: ``crash`` (aggregate_cell_refusal_code did not know
``not_applicable``) or nothing at all ("none counted"). Nothing crashed: the
keystrokes landed and the probe exited 0. The reader now gives such a
measure the reason its sibling measure records in the same launch.
"""

import json
from pathlib import Path

from perf.analysis import e2_cells as cells
from perf.runner.browser_run import aggregate_cell_refusal_code

RID = '20261112T180000000000Z-10000-000001'
INDEX = {(1, 1): 4, (1, 2): 5, (2, 1): 84, (2, 2): 85}
NA = 'no_glyph_geometry_to_witness_the_keystrokes_own_paint'


def write_job(root, seed, block, *, launch_outcome, launch_code, sibling):
    job = root / 'benchmark_warm_cold' / f'{RID}-{INDEX[(seed, block)]:03d}'
    reps = range((block - 1) * 5, block * 5)
    for rep in reps:
        cell = job / 'cells' / f'{rep:04d}-canvas' / 'attempts' / 'c05.json'
        cell.parent.mkdir(parents=True)
        cell.write_text(json.dumps(dict(
            editor_id='canvas', criterion_id='C05', measure='warm_steady', layer='browser_visible',
            outcome=sibling, refusal_code=sibling, failure_reason=NA, samples_ms=[],
            environment={'workload_id': 'prose-5kw', 'cache_state': 'warm_steady'})))
        row = job / 'samples' / f'{rep:04d}-canvas.json'
        row.parent.mkdir(parents=True, exist_ok=True)
        row.write_text(json.dumps(dict(editor_id='canvas', outcome=launch_outcome, refusal_code=launch_code,
                                       failure_reason=NA, accounting_scope='sample', exit_code=0)))
    (job / 'summary.json').write_text(json.dumps(dict(
        run_id=job.name, seed=seed, execution_profile='dedicated_publish',
        block=dict(index=block, of=2, repetitions=5), order=[[rep, 'canvas'] for rep in reps])))


def campaign(**kw):
    roots = []
    for seed in (1, 2):
        for block in (1, 2):
            root = Path('/runs') / f'r-{seed}-{block}'
            write_job(root, seed, block, **kw)
            roots.append(root)
    return roots


def _refusals(cell):
    out = {}
    for group in cell['groups']:
        for code, n in (group.get('refusals') or {}).items():
            out[code] = out.get(code, 0) + n
    return out


def test_a_cold_measure_takes_its_sibling_not_applicable_not_crash(fs):
    roots = campaign(launch_outcome='failed', launch_code='crash', sibling='not_applicable')
    cell = cells.read_criterion_cell(roots, 'canvas', 'C05', measure='process_cold_fs_warm', workload_id='prose-5kw')
    assert cell['published'] is False
    assert _refusals(cell) == {'not_applicable': 20}


def test_a_cold_measure_with_a_clean_launch_row_is_not_none_counted(fs):
    roots = campaign(launch_outcome='ok', launch_code=None, sibling='not_applicable')
    cell = cells.read_criterion_cell(roots, 'canvas', 'C05', measure='process_cold_fs_warm', workload_id='prose-5kw')
    assert _refusals(cell) == {'not_applicable': 20}


def test_the_warm_measure_keeps_its_own_rows(fs):
    roots = campaign(launch_outcome='failed', launch_code='crash', sibling='not_applicable')
    cell = cells.read_criterion_cell(roots, 'canvas', 'C05', measure='warm_steady', workload_id='prose-5kw')
    assert _refusals(cell) == {'not_applicable': 20}


def test_the_writer_names_a_lone_not_applicable(tmp_path):
    path = tmp_path / 'cells' / '0000-canvas' / 'attempts' / 'c05.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'outcome': 'not_applicable', 'refusal_code': 'not_applicable'}))
    assert aggregate_cell_refusal_code(tmp_path, True) == 'not_applicable'
