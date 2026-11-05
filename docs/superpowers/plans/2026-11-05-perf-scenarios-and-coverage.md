# Performance scenarios and coverage implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Check in one scenario record for each of the 24 criteria and a test that fails when a criterion or an interpretation condition is missing.

**Architecture:** `perf/scenarios/catalog.py` is the scenario list. `perf/scenarios/coverage.py` reads that list and the normative JSON matrix and reports gaps. It does not run editors. Adapters from the previous plan decide applicability per lane. This catalog says what a scenario is, not how a particular editor implements it.

**Tech Stack:** Python 3, `json`, `pathlib`, `unittest`.

## Global Constraints

- Scenario ids are `C01` through `C24` with no gaps.
- A scenario that publishes visible latency names evidence other than `raf_callback`, `constructor_return`, and `model_ready`.
- `C18` is `diagnostic`. `C20` is dedicated-host and at least 3600 seconds.
- `C10` does not use Event Timing wheel events as its clock.
- Failures stay in the scenario contract as outcome names, not as dropped rows.
- Coverage ids owned here: C01 C02 C03 C04 C05 C06 C07 C08 C09 C10 C11 C12 C13 C14 C15 C16 C17 C18 C19 C20 C21 C22 C23 C24 I01 I02 I03 I04 I12.

---

### Task 1: Load the 24 scenario records

**Files:**
- Create: `perf/scenarios/__init__.py`
- Create: `perf/scenarios/catalog.py`
- Test: `perf/tests/test_scenarios.py`

**Interfaces:**
- Consumes: nothing
- Produces: `scenarios() -> list[dict]`. Each dict has `id`, `title`, `layer`, `boundary`, `repetition_unit`, `cache_states`, `evidence`, `run_kind`, `correctness`.

- [ ] **Step 1: Write the failing test**

```python
import unittest

from perf.scenarios.catalog import scenarios


class Catalog(unittest.TestCase):
    def test_ids_are_exactly_the_twenty_four_criteria(self):
        ids = [row["id"] for row in scenarios()]
        self.assertEqual(ids, ["C%02d" % n for n in range(1, 25)])

    def test_startup_keeps_three_cache_states(self):
        startup = scenarios()[0]
        self.assertEqual(startup["id"], "C01")
        self.assertEqual(startup["cache_states"], [
            "process_cold_fs_warm",
            "os_cache_cold",
            "warm_steady",
        ])
        self.assertEqual(startup["repetition_unit"], "fresh_process")

    def test_visible_scenarios_do_not_use_a_raf_callback(self):
        for row in scenarios():
            if row["layer"] == "browser_visible":
                forbidden = {"raf_callback", "constructor_return", "model_ready"}
                for field in ("boundary", "evidence"):
                    self.assertNotIn(row[field], forbidden)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_scenarios.Catalog -v`

Expected: ERROR containing `No module named 'perf.scenarios'`

- [ ] **Step 3: Write the minimal implementation**

`perf/scenarios/__init__.py` is empty.

`perf/scenarios/catalog.py` must define `scenarios()` returning the 24 dictionaries below, in order. Copy them exactly.

