# Performance schema and outcomes implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Python trial schema that stores one performance sample with an explicit outcome, an explicit timing boundary, and a null latency whenever the editor was not measured.

**Architecture:** `perf/schema.py` is the only writer of the trial dictionary. Callers in later plans pass plain dictionaries into `validate_trial` and `dump_trial`. The module uses the standard library so `python3 -m unittest` runs without a virtual environment.

**Tech Stack:** Python 3, `json`, `unittest`.

## Global Constraints

- Do not modify anything under `repos/`.
- Do not write a latency of `0` for `unsupported`, `not_applicable`, `unverified`, `failed`, or `not_run`.
- A `raf_callback` boundary must not claim `visible_paint`.
- A `constructor_return` boundary must not claim `usable`.
- A `model_ready` boundary must not claim `user_visible`.
- Raw trial JSON keeps every sample. This plan does not summarize.
- This plan does not launch an editor and does not read `fixture/complex.docx`.
- Coverage ids owned here: C01 C02 C03 I07 I08 I12.

---

### Task 1: Reject clocks that over-claim

**Files:**
- Create: `perf/__init__.py`
- Create: `perf/schema.py`
- Create: `perf/tests/__init__.py`
- Test: `perf/tests/test_schema.py`

**Interfaces:**
- Consumes: nothing
- Produces: `validate_trial(trial: dict) -> None` raises `ValueError` whose message contains `raf_callback cannot claim visible paint`, `constructor_return cannot claim usable`, or `model_ready cannot claim user-visible latency`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from perf.schema import validate_trial


def _trial(boundary, claim):
    return {
        "outcome": "measured",
        "boundary": boundary,
        "claims": [claim],
        "samples_ms": [1.0],
        "latency_ms": None,
    }


