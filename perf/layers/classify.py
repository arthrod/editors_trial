"""Map timing marks and evidence strings to measurement layers (I08)."""

_MARKS = {
    "rust_instant": "native",
    "native_present": "browser_visible",
    "model_ready": "model",
    "constructor_return": "model",
    "handler_duration": "model",
    "serialization_complete": "model",
    "process_spawn": "native",
    "process_tree_sample": "native",
    "cpu_seconds": "native",
    "gc_or_allocator_pause": "native",
    "retained_after_close": "native",
    "wasm_call": "wasm_boundary",
    "wasm_instantiate": "wasm_boundary",
    "first_contentful_paint": "browser_visible",
    "presented_frame": "browser_visible",
    "external_pixel": "browser_visible",
    "input_to_next_paint": "browser_visible",
    "frame_time": "browser_visible",
    "first_usable": "browser_visible",
}

_VISIBLE_OK = {
    "C03": {"presented_frame", "external_pixel", "first_contentful_paint"},
    "C05": {"presented_frame", "external_pixel", "raf_plus_later_paint", "cdp_screencast_changed_frame"},
    "C10": {"frame_time", "presented_frame", "external_pixel"},
    "C12": {"presented_frame", "external_pixel"},
}


def classify_mark(mark: str) -> str:
    if mark == "raf_callback":
        raise ValueError("raf_callback is not a visible-paint mark")
    if mark not in _MARKS:
        raise ValueError("unknown mark %r" % (mark,))
    return _MARKS[mark]


def assert_visible_evidence(criterion_id: str, evidence: str) -> None:
    allowed = _VISIBLE_OK.get(criterion_id)
    if allowed is None:
        raise ValueError("no visible rule for %s" % (criterion_id,))
    if evidence not in allowed:
        raise ValueError("%s is not visible evidence for %s" % (evidence, criterion_id))


_DIAGNOSTIC = {"chrome_trace", "playwright_trace_on", "perf_stat", "gc_events"}
_TIMING = {"clock", "memory_sample"}


def assert_run_instruments(run_kind: str, instruments: list[str]) -> None:
    if run_kind not in ("timing", "diagnostic"):
        raise ValueError("run_kind")
    for instrument in instruments:
        if run_kind == "timing" and instrument not in _TIMING:
            raise ValueError("%s is diagnostic-only" % (instrument,))
        if run_kind == "diagnostic" and instrument not in _TIMING | _DIAGNOSTIC:
            raise ValueError("unknown instrument %s" % (instrument,))
