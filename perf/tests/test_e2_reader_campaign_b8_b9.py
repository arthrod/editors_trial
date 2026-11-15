"""B8 and B9 in a block campaign (#180).

B8: each resources job records its own pair verdict ("scheduled_below_10;
second_seed_required") — true of one 5-launch job, false of the pooled seed.
B9: a campaign run folder holds many lanes; a typing cell reads only the typing
job of its editor and kind, never every job of the folder.
"""

import json
from pathlib import Path

import pytest

from build import perf_e2_tables as report
from perf.analysis import e2_resources as res
from perf.tests import test_e2_reader_resources as rfx

PAIR_VERDICT = 'scheduled_below_10; second_seed_required'


def _pair_blocked_blocks(root, seed, reason=PAIR_VERDICT):
    rfx._blocks(root, seed, summary={'publishable': False, 'publication_block_reason': reason})


def test_b8_job_pair_verdict_does_not_block_the_pooled_seed(tmp_path):
    for seed in (1, 2):
        _pair_blocked_blocks(tmp_path, seed)
    cell = res.read_cell([tmp_path], 'plate', 'prose-250kw')
    assert cell['published'] is True, cell['reason']
    assert cell['kept'] == [10, 10] and cell['scheduled'] == [10, 10]


def test_b8_job_kept_below_verdict_is_rechecked_on_the_pooled_seed(tmp_path):
    for seed in (1, 2):
        _pair_blocked_blocks(tmp_path, seed, 'scheduled_below_10; kept_below_5; second_seed_required')
    cell = res.read_cell([tmp_path], 'plate', 'prose-250kw')
    assert cell['published'] is True, cell['reason']


def test_b8_other_run_level_reasons_still_block(tmp_path):
    _pair_blocked_blocks(tmp_path, 1)
    _pair_blocked_blocks(tmp_path, 2, 'host_class_not_publishable; scheduled_below_10; second_seed_required')
    cell = res.read_cell([tmp_path], 'plate', 'prose-250kw')
    assert cell['published'] is False
    assert cell['reason'].startswith('second seed: run blocked (host_class_not_publishable')


def test_b8_too_few_kept_in_the_pooled_seed_still_blocks(tmp_path):
    _pair_blocked_blocks(tmp_path, 1)
    bad = [rfx._record(outcome='failed', refusal_code='editor_timeout')] * 10
    rfx._blocks(tmp_path, 2, records=bad,
                summary={'publishable': False, 'publication_block_reason': PAIR_VERDICT})
    cell = res.read_cell([tmp_path], 'plate', 'prose-250kw')
    assert cell['published'] is False and cell['reason'].startswith('second seed: 0 of 10 launches kept')


# B9 ---------------------------------------------------------------------------------------------

TREE = 'b' * 64


def _typing_row(editor, kind, **over):
    row = dict(
        editor_id=editor, criterion_id='TYPING', outcome='measured', refusal_code=None,
        schema='perf.typing/2', session_kind=kind, correctness_oracle='dom_document_text',
        isolation='fresh_process', values_per_session=1, cadence_ms=0, budget_s=3600, session_wall_s=300,
        fixture_sha256='full-file', typed_text_sha256='full-stripped-text', fixture_words=12805,
        words_typed=12805, execution_profile='dedicated_publish', host_class='dedicated', publishable=False,
        publication_block_reason='inspect all witness and resource refusals; publication requires complete session set',
        throughput_chars_s=123, load_ms=25, load_refusal=None,
        key_to_paint={'outcome': 'measured', 'n_scheduled': 2, 'n_accepted': 2, 'n_refused': 0,
                      'median_ms': 20, 'p90_ms': 22,
                      'samples': [{'ms': 20, 'sub_frame': False}, {'ms': 22, 'sub_frame': False}]},
        resources={'phases': {'typing': {'cpu_ms': 0, 'rss_bytes': 1234}}},
        resource_endpoints={},
        host_provenance={'host_build': 'production', 'publishable': True, 'tree_sha256': TREE},
    )
    row.update(over)
    return row


def _typing_job(root, name, seed, editor, kind, *, failure_reason=None, row_over=None):
    job = root / 'benchmark_typing' / name
    job.mkdir(parents=True)
    summary = dict(run_id=name, seed=seed, runner='benchmark_typing', session_kind=kind,
                   order=[[i, editor] for i in range(6)], publishable=False,
                   execution_profile='dedicated_publish', host_class='shared_guarded')
    if failure_reason:
        summary['failure_reason'] = failure_reason
    (job / 'summary.json').write_text(json.dumps(summary))
    for i in range(6):
        path = job / 'cells' / f'{i:04d}-{editor}' / 'attempts' / 'TYPING.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(_typing_row(editor, kind, **(row_over or {}))))
    return job


def _other_lane_job(root, name, seed, editor):
    """A non-typing job in the same folder: its order holds the editor, its verdict is its own."""
    job = root / 'benchmark_warm_cold' / name
    (job / 'cells').mkdir(parents=True)
    (job / 'summary.json').write_text(json.dumps(dict(
        run_id=name, seed=seed, runner='benchmark_warm_cold', order=[[i, editor] for i in range(5)],
        failure_reason='cells_failed', execution_profile='dedicated_publish', host_class='shared_guarded')))
    return job


