"""#206: the report states how much of each timed load is still the harness's own text scan."""
from perf.tests import test_e2_report_fix3 as fixtures
from perf.tests.test_e2_report_fix3 import trial
from build import perf_e2_tables as report

runs = fixtures.runs


def _c11(runs, scan, load, workload='prose-250kw'):
    for root in runs:
        for rep in range(10):
            trial(root, rep, 'C11', name='c11-%s.json' % workload, samples_ms=[load], workload_id=workload,
                  diagnostic={'frame_interval_ms': 16.7, 'samples': [{'probe_scan_ms_at_text': scan}]})


def test_the_share_of_the_scan_is_stated_per_editor(runs):
    _c11(runs, 50, 10000, 'prose-5kw')
    _c11(runs, 1300, 20000, 'prose-250kw')
    text = report.probe_scan_text(list(runs), ['plate'])
    assert text == ('Share of the C11 load that is the harness\'s own text read, at the document size where it is '
                    'largest: Plate.js 6.5 percent (prose-250kw).')


def test_editors_under_one_percent_are_grouped(runs):
    _c11(runs, 7, 10000)
    text = report.probe_scan_text(list(runs), ['plate'])
    assert text == ('Share of the C11 load that is the harness\'s own text read, at the document size where it is '
                    'largest: under 1 percent for Plate.js.')


def test_records_without_the_scan_time_say_so(runs):
    for root in runs:
        for rep in range(10):
            trial(root, rep, 'C11', samples_ms=[100])
    assert report.probe_scan_text(list(runs), ['plate']) == 'The harness\'s own text read is not recorded in these runs.'
    assert report.unset_facts()['perf.e2.probe_scan'] == 'not yet measured'
