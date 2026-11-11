"""Frame-witness flags belong to witnessed criteria only.

C04 (model layer, deferred quiescence) has no paint-witness semantics: the
writer never produces ``sub_frame_samples`` for it, exactly as it produces no
flags for the byte criteria C17/C19. The reader must publish such trials
instead of refusing them as malformed, while browser-visible criteria keep
requiring complete flags checked against the witnessed interval.
"""

import pytest

from perf.tests import test_e2_report_fix3 as fixtures
from perf.tests.test_e2_report_fix3 import trial
from perf.analysis import e2_cells as cells
from build import perf_e2_tables as report

runs = fixtures.runs


def model_trials(root, count=10, value=2.3):
    for i in range(count):
        trial(
            root,
            i,
            'C04',
            layer='model',
            samples_ms=[value],
            sub_frame_samples=None,
            diagnostic={'frame_interval_ms': 16.7},
        )


def test_c04_model_trials_without_flags_are_measured(runs):
    for root in runs:
        model_trials(root)
    cell = cells.build_run_cell(runs[0], 'plate', 'C04')
    assert cell['refusals'] == {}
    assert cell['stats'] is not None and cell['stats']['n'] == 10
    text = cells.publication_text(cell)
    assert '2.3 ms' in text
    assert 'malformed_samples' not in text
    assert 'no witnessed frame interval' not in text


def test_c04_median_is_not_bucketed_by_an_ambient_frame_interval(runs):
    for root in runs:
        model_trials(root)
    cell = cells.build_run_cell(runs[0], 'plate', 'C04')
    assert cell['frame_interval_ms'] is None
    assert '< 1 frame' not in cells.publication_text(cell)
    facts = {}
    text = report._cell_text(facts, list(runs), 'plate', 'C04')
    assert facts['perf.e2.plate.C04.reproduced'] is True
    assert '2.3 ms' in text and '< 1 frame' not in text


def test_witnessed_trials_without_flags_are_still_refused(runs):
    for i in range(10):
        trial(
            runs[0],
            i,
            'C07',
            layer='browser_visible',
            samples_ms=[20],
            sub_frame_samples=None,
            diagnostic={'frame_interval_ms': 16.7},
        )
    cell = cells.build_run_cell(runs[0], 'plate', 'C07')
    assert cell['refusals'] == {'malformed_samples': 10}
    assert cell['stats'] is None
