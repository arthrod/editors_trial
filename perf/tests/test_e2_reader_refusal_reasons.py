"""#239: a cell keeps the reasons its refused launches recorded, not only their codes.

`not_applicable` covers "nothing to measure" (C04 with no deferred work) and
"the harness could not see it" (typing in an editor that draws on a canvas).
The report can only tell them apart from the recorded reason.
"""
import json
from pathlib import Path

from perf.analysis import e2_cells as cells

GLYPH = 'no_glyph_geometry_to_witness_the_keystrokes_own_paint'


def _job(run, job_id, editor, rows, *, sample=None):
    """rows: one (outcome, refusal_code, failure_reason) per launch; None is a measured launch."""
    job = run / 'benchmark_warm_cold' / job_id
    for rep, row in enumerate(rows):
        path = job / 'cells' / f'{rep:04d}-{editor}' / 'attempts' / 'c05.json'
        path.parent.mkdir(parents=True)
        base = dict(editor_id=editor, criterion_id='C05', measure='warm_steady', layer='browser_visible',
                    host_provenance={'host_build': 'production', 'publishable': True, 'tree_sha256': 'tree-a'})
        if row is None:
            base.update(outcome='measured', publishable=True, refusal_code=None, samples_ms=[20],
                        sub_frame_samples=[False], diagnostic={'frame_interval_ms': 16.7})
        else:
            base.update(outcome=row[0], refusal_code=row[1], failure_reason=row[2], samples_ms=[])
        path.write_text(json.dumps(base))
    if sample is not None:
        rep, reason, code = sample
        (job / 'samples').mkdir(parents=True)
        (job / 'samples' / f'{rep:04d}-{editor}.json').write_text(json.dumps(
            dict(editor_id=editor, outcome='failed', failure_reason=reason, refusal_code=code)))
    (job / 'summary.json').write_text(json.dumps(dict(
        run_id=job_id, seed=1, execution_profile='dedicated_publish', order=[[i, editor] for i in range(len(rows))])))
    return job


def test_a_cell_keeps_the_recorded_reason_of_its_refused_launches(fs):
    run = Path('/runs/campaign')
    _job(run, 'run-001', 'canvas', [('not_applicable', 'not_applicable', GLYPH)] * 3)
    cell = cells.build_run_cell(run, 'canvas', 'C05', measure='warm_steady')
    assert cell['refusals'] == {'not_applicable': 3}
    assert cell['refusal_reasons'] == {'not_applicable': [GLYPH]}


def test_two_reasons_under_one_code_are_both_kept_in_order(fs):
    run = Path('/runs/campaign')
    _job(run, 'run-001', 'wordcraft', [('not_applicable', 'not_applicable', GLYPH),
                                       ('not_applicable', 'not_applicable', 'document_content_unverifiable')])
    cell = cells.build_run_cell(run, 'wordcraft', 'C05', measure='warm_steady')
    assert cell['refusal_reasons'] == {'not_applicable': ['document_content_unverifiable', GLYPH]}


def test_only_the_first_line_of_a_reason_is_kept(fs):
    run = Path('/runs/campaign')
    _job(run, 'run-001', 'canvas', [('failed', 'crash', 'page_lost: Error: page.evaluate: Target crashed \n    at stack (file.js:1)')])
    cell = cells.build_run_cell(run, 'canvas', 'C05', measure='warm_steady')
    assert cell['refusal_reasons'] == {'crash': ['page_lost: Error: page.evaluate: Target crashed']}


def test_a_launch_refused_in_its_samples_row_gives_its_reason(fs):
    run = Path('/runs/campaign')
    _job(run, 'run-001', 'plate', [None, None, None], sample=(1, 'cpu_throttled', 'cpu_throttled'))
    cell = cells.build_run_cell(run, 'plate', 'C05', measure='warm_steady')
    assert cell['refusals'] == {'cpu_throttled': 1}
    assert cell['refusal_reasons'] == {'cpu_throttled': ['cpu_throttled']}


def test_a_cell_with_no_refusal_has_no_reasons_and_the_reasons_reach_the_facts(fs):
    run = Path('/runs/campaign')
    _job(run, 'run-001', 'plate', [None, None])
    cell = cells.build_run_cell(run, 'plate', 'C05', measure='warm_steady')
    assert cell['refusal_reasons'] == {}
    assert 'refusal_reasons' in cells.public_cell_dict(cell)
