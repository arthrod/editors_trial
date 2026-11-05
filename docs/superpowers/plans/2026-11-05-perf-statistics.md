# Performance statistics implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Summarize a list of latency samples with percentiles, a median absolute deviation, and a bootstrap confidence interval, and refuse to mix cache states or drop outliers.

**Architecture:** `perf/analysis/summarize.py` is a pure function of samples plus metadata. It does not read trial files. The runner plan calls `summarize` after it has grouped trials.

**Tech Stack:** Python 3, `random`, `statistics` is not required, `unittest`.

## Global Constraints

- Do not delete a sample because it is large.
- Do not mix `process_cold_fs_warm`, `os_cache_cold`, and `warm_steady` in one summary.
- Do not pool `fresh_process` with `in_process_iteration`.
- The confidence interval is for the median, at 95 percent, using a seeded bootstrap of 2000 resamples.
- Percentile interpolation is linear on the sorted sample: rank = (p / 100) * (n - 1).
- Coverage ids owned here: C01 I09 I10.

---

### Task 1: Percentiles and median absolute deviation

**Files:**
- Create: `perf/analysis/__init__.py`
- Create: `perf/analysis/summarize.py`
- Test: `perf/tests/test_summarize.py`

**Interfaces:**
- Consumes: nothing
- Produces: `percentile(samples: list[float], p: float) -> float` and `median_absolute_deviation(samples: list[float]) -> float`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from perf.analysis.summarize import median_absolute_deviation, percentile


