"""#228: a job does not start on a busy host.

The campaign's host check ran once, before the first job. Four warm/cold
jobs then ran while the shared host's 1-minute load was 16 to 66, and their
cells follow the load, not the editors. The bound is the one the quiet
machine check already uses: a third of the logical CPUs.
"""
import json
from types import SimpleNamespace

import pytest

from perf.container import run
from perf.runner import host_load
from perf.runner.browser_run import BrowserRun


class Clock:
    def __init__(self, loads):
        self.loads, self.now, self.slept = list(loads), 0.0, []

    def read(self):
        return self.loads.pop(0) if len(self.loads) > 1 else self.loads[0]

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds

    def monotonic(self):
        return self.now


def _wait(loads, **kwargs):
    clock = Clock(loads)
    result = host_load.wait_for_quiet(limit=21.33, read=clock.read, sleep=clock.sleep, monotonic=clock.monotonic, **kwargs)
    return result, clock


def test_the_bound_is_a_third_of_the_logical_cpus():
    assert host_load.load_limit(64) == 21.33
    assert host_load.load_limit(8) == 2.67


def test_a_quiet_host_starts_at_once():
    result, clock = _wait([4.2])
    assert result == {'quiet': True, 'load1': 4.2, 'load1_first': 4.2, 'load1_max': 21.33, 'waited_s': 0, 'readings': 1}
    assert clock.slept == []


def test_a_load_at_the_bound_is_quiet_and_one_above_is_not():
    assert _wait([21.33])[0]['quiet'] is True
    assert _wait([21.34], cap_s=0)[0]['quiet'] is False


def test_a_busy_host_is_waited_for_and_the_wait_is_recorded():
    result, clock = _wait([43.2, 30.1, 19.9], poll_s=30)
    assert result['quiet'] is True and result['waited_s'] == 60 and result['readings'] == 3
    assert result['load1_first'] == 43.2 and result['load1'] == 19.9
    assert clock.slept == [30, 30]


def test_a_host_that_stays_busy_is_given_up_on_at_the_cap():
    result, clock = _wait([50.0], poll_s=30, cap_s=90)
    assert result['quiet'] is False and result['waited_s'] == 90 and result['load1'] == 50.0
    assert sum(clock.slept) == 90


def test_the_last_wait_does_not_run_past_the_cap():
    _result, clock = _wait([50.0], poll_s=60, cap_s=90)
    assert clock.slept == [60, 30]


def test_an_unreadable_load_is_not_quiet():
    def boom():
        raise OSError('no loadavg')
    result = host_load.wait_for_quiet(limit=21.33, read=boom, sleep=lambda _s: None, monotonic=lambda: 0.0, cap_s=0)
    assert result['quiet'] is False and result['load1'] is None and 'no loadavg' in result['error']


def test_the_cap_comes_from_the_environment_and_a_bad_value_is_refused(monkeypatch):
    monkeypatch.setenv('E2_HOST_LOAD_WAIT_S', '120')
    assert host_load.cap_seconds() == 120
    monkeypatch.setenv('E2_HOST_LOAD_WAIT_S', 'soon')
    with pytest.raises(ValueError, match='E2_HOST_LOAD_WAIT_S'):
        host_load.cap_seconds()
    monkeypatch.delenv('E2_HOST_LOAD_WAIT_S')
    assert host_load.cap_seconds() == host_load.DEFAULT_CAP_S == 1800


def test_the_guard_uses_the_hosts_cpu_count_and_refuses_when_it_cannot_be_read(monkeypatch):
    monkeypatch.setattr(host_load.os, 'cpu_count', lambda: 64)
    monkeypatch.setattr(host_load, 'read_load1', lambda: 21.0)
    assert host_load.guard() == {'quiet': True, 'load1': 21.0, 'load1_first': 21.0, 'load1_max': 21.33,
                                 'waited_s': 0, 'readings': 1}
    monkeypatch.setattr(host_load.os, 'cpu_count', lambda: None)
    verdict = host_load.guard()
    assert verdict['quiet'] is False
    assert host_load.refusal(verdict) == 'host_load: 1-minute load unreadable (logical CPU count unreadable)'


ARGS = ['--publish', '--host-class', 'shared_guarded', '--seed', '1', '--seed2', '2', '--blocks', '2', '--jobs', '4']


def _publish(tmp_path, monkeypatch, verdict):
    started = []

    def process(command, **_kwargs):
        if command[2] != 'perf.container.check_host':
            started.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run.subprocess, 'run', process)
    monkeypatch.setattr(run.host_load, 'guard', lambda: dict(verdict))
    monkeypatch.setattr(run, 'pin_to_quota', lambda: 'pinned')
    monkeypatch.chdir(tmp_path)
    error = None
    try:
        run.main([*ARGS, '--out-root', str(tmp_path)])
    except RuntimeError as exc:
        error = str(exc)
    report = json.loads((tmp_path / 'out/e2-publication.json').read_text())
    return started, report, error


def test_a_job_is_not_started_on_a_host_that_stayed_busy(tmp_path, monkeypatch):
    busy = {'quiet': False, 'load1': 50.0, 'load1_first': 43.2, 'load1_max': 21.33, 'waited_s': 1800, 'readings': 61}
    started, report, error = _publish(tmp_path, monkeypatch, busy)
    assert started == []
    (row,) = report['runs']
    assert row['refusal'] == 'host_load: 1-minute load 50.00 above 21.33 after waiting 1800 s'
    assert row['host_load'] == busy
    assert 'host_load' in error
    assert not (tmp_path / row['runner']).exists()  # nothing measured, nothing to mistake for a job


