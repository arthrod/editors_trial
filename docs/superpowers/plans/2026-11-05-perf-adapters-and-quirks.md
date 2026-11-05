# Performance adapters and editor quirks implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record, in code, which scenario features apply to each pinned editor lane, and return a refusal trial whose latency is null.

**Architecture:** `perf/adapters/capabilities.py` holds the lane table and the overrides that this design verified from repository documents and from pages read on 2026-11-05. Anything not overridden is `unverified`. `perf/adapters/protocol.py` turns a non-supported capability into a trial dictionary that `validate_trial` accepts. No adapter starts a real editor in this plan.

**Tech Stack:** Python 3, `unittest`.

## Global Constraints

- Do not modify `repos/`.
- Do not mark a feature `supported` unless the design doc states that the product has that surface.
- `unverified` is the default. It is not `unsupported` and it is not a measured zero.
- `not_applicable` is used for lanes that have no such surface, such as hit testing on `office-open`.
- A refusal trial has `latency_ms: None` and an empty `samples_ms`.
- Coverage ids owned here: C02 C07 C09 C11 C16 C22 C23 I04 I06 I07.

---

### Task 1: Refusal trials are not zeros

**Files:**
- Create: `perf/adapters/__init__.py`
- Create: `perf/adapters/protocol.py`
- Test: `perf/tests/test_adapters.py`

**Interfaces:**
- Consumes: `perf.schema.validate_trial`
- Produces: `refusal_trial(editor_id: str, lane: str, feature: str, outcome: str, criterion_id: str) -> dict`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from perf.adapters.protocol import refusal_trial
from perf.schema import validate_trial