class BoundaryClaims(unittest.TestCase):
    def test_raf_callback_cannot_claim_visible_paint(self):
        with self.assertRaises(ValueError) as caught:
            validate_trial(_trial("raf_callback", "visible_paint"))
        self.assertIn("raf_callback cannot claim visible paint", str(caught.exception))

    def test_constructor_return_cannot_claim_usable(self):
        with self.assertRaises(ValueError) as caught:
            validate_trial(_trial("constructor_return", "usable"))
        self.assertIn("constructor_return cannot claim usable", str(caught.exception))

    def test_model_ready_cannot_claim_user_visible(self):
        with self.assertRaises(ValueError) as caught:
            validate_trial(_trial("model_ready", "user_visible"))
        self.assertIn("model_ready cannot claim user-visible latency", str(caught.exception))

    def test_paint_boundary_may_claim_visible_paint(self):
        validate_trial(_trial("first_contentful_paint", "visible_paint"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_schema.BoundaryClaims -v`

Expected: FAIL or ERROR containing `ModuleNotFoundError: No module named 'perf'`

- [ ] **Step 3: Write the minimal implementation**

`perf/__init__.py` and `perf/tests/__init__.py` are empty files.

`perf/schema.py`:

```python
"""Trial records for the performance harness.

A trial either measured a named boundary or it did not. Non-measurements do
not carry a latency. A requestAnimationFrame callback, a constructor return,
and a model-ready mark are real events, and none of them is a user-visible
result by itself.
"""

_FORBIDDEN = (
    ("raf_callback", "visible_paint", "raf_callback cannot claim visible paint"),
    ("constructor_return", "usable", "constructor_return cannot claim usable"),
    ("model_ready", "user_visible", "model_ready cannot claim user-visible latency"),
)


def validate_trial(trial):
    claims = set(trial.get("claims") or [])
    boundary = trial["boundary"]
    for blocked_boundary, blocked_claim, message in _FORBIDDEN:
        if boundary == blocked_boundary and blocked_claim in claims:
            raise ValueError(message)
    if trial["outcome"] == "measured" and not trial.get("samples_ms"):
        raise ValueError("measured trial needs samples")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_schema.BoundaryClaims -v`

Expected: `Ran 4 tests` and `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/__init__.py perf/schema.py perf/tests/__init__.py perf/tests/test_schema.py
git commit -m "test: reject performance clocks that over-claim visibility"
```

---

### Task 2: Keep unsupported results null

**Files:**
- Modify: `perf/schema.py`
- Modify: `perf/tests/test_schema.py`

**Interfaces:**
- Consumes: `validate_trial(trial: dict) -> None`
- Produces: the same function, now also requiring `samples_ms` to be a non-empty list of finite numbers `>= 0` when `outcome` is `measured`, and requiring `latency_ms` to be `None` and `samples_ms` to be missing or empty otherwise. Allowed outcomes: `measured`, `unsupported`, `not_applicable`, `unverified`, `failed`, `not_run`.

- [ ] **Step 1: Write the failing test**

Append this class to `perf/tests/test_schema.py`:

```python
class Outcomes(unittest.TestCase):
    def test_unsupported_rejects_zero_latency(self):
        trial = {
            "outcome": "unsupported",
            "boundary": "input_to_next_paint",
            "claims": [],
            "samples_ms": [],
            "latency_ms": 0,
        }
        with self.assertRaises(ValueError) as caught:
            validate_trial(trial)
        self.assertIn("non-measured latency must be null", str(caught.exception))

    def test_failed_rejects_samples(self):
        trial = {
            "outcome": "failed",
            "boundary": "first_usable",
            "claims": [],
            "samples_ms": [12.0],
            "latency_ms": None,
            "failure_reason": "timeout",
        }
        with self.assertRaises(ValueError) as caught:
            validate_trial(trial)
        self.assertIn("non-measured samples must be empty", str(caught.exception))

    def test_measured_zero_is_a_real_sample(self):
        validate_trial({
            "outcome": "measured",
            "boundary": "handler_duration",
            "claims": [],
            "samples_ms": [0.0],
            "latency_ms": None,
        })

    def test_unknown_outcome_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            validate_trial({
                "outcome": "skipped",
                "boundary": "handler_duration",
                "claims": [],
                "samples_ms": [],
                "latency_ms": None,
            })
        self.assertIn("unknown outcome", str(caught.exception))

    def test_not_run_is_distinct_from_failed(self):
        validate_trial({
            "outcome": "not_run",
            "boundary": "process_spawn",
            "claims": [],
            "samples_ms": [],
            "latency_ms": None,
            "failure_reason": "harness-seatbelt",
        })

    def test_scalar_samples_are_not_an_empty_list(self):
        with self.assertRaises(ValueError) as caught:
            validate_trial({
                "outcome": "unsupported",
                "boundary": "input_to_next_paint",
                "claims": [],
                "samples_ms": 0,
                "latency_ms": None,
            })
        self.assertIn("samples_ms", str(caught.exception))

    def test_failed_and_not_run_require_a_reason(self):
        for outcome in ("failed", "not_run"):
            with self.assertRaises(ValueError) as caught:
                validate_trial({
                    "outcome": outcome,
                    "boundary": "first_usable",
                    "claims": [],
                    "samples_ms": [],
                    "latency_ms": None,
                })
            self.assertIn("failure_reason", str(caught.exception))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_schema.Outcomes -v`

Expected: FAIL containing `non-measured latency must be null` is absent, so the assertion on the exception message fails, or `ValueError` is not raised for `latency_ms: 0`. The first test's expected failure text is `ValueError not raised` until Step 3.

- [ ] **Step 3: Write the minimal implementation**

Replace `validate_trial` in `perf/schema.py` with:

```python
OUTCOMES = (
    "measured",
    "unsupported",
    "not_applicable",
    "unverified",
    "failed",
    "not_run",
)


def validate_trial(trial):
    outcome = trial["outcome"]
    if outcome not in OUTCOMES:
        raise ValueError("unknown outcome %r" % (outcome,))
    claims = set(trial.get("claims") or [])
    boundary = trial["boundary"]
    for blocked_boundary, blocked_claim, message in _FORBIDDEN:
        if boundary == blocked_boundary and blocked_claim in claims:
            raise ValueError(message)
    raw_samples = trial.get("samples_ms", [])
    if raw_samples is None:
        raw_samples = []
    if not isinstance(raw_samples, list):
        raise ValueError("samples_ms")
    samples = raw_samples
    if outcome in ("failed", "not_run"):
        reason = trial.get("failure_reason")
        if not isinstance(reason, str) or not reason:
            raise ValueError("failure_reason")
    if outcome != "measured":
        if trial.get("latency_ms") is not None:
            raise ValueError("non-measured latency must be null")
        if samples:
            raise ValueError("non-measured samples must be empty")
        return
    if not samples:
        raise ValueError("measured trial needs samples")
    for sample in samples:
        if isinstance(sample, bool) or not isinstance(sample, (int, float)):
            raise ValueError("samples must be finite and non-negative")
        if sample != sample or sample in (float("inf"), float("-inf")) or sample < 0:
            raise ValueError("samples must be finite and non-negative")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_schema -v`

Expected: `OK` and both `BoundaryClaims` and `Outcomes` pass.

- [ ] **Step 5: Commit**

```bash
git add perf/schema.py perf/tests/test_schema.py
git commit -m "test: keep unsupported performance results null"
```

---

### Task 3: Round-trip the raw trial

**Files:**
- Modify: `perf/schema.py`
- Modify: `perf/tests/test_schema.py`

**Interfaces:**
- Consumes: `validate_trial`
- Produces: `dump_trial(trial: dict) -> str` and `load_trial(text: str) -> dict`. `dump_trial` validates first. `load_trial` validates after parsing. Key order is not significant. `samples_ms` values are preserved as numbers.

- [ ] **Step 1: Write the failing test**

```python
from perf.schema import dump_trial, load_trial


class RoundTrip(unittest.TestCase):
    def test_dump_and_load_preserve_samples(self):
        trial = {
            "schema_version": 1,
            "editor_id": "superdoc",
            "outcome": "measured",
            "boundary": "model_ready",
            "claims": [],
            "samples_ms": [3.5, 4.0],
            "latency_ms": None,
            "criterion_id": "C02",
        }
        loaded = load_trial(dump_trial(trial))
        self.assertEqual(loaded["samples_ms"], [3.5, 4.0])
        self.assertEqual(loaded["criterion_id"], "C02")

    def test_dump_rejects_a_zero_for_unverified(self):
        trial = {
            "schema_version": 1,
            "editor_id": "wordcraft",
            "outcome": "unverified",
            "boundary": "input_to_next_paint",
            "claims": [],
            "samples_ms": [],
            "latency_ms": 0,
            "criterion_id": "C23",
        }
        with self.assertRaises(ValueError) as caught:
            dump_trial(trial)
        self.assertIn("non-measured latency must be null", str(caught.exception))
```

Add `dump_trial, load_trial` to the import line.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_schema.RoundTrip -v`

Expected: ERROR containing `ImportError: cannot import name 'dump_trial'`

- [ ] **Step 3: Write the minimal implementation**

Add to `perf/schema.py`:

```python
import json


def dump_trial(trial):
    validate_trial(trial)
    return json.dumps(trial, sort_keys=True, separators=(",", ":"))


def load_trial(text):
    trial = json.loads(text)
    if not isinstance(trial, dict):
        raise ValueError("trial must be an object")
    validate_trial(trial)
    return trial
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_schema.RoundTrip -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/schema.py perf/tests/test_schema.py
git commit -m "feat: round-trip raw performance trials as JSON"
```

---

### Task 4: Require the environment fields a later summary needs

**Files:**
- Modify: `perf/schema.py`
- Modify: `perf/tests/test_schema.py`

**Interfaces:**
- Consumes: `validate_trial`
- Produces: `validate_environment(env: dict) -> None`. Required keys: `host_class` (`dedicated` or `ci_coarse`), `cpu_model`, `os`, `arch`, `ram_bytes` (int `> 0`), `power_source`, `editor_id`, `editor_version`, `fixture_sha256` (exactly 64 hex characters), `cache_state` (`process_cold_fs_warm`, `os_cache_cold`, or `warm_steady`), `feature_profile` (`P0`, `P1`, `P2`, or `P3`), `workload_id`, `repetition_unit` (`fresh_process` or `in_process_iteration`), `run_kind` (`timing` or `diagnostic`), `headless` (bool). `display_refresh_hz` is a finite number `> 0`, or `None` when `headless` is true. `os_cache_cold` also requires `page_cache_dropped` to be `True`.

- [ ] **Step 1: Write the failing test**

```python
from perf.schema import validate_environment


def _env(**overrides):
    env = {
        "host_class": "dedicated",
        "cpu_model": "unspecified-test-cpu",
        "os": "linux",
        "arch": "x86_64",
        "ram_bytes": 16 * 1024 ** 3,
        "power_source": "ac",
        "editor_id": "plate",
        "editor_version": "60c7f5530",
        "fixture_sha256": "a" * 64,
        "cache_state": "process_cold_fs_warm",
        "feature_profile": "P0",
        "workload_id": "flow-short-1mb",
        "repetition_unit": "fresh_process",
        "run_kind": "timing",
        "headless": False,
        "display_refresh_hz": 60,
    }
    env.update(overrides)
    return env


class Environment(unittest.TestCase):
    def test_accepts_a_dedicated_timing_environment(self):
        validate_environment(_env())

    def test_rejects_a_short_fixture_hash(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(fixture_sha256="abc"))
        self.assertIn("fixture_sha256", str(caught.exception))

    def test_headless_allows_a_null_refresh(self):
        validate_environment(_env(headless=True, display_refresh_hz=None))

    def test_headed_run_needs_a_refresh(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(display_refresh_hz=None))
        self.assertIn("display_refresh_hz", str(caught.exception))

    def test_ci_cannot_pretend_to_be_os_cache_cold(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(host_class="ci_coarse", cache_state="os_cache_cold"))
        self.assertIn("os_cache_cold", str(caught.exception))

    def test_hash_must_be_sixty_four_hex_characters_and_nothing_else(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(fixture_sha256=("a" * 64) + "\n"))
        self.assertIn("fixture_sha256", str(caught.exception))

    def test_headless_must_be_a_boolean(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(headless="false"))
        self.assertIn("headless", str(caught.exception))

    def test_refresh_rejects_nan(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(display_refresh_hz=float("nan")))
        self.assertIn("display_refresh_hz", str(caught.exception))

    def test_os_cache_cold_requires_a_recorded_page_cache_drop(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(cache_state="os_cache_cold"))
        self.assertIn("page_cache_dropped", str(caught.exception))
        validate_environment(_env(cache_state="os_cache_cold", page_cache_dropped=True))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_schema.Environment -v`

Expected: ERROR containing `ImportError: cannot import name 'validate_environment'`

- [ ] **Step 3: Write the minimal implementation**

Add to `perf/schema.py`:

```python
import math
import re

_SHA256 = re.compile(r"[0-9a-f]{64}")


def validate_environment(env):
    if env["host_class"] not in ("dedicated", "ci_coarse"):
        raise ValueError("host_class")
    if env["cache_state"] not in ("process_cold_fs_warm", "os_cache_cold", "warm_steady"):
        raise ValueError("cache_state")
    if env["host_class"] == "ci_coarse" and env["cache_state"] == "os_cache_cold":
        raise ValueError("os_cache_cold is dedicated-host only")
    if env["cache_state"] == "os_cache_cold" and env.get("page_cache_dropped") is not True:
        raise ValueError("page_cache_dropped")
    if env["feature_profile"] not in ("P0", "P1", "P2", "P3"):
        raise ValueError("feature_profile")
    if env["repetition_unit"] not in ("fresh_process", "in_process_iteration"):
        raise ValueError("repetition_unit")
    if env["run_kind"] not in ("timing", "diagnostic"):
        raise ValueError("run_kind")
    if not isinstance(env["ram_bytes"], int) or isinstance(env["ram_bytes"], bool) or env["ram_bytes"] <= 0:
        raise ValueError("ram_bytes")
    for key in ("cpu_model", "os", "arch", "power_source", "editor_id", "editor_version", "workload_id"):
        if not isinstance(env[key], str) or not env[key]:
            raise ValueError(key)
    if _SHA256.fullmatch(env["fixture_sha256"]) is None:
        raise ValueError("fixture_sha256")
    if not isinstance(env["headless"], bool):
        raise ValueError("headless")
    refresh = env["display_refresh_hz"]
    if env["headless"]:
        if refresh is not None:
            raise ValueError("display_refresh_hz")
        return
    if isinstance(refresh, bool) or not isinstance(refresh, (int, float)) or not math.isfinite(refresh) or refresh <= 0:
        raise ValueError("display_refresh_hz")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_schema -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/schema.py perf/tests/test_schema.py
git commit -m "feat: require a performance environment fingerprint"
```

## Acceptance criteria

- `python3 -m unittest perf.tests.test_schema -v` passes.
- A trial with `outcome: unsupported` and `latency_ms: 0` raises `ValueError`.
- A trial with `boundary: raf_callback` and claim `visible_paint` raises `ValueError`.
- `ci_coarse` plus `os_cache_cold` raises `ValueError`.
- No editor process is started.

## Coverage ids

C01 C02 C03 I07 I08 I12