def test_a_job_on_a_quiet_host_runs_and_records_what_it_waited(tmp_path, monkeypatch):
    quiet = {'quiet': True, 'load1': 9.5, 'load1_first': 30.0, 'load1_max': 21.33, 'waited_s': 60, 'readings': 3}
    started, report, _error = _publish(tmp_path, monkeypatch, quiet)
    assert len(started) == 1
    assert report['runs'][0]['host_load'] == quiet
    assert not str(report['runs'][0].get('refusal', '')).startswith('host_load')


def test_a_dry_run_reads_no_load(monkeypatch, capsys):
    def never():
        raise AssertionError('a dry run must not wait for the host')
    monkeypatch.setattr(run.host_load, 'guard', never)
    assert run.main(['--publish', '--dry-run', '--host-class', 'shared_guarded', '--seed', '1', '--seed2', '2',
                     '--blocks', '2', '--jobs', '4']) in (0, None)


# --- the same wait before each launch: two of the four busy jobs started on a quiet host ---

READING = {'available': True, 'nr_periods': 1, 'nr_throttled': 0, 'throttled_usec': 0,
           'cpu_ticks': {'total': 100, 'steal': 0}, 'loadavg': [1.0, 1.0, 1.0], 'cpu_max': '800000 100000',
           'cpu_count_visible': 64, 'cgroup_path': '/sys/fs/cgroup'}


def _run(tmp_path, monkeypatch, host_class, verdicts):
    calls = []

    def guard():
        calls.append(1)
        return dict(verdicts[min(len(calls), len(verdicts)) - 1])

    monkeypatch.setattr(host_load, 'sample_guard', guard)
    run_ = BrowserRun(tmp_path, 'fake', seed=1, run_id='t', snapshot=lambda: {}, accounting_reader=lambda: dict(READING))
    run_.host_class = host_class
    return run_, calls


QUIET = {'quiet': True, 'load1': 9.5, 'load1_first': 30.0, 'load1_max': 21.33, 'waited_s': 60, 'readings': 3}
BUSY = {'quiet': False, 'load1': 50.0, 'load1_first': 50.0, 'load1_max': 21.33, 'waited_s': 300, 'readings': 11}


def test_a_launch_on_a_guarded_host_waits_for_quiet_and_its_row_says_so(tmp_path, monkeypatch):
    run_, calls = _run(tmp_path, monkeypatch, 'shared_guarded', [QUIET])
    run_.begin_sample()
    row = json.loads(run_.sample('0000-plate', {'outcome': 'measured'}).read_text())
    assert calls == [1]
    assert row['host_load_wait'] == QUIET


def test_a_probe_inside_a_launch_does_not_wait(tmp_path, monkeypatch):
    """A wait between a launch's cold and warm loads would change what is being measured."""
    run_, calls = _run(tmp_path, monkeypatch, 'shared_guarded', [QUIET])
    run_.begin_sample()
    run_.begin_sample()
    inner = json.loads(run_.sample('probe', {'outcome': 'measured'}).read_text())
    outer = json.loads(run_.sample('0000-plate', {'outcome': 'measured'}).read_text())
    assert calls == [1]
    assert 'host_load_wait' not in inner and outer['host_load_wait'] == QUIET


def test_a_launch_that_started_on_a_host_still_busy_is_measured_and_marked(tmp_path, monkeypatch):
    """Not a refusal: the row keeps its figures and says the host was busy, so the report can name the cell."""
    run_, _calls = _run(tmp_path, monkeypatch, 'shared_guarded', [BUSY])
    run_.begin_sample()
    row = json.loads(run_.sample('0000-plate', {'outcome': 'measured', 'latency_ms': 12}).read_text())
    assert row['outcome'] == 'measured' and row['latency_ms'] == 12
    assert row['host_load_wait']['quiet'] is False


def test_each_launch_waits_on_its_own(tmp_path, monkeypatch):
    run_, calls = _run(tmp_path, monkeypatch, 'shared_guarded', [BUSY, QUIET])
    run_.begin_sample()
    first = json.loads(run_.sample('0000-plate', {'outcome': 'measured'}).read_text())
    run_.begin_sample()
    second = json.loads(run_.sample('0001-plate', {'outcome': 'measured'}).read_text())
    assert len(calls) == 2
    assert first['host_load_wait']['quiet'] is False and second['host_load_wait']['quiet'] is True


def test_a_run_that_is_not_on_a_guarded_host_reads_no_load(tmp_path, monkeypatch):
    run_, calls = _run(tmp_path, monkeypatch, 'ci_coarse', [QUIET])
    run_.begin_sample()
    row = json.loads(run_.sample('0000-plate', {'outcome': 'measured'}).read_text())
    assert calls == [] and 'host_load_wait' not in row


def test_the_launch_cap_is_shorter_than_the_job_cap(monkeypatch):
    monkeypatch.delenv('E2_SAMPLE_LOAD_WAIT_S', raising=False)
    assert host_load.sample_cap_seconds() == host_load.DEFAULT_SAMPLE_CAP_S == 300
    monkeypatch.setenv('E2_SAMPLE_LOAD_WAIT_S', '45')
    assert host_load.sample_cap_seconds() == 45
    monkeypatch.setenv('E2_SAMPLE_LOAD_WAIT_S', '-1')
    with pytest.raises(ValueError, match='E2_SAMPLE_LOAD_WAIT_S'):
        host_load.sample_cap_seconds()