```python
def scenarios():
    return [
        {"id": "C01", "title": "cold/warm startup", "layer": "browser_visible", "boundary": "first_usable", "repetition_unit": "fresh_process", "cache_states": ["process_cold_fs_warm", "os_cache_cold", "warm_steady"], "evidence": "presented_frame", "run_kind": "timing", "correctness": []},
        {"id": "C02", "title": "document loading/model construction", "layer": "model", "boundary": "model_ready", "repetition_unit": "fresh_process", "cache_states": ["process_cold_fs_warm", "warm_steady"], "evidence": "model_ready", "run_kind": "timing", "correctness": ["I01"]},
        {"id": "C03", "title": "first visible content/first usable state", "layer": "browser_visible", "boundary": "first_contentful_paint", "repetition_unit": "fresh_process", "cache_states": ["process_cold_fs_warm"], "evidence": "presented_frame", "run_kind": "timing", "correctness": []},
        {"id": "C04", "title": "deferred work", "layer": "model", "boundary": "deferred_quiescence", "repetition_unit": "fresh_process", "cache_states": ["process_cold_fs_warm"], "evidence": "quiescence_or_timeout", "run_kind": "timing", "correctness": []},
        {"id": "C05", "title": "single-edit responsiveness", "layer": "browser_visible", "boundary": "input_to_next_paint", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "input_to_next_paint", "run_kind": "timing", "correctness": ["I01", "I02", "I03", "I04"]},
        {"id": "C06", "title": "sustained typing/bursts", "layer": "browser_visible", "boundary": "input_to_next_paint", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "presented_frame", "run_kind": "timing", "correctness": ["I01", "I02", "I03", "I04"]},
        {"id": "C07", "title": "cursor/selection/hit testing", "layer": "browser_visible", "boundary": "input_to_next_paint", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "presented_frame", "run_kind": "timing", "correctness": ["I01", "I02", "I03"]},
        {"id": "C08", "title": "clipboard/bulk editing", "layer": "browser_visible", "boundary": "input_to_next_paint", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "presented_frame", "run_kind": "timing", "correctness": ["I01"]},
        {"id": "C09", "title": "undo/redo", "layer": "browser_visible", "boundary": "input_to_next_paint", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "presented_frame", "run_kind": "timing", "correctness": ["I01"]},
        {"id": "C10", "title": "scrolling/viewport", "layer": "browser_visible", "boundary": "frame_time", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "frame_time", "run_kind": "timing", "correctness": []},
        {"id": "C11", "title": "initial layout/pagination", "layer": "browser_visible", "boundary": "first_contentful_paint", "repetition_unit": "fresh_process", "cache_states": ["process_cold_fs_warm"], "evidence": "presented_frame", "run_kind": "timing", "correctness": []},
        {"id": "C12", "title": "incremental reflow", "layer": "browser_visible", "boundary": "presented_frame", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "presented_frame", "run_kind": "timing", "correctness": []},
        {"id": "C13", "title": "global invalidation", "layer": "model", "boundary": "model_ready", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "model_ready", "run_kind": "timing", "correctness": ["I01"]},
        {"id": "C14", "title": "large-document scaling", "layer": "browser_visible", "boundary": "first_usable", "repetition_unit": "fresh_process", "cache_states": ["process_cold_fs_warm"], "evidence": "presented_frame", "run_kind": "timing", "correctness": ["I01", "I02", "I03"]},
        {"id": "C15", "title": "search/replace/indexing", "layer": "model", "boundary": "model_ready", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "model_ready", "run_kind": "timing", "correctness": []},
        {"id": "C16", "title": "serialization/save/export", "layer": "model", "boundary": "serialization_complete", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "durable_bytes", "run_kind": "timing", "correctness": []},
        {"id": "C17", "title": "memory footprint", "layer": "native", "boundary": "process_tree_sample", "repetition_unit": "fresh_process", "cache_states": ["process_cold_fs_warm", "warm_steady"], "evidence": "smaps_and_cgroup", "run_kind": "timing", "correctness": []},
        {"id": "C18", "title": "allocation/GC", "layer": "native", "boundary": "gc_or_allocator_pause", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "gc_events", "run_kind": "diagnostic", "correctness": []},
        {"id": "C19", "title": "disposal/reopen", "layer": "native", "boundary": "retained_after_close", "repetition_unit": "fresh_process", "cache_states": ["process_cold_fs_warm"], "evidence": "smaps_and_cgroup", "run_kind": "timing", "correctness": []},
        {"id": "C20", "title": "long-session stability", "layer": "browser_visible", "boundary": "input_to_next_paint", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "presented_frame", "run_kind": "timing", "correctness": ["I01"]},
        {"id": "C21", "title": "CPU/background interference", "layer": "native", "boundary": "cpu_seconds", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "process_tree_cpu", "run_kind": "timing", "correctness": []},
        {"id": "C22", "title": "feature/extension overhead", "layer": "browser_visible", "boundary": "input_to_next_paint", "repetition_unit": "fresh_process", "cache_states": ["process_cold_fs_warm", "warm_steady"], "evidence": "presented_frame", "run_kind": "timing", "correctness": []},
        {"id": "C23", "title": "collaboration", "layer": "browser_visible", "boundary": "input_to_next_paint", "repetition_unit": "fresh_process", "cache_states": ["warm_steady"], "evidence": "presented_frame", "run_kind": "timing", "correctness": ["I04"]},
        {"id": "C24", "title": "Rust/TS/WASM overhead", "layer": "wasm_boundary", "boundary": "wasm_call", "repetition_unit": "in_process_iteration", "cache_states": ["warm_steady"], "evidence": "wasm_call", "run_kind": "timing", "correctness": []},
    ]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_scenarios.Catalog -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/scenarios/__init__.py perf/scenarios/catalog.py perf/tests/test_scenarios.py
git commit -m "feat: add one scenario record for each performance criterion"
```

