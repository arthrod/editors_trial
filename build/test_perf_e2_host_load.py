"""#228: the report names the jobs whose samples were taken on a busy host."""
import json
from pathlib import Path

from build import perf_e2_host_load as hl


def _reading(load):
    return {'available': True, 'loadavg': [load, 9.0, 9.0], 'cpu_count_visible': 64}


def _job(root: Path, lane: str, name: str, loads, *, seed=1, block=1, fixture='prose-50kw', extra=(),
         editors=('folio', 'plate')):
    job = root / lane / name
    (job / 'samples').mkdir(parents=True)
    summary = {'runner': lane, 'seed': seed, 'fixtures': ['fixtures/%s-0123456789abcdef.docx' % fixture] if fixture else [],
               'order': [[index, editor] for index, editor in enumerate(editors)]}
    if block:
        summary['block'] = {'index': block, 'of': 2, 'repetitions': 5}
    (job / 'summary.json').write_text(json.dumps(summary))
    for index, (before, after) in enumerate(loads):
        row = {'editor_id': 'plate', 'accounting_scope': 'sample',
               'cpu_accounting': {'available': True, 'before': _reading(before), 'after': _reading(after)}}
        (job / 'samples' / ('%04d-plate.json' % index)).write_text(json.dumps(row))
    for index, row in enumerate(extra):
        (job / 'samples' / ('x%04d.json' % index)).write_text(json.dumps(row))
    return job


def test_a_row_is_above_the_bound_when_either_end_was():
    assert hl.BOUND_FRACTION == 1 / 3
    quiet = {'cpu_accounting': {'available': True, 'before': _reading(21.33), 'after': _reading(3.0)}}
    busy_end = {'cpu_accounting': {'available': True, 'before': _reading(3.0), 'after': _reading(21.34)}}
    assert hl.row_load(quiet) == (21.33, False, 21.33)
    assert hl.row_load(busy_end) == (21.34, True, 21.33)


def test_a_row_without_a_reading_is_counted_apart_never_as_quiet():
    assert hl.row_load({'cpu_accounting': {'available': False, 'reason': 'darwin'}}) is None
    assert hl.row_load({}) is None
    assert hl.row_load({'cpu_accounting': {'available': True, 'before': {'loadavg': [1.0]}, 'after': {'loadavg': [1.0]}}}) is None


def test_job_rows_count_samples_and_leave_diagnostic_rows_out(tmp_path):
    root = tmp_path / 'e2-apryse--20261112T183630601693Z-12164-085332'
    diagnostic = {'accounting_scope': 'diagnostic',
                  'cpu_accounting': {'available': True, 'before': _reading(60.0), 'after': _reading(60.0)}}
    _job(root, 'benchmark_warm_cold', 'r-004', [(50.0, 60.0), (10.0, 12.0), (10.0, 30.0), (5.0, 5.0)], extra=[diagnostic, {}])
    (row,) = hl.job_rows([root])
    assert row == {'space': 'e2-apryse', 'lane': 'benchmark_warm_cold', 'job': 'r-004', 'seed': 1, 'block': 1,
                   'workload': 'prose-50kw', 'editors': ['folio', 'plate'], 'samples': 4, 'above': 2, 'unread': 1,
                   'highest': 60.0, 'bound': 21.33}


def test_the_section_gives_each_lane_and_names_the_busy_jobs(tmp_path):
    root = tmp_path / 'e2-apryse--rid1'
    _job(root, 'benchmark_warm_cold', 'r-004', [(50.0, 66.0)] * 3 + [(5.0, 5.0)])           # 3 of 4
    _job(root, 'benchmark_warm_cold', 'r-006', [(5.0, 5.0)] * 7 + [(22.0, 5.0)], block=2)    # 1 of 8: not named
    other = tmp_path / 'e2-docen--rid2'
    _job(other, 'benchmark_document', 'r-010', [(5.0, 5.0)] * 4, seed=2, fixture='prose-5kw')
    text, facts = hl.section([root, other], ['folio', 'plate'], {'folio': 'Folio', 'plate': 'Plate.js'})
    assert facts['perf.e2.host_load.samples'] == 16 and facts['perf.e2.host_load.above'] == 4
    assert facts['perf.e2.host_load.jobs_named'] == 1
    assert 'Of the 16 launches of these runs, 4 (25.0 percent) began or ended with the load above 21.3' in text
    assert '| document | 4 | 0 | 0.0 percent |' in text
    assert '| warm and cold load | 12 | 4 | 33.3 percent |' in text
    assert '| warm and cold load | 50,000 words | first | 1 | e2-apryse | every editor | 3 of 4 | 66.0 |' in text
    assert 'r-006' not in text and '| 1 of 8 |' not in text
    assert text.index('| document |') < text.index('| warm and cold load | 12')  # lanes alphabetical, not ranked


