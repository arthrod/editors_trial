"""An editor-scoped supersede: one editor's cells of a job measured again (#185).

canvas-editor's C11 and C14 timed its empty page. Its cells are measured
again by canvas-only runs that keep the job indices; the other editors of the
same interleaved block jobs stay as measured. Inside ``superseded_cells`` the
reader ignores the superseded editor's rows of an old job, pairs only the new
runs' jobs with that editor's cells, and counts their schedule only.
"""

import json
import sys
from pathlib import Path

from perf.analysis import e2_cells as cells

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'build'))
import perf_e2_tables as tables  # noqa: E402

OLD = '20261112T180000000000Z-10000-000001'
NEW = '20261114T010000000000Z-50000-000009'
INDEX = {(1, 1): 10, (1, 2): 11, (2, 1): 90, (2, 2): 91}


def write_job(root, rid, seed, block, editors, sample_ms):
    job = root / 'benchmark_document' / f'{rid}-{INDEX[(seed, block)]:03d}'
    reps = range((block - 1) * 5, block * 5)
    for editor in editors:
        for rep in reps:
            path = job / 'cells' / f'{rep:04d}-{editor}' / 'attempts' / 'c11.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(dict(
                editor_id=editor, criterion_id='C11', outcome='measured', publishable=True, refusal_code=None,
                layer='browser_visible', samples_ms=[sample_ms[editor]], sub_frame_samples=[False],
                diagnostic={'frame_interval_ms': 16.7},
                host_provenance={'host_build': 'production', 'publishable': True, 'tree_sha256': 'tree-' + editor},
            )))
    (job / 'summary.json').write_text(json.dumps(dict(
        run_id=job.name, seed=seed, execution_profile='dedicated_publish',
        block=dict(index=block, of=2, repetitions=5),
        order=[[rep, editor] for rep in reps for editor in editors],
    )))
    return job


def campaign(base=Path('/runs')):
    roots = []
    for seed in (1, 2):
        for block in (1, 2):
            old = base / f'old-{seed}-{block}'
            write_job(old, OLD, seed, block, ['plate', 'canvas'], {'plate': 800, 'canvas': 130})
            new = base / f'new-{seed}-{block}'
            write_job(new, NEW, seed, block, ['canvas'], {'canvas': 31000})
            roots += [old, new]
    return roots


SUPERSEDED = [{'issue': '185', 'editor': 'canvas', 'jobs': [10, 11, 90, 91], 'kept_runs': [NEW]}]


def _pooled(cell):
    return [cells._build_cell_from_jobs(cell[seed], 'canvas', 'C11') for seed in (1, 2)]


def test_without_the_supersede_the_two_measurements_collide(fs):
    roots = campaign()
    cell = cells.read_criterion_cell(roots, 'canvas', 'C11')
    assert cell['published'] is False


def test_the_superseded_editor_takes_only_the_new_runs(fs):
    roots = campaign()
    with cells.superseded_cells(SUPERSEDED):
        canvas = cells.read_criterion_cell(roots, 'canvas', 'C11')
        plate = cells.read_criterion_cell(roots, 'plate', 'C11')
        jobs = {job.name.rsplit('-', 1)[0] for seed in (1, 2) for _root, job in canvas['by_seed'][seed]}
    assert canvas['published'] is True, canvas['reason']
    assert jobs == {NEW}
    for group in canvas['groups']:
        assert group['stats']['n'] == 10 and group['stats']['median'] == 31000
    assert plate['published'] is True, plate['reason']
    for group in plate['groups']:
        assert group['stats']['n'] == 10 and group['stats']['median'] == 800


def test_old_rows_of_the_superseded_editor_are_not_read(fs):
    roots = campaign()
    with cells.superseded_cells(SUPERSEDED):
        rows = [row for root in roots for row in cells._iter_trials(root) if row['editor_id'] == 'canvas']
    assert rows and {row['samples_ms'][0] for row in rows} == {31000}


def test_the_schedule_counts_only_the_new_runs(fs):
    roots = campaign()
    with cells.superseded_cells(SUPERSEDED):
        assert tables._scheduled_sum(roots, 0, 'canvas') == 10
        assert tables._scheduled_sum(roots, 1, 'canvas') == 10
        assert tables._scheduled_sum(roots, 0, 'plate') == 10


def test_the_context_is_cleared_on_exit(fs):
    roots = campaign()
    with cells.superseded_cells(SUPERSEDED):
        pass
    assert cells.read_criterion_cell(roots, 'canvas', 'C11')['published'] is False
