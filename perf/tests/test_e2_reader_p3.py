"""P3 report regressions on upstream pyfakefs evidence trees."""

import json
import pytest
from perf.tests import test_e2_report_fix3 as fixtures
from perf.tests.test_e2_report_fix3 import trial, sample
from perf.analysis import e2_cells as cells
from build import perf_e2_tables as report

runs = fixtures.runs


def test_only_attempts_are_trials(runs):
    root = runs[0]
    (root / 'cells/0000-plate/summary_c10.json').write_text(
        json.dumps(dict(editor_id='plate', criterion_id='C07', publishable=True))
    )
    (root / 'cells/0000-plate/resources.json').write_text('[]')
    assert cells.build_run_cell(root, 'plate', 'C07')['refusals'] == {}
    assert len(list(report._iter_trials(root))) == 10
    assert len(list(cells._iter_trials(root))) == 10
    assert report._pins(root) == report._pins(runs[1])


@pytest.mark.parametrize('code', ['cpu_throttled', 'host_build', 'cpu_accounting_unavailable'])
def test_quarantine_preserves_other_evidence(runs, code):
    root = runs[0]
    (root / 'rejected-evidence/0000-plate').mkdir(parents=True)
    sample(root, 0, code, code)
    (root / 'cells/0000-plate/attempts/bad.json').write_text('{')
    cell = cells.build_run_cell(root, 'plate', 'C07')
    assert cell['refusals'] == {'quarantined': 1}
    assert cell['additional_refusals'] == {'unreadable_trial': 1, code: 1}
    assert 'also' in cells.failure_text(cell)


def test_ledger_retains_measure_and_workload(runs):
    for root in runs:
        trial(root, 0, 'C14', measure='50kw', workload_id='prose')
    facts = {}
    report._cell_text(facts, list(runs), 'plate', 'C14', '50kw', 'prose')
    text = report._not_reproduced_table(facts)
    assert '50kw' in text and 'prose' in text


@pytest.mark.parametrize('value', [5, 20])
def test_success_shows_kept_and_scheduled(runs, value):
    for i in range(10):
        trial(runs[0], i, samples_ms=[value], sub_frame_samples=[value < 16.7])
    text = cells.publication_text(cells.build_run_cell(runs[0], 'plate', 'C07'))
    assert 'n = 10 of 30' in text


def test_empty_criteria_do_not_invent_cells(runs):
    facts = report.facts_from_runs(*runs)
    assert facts['perf.e2.cells_checked'] == 1
    assert 'unspecified' not in facts['perf.e2.table.C14']
    assert 'unspecified' not in report._criterion_table({}, list(runs), 'C15', ['plate'])


@pytest.mark.parametrize('verified', [True, False, None])
def test_c11_content_is_not_inferred(runs, verified):
    for root in runs:
        for i in range(10):
            trial(root, i, 'C11', content_verified=verified)
    text = report._cell_text({}, list(runs), 'plate', 'C11')
    assert ('content not verified' in text) == (verified is not True)


def test_reproduction_content_is_also_disclosed(runs):
    for root in runs:
        for i in range(10):
            trial(root, i, 'C11', content_verified=root == runs[0])
    assert 'content not verified' in report._cell_text({}, list(runs), 'plate', 'C11')


def test_accounting_outage_reaches_host_note():
    text = report._host_note({
        'cpu_accounting': {'samples_total': 30, 'samples_refused': 0, 'samples_unavailable': 30}
    })
    assert '30 of 30' in text and 'unavailable' in text


@pytest.mark.parametrize(
    'value,expected',
    [
        (0, '0 B'),
        (1234, '1.2 KiB'),
        (
            {'marker': 'not_available_on_platform', 'reason': 'single_sample_phase'},
            'not available on this platform (single_sample_phase)',
        ),
        ('not_applicable_endpoint', 'not applicable at this endpoint'),
        ('not_available_on_platform', 'not available on this platform'),
        (True, 'not recorded'),
    ],
)
def test_resource_markers(value, expected):
    assert callable(getattr(report, 'fmt_resource', None)), 'resource formatter is absent'
    assert report.fmt_resource(value) == expected


def test_memory_is_in_generated_tables(runs):
    for root in runs:
        for i in range(10):
            trial(root, i, 'C19', sample_unit='bytes', samples_ms=[0], diagnostic={}, sub_frame_samples=None)
    facts = report.facts_from_runs(*runs)
    assert 'perf.e2.table.C19' in facts
    assert '0.0 bytes' in facts['perf.e2.table.C19']


def test_unverified_content_also_labels_nonreproduced_medians(runs):
    for root, value in zip(runs, (20, 200)):
        for i in range(10):
            trial(root, i, 'C11', samples_ms=[value], content_verified=False)
    text = report._cell_text({}, list(runs), 'plate', 'C11')
    assert 'not reproduced' in text
    assert text.count('content not verified') == 2


def test_quarantine_does_not_lose_unreadable_before_run_refusal(runs):
    root = runs[0]
    (root / 'cells/0000-plate/attempts/A.json').write_text('{')
    trial(root, 0, 'C04', name='Z.json', refusal_code='host_build', outcome='refused')
    (root / 'rejected-evidence/0000-plate').mkdir(parents=True)
    result = cells.build_run_cell(root, 'plate', 'C07')
    assert result['refusals'] == {'quarantined': 1}
    assert result['additional_refusals'] == {'unreadable_trial': 1, 'host_build': 1}
