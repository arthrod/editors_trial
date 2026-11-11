"""Issue #139: pure guard tests and isolated filesystem integration tests."""
import ast
from functools import partial
import json
from pathlib import Path
import sys

from perf.runner import browser_run as api

ROOT = Path(__file__).parents[1]


def test_rr1_build_log_is_immutable():
    source = (ROOT / 'runner/browser_hosts.py').read_text()
    assert '.write_text(' not in source
    assert "log_path.open('a'" not in source


def test_rr2_system_exit_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['fake', '--out-root', str(tmp_path)])
    def cell():
        raise SystemExit('unsupported criterion id(s): C99')
    try:
        api.run_cli(cell, 'fake', {'a': {}}, facts=(lambda: {}, lambda: {}),
                    run_factory=partial(api.BrowserRun, snapshot=lambda: {},
                                        accounting_reader=lambda: {'available': False, 'reason': 'fake'}))
    except SystemExit:
        pass
    summaries = list(tmp_path.rglob('summary.json'))
    assert len(summaries) == 1
    row = json.loads(summaries[0].read_text())['samples'][0]
    assert row['outcome'] == 'failed'
    assert 'C99' in row['failure_reason']


def reading(n):
    return dict(available=True, nr_periods=10, nr_throttled=n, throttled_usec=n*10000,  # lax layer (owner 2026-11-11): 10 ms per event is above the max(1 ms, 1 %) tolerance
                cpu_ticks=dict(total=100, steal=0), loadavg=[0, 0, 0],
                cpu_max='100 100', cpu_count_visible=1, cgroup_path='/fake')


def test_rr3_leaked_bracket_restores_cell_window(tmp_path):
    state = [reading(2)]
    run = api.BrowserRun(tmp_path, 'fake', snapshot=lambda: {}, accounting_reader=lambda: state[0])
    for rep in range(2):
        token = api.CELL.set(dict(repetition=rep, editor_id='a'))
        try:
            run.begin_sample()
            if rep == 0:
                state[0] = reading(5)
                def leak():
                    run.begin_sample()
                    raise ValueError('probe crashed')
                row = api.capture(leak)
            else:
                row = {'outcome': 'ok'}
            run.sample(f'{rep:04d}-a', row)
        finally:
            api.CELL.reset(token)
    result = run.finish({})
    assert result['cpu_accounting']['samples_total'] == 2
    assert result['cpu_accounting']['samples_refused'] == 1
    assert run.samples[0]['brackets_force_closed'] == 1
    assert run.samples[0]['cpu_accounting']['delta']['nr_throttled'] == 3
    assert run.samples[1]['outcome'] == 'ok'


def test_rr4_guard_covers_writable_routes():
    from perf.tests.test_b1a_fixes import SummaryGuard
    assert hasattr(SummaryGuard, 'write_violations')
    for source in ("open('a', 'w')", "p.open(mode='a')", "os.open(p, os.O_WRONLY | os.O_TRUNC)",
                   "json.dump(row, stream)", "p.write_bytes(b'x')"):
        assert SummaryGuard.write_violations(ast.parse(source)), source


def test_rr5_refusal_keeps_identity_and_safe_skip_listing(tmp_path):
    state = [reading(0)]
    run = api.BrowserRun(tmp_path, 'fake', snapshot=lambda: {}, accounting_reader=lambda: state[0])
    token = api.CELL.set(dict(repetition=3, editor_id='a'))
    try:
        run.begin_sample()
        state[0] = reading(1)
        run.sample('saturation-3-a', dict(outcome='failed', non_failure_outcomes=[
            dict(outcome='not_run', failure_reason='unsupported', latency_ms=99)]))
    finally:
        api.CELL.reset(token)
    row = run.samples[0]
    assert row.get('repetition') == 3
    assert row.get('editor_id') == 'a'
    assert row.get('non_failure_outcomes') == [dict(outcome='not_run', failure_reason='unsupported')]


def test_rr6_saturation_policy_is_explicit():
    assert 'warm_cold_identical' in (api.has_failure.__doc__ or '')
    assert api.has_failure(dict(outcome='failed', failure_reason='warm_cold_identical'))
    assert not api.has_failure(dict(outcome='not_run', failure_reason='warm_cold_identical'))


def test_rr7_baseline_is_operator_selected():
    source = (ROOT / 'tests/b1a_smoke.py').read_text()
    assert '987284c' not in source
    assert '--baseline-ref' in source