---

### Task 2: Lock the clocks that are easy to fake

**Files:**
- Modify: `perf/tests/test_scenarios.py`

**Interfaces:**
- Consumes: `scenarios`
- Produces: no new function. The test is the contract.

- [ ] **Step 1: Write the failing test**

Add this class before implementing the extra fields. The catalog from Task 1 already has the fields, so write the test and run it. If Task 1 was copied exactly, this test passes immediately. That is not a red step. To keep a red step, add `host_class` in this task and assert it. Task 1's records do not include `host_class`, so the new test fails with `KeyError`.

```python
class Clocks(unittest.TestCase):
    def test_scroll_evidence_is_frame_time(self):
        scroll = next(row for row in scenarios() if row["id"] == "C10")
        self.assertEqual(scroll["evidence"], "frame_time")
        self.assertNotEqual(scroll["evidence"], "event_timing_wheel")

    def test_allocation_scenario_is_diagnostic(self):
        allocation = next(row for row in scenarios() if row["id"] == "C18")
        self.assertEqual(allocation["run_kind"], "diagnostic")

    def test_long_session_is_dedicated_and_at_least_one_hour(self):
        soak = next(row for row in scenarios() if row["id"] == "C20")
        self.assertEqual(soak["host_class"], "dedicated")
        self.assertGreaterEqual(soak["min_seconds"], 3600)

    def test_model_load_does_not_claim_user_visible(self):
        load = next(row for row in scenarios() if row["id"] == "C02")
        self.assertEqual(load["layer"], "model")
        self.assertEqual(load["boundary"], "model_ready")
        self.assertNotIn("user_visible", load.get("claims", []))

    def test_wasm_scenario_names_the_boundary_operations(self):
        wasm = next(row for row in scenarios() if row["id"] == "C24")
        self.assertEqual(wasm["operations"], [
            "compile_and_instantiate",
            "empty_call",
            "scalar_call",
            "string_conversion",
            "typed_array_transfer",
            "batched_call",
            "memory_grow",
        ])

    def test_feature_overhead_names_every_profile(self):
        overhead = next(row for row in scenarios() if row["id"] == "C22")
        self.assertEqual(overhead["feature_profiles"], ["P0", "P1", "P2", "P3"])

    def test_startup_records_every_phase(self):
        startup = next(row for row in scenarios() if row["id"] == "C01")
        self.assertEqual(startup["marks"], [
            "process_spawn",
            "presented_frame",
            "input_ready",
            "deferred_quiescence",
        ])

    def test_first_content_requires_document_text_and_a_usable_edit(self):
        visible = next(row for row in scenarios() if row["id"] == "C03")
        self.assertEqual(visible["marks"], ["document_text_visible", "first_usable"])
        self.assertNotEqual(visible["evidence"], "first_contentful_paint")

    def test_search_records_each_phase(self):
        search = next(row for row in scenarios() if row["id"] == "C15")
        self.assertEqual(search["measurements"], [
            "first_match",
            "search_complete",
            "replace_all",
            "index_quiescence",
        ])

    def test_save_labels_rereadable_separately_from_durable(self):
        save = next(row for row in scenarios() if row["id"] == "C16")
        self.assertEqual(save["evidence"], "rereadable_bytes")
        self.assertEqual(save["durability"], "durable_only_when_data_and_directory_are_synced")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_scenarios.Clocks -v`

