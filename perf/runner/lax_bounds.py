"""Relaxed measurement bounds (lax layer, owner decision 2026-11-11).

Single source of truth for Report E2 disclosure and harness checks.
"""

from __future__ import annotations

from perf.runner.browser_throttle import THROTTLE_TOLERANCE_MIN_USEC, THROTTLE_TOLERANCE_SPAN_FRACTION
from perf.runner.load_timeouts import (
    BIG_DOCUMENT_LOAD_TIMEOUT_MS,
    DEFAULT_LOAD_TIMEOUT_MS,
    load_timeout_ms,
)
from perf.runner.witness import DEFAULT_SKEW_BOUND_MS, LAG_BOUND_INTERVALS, LAG_BOUND_MIN_MS

# Kept in sync with ONSET_BOUND_FLOOR_MS in perf/runner/b2_settle.mjs.
ONSET_BOUND_FLOOR_MS = 100

# Document / typing content length check tolerance (issue #155).
CONTENT_LENGTH_REL_TOL = 0.02

_RELAXED_BOUND_LINES = (
    f"Clock skew: {DEFAULT_SKEW_BOUND_MS:g} ms.",
    f"Ready/navigation load timeouts: {DEFAULT_LOAD_TIMEOUT_MS // 1000} s by default, "
    f"{BIG_DOCUMENT_LOAD_TIMEOUT_MS // 1000} s on the largest document workload.",
    f"Sparse-witness settle onset floor: {ONSET_BOUND_FLOOR_MS} ms.",
    "CPU throttle tolerance: max(1 ms, 1% of the sample span).",
    f"Witness anchor lag: max({LAG_BOUND_INTERVALS} frame intervals, {LAG_BOUND_MIN_MS:g} ms).",
    f"Typing/document content length tolerance: {CONTENT_LENGTH_REL_TOL * 100:g}%.",
)


def relaxed_bounds_paragraph() -> str:
    """Prose block for Report E2 template substitution."""
    return "Relaxed bounds: " + " ".join(_RELAXED_BOUND_LINES)


def throttle_tolerance_description() -> str:
    return "max(%d ms, %g%% of the span)" % (
        int(THROTTLE_TOLERANCE_MIN_USEC / 1000),
        THROTTLE_TOLERANCE_SPAN_FRACTION * 100,
    )


__all__ = [
    "CONTENT_LENGTH_REL_TOL",
    "relaxed_bounds_paragraph",
    "load_timeout_ms",
    "DEFAULT_LOAD_TIMEOUT_MS",
    "BIG_DOCUMENT_LOAD_TIMEOUT_MS",
]
