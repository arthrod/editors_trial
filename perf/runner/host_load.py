"""A job waits for a quiet host, and is not started on one that stays busy (#228).

The campaign's host check runs once, before the first job. A Space is a
container on a host shared with other tenants: the load can rise hours
later. The bound is the quiet machine check's own (perf.runner.host): a
1-minute load average above a third of the logical CPUs is not quiet.

A job that finds the host busy waits, reading the load every POLL_S
seconds, for at most E2_HOST_LOAD_WAIT_S seconds (default 1800). If the
host is still busy the job is not started; run.py records the refusal and
the job is run again later.

The load can also rise while a job runs, so each launch waits the same
way before it starts (BrowserRun.begin_sample on a shared_guarded host),
for at most E2_SAMPLE_LOAD_WAIT_S seconds (default 300). A launch is never
refused for load: one that starts on a host still busy is measured and
marked, and every row already records the load at both of its ends.
"""
from __future__ import annotations

import math
import os
import time

from perf.runner.host import LOAD_FRACTION

POLL_S = 30
DEFAULT_CAP_S = 1800
SAMPLE_POLL_S = 10
DEFAULT_SAMPLE_CAP_S = 300


def load_limit(logical_cpus: int) -> float:
    return round(logical_cpus * LOAD_FRACTION, 2)


def _seconds(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        value = -1
    if value < 0:
        raise ValueError('%s must be a whole number of seconds, 0 or more: %r' % (name, raw))
    return value


def cap_seconds() -> int:
    """How long a job waits for a quiet host before it is not started."""
    return _seconds('E2_HOST_LOAD_WAIT_S', DEFAULT_CAP_S)


def sample_cap_seconds() -> int:
    """How long one launch waits; after it the launch is measured and marked as started on a busy host."""
    return _seconds('E2_SAMPLE_LOAD_WAIT_S', DEFAULT_SAMPLE_CAP_S)


def read_load1() -> float:
    value = os.getloadavg()[0]
    if not math.isfinite(value) or value < 0:
        raise OSError('invalid 1-minute load average: %r' % (value,))
    return value


def wait_for_quiet(*, limit: float, read=None, sleep=time.sleep, monotonic=time.monotonic,
                   poll_s: int = POLL_S, cap_s: int = DEFAULT_CAP_S) -> dict:
    """Read the 1-minute load until it is at or under `limit`, or `cap_s` seconds have been waited.

    A load that cannot be read is not quiet: the job must not start on a host nobody could look at.
    """
    read = read or read_load1
    started, first, readings = monotonic(), None, 0
    while True:
        waited = int(round(monotonic() - started))
        try:
            load = round(float(read()), 2)
        except (OSError, ValueError) as exc:
            return {'quiet': False, 'load1': None, 'load1_first': first, 'load1_max': limit,
                    'waited_s': waited, 'readings': readings, 'error': str(exc)}
        readings += 1
        first = load if first is None else first
        result = {'quiet': load <= limit, 'load1': load, 'load1_first': first, 'load1_max': limit,
                  'waited_s': waited, 'readings': readings}
        if result['quiet'] or waited >= cap_s:
            return result
        sleep(min(poll_s, cap_s - waited))


def _guard(cap_s: int, poll_s: int) -> dict:
    # The CPU count is the host's (os.cpu_count ignores the affinity run.py
    # pins), as in the quiet machine check; it is read without a subprocess.
    cpus = os.cpu_count()
    if not cpus:
        return {'quiet': False, 'load1': None, 'load1_first': None, 'load1_max': None, 'waited_s': 0,
                'readings': 0, 'error': 'logical CPU count unreadable'}
    return wait_for_quiet(limit=load_limit(cpus), cap_s=cap_s, poll_s=poll_s)


def guard() -> dict:
    """The verdict for the job about to start, on this host."""
    return _guard(cap_seconds(), POLL_S)


def sample_guard() -> dict:
    """The verdict for the launch about to start (BrowserRun.begin_sample, outermost bracket only).

    Two of the four busy jobs of #228 started on a quiet host and the load
    rose under them, so the job's own wait is not enough. A launch that
    finds the host still busy at the cap is measured all the same and its
    row says so (`host_load_wait.quiet` false): the report names the cell.
    """
    return _guard(sample_cap_seconds(), SAMPLE_POLL_S)


def refusal(verdict: dict) -> str:
    if verdict.get('load1') is None:
        return 'host_load: 1-minute load unreadable (%s)' % verdict.get('error', 'no reading')
    return 'host_load: 1-minute load %.2f above %.2f after waiting %d s' % (
        verdict['load1'], verdict['load1_max'], verdict['waited_s'])