def test_no_job_named_says_so_and_no_readings_says_that(tmp_path):
    root = tmp_path / 'e2-docen--rid'
    _job(root, 'benchmark_document', 'r-010', [(5.0, 5.0)] * 4)
    text, facts = hl.section([root])
    assert 'In no job were a quarter or more of the launches above it.' in text and facts['perf.e2.host_load.jobs_named'] == 0
    empty = tmp_path / 'e2-x--rid'
    (empty / 'benchmark_document' / 'r-1' / 'samples').mkdir(parents=True)
    text, facts = hl.section([empty])
    assert text == 'The host load of the launches was not recorded in these runs.'
    assert facts['perf.e2.host_load.samples'] == 0


def test_rows_without_a_reading_are_disclosed(tmp_path):
    root = tmp_path / 'e2-docen--rid'
    _job(root, 'benchmark_document', 'r-010', [(5.0, 5.0)] * 4, extra=[{'editor_id': 'plate'}] * 2)
    text, facts = hl.section([root])
    assert facts['perf.e2.host_load.unread'] == 2
    assert '2 further launches carry no load reading and are not counted.' in text


def test_a_job_that_names_several_documents_or_no_block_is_still_listed(tmp_path):
    root = tmp_path / 'e2-publish--rid'
    job = _job(root, 'benchmark_typing', 'r-050', [(40.0, 40.0)] * 4, block=None, fixture=None)
    assert job.exists()
    text, _facts = hl.section([root], ['folio', 'plate'], {})
    assert '| typing | not recorded | first | not recorded | e2-publish | every editor | 4 of 4 | 40.0 |' in text


def test_the_lane_words_are_the_reports_own():
    from build.perf_e2_tables import LANE_NAMES
    assert hl.LANES == LANE_NAMES


def test_a_job_that_measured_one_editor_again_names_it(tmp_path):
    """An editor round re-ran one editor under the job's number: its five rows are that editor's, not everyone's."""
    root = tmp_path / 'e2-superdoc--rid'
    _job(root, 'benchmark_warm_cold', 'r-080', [(24.0, 24.0)] * 3 + [(5.0, 5.0)] * 2, seed=2, fixture='prose-500w',
         editors=('wordcraft',))
    text, _facts = hl.section([root], ['folio', 'plate', 'wordcraft'], {'wordcraft': 'WordCraft'})
    assert '| warm and cold load | 500 words | second | 1 | e2-superdoc | WordCraft | 3 of 5 | 24.0 |' in text


def test_a_job_whose_summary_lists_no_document_takes_it_from_its_attempts(tmp_path):
    root = tmp_path / 'e2-docen--rid'
    job = _job(root, 'benchmark_memory', 'r-066', [(30.0, 30.0)] * 4, fixture=None)
    attempts = job / 'cells' / '0000-plate' / 'attempts'
    attempts.mkdir(parents=True)
    (attempts / 'c17.json').write_text(json.dumps({'environment': {'workload_id': 'prose-250kw'}}))
    text, _facts = hl.section([root], ['folio', 'plate'], {})
    assert '| memory | 250,000 words | first | 1 | e2-docen | every editor | 4 of 4 | 30.0 |' in text


def test_the_bound_printed_is_the_bound_each_launch_was_judged_by(tmp_path):
    """Review: the count read the CPU count from either end and the printed bound from the first end only."""
    after_only = {'cpu_accounting': {'available': True, 'before': {'available': True, 'loadavg': [30.0, 1, 1]},
                                     'after': _reading(30.0)}}
    assert hl.row_load(after_only) == (30.0, True, 21.33)
    root = tmp_path / 'e2-docen--rid'
    _job(root, 'benchmark_document', 'r-010', [], extra=[after_only] * 4)
    (row,) = hl.job_rows([root])
    assert row['bound'] == 21.33 and row['above'] == 4
    text, _facts = hl.section([root], ['folio', 'plate'], {})
    assert 'began or ended with the load above 21.3.' in text


def test_the_template_does_not_say_the_machine_caused_a_disagreement():
    template = (Path(hl.__file__).resolve().parents[1] / 'templates/reports/Report E2 - Speed in the Browser (2026).md').read_text()
    assert 'likelier cause' not in template
    assert 'the load is one possible reason, and the report cannot tell it from the editor' in template
