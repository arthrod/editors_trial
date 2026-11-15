"""Campaign 2 runs one editor per job; a cell merges those jobs' launches.

Run ids keep a global index across the campaign, and a job that is resumed or
retried numbers its launches from 0000 again, so launch identity is per job:
``<job>/<launch>``. A cell for one editor must merge the editor's jobs under
``<run>/<runner>/<job>/cells/`` without treating same-named launches of two
jobs as conflicting trials.
"""

import json
from pathlib import Path

from perf.analysis import e2_cells as cells


def write_job(run, job_id, editor, reps, *, refused_sample=None, quarantined=()):
    job = run / 'benchmark_input' / job_id
    for rep in range(reps):
        if rep in quarantined:
            (job / 'rejected-evidence' / f'{rep:04d}-{editor}' / 'cell').mkdir(parents=True)
            continue
        path = job / 'cells' / f'{rep:04d}-{editor}' / 'attempts' / 'C07.json'
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                dict(
                    editor_id=editor,
                    criterion_id='C07',
                    outcome='measured',
                    publishable=True,
                    refusal_code=None,
                    layer='browser_visible',
                    samples_ms=[20],
                    sub_frame_samples=[False],
                    diagnostic={'frame_interval_ms': 16.7},
                    host_provenance={'host_build': 'production', 'publishable': True, 'tree_sha256': 'tree-a'},
                )
            )
        )
    if refused_sample is not None:
        rep, reason, code = refused_sample
        directory = job / 'samples'
        directory.mkdir(parents=True)
        (directory / f'{rep:04d}-{editor}.json').write_text(
            json.dumps(
                dict(
                    editor_id=editor,
                    outcome='failed',
                    failure_reason=reason,
                    refusal_code=code,
                )
            )
        )
    (job / 'summary.json').write_text(
        json.dumps(
            dict(
                run_id=job_id,
                seed=1,
                execution_profile='dedicated_publish',
                order=[[i, editor] for i in range(30)],
            )
        )
    )
    return job


def test_one_editor_jobs_merge_into_one_cell(fs):
    run = Path('/runs/campaign')
    write_job(run, 'run-011', 'plate', 10)
    write_job(run, 'run-012', 'plate', 10)  # resumed job renumbers from 0000
    write_job(run, 'run-013', 'docen', 10)  # another editor's own job
    cell = cells.build_run_cell(run, 'plate', 'C07')
    assert cell['refusals'] == {}
    assert cell['stats'] is not None and cell['stats']['n'] == 20
    assert cell['scheduled'] == 60
    assert cell['stats']['median'] == 20


def test_launch_refusals_are_scoped_to_their_job(fs):
    run = Path('/runs/campaign')
    write_job(run, 'run-011', 'plate', 10, refused_sample=(5, 'cpu_throttled', 'cpu_throttled'))
    write_job(run, 'run-012', 'plate', 10, quarantined=(6,))
    cell = cells.build_run_cell(run, 'plate', 'C07')
    # run-011's 0005-plate is refused and run-012's 0005-plate still counts;
    # run-012's 0006-plate is quarantined while run-011's 0006-plate still counts.
    assert cell['stats']['n'] == 18
    assert cell['refusals'] == {'cpu_throttled': 1, 'quarantined': 1}


def test_other_lane_refusals_do_not_veto_the_cell(fs):
    run = Path('/runs/campaign')
    write_job(run, 'run-011', 'plate', 10)  # benchmark_input lane measures C07
    warm = run / 'benchmark_warm_cold' / 'run-091'  # another lane, same editor
    directory = warm / 'samples'
    directory.mkdir(parents=True)
    (directory / '0005-plate.json').write_text(
        json.dumps(dict(editor_id='plate', outcome='failed', failure_reason='cpu_throttled', refusal_code='cpu_throttled'))
    )
    (warm / 'summary.json').write_text(
        json.dumps(dict(run_id='run-091', seed=1, order=[[i, 'plate'] for i in range(30)]))
    )
    cell = cells.build_run_cell(run, 'plate', 'C07')
    assert cell['refusals'] == {}
    assert cell['stats']['n'] == 10
    assert cell['scheduled'] == 30


def test_blocked_job_blocks_the_merged_cell(fs):
    run = Path('/runs/campaign')
    write_job(run, 'run-011', 'plate', 10)
    job = write_job(run, 'run-012', 'plate', 10)
    summary = json.loads((job / 'summary.json').read_text())
    summary.update(publishable=False, publication_block_reason='repos_modified')
    (job / 'summary.json').write_text(json.dumps(summary))
    cell = cells.build_run_cell(run, 'plate', 'C07')
    assert cell['blocked'] is True
    assert cell['block_reason'] == 'repos_modified'
