"""A resources cell writes resource.json, not attempts/*.json (#155.2).

The shakedown's verify_run said nothing_measured for every resources job.
"""
from __future__ import annotations

import json

import pytest

from perf.container.policy import cell_counts, read_trials, verify_run


def _cell(tmp_path, name, record, attempts=None):
    cell = tmp_path / name
    cell.mkdir()
    if record is not None:
        (cell / 'resource.json').write_text(json.dumps(record))
    for index, row in enumerate(attempts or []):
        (cell / 'attempts').mkdir(exist_ok=True)
        (cell / 'attempts' / f'{index}.json').write_text(json.dumps(row))
    return {'cell_directory': str(cell), 'editor_id': record['editor_id'] if record else 'plate', 'outcome': 'ok'}


def _run(samples):
    return {'runner': 'benchmark_resources', 'rendering': {'renderer': 'swiftshader'}, 'samples': samples}


def test_a_measured_resource_record_is_one_measured_trial(tmp_path):
    row = _cell(tmp_path, '0000-plate', {'record_kind': 'browser_resources', 'editor_id': 'plate', 'outcome': 'measured'})
    trials = read_trials(row)
    assert [(t['criterion_id'], t['editor_id'], t['outcome']) for t in trials] == [('B8', 'plate', 'measured')]
    data = verify_run(_run([row]))
    assert cell_counts(data)['by_editor_criterion']['plate']['B8']['measured'] == 1


def test_a_refused_resource_record_counts_under_its_refusal_code(tmp_path):
    row = _cell(tmp_path, '0000-canvas', {'record_kind': 'browser_resources', 'editor_id': 'canvas',
                                           'outcome': 'refused', 'refusal_code': 'editor_load_failed',
                                           'failure_reason': 'editor_load_failed'})
    counts = cell_counts(_run([row]))
    assert counts['measured'] == 0
    assert counts['refused_by_reason'] == {'editor_load_failed': 1}
    with pytest.raises(ValueError, match='nothing_measured'):
        verify_run(_run([row]))


def test_attempt_files_still_win_and_other_json_is_ignored(tmp_path):
    attempt = {'criterion_id': 'C07', 'editor_id': 'plate', 'outcome': 'measured'}
    row = _cell(tmp_path, '0000-plate', {'record_kind': 'something_else', 'editor_id': 'plate', 'outcome': 'measured'},
                attempts=[attempt])
    assert read_trials(row) == [attempt]
