"""B8 reader regressions; pyfakefs supplies deterministic evidence trees."""

import json
import pytest
from perf.tests import test_e2_report_fix3 as fixtures
from perf.tests.test_e2_report_fix3 import trial
from perf.analysis import e2_cells as cells
from build import perf_e2_tables as report

runs = fixtures.runs


@pytest.mark.parametrize(
    'criterion,phase',
    [('C17', 'ready'), ('C17', 'after_edit_burst'), ('C17', 'quiescent'), ('C17', 'peak_during_run'), ('C19', '')],
)
def test_byte_trials_keep_phases_without_timing_fields(runs, criterion, phase):
    for root in runs:
        for rep in range(10):
            for p in ['ready', 'after_edit_burst', 'quiescent', 'peak_during_run'] if criterion == 'C17' else ['']:
                trial(
                    root,
                    rep,
                    criterion,
                    name=criterion + p + '.json',
                    sample_unit='bytes',
                    measurement_phase=p,
                    samples_ms=[65536],
                    sub_frame_samples=None,
                    diagnostic={},
                )
    cell = cells.build_run_cell(runs[0], 'plate', criterion, measure=phase)
    assert cell['refusals'] == {}
    assert cell['stats']['n'] == 10
    text = report._cell_text({}, list(runs), 'plate', criterion, phase)
    assert 'bytes' in text and ' ms' not in text


def test_memory_summary_delegates_only_its_neutral_flag(runs):
    for root in runs:
        s = json.loads((root / 'summary.json').read_text())
        s.update(publishable=False, publication_block_reason='summary is not a trial; trials carry publishability')
        (root / 'summary.json').write_text(json.dumps(s))
    assert 'unpublishable' not in report._cell_text({}, list(runs), 'plate', 'C07')
    assert not cells.build_run_cell(runs[0], 'plate', 'C07')['blocked']
    s.update(outcome='failed', failure_reason='repos_modified')
    (runs[0] / 'summary.json').write_text(json.dumps(s))
    assert cells.build_run_cell(runs[0], 'plate', 'C07')['blocked']


@pytest.mark.parametrize('value', [-1, True, 1.5])
def test_byte_values_are_nonnegative_integers(runs, value):
    trial(runs[0], 0, 'C19', sample_unit='bytes', samples_ms=[value], sub_frame_samples=None, diagnostic={})
    assert cells.build_run_cell(runs[0], 'plate', 'C19')['refusals'] == {'malformed_samples': 1}


def test_delegated_summary_still_requires_independent_reproduction(runs):
    for root in runs:
        s = json.loads((root / 'summary.json').read_text())
        s.update(
            publishable=False, publication_block_reason='summary is not a trial; trials carry publishability', seed=0
        )
        (root / 'summary.json').write_text(json.dumps(s))
    with pytest.raises(ValueError, match='same seed'):
        report.facts_from_runs(*runs)
