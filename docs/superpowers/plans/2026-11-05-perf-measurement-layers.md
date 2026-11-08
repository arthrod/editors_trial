# Performance measurement layers implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify every timing mark into `native`, `model`, `browser_visible`, or `wasm_boundary`, and reject marks that pretend to be a later layer.

**Architecture:** `perf/layers/classify.py` is a pure classifier. `perf/layers/wasm.py` lists the boundary operations a WASM editor must report separately from a native Criterion run. The runner's publication policy already blocks CI from publishing `browser_visible`. This plan defines which evidence is allowed to enter that layer.

**Tech Stack:** Python 3, `unittest`.

## Global Constraints

- `requestAnimationFrame` callback completion is layer evidence `raf_callback` and cannot satisfy `browser_visible`.
- Constructor return is `model` or `native` and cannot satisfy `browser_visible`.
- Model-ready cannot satisfy `browser_visible`.
- Event Timing is not evidence for wheel or pointer-move scrolling.
- A WASM boundary sample is not a native sample and not a frame sample.
- Playwright `trace: 'on'` is diagnostic.
- Coverage ids owned here: C03 C05 C10 C12 C18 C24 I08 I11.

---

### Task 1: Classify marks

**Files:**
- Create: `perf/layers/__init__.py`
- Create: `perf/layers/classify.py`
- Test: `perf/tests/test_layers.py`

**Interfaces:**
- Consumes: nothing
- Produces: `classify_mark(mark: str) -> str` returning `native`, `model`, `browser_visible`, or `wasm_boundary`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from perf.layers.classify import classify_mark


