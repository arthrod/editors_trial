"""#136: launch contracts and accounting outages (disk cases are integration tests)."""

import json
import sys
from functools import partial
from pathlib import Path

import pytest

from perf.runner import browser_run as api
from perf.runner.criteria_input_io import trial_from_entry
from perf.tests.test_b7_fix2 import accounting
from perf.tests.test_b7_samples import _env
from perf.tests.test_b4_input_criteria import _entry, _witness


@pytest.mark.parametrize('cid', ['C04', 'C08', 'C09'])
@pytest.mark.parametrize('hint', [True, False])
def test_fresh_process_multiple_samples_refused(cid, hint):
    entry = _entry(
        cid=cid, samples_ms=[21.0, 22.0, 23.0], trial_hints={'repetition_unit': 'fresh_process'} if hint else {}
    )
    trial = trial_from_entry(cid, entry, _env(), witness=_witness())
    assert trial.get('failure_reason') == 'fresh_process_multi_sample'
    assert trial['outcome'] == 'failed'
    assert trial['publishable'] is False
    assert trial['samples_ms'] == []


@pytest.mark.parametrize('host', ['shared_guarded', 'dedicated', 'ci_coarse'])
@pytest.mark.parametrize('broken_read', ['before', 'after', 'both', 'persistent'])
def test_raising_accounting_reader_continues_and_finishes_integration(tmp_path, monkeypatch, host, broken_read):
    calls = 0

    def reader():
        nonlocal calls
        calls += 1
        # ci_broad has no publication preflight: init, before, after, ... finish.
        if (
            (broken_read in ('before', 'both') and calls == 2)
            or (broken_read in ('after', 'both') and calls == 3)
            or (broken_read == 'persistent' and calls >= 2)
        ):
            raise OSError('cgroup vanished')
        return accounting()

    monkeypatch.setattr(
        sys,
        'argv',
        [
            'fake',
            '--out-root',
            str(tmp_path),
            '--run-id',
            'outage',
            '--seed',
            '7',
            '--repetitions',
            '2',
            '--host-class',
            host,
            '--editors',
            'plate',
        ],
    )
    error = None
    try:
        code = api.run_cli(
            lambda: 0,
            'fake',
            {'plate': {}},
            run_factory=partial(api.BrowserRun, snapshot=lambda: {}, accounting_reader=reader),
            facts=(lambda: {}, lambda: {}),
        )
    except Exception as exc:
        error = exc
    assert error is None, f'accounting outage escaped: {error!r}'
    # B1 contract: browser_run.py:633; e2-logs/b1-fix3-report.md F1.
    assert code == (3 if host == 'shared_guarded' and broken_read == 'persistent' else 0)
    summary = json.loads((tmp_path / 'fake/outage/summary.json').read_text())
    assert len(summary['samples']) == 2
    first = summary['samples'][0]
    assert first['cpu_accounting']['available'] is False
    assert 'OSError: cgroup vanished' in json.dumps(first['cpu_accounting'])
    if host == 'shared_guarded':
        assert first['failure_reason'] == 'cpu_accounting_unavailable'
        assert first['publishable'] is False
    else:
        assert first['outcome'] == 'ok'
    if broken_read != 'persistent':
        assert summary['samples'][1]['outcome'] == 'ok'
        assert summary['samples'][1]['cpu_accounting']['available'] is True


@pytest.mark.parametrize('with_duplicate', [False, True])
def test_one_attempt_per_criterion_measure_and_rung_per_launch_integration(tmp_path, monkeypatch, with_duplicate):
    """72cec1e8 (#151) publishes each C14 rung under its own measurement name,
    so one launch carries the same (criterion, measure) for several rungs; the
    rung is part of the attempt's identity, and only a true duplicate within
    one rung refuses."""
    def main():
        directory = Path(sys.argv[sys.argv.index('--out-root') + 1])
        for index, rung in enumerate(['prose-500w', 'prose-5kw']):
            api.write_json(
                directory / str(index) / 'attempts' / f'c14-{rung}.json',
                {
                    'criterion_id': 'C14',
                    'measure': 'presented_frame',
                    'outcome': 'measured',
                    'samples_ms': [21.0],
                    'publishable': True,
                    'diagnostic': {'size_rung': rung},
                },
            )
        if with_duplicate:
            # a genuine duplicate: the same rung twice
            api.write_json(
                directory / '2' / 'attempts' / 'c14-dup.json',
                {
                    'criterion_id': 'C14',
                    'measure': 'presented_frame',
                    'outcome': 'measured',
                    'samples_ms': [22.0],
                    'publishable': True,
                    'diagnostic': {'size_rung': 'prose-500w'},
                },
            )
        return 0

    monkeypatch.setattr(
        sys, 'argv', ['fake', '--out-root', str(tmp_path), '--run-id', 'rungs', '--seed', '7', '--editors', 'plate']
    )
    expected = 3 if with_duplicate else 0
    assert api.run_cli(
        main,
        'fake',
        {'plate': {}},
        run_factory=partial(api.BrowserRun, snapshot=lambda: {}, accounting_reader=lambda: {'available': False, 'reason': 'darwin'}),
        facts=(lambda: {}, lambda: {}),
    ) == expected
    summary = json.loads((tmp_path / 'fake/rungs/summary.json').read_text())
    sample = summary['samples'][0]
    if with_duplicate:
        assert sample['failure_reason'] == 'multiple_attempts_per_launch'
    else:
        assert sample['outcome'] == 'ok'


@pytest.mark.parametrize('criteria,refused', [(['C08', 'C08'], True), (['C08', 'C09'], False)])
def test_one_attempt_per_criterion_per_launch_integration(tmp_path, monkeypatch, criteria, refused):
    def main():
        directory = Path(sys.argv[sys.argv.index('--out-root') + 1])
        for index, cid in enumerate(criteria):
            # Nested attempts also belong to the same launch.
            api.write_json(
                directory / str(index) / 'attempts' / f'{cid}.json',
                {'criterion_id': cid, 'outcome': 'measured', 'samples_ms': [21.0], 'publishable': True},
            )
        return 0

    monkeypatch.setattr(
        sys, 'argv', ['fake', '--out-root', str(tmp_path), '--run-id', 'attempts', '--seed', '7', '--editors', 'plate']
    )
    assert (
        api.run_cli(
            main,
            'fake',
            {'plate': {}},
            run_factory=partial(api.BrowserRun, snapshot=lambda: {}, accounting_reader=accounting),
            facts=(lambda: {}, lambda: {}),
        )
        == (3 if refused else 0)
    )
    summary = json.loads((tmp_path / 'fake/attempts/summary.json').read_text())
    sample = summary['samples'][0]
    if refused:
        assert sample['failure_reason'] == 'multiple_attempts_per_launch'
        assert sample['outcome'] == 'failed'
        assert sample['publishable'] is False
        assert not list((tmp_path / 'fake/attempts/cells').rglob('attempts/*.json'))
        assert len(list(Path(sample['rejected_evidence_directory']).rglob('attempts/*.json'))) == 2
    else:
        assert sample['outcome'] == 'ok'
