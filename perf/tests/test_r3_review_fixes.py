"""Findings of the adversarial review of the resources lane (review-r3mine, 2026-11-11)."""
import json

from perf.analysis import e2_cells, e2_resources as res
from perf.container import policy
from perf.runner import resources
from perf.tests.test_e2_reader_resources import _job, _record


def _sample(*procs):
    return {'processes': [dict(pid=pid, start_time=start, cpu_ms=cpu, role='renderer') for pid, start, cpu in procs]}


def test_a_process_older_than_the_window_that_was_missed_is_incomplete():
    # pid 11 started before pid 10 did, so it existed at the first sample and was missed.
    rows = [_sample((10, 500, 100)), _sample((10, 500, 110), (11, 400, 50000))]
    assert resources.process_accounting_status(rows) == 'incomplete'
    assert resources._identity_delta(rows, 'cpu_ms')[1] == 'incomplete'


def test_a_process_born_inside_the_window_counts_from_zero():
    rows = [_sample((10, 500, 100)), _sample((10, 500, 110), (11, 900, 40))]
    assert resources._identity_delta(rows, 'cpu_ms') == (50, 'complete')


def test_a_new_process_without_a_start_time_is_incomplete():
    rows = [_sample((10, 500, 100)), _sample((10, 500, 110), (11, None, 40))]
    assert resources.process_accounting_status(rows) == 'incomplete'


def _cell(tmp_path):
    cell = tmp_path / 'cells' / '0000-plate'
    (cell / 'attempts').mkdir(parents=True)
    (cell / 'resource.json').write_text(json.dumps(
        {'record_kind': 'browser_resources', 'editor_id': 'plate', 'outcome': 'measured'}))
    return cell


def test_a_trace_sidecar_does_not_hide_the_resources_record(tmp_path):
    cell = _cell(tmp_path)
    (cell / 'attempts' / 'chrome-profile-b8-0123456789.json').write_text(
        json.dumps({'criterion_id': 'B8', 'outcome': 'profiled', 'accounting_scope': 'diagnostic'}))
    trials = policy.read_trials({'cell_directory': str(cell)})
    assert [t['outcome'] for t in trials if t['outcome'] != 'profiled'] == ['measured']


def test_a_truncated_trace_sidecar_is_skipped(tmp_path):
    cell = _cell(tmp_path)
    (cell / 'attempts' / 'chrome-profile-b8-0123456789.json').write_text('{"criterion_id": "B8", "outc')
    trials = policy.read_trials({'cell_directory': str(cell)})
    assert [t['outcome'] for t in trials] == ['measured']


def test_the_reader_skips_a_truncated_trace_sidecar(tmp_path):
    job = tmp_path / 'benchmark_document' / 'j1'
    attempts = job / 'cells' / '0000-plate' / 'attempts'
    attempts.mkdir(parents=True)
    (job / 'summary.json').write_text(json.dumps({'seed': 1}))
    (attempts / 'c11.json').write_text(json.dumps({'criterion_id': 'C11', 'outcome': 'measured'}))
    (attempts / 'chrome-profile-c11-0123456789.json').write_text('{"trunc')
    rows = list(e2_cells._attempt_rows_of(tmp_path, [job]))
    assert [row.get('criterion_id') for _launch, _path, row in rows] == ['C11']


def test_a_record_without_a_document_belongs_to_no_document(tmp_path):
    nameless = _record()
    del nameless['workload_id']
    _job(tmp_path, 'j1', seed=1, launches=10, records=[nameless] * 10)
    _job(tmp_path, 'j2', seed=2, launches=10, records=[nameless] * 10)
    for workload in ('prose-500w', 'prose-250kw'):
        assert res.read_cell([tmp_path], 'plate', workload)['published'] is False


def test_one_job_pulled_into_two_roots_counts_once(tmp_path):
    for space in ('a', 'b'):
        _job(tmp_path / space, 'j1', seed=1, launches=10)
    _job(tmp_path / 'c', 'j2', seed=2, launches=10)
    cell = res.read_cell([tmp_path / 'a', tmp_path / 'b', tmp_path / 'c'], 'plate', 'prose-250kw')
    assert cell['kept'] == [10, 10] and cell['published'] is True


def test_a_block_measured_twice_blocks_its_seed(tmp_path):
    _job(tmp_path / 'a', 'j1', seed=1, launches=10)
    _job(tmp_path / 'b', 'j9', seed=1, launches=10)  # a re-run of the same launches
    _job(tmp_path / 'c', 'j2', seed=2, launches=10)
    cell = res.read_cell([tmp_path / 'a', tmp_path / 'b', tmp_path / 'c'], 'plate', 'prose-250kw')
    assert cell['published'] is False and 'measured twice' in cell['reason']


def test_one_insertion_in_the_same_block():
    import subprocess
    from pathlib import Path
    module = Path(__file__).resolve().parents[1] / 'runner' / 'edit_surface.mjs'
    script = (
        "import {insertedOnce as f} from %s;"
        "console.log(JSON.stringify(["
        "f('Article one','B8B8Article one','B8B8'),"   # at the start
        "f('Article one','ArtiB8B8cle one','B8B8'),"   # inside
        "f('Article one two','B8B8Article one','B8B8'),"  # the line wrapped its tail away
        "f('Article one','B8B8','B8B8'),"              # the block was replaced
        "f('Article one','B8 Article B8 one','B8B8'),"  # two places
        "f('Article one','XrticleB8B8 one','B8B8')]))"  # other text changed
    ) % json.dumps(module.as_uri())
    out = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout) == [True, True, True, False, False, False]
