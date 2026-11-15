"""C11's surface clock on a model host stays on the page clock (#193, review D).

Every docen C11 attempt was refused "presented frame precedes the document
surface": `loadResult` bound the surface to max(settled ink frame, readyMs),
and readyMs is `Date.now() - t0` from after `goto`, plus the host's
wait_after_ready — a duration on another clock, not a page-clock instant.
The settled ink frame is the first frame identical to the screen captured
after ready, so it is the surface; the ready fallback applies only when no
ink stamp exists, and then as `performance.now()` at ready.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CLOCK = REPO / "perf/runner/surface_clock.mjs"
PROBE = REPO / "perf/runner/document_probe.mjs"


def bind(**kw):
    script = f"""
const mod = await import({json.dumps(str(CLOCK))});
console.log(JSON.stringify({{at: mod.bindModelSurfaceClock({json.dumps(kw)})}}));
"""
    proc = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["at"]


def test_docen_ink_before_ready_keeps_the_ink_frame():
    # frame=2302.871 document=2667.0 (wordcraft Space, job 014, docen rep 4).
    assert bind(at=2302.871, inkAt=2302.871, firstElementMs=None, readyPageMs=2650.0) == 2302.871


def test_no_ink_falls_back_to_the_page_clock_ready_instant():
    assert bind(at=None, inkAt=None, firstElementMs=None, readyPageMs=2650.5) == 2650.5


def test_a_first_layout_box_still_bounds_a_dom_or_pixel_surface():
    # eigenpal and canvas stamp first_element_ms on the page clock: unchanged.
    assert bind(at=900.0, inkAt=900.0, firstElementMs=1200.0, readyPageMs=5000.0) == 1200.0
    assert bind(at=900.0, inkAt=900.0, firstElementMs=300.0, readyPageMs=5000.0) == 900.0


def test_nothing_known_stays_unknown():
    assert bind(at=None, inkAt=None, firstElementMs=None, readyPageMs=None) is None


def test_load_result_uses_the_page_clock_ready_and_never_the_ready_duration():
    source = PROBE.read_text()
    start = source.index("async function loadResult(")
    body = source[start:source.index("\nasync function ", start + 10)]
    assert "bindModelSurfaceClock(" in body
    assert "?? readyMs" not in body
    assert "readyPageMs" in body



def test_a_new_navigation_forgets_the_previous_ready_instant():
    # octo review: a reused page must not carry the previous page's ready instant.
    source = PROBE.read_text()
    start = source.index("const navT0 = Date.now();")
    assert "readyPageClock.delete(ctx.page)" in source[start - 400:start]