class Classify(unittest.TestCase):
    def test_known_marks(self):
        self.assertEqual(classify_mark("rust_instant"), "native")
        self.assertEqual(classify_mark("native_present"), "browser_visible")
        self.assertEqual(classify_mark("model_ready"), "model")
        self.assertEqual(classify_mark("constructor_return"), "model")
        self.assertEqual(classify_mark("first_contentful_paint"), "browser_visible")
        self.assertEqual(classify_mark("presented_frame"), "browser_visible")
        self.assertEqual(classify_mark("external_pixel"), "browser_visible")
        self.assertEqual(classify_mark("wasm_instantiate"), "wasm_boundary")

    def test_raf_is_not_browser_visible(self):
        with self.assertRaises(ValueError) as caught:
            classify_mark("raf_callback")
        self.assertIn("raf_callback", str(caught.exception))

    def test_unknown_mark_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            classify_mark("looks_fast")
        self.assertIn("unknown mark", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_layers.Classify -v`

Expected: ERROR containing `No module named 'perf.layers'`

- [ ] **Step 3: Write the minimal implementation**

`perf/layers/__init__.py` is empty.

`perf/layers/classify.py`:

```python
_MARKS = {
    "rust_instant": "native",
    "native_present": "browser_visible",
    "model_ready": "model",
    "constructor_return": "model",
    "handler_duration": "model",
    "first_contentful_paint": "browser_visible",
    "presented_frame": "browser_visible",
    "external_pixel": "browser_visible",
    "input_to_next_paint": "browser_visible",
    "wasm_instantiate": "wasm_boundary",
    "wasm_call": "wasm_boundary",
}


def classify_mark(mark):
    if mark == "raf_callback":
        raise ValueError("raf_callback is not a visible-paint mark")
    if mark not in _MARKS:
        raise ValueError("unknown mark %r" % (mark,))
    return _MARKS[mark]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_layers.Classify -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/layers/__init__.py perf/layers/classify.py perf/tests/test_layers.py
git commit -m "test: classify performance marks into measurement layers"
```

---

### Task 2: Visible evidence for typing, scroll, and reflow

**Files:**
- Modify: `perf/layers/classify.py`
- Modify: `perf/tests/test_layers.py`

**Interfaces:**
- Consumes: `classify_mark`
- Produces: `assert_visible_evidence(criterion_id: str, evidence: str) -> None`

- [ ] **Step 1: Write the failing test**

```python
from perf.layers.classify import assert_visible_evidence


class Evidence(unittest.TestCase):
    def test_first_usable_accepts_a_presented_frame(self):
        assert_visible_evidence("C03", "presented_frame")

    def test_first_usable_rejects_constructor_return(self):
        with self.assertRaises(ValueError) as caught:
            assert_visible_evidence("C03", "constructor_return")
        self.assertIn("constructor_return", str(caught.exception))

    def test_single_edit_rejects_a_raf_callback(self):
        with self.assertRaises(ValueError) as caught:
            assert_visible_evidence("C05", "raf_callback")
        self.assertIn("raf_callback", str(caught.exception))

    def test_event_timing_duration_is_not_edit_paint(self):
        with self.assertRaises(ValueError) as caught:
            assert_visible_evidence("C05", "event_timing_duration")
        self.assertIn("event_timing_duration", str(caught.exception))

    def test_unrelated_paint_does_not_complete_the_edit(self):
        with self.assertRaises(ValueError) as caught:
            assert_visible_evidence("C05", "unrelated_paint")
        self.assertIn("unrelated_paint", str(caught.exception))

    def test_raf_plus_later_paint_is_accepted(self):
        assert_visible_evidence("C05", "raf_plus_later_paint")

    def test_scroll_rejects_event_timing_wheel(self):
        with self.assertRaises(ValueError) as caught:
            assert_visible_evidence("C10", "event_timing_wheel")
        self.assertIn("event_timing_wheel", str(caught.exception))

    def test_scroll_accepts_frame_time(self):
        assert_visible_evidence("C10", "frame_time")

    def test_reflow_must_name_paint_separately_from_dirty_count(self):
        with self.assertRaises(ValueError) as caught:
            assert_visible_evidence("C12", "dirty_region_count")
        self.assertIn("dirty_region_count", str(caught.exception))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_layers.Evidence -v`

Expected: ERROR containing `cannot import name 'assert_visible_evidence'`

- [ ] **Step 3: Write the minimal implementation**

Add to `perf/layers/classify.py`:

```python
_VISIBLE_OK = {
    "C03": {"presented_frame", "external_pixel", "first_contentful_paint"},
    "C05": {"presented_frame", "external_pixel", "raf_plus_later_paint"},
    "C10": {"frame_time", "presented_frame", "external_pixel"},
    "C12": {"presented_frame", "external_pixel"},
}


def assert_visible_evidence(criterion_id, evidence):
    allowed = _VISIBLE_OK.get(criterion_id)
    if allowed is None:
        raise ValueError("no visible rule for %s" % (criterion_id,))
    if evidence not in allowed:
        raise ValueError("%s is not visible evidence for %s" % (evidence, criterion_id))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_layers.Evidence -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/layers/classify.py perf/tests/test_layers.py
git commit -m "feat: require real paint evidence for visible scenarios"
```

---

### Task 3: WASM boundary contract

**Files:**
- Create: `perf/layers/wasm.py`
- Modify: `perf/tests/test_layers.py`

**Interfaces:**
- Consumes: nothing
- Produces: `required_wasm_operations() -> tuple[str, ...]` and `assert_wasm_report(report: dict, capabilities: dict | None = None) -> None`. Each operation name is a capability flag. `True` requires a non-empty list of finite samples. `False` requires `None`. A report that only contains `editor_scenario_ms` is rejected. Omitting `capabilities` means every operation is enabled, which is the wasm-bindgen reference fixture, not a closed product lane.

- [ ] **Step 1: Write the failing test**

```python
from perf.layers.wasm import assert_wasm_report, required_wasm_operations


class Wasm(unittest.TestCase):
    def test_required_operations_cover_calls_and_copies(self):
        self.assertEqual(required_wasm_operations(), (
            "compile_and_instantiate",
            "empty_call",
            "scalar_call",
            "string_conversion",
            "typed_array_transfer",
            "batched_call",
            "memory_grow",
        ))

    def test_an_editor_scenario_does_not_replace_the_boundary(self):
        with self.assertRaises(ValueError) as caught:
            assert_wasm_report({"editor_scenario_ms": [10.0]})
        self.assertIn("compile_and_instantiate", str(caught.exception))

    def test_a_complete_report_passes(self):
        report = {name: [1.0] for name in required_wasm_operations()}
        assert_wasm_report(report)

    def test_a_string_is_not_a_sample_list(self):
        report = {name: [1.0] for name in required_wasm_operations()}
        report["empty_call"] = "1.0"
        with self.assertRaises(ValueError) as caught:
            assert_wasm_report(report)
        self.assertIn("empty_call", str(caught.exception))

    def test_nan_is_not_a_sample(self):
        report = {name: [1.0] for name in required_wasm_operations()}
        report["scalar_call"] = [float("nan")]
        with self.assertRaises(ValueError) as caught:
            assert_wasm_report(report)
        self.assertIn("scalar_call", str(caught.exception))

    def test_closed_lane_leaves_unavailable_operations_null(self):
        names = required_wasm_operations()
        capabilities = {name: False for name in names}
        capabilities["compile_and_instantiate"] = True
        report = {name: None for name in names}
        report["compile_and_instantiate"] = [2.0]
        report["runtime"] = "proprietary"
        assert_wasm_report(report, capabilities)

    def test_a_disabled_operation_cannot_carry_samples(self):
        names = required_wasm_operations()
        capabilities = {name: False for name in names}
        report = {name: None for name in names}
        report["empty_call"] = [1.0]
        with self.assertRaises(ValueError) as caught:
            assert_wasm_report(report, capabilities)
        self.assertIn("empty_call", str(caught.exception))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_layers.Wasm -v`

Expected: ERROR containing `No module named 'perf.layers.wasm'`

- [ ] **Step 3: Write the minimal implementation**

`perf/layers/wasm.py`:

```python
def required_wasm_operations():
    return (
        "compile_and_instantiate",
        "empty_call",
        "scalar_call",
        "string_conversion",
        "typed_array_transfer",
        "batched_call",
        "memory_grow",
    )


def assert_wasm_report(report, capabilities=None):
    names = required_wasm_operations()
    if capabilities is None:
        capabilities = {name: True for name in names}
    if "editor_scenario_ms" in report and not any(capabilities.values()):
        raise ValueError("editor_scenario_ms is not a boundary operation")
    enabled = False
    for name in names:
        if name not in capabilities:
            raise ValueError("capability %s" % (name,))
        samples = report.get(name)
        if not capabilities[name]:
            if samples is not None:
                raise ValueError("disabled wasm operation %s must be null" % (name,))
            continue
        enabled = True
        if not isinstance(samples, list) or not samples:
            raise ValueError("missing wasm operation %s" % (name,))
        for sample in samples:
            if isinstance(sample, bool) or not isinstance(sample, (int, float)):
                raise ValueError("wasm sample %s" % (name,))
            if sample != sample or sample in (float("inf"), float("-inf")) or sample < 0:
                raise ValueError("wasm sample %s" % (name,))
    if not enabled and "editor_scenario_ms" in report:
        raise ValueError("missing wasm operation compile_and_instantiate")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_layers.Wasm -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/layers/wasm.py perf/tests/test_layers.py
git commit -m "feat: require a WASM boundary report separate from the editor scenario"
```

---

### Task 4: Diagnostic traces stay off the timing run

**Files:**
- Modify: `perf/layers/classify.py`
- Modify: `perf/tests/test_layers.py`

**Interfaces:**
- Consumes: nothing else
- Produces: `assert_run_instruments(run_kind: str, instruments: list[str]) -> None`. `timing` allows `clock` and `memory_sample`. `diagnostic` is required before `chrome_trace`, `playwright_trace_on`, `perf_stat`, or `gc_events`.

- [ ] **Step 1: Write the failing test**

```python
from perf.layers.classify import assert_run_instruments


class Instruments(unittest.TestCase):
    def test_timing_run_allows_a_clock_and_a_memory_sample(self):
        assert_run_instruments("timing", ["clock", "memory_sample"])

    def test_timing_run_rejects_a_chrome_trace(self):
        with self.assertRaises(ValueError) as caught:
            assert_run_instruments("timing", ["clock", "chrome_trace"])
        self.assertIn("chrome_trace", str(caught.exception))

    def test_timing_run_rejects_playwright_trace_on(self):
        with self.assertRaises(ValueError) as caught:
            assert_run_instruments("timing", ["playwright_trace_on"])
        self.assertIn("playwright_trace_on", str(caught.exception))

    def test_diagnostic_run_may_record_gc_events(self):
        assert_run_instruments("diagnostic", ["gc_events", "chrome_trace"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_layers.Instruments -v`

Expected: ERROR containing `cannot import name 'assert_run_instruments'`

- [ ] **Step 3: Write the minimal implementation**

Add to `perf/layers/classify.py`:

```python
_DIAGNOSTIC = {"chrome_trace", "playwright_trace_on", "perf_stat", "gc_events"}
_TIMING = {"clock", "memory_sample"}


def assert_run_instruments(run_kind, instruments):
    if run_kind not in ("timing", "diagnostic"):
        raise ValueError("run_kind")
    for instrument in instruments:
        if run_kind == "timing" and instrument not in _TIMING:
            raise ValueError("%s is diagnostic-only" % (instrument,))
        if run_kind == "diagnostic" and instrument not in _TIMING | _DIAGNOSTIC:
            raise ValueError("unknown instrument %s" % (instrument,))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_layers -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/layers/classify.py perf/tests/test_layers.py
git commit -m "feat: keep allocation traces on diagnostic runs"
```

### Task 5: Event Timing censoring is not the paint proof

**Files:**
- Create: `perf/layers/event_timing.py`
- Modify: `perf/tests/test_layers.py`

**Interfaces:**
- Consumes: nothing
- Produces: `effective_duration_threshold(requested) -> int`, `rounded_duration_ms(raw) -> int`, `event_timing_status(raw_duration, requested_threshold, buffered_default=False) -> dict`, `aggregate_inp(entries) -> int | None`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from perf.layers.event_timing import (
    aggregate_inp,
    effective_duration_threshold,
    event_timing_status,
    rounded_duration_ms,
)


class EventTiming(unittest.TestCase):
    def test_threshold_cannot_drop_below_16(self):
        self.assertEqual(effective_duration_threshold(None), 104)
        self.assertEqual(effective_duration_threshold(0), 16)
        self.assertEqual(effective_duration_threshold(8), 16)
        self.assertEqual(effective_duration_threshold(16), 16)

    def test_duration_uses_an_8_millisecond_quantum(self):
        self.assertEqual(rounded_duration_ms(20), 24)
        self.assertEqual(rounded_duration_ms(12), 16)

    def test_buffered_history_stays_at_104(self):
        got = event_timing_status(40, 16, buffered_default=True)
        self.assertEqual(got["status"], "censored")
        self.assertIsNone(got["duration_ms"])

    def test_a_censored_edit_is_not_zero(self):
        got = event_timing_status(10, 16, buffered_default=False)
        self.assertEqual(got["status"], "censored")
        self.assertIsNone(got["duration_ms"])
        self.assertNotEqual(got["duration_ms"], 0)

    def test_inp_groups_one_interaction_id(self):
        entries = [
            {"interaction_id": 7, "duration_ms": 24, "name": "keydown"},
            {"interaction_id": 7, "duration_ms": 40, "name": "input"},
            {"interaction_id": 7, "duration_ms": 24, "name": "keyup"},
            {"interaction_id": 0, "duration_ms": 80, "name": "keydown"},
            {"interaction_id": 8, "duration_ms": 16, "name": "keydown"},
        ]
        self.assertEqual(aggregate_inp(entries), 40)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_layers.EventTiming -v`

Expected: ERROR containing `No module named 'perf.layers.event_timing'`

- [ ] **Step 3: Write the minimal implementation**

`perf/layers/event_timing.py`:

```python
def effective_duration_threshold(requested):
    if requested is None:
        return 104
    return max(16, int(requested))


def rounded_duration_ms(raw):
    return int((raw + 4) // 8 * 8)


def event_timing_status(raw_duration, requested_threshold, buffered_default=False):
    threshold = 104 if buffered_default else effective_duration_threshold(requested_threshold)
    duration = rounded_duration_ms(raw_duration)
    if duration < threshold:
        return {"status": "censored", "duration_ms": None, "rounded_ms": duration}
    return {"status": "observed", "duration_ms": duration, "rounded_ms": duration}


def aggregate_inp(entries):
    grouped = {}
    for entry in entries:
        interaction_id = entry["interaction_id"]
        if not interaction_id:
            continue
        grouped.setdefault(interaction_id, []).append(entry["duration_ms"])
    if not grouped:
        return None
    return max(max(samples) for samples in grouped.values())
```

`rounded_duration_ms` uses half-up for positive durations so 20 ms becomes 24 ms. That is this plan's 8 millisecond quantum, not a claim about every browser tie.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_layers.EventTiming -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/layers/event_timing.py perf/tests/test_layers.py
git commit -m "test: censor Event Timing entries instead of dropping them"
```

## Acceptance criteria

- `python3 -m unittest perf.tests.test_layers -v` passes.
- `classify_mark("raf_callback")` raises `ValueError`.
- `assert_visible_evidence("C10", "event_timing_wheel")` raises `ValueError`.
- A WASM report without `memory_grow` raises `ValueError`.
- `assert_run_instruments("timing", ["gc_events"])` raises `ValueError`.
- No browser and no editor is launched.

## Coverage ids

C03 C05 C10 C12 C18 C24 I08 I11
