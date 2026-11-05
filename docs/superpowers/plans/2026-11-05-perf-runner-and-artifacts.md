# Performance runner and artifacts implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write one immutable raw trial file per attempt, refuse to publish GUI latency from CI, and keep diagnostic traces off the timing distribution.

**Architecture:** `perf/runner/artifacts.py` writes JSON under a directory the caller supplies. `perf/runner/policy.py` decides whether a finished trial may be published. Neither module starts an editor. Plan 1's `validate_trial` and `validate_environment` are called before a write.

**Tech Stack:** Python 3, `json`, `pathlib`, `unittest`, `tempfile`.

## Global Constraints

- A raw trial file is created with `os.O_EXCL`. A second write to the same attempt id fails.
- `run_kind: diagnostic` cannot be published as a timing result.
- `host_class: ci_coarse` cannot publish a browser-visible or native-present latency.
- `os_cache_cold` on `ci_coarse` is already rejected by `validate_environment`. This plan also rejects publishing it.
- The runner does not call `drop_caches`.
- Coverage ids owned here: C01 C04 C17 C18 C19 C20 C21 I05 I09 I11.

---

### Task 1: Immutable raw trial files

**Files:**
- Create: `perf/runner/__init__.py`
- Create: `perf/runner/artifacts.py`
- Test: `perf/tests/test_runner.py`

**Interfaces:**
- Consumes: `perf.schema.dump_trial`
- Produces: `write_attempt(directory: Path, attempt_id: str, trial: dict) -> Path`. The file name is `attempt_id + ".json"`. `attempt_id` matches `^[a-z0-9][a-z0-9._-]{0,80}$`.

- [ ] **Step 1: Write the failing test**

```python
import json
import tempfile
import unittest
from pathlib import Path

from perf.runner.artifacts import write_attempt


def _trial():
    return {
        "outcome": "measured",
        "boundary": "handler_duration",
        "claims": [],
        "samples_ms": [1.5],
        "latency_ms": None,
    }


class Artifacts(unittest.TestCase):
    def test_writes_the_trial_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_attempt(Path(tmp), "attempt-1", _trial())
            self.assertEqual(json.loads(path.read_text())["samples_ms"], [1.5])
            with self.assertRaises(FileExistsError):
                write_attempt(Path(tmp), "attempt-1", _trial())

    def test_rejects_an_unsafe_attempt_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as caught:
                write_attempt(Path(tmp), "../escape", _trial())
            self.assertIn("attempt_id", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_runner.Artifacts -v`

Expected: ERROR containing `No module named 'perf.runner'`

- [ ] **Step 3: Write the minimal implementation**

`perf/runner/__init__.py` is empty.

`perf/runner/artifacts.py`:

```python
import os
import re
from pathlib import Path

from perf.schema import dump_trial

_ATTEMPT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,80}$")


def write_attempt(directory, attempt_id, trial):
    if not _ATTEMPT.match(attempt_id):
        raise ValueError("attempt_id")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (attempt_id + ".json")
    payload = dump_trial(trial).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o644)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    return path
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_runner.Artifacts -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/runner/__init__.py perf/runner/artifacts.py perf/tests/test_runner.py
git commit -m "feat: write immutable raw performance attempts"
```

---

### Task 2: Publication policy for host class and cache state

**Files:**
- Create: `perf/runner/policy.py`
- Modify: `perf/tests/test_runner.py`

**Interfaces:**
- Consumes: environment fields from `validate_environment` and a `layer` string
- Produces: `publication_decision(env: dict, layer: str) -> str` returning `publish` or raising `ValueError`

- [ ] **Step 1: Write the failing test**

```python
from perf.runner.policy import publication_decision


def _env(**overrides):
    env = {
        "host_class": "dedicated",
        "cache_state": "process_cold_fs_warm",
        "run_kind": "timing",
        "repetition_unit": "fresh_process",
    }
    env.update(overrides)
    return env


class Policy(unittest.TestCase):
    def test_dedicated_timing_run_can_publish_visible_latency(self):
        self.assertEqual(publication_decision(_env(), "browser_visible"), "publish")

    def test_ci_cannot_publish_visible_latency(self):
        with self.assertRaises(ValueError) as caught:
            publication_decision(_env(host_class="ci_coarse"), "browser_visible")
        self.assertIn("ci_coarse", str(caught.exception))

    def test_ci_may_publish_a_model_microbenchmark(self):
        self.assertEqual(
            publication_decision(_env(host_class="ci_coarse", repetition_unit="in_process_iteration"), "model"),
            "publish",
        )

    def test_native_present_is_not_a_layer_name(self):
        with self.assertRaises(ValueError) as caught:
            publication_decision(_env(host_class="ci_coarse"), "native_present")
        self.assertIn("layer", str(caught.exception))

    def test_diagnostic_run_is_not_a_timing_publication(self):
        with self.assertRaises(ValueError) as caught:
            publication_decision(_env(run_kind="diagnostic"), "browser_visible")
        self.assertIn("diagnostic", str(caught.exception))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_runner.Policy -v`

Expected: ERROR containing `No module named 'perf.runner.policy'`

- [ ] **Step 3: Write the minimal implementation**

`perf/runner/policy.py`:

```python
_LAYERS = {"native", "model", "browser_visible", "wasm_boundary"}
_VISIBLE = {"browser_visible"}


def publication_decision(env, layer):
    if layer not in _LAYERS:
        raise ValueError("layer")
    if env["run_kind"] != "timing":
        raise ValueError("diagnostic runs are not timing publications")
    if env["host_class"] == "ci_coarse" and layer in _VISIBLE:
        raise ValueError("ci_coarse cannot publish visible latency")
    if env["cache_state"] == "os_cache_cold" and env["host_class"] != "dedicated":
        raise ValueError("os_cache_cold is dedicated-host only")
    if layer in _VISIBLE and env["repetition_unit"] != "fresh_process":
        raise ValueError("visible latency requires fresh_process")
    return "publish"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_runner.Policy -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/runner/policy.py perf/tests/test_runner.py
git commit -m "feat: gate published latency on the host class"
```

