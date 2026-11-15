"""Linux cgroup v2 accounting for browser samples; missing facts stay missing.

Explicit cgroup_root denotes the container's CPU accounting directory. By
default use Report E's membership/mount resolution and the sole visible quota.
Multiple limiting ancestors are unavailable rather than silently ignored.
/proc ticks and load describe the shared host, not just the container.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import sys


COUNTERS = ('nr_periods', 'nr_throttled', 'throttled_usec')


def read_cpu_accounting(*, cgroup_root=None, proc_root='/proc', platform=None, cpu_count=os.cpu_count):
    platform = sys.platform if platform is None else platform
    if platform != 'linux':
        return {'available': False, 'reason': f'cgroup v2 CPU accounting unavailable on {platform}'}
    try:
        if cgroup_root is None:
            from perf.runner.host import _cgroup_dirs, _v2_quota

            dirs = _cgroup_dirs('cpu')
            limited = [(q, d) for d in dirs if (q := _v2_quota(d)) is not None]
            if len(limited) > 1:
                return {
                    'available': False,
                    'reason': 'multiple cgroup v2 CPU quotas: hierarchical accounting unsupported',
                }
            cgroup_root = limited[0][1] if limited else dirs[0]
        root, proc = Path(cgroup_root), Path(proc_root)
        if not (root / 'cpu.max').exists() and (root / 'cpu.cfs_period_us').exists():
            return {
                'available': False,
                'reason': 'cgroup v1 CPU accounting unsupported; throttle refusal unavailable (requires cgroup v2)',
            }
        quota, period = (root / 'cpu.max').read_text().split()
        if int(period) <= 0 or (quota != 'max' and int(quota) <= 0):
            raise ValueError('invalid cpu.max quota/period')
        stat = dict(line.split() for line in (root / 'cpu.stat').read_text().splitlines())
        counters = {key: int(stat[key]) for key in COUNTERS}
        if any(value < 0 for value in counters.values()):
            raise ValueError('negative cpu.stat counter')
        fields = (proc / 'stat').read_text().splitlines()[0].split()
        if len(fields) < 9 or fields[0] != 'cpu':
            raise ValueError('missing /proc/stat aggregate CPU line')
        ticks = [int(value) for value in fields[1:9]]  # guest already included in user/nice
        if any(value < 0 for value in ticks):
            raise ValueError('negative /proc/stat ticks')
        load = [float(value) for value in (proc / 'loadavg').read_text().split()[:3]]
        if len(load) != 3 or any(not math.isfinite(v) or v < 0 for v in load):
            raise ValueError('invalid /proc/loadavg')
        count = cpu_count()
        if not count or count < 0:
            raise ValueError('visible CPU count unreadable')
        return dict(
            available=True,
            **counters,
            cpu_ticks={'total': sum(ticks), 'steal': ticks[7]},
            loadavg=load,
            cpu_max=f'{quota} {period}',
            cpu_count_visible=count,
            cgroup_path=str(root),
        )
    except (OSError, ValueError, KeyError, IndexError) as exc:
        return {'available': False, 'reason': f'cgroup v2 CPU accounting unavailable: {exc}'}


def accounting_delta(before, after):
    for reading in (before, after):
        if not reading['available']:
            return {'available': False, 'reason': reading['reason']}
    delta = {key: after[key] - before[key] for key in COUNTERS}
    delta.update({key + '_ticks': after['cpu_ticks'][key] - before['cpu_ticks'][key] for key in ('total', 'steal')})
    reason = None
    if any(value < 0 for value in delta.values()):
        reason = 'CPU accounting counters decreased'
    if any(before[key] != after[key] for key in ('cgroup_path', 'cpu_max', 'cpu_count_visible')):
        reason = 'CPU accounting cgroup or quota/CPU count changed'
    if reason:
        return dict(available=False, reason=reason, before=before, after=after)
    total = delta['total_ticks']
    # The sample's own wall-clock span, when the readings carry a monotonic
    # stamp (browser_run's probe adds one); the throttle tolerance is a
    # fraction of it (lax layer, owner decision 2026-11-11).
    span = None
    if _monotonic_ms(before) is not None and _monotonic_ms(after) is not None:
        span = _monotonic_ms(after) - _monotonic_ms(before)
        if span < 0:
            span = None
    return dict(
        available=True,
        before=before,
        after=after,
        delta=delta,
        span_ms=span,
        steal_percent=100 * delta['steal_ticks'] / total if total else None,
    )


def _monotonic_ms(reading):
    value = reading.get('monotonic_ms') if isinstance(reading, dict) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


#: Lax layer (owner decision 2026-11-11; issue #155 item 6): a sample whose
#: cgroup throttled away no more than max(1 ms, 1 % of the sample's own
#: wall-clock span) stays measurable -- the scheduler's occasional 100-200 us
#: slice theft is not the editor's result -- with ``throttled_usec`` recorded
#: on the kept row; anything above refuses exactly as before.
THROTTLE_TOLERANCE_MIN_USEC = 1000.0
THROTTLE_TOLERANCE_SPAN_FRACTION = 0.01


def throttle_tolerance_usec(span_ms=None):
    """max(1 ms, 1 % of the sample's span) in microseconds.

    An unknown span (``None``) keeps only the 1 ms floor: without a span the
    percentage part is unverified, so it is never assumed."""
    span = (
        float(span_ms)
        if isinstance(span_ms, (int, float)) and not isinstance(span_ms, bool)
        and math.isfinite(span_ms) and span_ms >= 0
        else None
    )
    span_usec = span * 1000.0 if span is not None else 0.0
    return max(THROTTLE_TOLERANCE_MIN_USEC, THROTTLE_TOLERANCE_SPAN_FRACTION * span_usec)


def throttled_within_tolerance(delta, span_ms=None):
    """True when a sample's throttling stays within the tolerance.

    ``delta`` is an accounting ``delta`` mapping; a missing or non-numeric
    ``throttled_usec`` carries no throttling to tolerate."""
    if not isinstance(delta, dict):
        return True
    usec = delta.get('throttled_usec')
    if isinstance(usec, bool) or not isinstance(usec, (int, float)) or not math.isfinite(usec):
        return True
    tolerance = throttle_tolerance_usec(span_ms)
    return float(usec) <= tolerance


def accounting_summary(before, after, samples):
    span = accounting_delta(before, after)
    rows = [row['cpu_accounting'] for row in samples]
    missing = [row['reason'] for row in rows if not row['available']]
    diagnostics = [row for row in samples if row.get('accounting_scope') == 'diagnostic']
    samples = [row for row in samples if row.get('accounting_scope') != 'diagnostic']
    readings = [before, after] + [r[side] for r in rows for side in ('before', 'after') if side in r]
    readings = [r for r in readings if r['available']]
    available = span['available'] and not missing
    result = dict(
        available=available,
        samples_total=len(samples),
        samples_refused=sum(row.get('failure_reason') == 'cpu_throttled' for row in samples),
        samples_throttled_kept=sum(
            row.get('failure_reason') != 'cpu_throttled'
            and isinstance(row.get('throttled_usec'), (int, float))
            and not isinstance(row.get('throttled_usec'), bool)
            and row.get('throttled_usec') > 0
            for row in samples
        ),
        samples_unavailable=sum(not row['cpu_accounting']['available'] for row in samples),
        diagnostics_total=len(diagnostics),
        diagnostics_refused=sum(row.get('failure_reason') == 'cpu_throttled' for row in diagnostics),
        diagnostics_unavailable=sum(not row['cpu_accounting']['available'] for row in diagnostics),
        steal_percent=span.get('steal_percent'),
        throttled_usec=span.get('delta', {}).get('throttled_usec'),
        loadavg_range=[
            [min(r['loadavg'][i] for r in readings), max(r['loadavg'][i] for r in readings)] for i in range(3)
        ]
        if readings
        else None,
        cpu_max=after.get('cpu_max', before.get('cpu_max')),
        cpu_count_visible=after.get('cpu_count_visible', before.get('cpu_count_visible')),
        before=before,
        after=after,
    )
    if not available:
        result['reason'] = '; '.join(dict.fromkeys(([span['reason']] if not span['available'] else []) + missing))
    return result