def _campaign(tmp_path):
    roots = []
    for seed in (1, 2):
        root = tmp_path / f'space-{seed}'
        _typing_job(root, f'plate-lat-{seed}', seed, 'plate', 'latency')
        _typing_job(root, f'plate-thr-{seed}', seed, 'plate', 'throughput')
        _typing_job(root, f'canvas-lat-{seed}', seed, 'canvas', 'latency',
                    failure_reason='insufficient_typing_sessions',
                    row_over={'outcome': 'failed', 'refusal_code': 'text_mismatch'})
        _other_lane_job(root, f'warm-{seed}', seed, 'plate')
        roots.append(root)
    return roots


@pytest.mark.parametrize('kind', ['latency', 'throughput'])
def test_b9_typing_cell_reads_only_its_editor_and_kind(tmp_path, kind):
    roots = _campaign(tmp_path)
    for seed in (1, 2):
        group = report._typing_group_for_seed(roots, 'plate', kind, seed)
        assert group['scheduled'] == 6, group['scheduled']
        assert len(group['kept']) == 6
        assert not group['blocked'], group.get('block_reason')


def test_b9_a_cell_keeps_its_own_jobs_verdict(tmp_path):
    roots = _campaign(tmp_path)
    group = report._typing_group_for_seed(roots, 'canvas', 'latency', 1)
    assert group['scheduled'] == 6 and group['kept'] == []
    assert group['blocked'] and group['block_reason'] == 'insufficient_typing_sessions'


def test_b9_progress_is_prose_not_a_python_repr():
    text = report._typing_progress_text([{'characters_typed': 30939}, {'characters_typed': 30748}])
    assert '{' not in text and '[' not in text
    assert text == 'characters typed in the refused sessions that recorded progress: 30,939, 30,748'


def test_b9_a_cell_that_does_not_reproduce_says_instrumented_once(tmp_path, monkeypatch):
    roots = _campaign(tmp_path)
    second = tmp_path / 'space-2' / 'benchmark_typing' / 'plate-lat-2'
    for path in second.glob('cells/*/attempts/TYPING.json'):
        row = json.loads(path.read_text())
        row['key_to_paint'] = {**row['key_to_paint'], 'median_ms': 80, 'p90_ms': 90}
        path.write_text(json.dumps(row))
    monkeypatch.setattr(report, 'check_roots_comparable', lambda roots: None)
    text = report.typing_table({}, roots, 'plate', 'latency')
    assert 'did not reproduce' in text, text
    assert text.count('figures withheld') == 1, text


def _throttle_one_launch(root, seed, block, rep):
    """The runner refused one launch for CPU throttling: a sample row, no resource.json."""
    job = root / 'benchmark_resources' / ('plate-s%d-b%d' % (seed, block))
    (job / 'cells' / ('%04d-plate' % rep) / 'resource.json').unlink()
    (job / 'samples').mkdir(exist_ok=True)
    (job / 'samples' / ('%04d-plate.json' % rep)).write_text(json.dumps(
        dict(editor_id='plate', outcome='failed', failure_reason='cpu_throttled', refusal_code='cpu_throttled')))


def test_b8_a_throttled_launch_is_a_refusal_not_a_missing_file(tmp_path):
    for seed in (1, 2):
        _pair_blocked_blocks(tmp_path, seed)
    _throttle_one_launch(tmp_path, 2, 1, 2)
    _throttle_one_launch(tmp_path, 2, 2, 6)
    cell = res.read_cell([tmp_path], 'plate', 'prose-250kw')
    assert cell['published'] is True, cell['reason']
    assert cell['kept'] == [10, 8] and cell['scheduled'] == [10, 10]


def test_b8_a_launch_with_no_record_and_no_sample_still_blocks(tmp_path):
    for seed in (1, 2):
        _pair_blocked_blocks(tmp_path, seed)
    (tmp_path / 'benchmark_resources' / 'plate-s2-b2' / 'cells' / '0006-plate' / 'resource.json').unlink()
    cell = res.read_cell([tmp_path], 'plate', 'prose-250kw')
    assert cell['published'] is False and 'block 2' in cell['reason']


def test_b9_a_blocked_cell_without_a_reason_lists_refusals_as_prose(tmp_path, monkeypatch):
    """Review of #180, nit 4: a refusal tally is prose, never a Python dict."""
    roots = _campaign(tmp_path)
    for seed in (1, 2):
        job = tmp_path / f'space-{seed}' / 'benchmark_typing' / f'canvas-lat-{seed}' / 'summary.json'
        summary = json.loads(job.read_text())
        summary.pop('failure_reason')
        job.write_text(json.dumps(summary))
    monkeypatch.setattr(report, 'check_roots_comparable', lambda roots: None)
    text = report.typing_table({}, roots, 'canvas', 'latency')
    assert 'not enough sessions' in text, text
    assert '{' not in text and "'" not in text, text
    assert 'refusals: crash (6)' in text, text


def test_b9_a_latency_table_is_a_block_of_its_own(tmp_path, monkeypatch):
    """#214: Markdown needs a blank line before a table; without it the twin shows pipes as text."""
    roots = _campaign(tmp_path)
    monkeypatch.setattr(report, 'check_roots_comparable', lambda roots: None)
    lines = report.typing_table({}, roots, 'plate', 'latency').split('\n')
    head = lines.index('| Measure | First seed | Second seed |')
    assert lines[head - 1] == '', lines[:head + 1]
    assert lines[head + 1] == '|---|---|---|'
    rows = [i for i, line in enumerate(lines) if line.startswith('|')]
    assert rows == list(range(head, rows[-1] + 1)), 'the table rows are contiguous'
    witnesses = [i for i, line in enumerate(lines) if line.endswith('key witnesses.')]
    assert len(witnesses) == 2
    for i in witnesses:
        assert lines[i - 1] == '', lines[rows[-1]:]