Expected: ERROR containing `KeyError: 'host_class'`

- [ ] **Step 3: Write the minimal implementation**

Add these keys to the existing dictionaries in `scenarios()`:

- On `C20`, add `"host_class": "dedicated"` and `"min_seconds": 3600`.
- On `C24`, add `"operations"` with the seven strings in the test, in that order.
- On `C22`, add `"feature_profiles": ["P0", "P1", "P2", "P3"]`.
- On `C01`, add `"marks": ["process_spawn", "presented_frame", "input_ready", "deferred_quiescence"]`.
- On `C03`, set `"evidence"` to `"document_text_pixel"` and add `"marks": ["document_text_visible", "first_usable"]`. Leave `"boundary"` as `"first_contentful_paint"` only if that value is still absent from the forbidden set; the usable endpoint is the second mark, not first-contentful-paint. Change `"boundary"` to `"first_usable"`.
- On `C15`, add `"measurements": ["first_match", "search_complete", "replace_all", "index_quiescence"]`.
- On `C16`, set `"evidence"` to `"rereadable_bytes"` and add `"durability": "durable_only_when_data_and_directory_are_synced"`.
- On every other scenario, add `"host_class": "dedicated"` as well, so a caller can read the key without a special case. `C18` stays `"run_kind": "diagnostic"` and also gets `"host_class": "dedicated"`.

Do not change `C10.evidence`, `C18.run_kind`, or `C02.boundary`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_scenarios -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/scenarios/catalog.py perf/tests/test_scenarios.py
git commit -m "test: lock scroll, soak, allocation, and WASM scenario clocks"
```

---

### Task 3: Compare the catalog to the normative matrix

**Files:**
- Create: `perf/scenarios/coverage.py`
- Modify: `perf/tests/test_scenarios.py`

**Interfaces:**
- Consumes: `scenarios` and `docs/superpowers/specs/2026-11-05-editor-performance-coverage.json`
- Produces: `matrix_gaps(matrix: dict, rows: list[dict]) -> list[str]`. An empty list means the catalog covers every criterion id and every interpretation-condition id that the matrix assigns to this plan's scenarios. A gap string names the missing id.

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

from perf.scenarios.catalog import scenarios
from perf.scenarios.coverage import matrix_gaps


class Matrix(unittest.TestCase):
    def test_catalog_covers_the_normative_criteria_and_conditions(self):
        matrix = json.loads(Path(
            "docs/superpowers/specs/2026-11-05-editor-performance-coverage.json"
        ).read_text())
        self.assertEqual(matrix_gaps(matrix, scenarios()), [])

    def test_a_missing_condition_is_reported(self):
        matrix = {"criteria": [{"id": "C01"}], "interpretation_conditions": [{"id": "I12"}]}
        rows = [{"id": "C01", "correctness": []}]
        self.assertEqual(matrix_gaps(matrix, rows), ["I12"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_scenarios.Matrix -v`

Expected: ERROR containing `No module named 'perf.scenarios.coverage'`

- [ ] **Step 3: Write the minimal implementation**

Create `perf/scenarios/coverage.py` with this module and no other function:

