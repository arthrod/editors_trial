"""#211: C19 is the browser's baseline after the page closes; the report prints no table of it.

The memory lane reads the browser's process tree 1 s and 5 s after the context
closes and subtracts no empty-browser reading. Every editor at every size read
334 to 379 MB. The report says so, with the range of the readings, and the
cells neither count as published cells nor appear as not reproduced.
"""
from perf.tests import test_e2_report_fix3 as fixtures
from perf.tests.test_e2_report_fix3 import trial
from build import perf_e2_tables as report

runs = fixtures.runs


def _c19(runs, first=336 * 2 ** 20, second=340 * 2 ** 20):
    for root, value in zip(runs, (first, second)):
        for rep in range(10):
            trial(root, rep, 'C19', sample_unit='bytes', samples_ms=[value], sub_frame_samples=None, diagnostic={})


def test_c19_has_no_table_and_no_published_cell(runs):
    _c19(runs)
    facts = report.facts_from_runs(*runs)
    assert facts['perf.e2.table.C19'] == 'not published.'
    assert not [key for key in facts if '.C19.' in key and key.endswith('.reproduced')]
    assert facts['perf.e2.withheld.C19'] == (
        'In these runs the seed medians of the 1 editor and document cell that reproduced lay between '
        '336.0 MiB and 340.0 MiB.')


def test_c19_cells_that_disagree_are_not_listed_as_not_reproduced(runs):
    _c19(runs, second=900 * 2 ** 20)
    facts = report.facts_from_runs(*runs)
    assert 'C19' not in facts['perf.e2.not_reproduced']
    assert facts['perf.e2.withheld.C19'] == 'In these runs no editor and document cell reproduced.'


def test_the_unset_report_names_the_fact():
    assert report.unset_facts()['perf.e2.withheld.C19'] == 'not yet measured'