class Refusal(unittest.TestCase):
    def test_not_applicable_has_null_latency(self):
        trial = refusal_trial("office-open", "library", "hit_testing", "not_applicable", "C07")
        validate_trial(trial)
        self.assertIsNone(trial["latency_ms"])
        self.assertEqual(trial["samples_ms"], [])
        self.assertEqual(trial["outcome"], "not_applicable")
        self.assertEqual(trial["criterion_id"], "C07")

    def test_measured_is_not_a_refusal_outcome(self):
        with self.assertRaises(ValueError) as caught:
            refusal_trial("plate", "browser_slate", "typing", "measured", "C05")
        self.assertIn("refusal", str(caught.exception))

    def test_zero_cannot_be_smuggled_in(self):
        trial = refusal_trial("wordcraft", "native_ui", "collaboration", "unverified", "C23")
        self.assertNotIn(0, trial["samples_ms"])
        self.assertIsNone(trial["latency_ms"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_adapters.Refusal -v`

Expected: ERROR containing `No module named 'perf.adapters'`

- [ ] **Step 3: Write the minimal implementation**

`perf/adapters/__init__.py` is empty.

`perf/adapters/protocol.py`:

```python
_REFUSALS = ("unsupported", "not_applicable", "unverified", "failed", "not_run")


def refusal_trial(editor_id, lane, feature, outcome, criterion_id):
    if outcome not in _REFUSALS:
        raise ValueError("refusal outcome required, got %r" % (outcome,))
    return {
        "editor_id": editor_id,
        "lane": lane,
        "feature": feature,
        "outcome": outcome,
        "boundary": "not_measured",
        "claims": [],
        "samples_ms": [],
        "latency_ms": None,
        "criterion_id": criterion_id,
    }
```

`validate_trial` allows any boundary string today. `not_measured` does not claim `visible_paint`, so the refusal passes `validate_trial`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_adapters.Refusal -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/adapters/__init__.py perf/adapters/protocol.py perf/tests/test_adapters.py
git commit -m "test: represent unsupported editor features as null latency"
```

---

### Task 2: Lane table and verified overrides

**Files:**
- Create: `perf/adapters/capabilities.py`
- Modify: `perf/tests/test_adapters.py`

**Interfaces:**
- Consumes: nothing
- Produces: `capability(editor_id: str, lane: str, feature: str) -> str` and `lanes() -> dict[str, tuple[str, ...]]`

- [ ] **Step 1: Write the failing test**

```python
from perf.adapters.capabilities import capability, lanes


class Capabilities(unittest.TestCase):
    def test_every_design_editor_has_a_lane(self):
        self.assertEqual(set(lanes()), {
            "plate", "docxodus", "apryse", "superdoc", "folio", "genoffice",
            "eigenpal", "office-open", "docen", "wordcraft", "fidus", "canvas",
            "docsplus", "libreoffice",
        })

    def test_office_open_has_no_hit_testing_surface(self):
        self.assertEqual(capability("office-open", "library", "hit_testing"), "not_applicable")
        self.assertEqual(capability("office-open", "library", "typing"), "not_applicable")
        self.assertEqual(capability("office-open", "library", "save"), "supported")

    def test_plate_flow_is_not_a_page_model(self):
        self.assertEqual(capability("plate", "browser_slate", "pagination"), "not_applicable")
        self.assertEqual(capability("plate", "browser_slate", "collaboration"), "supported")
        self.assertEqual(capability("plate", "headless_docx", "visible_paint"), "not_applicable")

    def test_docsplus_collaboration_is_the_app_lane(self):
        self.assertEqual(capability("docsplus", "app", "collaboration"), "supported")
        self.assertEqual(capability("docsplus", "conversion", "collaboration"), "not_applicable")

    def test_canvas_crdt_branch_is_not_the_pin(self):
        self.assertEqual(capability("canvas", "editor", "collaboration"), "unverified")
        self.assertEqual(capability("canvas", "editor", "hit_testing"), "supported")

    def test_wordcraft_native_claims_ime_and_not_collaboration(self):
        self.assertEqual(capability("wordcraft", "native_ui", "ime"), "supported")
        self.assertEqual(capability("wordcraft", "native_ui", "undo"), "supported")
        self.assertEqual(capability("wordcraft", "native_ui", "collaboration"), "unverified")
        self.assertEqual(capability("wordcraft", "docx_crate", "visible_paint"), "not_applicable")

    def test_docxodus_session_undo_is_a_documented_api(self):
        self.assertEqual(capability("docxodus", "session", "undo"), "supported")
        self.assertEqual(capability("plate", "browser_slate", "undo"), "supported")

    def test_docxodus_and_apryse_expose_wasm(self):
        self.assertEqual(capability("docxodus", "wasm_editor", "wasm"), "supported")
        self.assertEqual(capability("apryse", "webviewer", "wasm"), "supported")

    def test_superdoc_sdk_is_not_a_paint_clock(self):
        self.assertEqual(capability("superdoc", "sdk", "visible_paint"), "not_applicable")
        self.assertEqual(capability("superdoc", "browser", "pagination"), "supported")

    def test_headless_libreoffice_does_not_type(self):
        self.assertEqual(capability("libreoffice", "headless", "typing"), "not_applicable")
        self.assertEqual(capability("libreoffice", "gui", "typing"), "unverified")

    def test_unknown_lane_is_an_error(self):
        with self.assertRaises(ValueError) as caught:
            capability("plate", "imaginary", "typing")
        self.assertIn("lane", str(caught.exception))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_adapters.Capabilities -v`

Expected: ERROR containing `No module named 'perf.adapters.capabilities'`

- [ ] **Step 3: Write the minimal implementation**

`perf/adapters/capabilities.py`:

```python
LANES = {
    "plate": ("headless_docx", "browser_slate"),
    "docxodus": ("session", "wasm_editor"),
    "apryse": ("webviewer",),
    "superdoc": ("sdk", "browser"),
    "folio": ("model", "editor"),
    "genoffice": ("editor",),
    "eigenpal": ("store", "server", "browser"),
    "office-open": ("library",),
    "docen": ("editor",),
    "wordcraft": ("docx_crate", "native_ui", "wasm_ui"),
    "fidus": ("document", "app"),
    "canvas": ("editor",),
    "docsplus": ("conversion", "app"),
    "libreoffice": ("headless", "gui"),
}

# Overrides justified in docs/superpowers/specs/2026-11-05-editor-performance-benchmark-design.md.
# Every other (editor, lane, feature) triple is unverified.
OVERRIDES = {
    ("plate", "headless_docx", "pagination"): "not_applicable",
    ("plate", "headless_docx", "hit_testing"): "not_applicable",
    ("plate", "headless_docx", "collaboration"): "not_applicable",
    ("plate", "headless_docx", "wasm"): "not_applicable",
    ("plate", "headless_docx", "typing"): "not_applicable",
    ("plate", "headless_docx", "visible_paint"): "not_applicable",
    ("plate", "headless_docx", "ime"): "not_applicable",
    ("plate", "headless_docx", "save"): "supported",
    ("plate", "browser_slate", "pagination"): "not_applicable",
    ("plate", "browser_slate", "collaboration"): "supported",
    ("plate", "browser_slate", "wasm"): "not_applicable",
    ("plate", "browser_slate", "typing"): "supported",
    ("plate", "browser_slate", "visible_paint"): "supported",
    ("office-open", "library", "pagination"): "not_applicable",
    ("office-open", "library", "hit_testing"): "not_applicable",
    ("office-open", "library", "typing"): "not_applicable",
    ("office-open", "library", "visible_paint"): "not_applicable",
    ("office-open", "library", "ime"): "not_applicable",
    ("office-open", "library", "wasm"): "not_applicable",
    ("office-open", "library", "collaboration"): "unverified",
    ("office-open", "library", "save"): "supported",
    ("docsplus", "app", "collaboration"): "supported",
    ("docsplus", "app", "pagination"): "not_applicable",
    ("docsplus", "conversion", "collaboration"): "not_applicable",
    ("docsplus", "conversion", "visible_paint"): "not_applicable",
    ("docsplus", "conversion", "typing"): "not_applicable",
    ("canvas", "editor", "collaboration"): "unverified",
    ("canvas", "editor", "hit_testing"): "supported",
    ("canvas", "editor", "wasm"): "not_applicable",
    ("wordcraft", "native_ui", "ime"): "supported",
    ("wordcraft", "native_ui", "undo"): "supported",
    ("docxodus", "session", "undo"): "supported",
    ("plate", "browser_slate", "undo"): "supported",
    ("wordcraft", "native_ui", "collaboration"): "unverified",
    ("wordcraft", "native_ui", "hit_testing"): "supported",
    ("wordcraft", "native_ui", "pagination"): "supported",
    ("wordcraft", "native_ui", "wasm"): "not_applicable",
    ("wordcraft", "docx_crate", "visible_paint"): "not_applicable",
    ("wordcraft", "docx_crate", "typing"): "not_applicable",
    ("wordcraft", "docx_crate", "pagination"): "not_applicable",
    ("wordcraft", "wasm_ui", "wasm"): "supported",
    ("docxodus", "wasm_editor", "wasm"): "supported",
    ("docxodus", "session", "visible_paint"): "not_applicable",
    ("docxodus", "session", "save"): "supported",
    ("apryse", "webviewer", "wasm"): "supported",
    ("apryse", "webviewer", "save"): "supported",
    ("superdoc", "sdk", "visible_paint"): "not_applicable",
    ("superdoc", "sdk", "save"): "supported",
    ("superdoc", "browser", "pagination"): "supported",
    ("folio", "model", "visible_paint"): "not_applicable",
    ("folio", "model", "save"): "supported",
    ("genoffice", "editor", "pagination"): "supported",
    ("eigenpal", "store", "visible_paint"): "not_applicable",
    ("eigenpal", "store", "save"): "supported",
    ("eigenpal", "server", "visible_paint"): "not_applicable",
    ("docen", "editor", "pagination"): "supported",
    ("fidus", "document", "collaboration"): "not_applicable",
    ("fidus", "document", "pagination"): "not_applicable",
    ("fidus", "document", "visible_paint"): "not_applicable",
    ("fidus", "app", "collaboration"): "unverified",
    ("fidus", "app", "pagination"): "not_applicable",
    ("libreoffice", "headless", "typing"): "not_applicable",
    ("libreoffice", "headless", "visible_paint"): "not_applicable",
    ("libreoffice", "headless", "save"): "supported",
    ("libreoffice", "gui", "typing"): "unverified",
}


def lanes():
    return dict(LANES)


def capability(editor_id, lane, feature):
    known = LANES.get(editor_id)
    if known is None or lane not in known:
        raise ValueError("unknown lane %s/%s" % (editor_id, lane))
    return OVERRIDES.get((editor_id, lane, feature), "unverified")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_adapters.Capabilities -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/adapters/capabilities.py perf/tests/test_adapters.py
git commit -m "feat: record editor-lane capability overrides"
```

---

### Task 3: Ask the registry before inventing a zero

**Files:**
- Modify: `perf/adapters/protocol.py`
- Modify: `perf/tests/test_adapters.py`

**Interfaces:**
- Consumes: `capability`, `refusal_trial`
- Produces: `trial_or_refusal(editor_id: str, lane: str, feature: str, criterion_id: str) -> dict`. When `capability` is `supported`, the returned trial has `outcome` `not_run`, `failure_reason` `adapter-not-implemented`, and null latency. This plan does not invent a timing. When the capability is anything else, the outcome is that capability string.

- [ ] **Step 1: Write the failing test**

```python
from perf.adapters.protocol import trial_or_refusal


class Dispatch(unittest.TestCase):
    def test_missing_adapter_is_not_run_rather_than_zero(self):
        trial = trial_or_refusal("plate", "browser_slate", "typing", "C05")
        self.assertEqual(trial["outcome"], "not_run")
        self.assertEqual(trial["failure_reason"], "adapter-not-implemented")
        self.assertIsNone(trial["latency_ms"])

    def test_not_applicable_feature_uses_the_registry(self):
        trial = trial_or_refusal("office-open", "library", "hit_testing", "C07")
        self.assertEqual(trial["outcome"], "not_applicable")
        self.assertIsNone(trial["latency_ms"])

    def test_unverified_collaboration_stays_unverified(self):
        trial = trial_or_refusal("wordcraft", "native_ui", "collaboration", "C23")
        self.assertEqual(trial["outcome"], "unverified")
        self.assertIsNone(trial["latency_ms"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_adapters.Dispatch -v`

Expected: ERROR containing `cannot import name 'trial_or_refusal'`

- [ ] **Step 3: Write the minimal implementation**

Add to `perf/adapters/protocol.py`:

```python
from perf.adapters.capabilities import capability


def trial_or_refusal(editor_id, lane, feature, criterion_id):
    state = capability(editor_id, lane, feature)
    if state == "supported":
        trial = refusal_trial(editor_id, lane, feature, "not_run", criterion_id)
        trial["failure_reason"] = "adapter-not-implemented"
        return trial
    return refusal_trial(editor_id, lane, feature, state, criterion_id)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_adapters -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/adapters/protocol.py perf/tests/test_adapters.py
git commit -m "feat: refuse editor scenarios from the capability table"
```

---

### Task 4: Feature-profile note on the refusal

**Files:**
- Modify: `perf/adapters/protocol.py`
- Modify: `perf/tests/test_adapters.py`

**Interfaces:**
- Consumes: `trial_or_refusal`
- Produces: the same function gains a keyword argument `feature_profile: str = "P0"`. The trial includes that string. `P3` does not change a `not_applicable` outcome into `supported`.

- [ ] **Step 1: Write the failing test**

```python
class ProfileNote(unittest.TestCase):
    def test_profile_is_stored_and_does_not_invent_a_surface(self):
        trial = trial_or_refusal(
            "office-open", "library", "typing", "C06", feature_profile="P3"
        )
        self.assertEqual(trial["feature_profile"], "P3")
        self.assertEqual(trial["outcome"], "not_applicable")

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            trial_or_refusal("plate", "browser_slate", "typing", "C05", feature_profile="fast")
        self.assertIn("feature_profile", str(caught.exception))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_adapters.ProfileNote -v`

Expected: ERROR containing `unexpected keyword argument 'feature_profile'`

- [ ] **Step 3: Write the minimal implementation**

Change `trial_or_refusal` to:

```python
def trial_or_refusal(editor_id, lane, feature, criterion_id, feature_profile="P0"):
    if feature_profile not in ("P0", "P1", "P2", "P3"):
        raise ValueError("feature_profile")
    state = capability(editor_id, lane, feature)
    if state == "supported":
        trial = refusal_trial(editor_id, lane, feature, "not_run", criterion_id)
        trial["failure_reason"] = "adapter-not-implemented"
    else:
        trial = refusal_trial(editor_id, lane, feature, state, criterion_id)
    trial["feature_profile"] = feature_profile
    return trial
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_adapters -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/adapters/protocol.py perf/tests/test_adapters.py
git commit -m "feat: keep feature profile on refusal trials"
```

## Acceptance criteria

- `python3 -m unittest perf.tests.test_adapters -v` passes.
- `office-open` / `library` / `hit_testing` is `not_applicable` and the trial latency is null.
- `wordcraft` / `native_ui` / `collaboration` is `unverified`.
- `plate` / `browser_slate` / `typing` is `not_run` with reason `adapter-not-implemented` because no live adapter exists yet.
- No editor process is started.

## Coverage ids

C02 C07 C09 C11 C16 C22 C23 I04 I06 I07