```python
_OWNED_CONDITIONS = ("I01", "I02", "I03", "I04", "I12")


def matrix_gaps(matrix, rows):
    present = {row["id"] for row in rows}
    mentioned = set()
    for row in rows:
        mentioned.update(row.get("correctness") or [])
    declared_conditions = {item["id"] for item in matrix["interpretation_conditions"]}
    gaps = [item["id"] for item in matrix["criteria"] if item["id"] not in present]
    for condition_id in _OWNED_CONDITIONS:
        if condition_id in declared_conditions and condition_id not in mentioned:
            gaps.append(condition_id)
    unknown = sorted(mentioned - declared_conditions)
    if unknown:
        raise ValueError("unknown correctness id %s" % (unknown,))
    return gaps
```

In `perf/scenarios/catalog.py`, change the `C04` correctness list from `[]` to `["I12"]`. A deferred-work timeout stays a failed outcome, which is condition I12. `C05` already lists `I01`, `I02`, `I03`, and `I04`.

An owned condition is required only when the matrix declares it. The synthetic matrix declares `I12` and not `I01` through `I04`, and the rows mention neither, so the result is `["I12"]`. A correctness value that is not a declared condition id, such as `I99`, raises `ValueError`. Add this test next to the synthetic one:

```python
def test_unknown_correctness_id_is_rejected(self):
    matrix = {
        "criteria": [{"id": "C01"}],
        "interpretation_conditions": [{"id": "I12"}],
    }
    rows = [{"id": "C01", "correctness": ["I12", "I99"]}]
    with self.assertRaises(ValueError) as caught:
        matrix_gaps(matrix, rows)
    self.assertIn("I99", str(caught.exception))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_scenarios.Matrix -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/scenarios/catalog.py perf/scenarios/coverage.py perf/tests/test_scenarios.py
git commit -m "test: fail when a scenario criterion or condition is missing"
```

---

### Task 4: Record failure outcomes on every scenario

**Files:**
- Modify: `perf/scenarios/catalog.py`
- Modify: `perf/tests/test_scenarios.py`

**Interfaces:**
- Consumes: `scenarios`
- Produces: each scenario includes `failure_outcomes` equal to `["failed", "not_run", "unverified", "unsupported", "not_applicable"]`.

- [ ] **Step 1: Write the failing test**

```python
class Failures(unittest.TestCase):
    def test_every_scenario_keeps_non_measurements(self):
        expected = ["failed", "not_run", "unverified", "unsupported", "not_applicable"]
        for row in scenarios():
            self.assertEqual(row["failure_outcomes"], expected, row["id"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_scenarios.Failures -v`

Expected: ERROR containing `KeyError: 'failure_outcomes'`

- [ ] **Step 3: Write the minimal implementation**

Add the key to every dictionary returned by `scenarios()`:

```python
"failure_outcomes": ["failed", "not_run", "unverified", "unsupported", "not_applicable"],
```

A practical way that still shows the data is to attach it in `scenarios()` after the list is built:

```python
_FAILURES = ["failed", "not_run", "unverified", "unsupported", "not_applicable"]


def scenarios():
    rows = [ ... the 24 dictionaries ... ]
    for row in rows:
        row["failure_outcomes"] = list(_FAILURES)
    return rows
```

Keep the 24 dictionaries from Task 1 plus the Task 2 and Task 3 keys. Do not drop `I12` from `C04`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_scenarios -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/scenarios/catalog.py perf/tests/test_scenarios.py
git commit -m "feat: keep failure outcomes on every performance scenario"
```

## Acceptance criteria

- `python3 -m unittest perf.tests.test_scenarios -v` passes.
- The catalog has 24 ids, `C01` through `C24`.
- `C10` evidence is `frame_time`.
- `C18` run kind is `diagnostic`.
- `C20` asks for a dedicated host and at least 3600 seconds.
- `matrix_gaps` on the normative JSON returns an empty list.
- No editor is launched.

## Coverage ids

C01 C02 C03 C04 C05 C06 C07 C08 C09 C10 C11 C12 C13 C14 C15 C16 C17 C18 C19 C20 C21 C22 C23 C24 I01 I02 I03 I04 I12
