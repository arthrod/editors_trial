"""#136 round two: pure policy checks and real-parser integration dry runs."""
import importlib
import sys
from functools import partial

import pytest

from perf.analysis.publication_gate import trial_publishable_flags
from perf.runner import browser_run as api
from perf.runner.criteria_input_io import trial_from_entry
from perf.tests.test_b7_samples import _env
from perf.tests.test_b4_input_criteria import _entry, _witness


def accounting():
    return dict(available=True, nr_periods=1, nr_throttled=0, throttled_usec=0,
                cpu_ticks={'total': 1, 'steal': 0}, loadavg=[0, 0, 0],
                cpu_max='200000 100000', cpu_count_visible=2, cgroup_path='/fake')


class ReachedCell(BaseException):
    """Stop an integration dry run before any real browser or host is started."""


@pytest.mark.parametrize('module,boundary,count,single', [
    ('benchmark_warm_cold', 'build_workload', '--pairs', False),
    ('benchmark_document', 'assert_catalog_alignment', '--samples', False),
    ('benchmark_input', 'run_editor', None, False),
    ('adversarial_c10_scroll', 'scroll_fixture', '--pairs', True),
])
@pytest.mark.parametrize('host', ['dedicated', 'shared_guarded'])
def test_real_runner_parser_integration(tmp_path, monkeypatch, module, boundary, count, single, host):
    runner = importlib.import_module('perf.runner.' + module)
    seen = []

    def fake_host_boundary(*args, **kwargs):
        seen.append((api.execution_profile(), api.host_class(), api.CELL.get()))
        raise ReachedCell

    # No upstream test transport exists for these local runner functions. Stop at
    # their first post-parser workload/host boundary; keep the actual main/parser.
    monkeypatch.setattr(runner, boundary, fake_host_boundary)
    monkeypatch.setattr(sys, 'argv', [module, '--out-root', str(tmp_path),
        '--execution-profile', 'dedicated_publish', '--host-class', host,
        '--editor' if single else '--editors', 'plate'])
    parse_exit = None
    try:
        api.run_cli(runner._main, module, {'plate': {}}, count_flag=count, single=single,
            run_factory=partial(api.BrowserRun, snapshot=lambda: {}, accounting_reader=accounting),
            facts=(lambda: {}, lambda: {}))
    except ReachedCell:
        pass
    except SystemExit as exc:
        parse_exit = exc
    assert parse_exit is None, f"runner parser exited: {parse_exit}"
    assert seen == [('dedicated_publish', host, {'repetition': 0, 'editor_id': 'plate'})]


@pytest.mark.parametrize('cid', ['C07', 'C08', 'C09'])
def test_one_launch_trial_publishable(cid):
    entry = _entry(cid=cid, samples_ms=[20.0], sub_frame_samples=[False],
                   trial_hints={'cache_state': 'warm_steady', 'repetition_unit': 'fresh_process'})
    trial = trial_from_entry(cid, entry, _env(), witness=_witness())
    assert trial['publishable'], trial['publication_block_reason']
    assert trial['diagnostic']['frame_interval_ms'] == 16.667


@pytest.mark.parametrize('unit', ['fresh_process', 'in_process_iteration'])
def test_headless_i10_still_applies(unit):
    env = _env(repetition_unit=unit)
    assert 'I10' in trial_publishable_flags(env, 'model', 1)[1]
    assert trial_publishable_flags(env, 'model', 2) == (True, None)


@pytest.mark.parametrize('samples,flags,expected', [
    ([8.5, 20, 30], [True, False, False], False),
    ([30, 8.5, 20], [False, False, True], True),
    ([8, 10, 20, 30], [True, True, False, False], False),
    ([30, 10, 20, 8], [False, True, True, False], True),
])
def test_c07_flag_tracks_middle_clicks(samples, flags, expected):
    entry = _entry(samples_ms=samples, sub_frame_samples=flags,
                   trial_hints={'cache_state': 'warm_steady', 'repetition_unit': 'fresh_process'})
    trial = trial_from_entry('C07', entry, _env(), witness=_witness())
    assert trial['sub_frame_samples'] == [expected]
    assert trial['diagnostic']['c07_click_samples_ms'] == samples


@pytest.mark.parametrize('missing', ['before', 'after'])
def test_shared_guarded_requires_both_bracket_reads_integration(tmp_path, missing):
    unavailable = {'available': False, 'reason': 'test outage'}
    readings = iter([accounting(), unavailable if missing == 'before' else accounting(),
                     unavailable if missing == 'after' else accounting(), accounting()])
    run = api.BrowserRun(tmp_path, 'test', snapshot=lambda: {}, accounting_reader=lambda: next(readings))
    run.host_class = 'shared_guarded'
    run.begin_sample()
    run.sample('one', {'outcome': 'ok'})
    assert run.samples[0]['outcome'] == 'failed'
    assert run.samples[0]['failure_reason'] == 'cpu_accounting_unavailable'


@pytest.mark.parametrize('samples,expected', [([20.0], False), ([20.0, 30.0], True)])
def test_input_in_process_keeps_per_trial_i10(samples, expected):
    entry = _entry(cid='C04', samples_ms=samples,
                   trial_hints={'cache_state': 'warm_steady', 'repetition_unit': 'in_process_iteration'})
    trial = trial_from_entry('C04', entry, _env(repetition_unit='in_process_iteration'), witness=_witness())
    assert trial['publishable'] is expected
    if not expected:
        assert 'I10' in trial['publication_block_reason']