class Spread(unittest.TestCase):
    def test_median_of_five_values(self):
        self.assertEqual(percentile([1, 2, 3, 4, 100], 50), 3)

    def test_endpoints_are_min_and_max(self):
        samples = [1, 2, 3, 4, 100]
        self.assertEqual(percentile(samples, 0), 1)
        self.assertEqual(percentile(samples, 100), 100)

    def test_mad_keeps_the_tail_in_the_deviation_list(self):
        # deviations from median 3 are 2, 1, 0, 1, 97; median of those is 1
        self.assertEqual(median_absolute_deviation([1, 2, 3, 4, 100]), 1)

    def test_empty_samples_are_rejected(self):
        with self.assertRaises(ValueError) as caught:
            percentile([], 50)
        self.assertIn("empty", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_summarize.Spread -v`

Expected: ERROR containing `No module named 'perf.analysis'`

- [ ] **Step 3: Write the minimal implementation**

`perf/analysis/__init__.py` is empty.

`perf/analysis/summarize.py`:

```python
def percentile(samples, p):
    if not samples:
        raise ValueError("empty samples")
    if p < 0 or p > 100:
        raise ValueError("percentile out of range")
    ordered = sorted(samples)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (p / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    fraction = rank - low
    return float(ordered[low] * (1.0 - fraction) + ordered[high] * fraction)


def median_absolute_deviation(samples):
    center = percentile(samples, 50)
    deviations = [abs(sample - center) for sample in samples]
    return percentile(deviations, 50)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_summarize.Spread -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/analysis/__init__.py perf/analysis/summarize.py perf/tests/test_summarize.py
git commit -m "test: compute latency percentiles without dropping the tail"
```

---

### Task 2: Seeded bootstrap confidence interval

**Files:**
- Modify: `perf/analysis/summarize.py`
- Modify: `perf/tests/test_summarize.py`

**Interfaces:**
- Consumes: `percentile`
- Produces: `bootstrap_median_ci(samples: list[float], seed: int = 0, draws: int = 2000, level: float = 0.95) -> tuple[float, float]`

- [ ] **Step 1: Write the failing test**

```python
from perf.analysis.summarize import bootstrap_median_ci


class Interval(unittest.TestCase):
    def test_interval_contains_the_median_of_a_constant_sample(self):
        low, high = bootstrap_median_ci([5, 5, 5, 5], seed=0, draws=50)
        self.assertEqual(low, 5)
        self.assertEqual(high, 5)

    def test_interval_is_ordered(self):
        low, high = bootstrap_median_ci([1, 2, 3, 4, 100], seed=1, draws=200)
        self.assertLessEqual(low, 3)
        self.assertGreaterEqual(high, 3)
        self.assertLessEqual(low, high)

    def test_same_seed_is_reproducible(self):
        self.assertEqual(
            bootstrap_median_ci([1, 2, 3, 4, 100], seed=7, draws=100),
            bootstrap_median_ci([1, 2, 3, 4, 100], seed=7, draws=100),
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_summarize.Interval -v`

Expected: ERROR containing `cannot import name 'bootstrap_median_ci'`

- [ ] **Step 3: Write the minimal implementation**

Add to `perf/analysis/summarize.py`:

```python
import random


def bootstrap_median_ci(samples, seed=0, draws=2000, level=0.95):
    if not samples:
        raise ValueError("empty samples")
    if not 0 < level < 1:
        raise ValueError("level")
    rng = random.Random(seed)
    count = len(samples)
    medians = []
    for _ in range(draws):
        draw = [samples[rng.randrange(count)] for _ in range(count)]
        medians.append(percentile(draw, 50))
    alpha = (1.0 - level) / 2.0
    return (percentile(medians, alpha * 100.0), percentile(medians, (1.0 - alpha) * 100.0))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_summarize.Interval -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/analysis/summarize.py perf/tests/test_summarize.py
git commit -m "feat: add a seeded bootstrap interval for the median"
```

---

### Task 3: Refuse mixed cache states and dropped outliers

**Files:**
- Modify: `perf/analysis/summarize.py`
- Modify: `perf/tests/test_summarize.py`

**Interfaces:**
- Consumes: `percentile`, `median_absolute_deviation`, `bootstrap_median_ci`
- Produces: `summarize(samples: list[float], cache_state: str, repetition_unit: str, seed: int = 0) -> dict` with keys `n`, `median`, `p90`, `p95`, `p99`, `mad`, `ci95_low`, `ci95_high`, `minimum`, `maximum`, `cache_state`, `repetition_unit`. `summarize_groups(groups: list[dict]) -> dict` raises `ValueError` if cache states or repetition units differ. Each group is `{"cache_state", "repetition_unit", "samples"}`.

- [ ] **Step 1: Write the failing test**

```python
from perf.analysis.summarize import summarize, summarize_groups


class Summary(unittest.TestCase):
    def test_summary_keeps_the_maximum(self):
        result = summarize([1, 2, 3, 4, 100], "process_cold_fs_warm", "fresh_process", seed=0)
        self.assertEqual(result["n"], 5)
        self.assertEqual(result["maximum"], 100)
        self.assertEqual(result["median"], 3)
        self.assertEqual(result["mad"], 1)
        self.assertIn("p95", result)
        self.assertLessEqual(result["ci95_low"], result["ci95_high"])

    def test_mixed_cache_states_are_rejected(self):
        with self.assertRaises(ValueError) as caught:
            summarize_groups([
                {"cache_state": "process_cold_fs_warm", "repetition_unit": "fresh_process", "samples": [1, 2]},
                {"cache_state": "warm_steady", "repetition_unit": "fresh_process", "samples": [1, 2]},
            ])
        self.assertIn("cache_state", str(caught.exception))

    def test_mixed_repetition_units_are_rejected(self):
        with self.assertRaises(ValueError) as caught:
            summarize_groups([
                {"cache_state": "warm_steady", "repetition_unit": "fresh_process", "samples": [1, 2]},
                {"cache_state": "warm_steady", "repetition_unit": "in_process_iteration", "samples": [1, 2]},
            ])
        self.assertIn("repetition_unit", str(caught.exception))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_summarize.Summary -v`

Expected: ERROR containing `cannot import name 'summarize'`

- [ ] **Step 3: Write the minimal implementation**

Add to `perf/analysis/summarize.py`:

```python
def summarize(samples, cache_state, repetition_unit, seed=0):
    if cache_state not in ("process_cold_fs_warm", "os_cache_cold", "warm_steady"):
        raise ValueError("cache_state")
    if repetition_unit not in ("fresh_process", "in_process_iteration"):
        raise ValueError("repetition_unit")
    low, high = bootstrap_median_ci(samples, seed=seed)
    return {
        "n": len(samples),
        "median": percentile(samples, 50),
        "p90": percentile(samples, 90),
        "p95": percentile(samples, 95),
        "p99": percentile(samples, 99),
        "mad": median_absolute_deviation(samples),
        "ci95_low": low,
        "ci95_high": high,
        "minimum": percentile(samples, 0),
        "maximum": percentile(samples, 100),
        "cache_state": cache_state,
        "repetition_unit": repetition_unit,
    }


def summarize_groups(groups):
    if not groups:
        raise ValueError("empty groups")
    cache_state = groups[0]["cache_state"]
    repetition_unit = groups[0]["repetition_unit"]
    pooled = []
    for group in groups:
        if group["cache_state"] != cache_state:
            raise ValueError("cache_state values differ")
        if group["repetition_unit"] != repetition_unit:
            raise ValueError("repetition_unit values differ")
        pooled.extend(group["samples"])
    return summarize(pooled, cache_state, repetition_unit)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_summarize -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/analysis/summarize.py perf/tests/test_summarize.py
git commit -m "feat: summarize one cache state and keep every sample"
```

---

### Task 4: Fresh-process rule for interactive criteria

**Files:**
- Modify: `perf/analysis/summarize.py`
- Modify: `perf/tests/test_summarize.py`

**Interfaces:**
- Consumes: `summarize`
- Produces: `assert_interactive_repetition(criterion_id: str, repetition_unit: str) -> None`. Criterion ids `C01`, `C03`, `C05`, `C06`, `C10`, and `C20` require `fresh_process`.

- [ ] **Step 1: Write the failing test**

```python
from perf.analysis.summarize import assert_interactive_repetition


class Repetition(unittest.TestCase):
    def test_startup_requires_a_fresh_process(self):
        with self.assertRaises(ValueError) as caught:
            assert_interactive_repetition("C01", "in_process_iteration")
        self.assertIn("fresh_process", str(caught.exception))

    def test_startup_accepts_a_fresh_process(self):
        assert_interactive_repetition("C01", "fresh_process")

    def test_wasm_boundary_may_use_in_process_iterations(self):
        assert_interactive_repetition("C24", "in_process_iteration")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_summarize.Repetition -v`

Expected: ERROR containing `cannot import name 'assert_interactive_repetition'`

- [ ] **Step 3: Write the minimal implementation**

Add to `perf/analysis/summarize.py`:

```python
_FRESH = {"C01", "C03", "C05", "C06", "C10", "C20"}


def assert_interactive_repetition(criterion_id, repetition_unit):
    if criterion_id in _FRESH and repetition_unit != "fresh_process":
        raise ValueError("fresh_process is required for %s" % (criterion_id,))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_summarize -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/analysis/summarize.py perf/tests/test_summarize.py
git commit -m "feat: require fresh processes for interactive latency"
```

## Acceptance criteria

- `python3 -m unittest perf.tests.test_summarize -v` passes.
- The sample `100` remains the maximum of `[1, 2, 3, 4, 100]`.
- Two groups with different `cache_state` values raise `ValueError`.
- `C01` with `in_process_iteration` raises `ValueError`.
- No editor is launched.

## Coverage ids

C01 I09 I10