---

### Task 3: Memory sample records

**Files:**
- Create: `perf/runner/memory.py`
- Modify: `perf/tests/test_runner.py`

**Interfaces:**
- Consumes: nothing from the operating system. The function checks a sample the caller already gathered.
- Produces: `validate_memory_sample(sample: dict) -> None`. Required keys: `rss_bytes`, `pss_bytes`, `uss_bytes`, `process_count`, `cgroup_current_bytes`, `cgroup_peak_bytes`. `process_count` is an int `>= 1`. All byte fields are ints `>= 0`. `pss_bytes` must be `<= rss_bytes`. A sample with `process_count: 0` is rejected. Missing cgroup fields are rejected rather than stored as zero.

- [ ] **Step 1: Write the failing test**

```python
from perf.runner.memory import validate_memory_sample


def _sample(**overrides):
    sample = {
        "rss_bytes": 1000,
        "pss_bytes": 800,
        "uss_bytes": 700,
        "process_count": 3,
        "cgroup_current_bytes": 1200,
        "cgroup_peak_bytes": 1500,
    }
    sample.update(overrides)
    return sample


class Memory(unittest.TestCase):
    def test_accepts_a_process_tree_sample(self):
        validate_memory_sample(_sample())

    def test_rejects_a_single_missing_process(self):
        with self.assertRaises(ValueError) as caught:
            validate_memory_sample(_sample(process_count=0))
        self.assertIn("process_count", str(caught.exception))

    def test_rejects_a_missing_cgroup_field(self):
        sample = _sample()
        del sample["cgroup_peak_bytes"]
        with self.assertRaises(ValueError) as caught:
            validate_memory_sample(sample)
        self.assertIn("cgroup_peak_bytes", str(caught.exception))

    def test_rejects_pss_above_rss(self):
        with self.assertRaises(ValueError) as caught:
            validate_memory_sample(_sample(pss_bytes=5000))
        self.assertIn("pss_bytes", str(caught.exception))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_runner.Memory -v`

Expected: ERROR containing `No module named 'perf.runner.memory'`

- [ ] **Step 3: Write the minimal implementation**

`perf/runner/memory.py`:

```python
_FIELDS = (
    "rss_bytes",
    "pss_bytes",
    "uss_bytes",
    "cgroup_current_bytes",
    "cgroup_peak_bytes",
)


def validate_memory_sample(sample):
    for key in _FIELDS:
        if key not in sample:
            raise ValueError(key)
        value = sample[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(key)
    count = sample["process_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("process_count")
    if sample["pss_bytes"] > sample["rss_bytes"]:
        raise ValueError("pss_bytes exceeds rss_bytes")
    if sample["uss_bytes"] > sample["pss_bytes"]:
        raise ValueError("uss_bytes exceeds pss_bytes")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_runner.Memory -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/runner/memory.py perf/tests/test_runner.py
git commit -m "feat: validate whole-tree memory samples"
```

---

### Task 4: Seeded editor order

**Files:**
- Create: `perf/runner/order.py`
- Modify: `perf/tests/test_runner.py`

**Interfaces:**
- Consumes: nothing
- Produces: `editor_order(editor_ids: list[str], seed: int) -> list[str]`. The result is a permutation. The same seed returns the same order. A different seed may return a different order. The input list is not mutated.

- [ ] **Step 1: Write the failing test**

```python
from perf.runner.order import editor_order


class Order(unittest.TestCase):
    def test_order_is_a_permutation_and_is_stable(self):
        editors = ["plate", "superdoc", "wordcraft", "docxodus"]
        first = editor_order(editors, seed=11)
        second = editor_order(editors, seed=11)
        self.assertEqual(first, second)
        self.assertEqual(sorted(first), sorted(editors))
        self.assertEqual(editors, ["plate", "superdoc", "wordcraft", "docxodus"])

    def test_a_different_seed_is_allowed_to_differ(self):
        editors = ["plate", "superdoc", "wordcraft", "docxodus", "folio", "docen"]
        self.assertNotEqual(editor_order(editors, 1), editor_order(editors, 2))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_runner.Order -v`

Expected: ERROR containing `No module named 'perf.runner.order'`

- [ ] **Step 3: Write the minimal implementation**

`perf/runner/order.py`:

```python
import random


def editor_order(editor_ids, seed):
    ordered = list(editor_ids)
    random.Random(seed).shuffle(ordered)
    return ordered
```

The test `assertNotEqual` for seeds 1 and 2 is deterministic for this list under Python's `random.Random`. If a future Python changes the shuffle algorithm and the two seeds collide, change the second seed in the test to `99` and keep the assertion that the two results differ. Do not weaken the assertion to allow any order.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_runner -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/runner/order.py perf/tests/test_runner.py
git commit -m "feat: shuffle editor order from a recorded seed"
```

## Acceptance criteria

- `python3 -m unittest perf.tests.test_runner -v` passes.
- The second write of `attempt-1` raises `FileExistsError`.
- `publication_decision` rejects `ci_coarse` plus `browser_visible`.
- A memory sample without `cgroup_peak_bytes` raises `ValueError`.
- No editor is launched and `/proc/sys/vm/drop_caches` is not written.

## Coverage ids

C01 C04 C17 C18 C19 C20 C21 I05 I09 I11
