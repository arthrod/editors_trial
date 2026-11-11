"""The lax layer (owner decision 2026-11-11; GitHub issue #155 item 6).

Each relaxation here is bound to the evidence that justifies it and to a
recording in the trial artifacts so Report E2 can disclose it:

1. clock-skew bound 2 ms -> 5 ms (witness.py, witness.mjs,
   benchmark_document.py);
2. ready/navigation load timeouts 120 s -> 300 s, 600 s on prose-250kw
   (warm_cold_browser, memory_probe, adversarial_c10_scroll, wasm_host,
   document_probe, typing_session);
3. settle onset bound floor 100 ms (b2_settle.mjs) — the shakedown's folio
   witness_sparse cells show glyph onsets 50/66.7/100 ms after the last
   ink-less delivered frame; nothing supports relaxing the delivery-gap
   bound (no refusal exceeded it) or accepting a sample whose witness never
   painted;
4. CPU-throttle tolerance: a sample whose cgroup throttling stayed within
   max(1 ms, 1 % of the sample's span) is kept with throttled_usec recorded
   on the row; above it refuses as before;
6. witness anchor-lag bound max(3 intervals, 100 ms) -> max(3 intervals,
   250 ms) (wordcraft frame lags 101.3-151.8 ms refused C10/C11/C14).

Item 5 (disclosure prose in Report E2) is not code and lives elsewhere.
"""

import importlib
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WITNESS_MJS = REPO / "perf" / "runner" / "witness.mjs"

PROBES = {
    "warm_cold_browser.mjs": "ready/navigation waits",
    "memory_probe.mjs": "ready/navigation waits",
    "adversarial_c10_scroll.mjs": "ready/navigation waits",
    "wasm_host.mjs": "navigation wait",
    "document_probe.mjs": "ready/document-text waits",
    "typing_session.mjs": "navigation/ready waits",
}


def _load(name):
    return importlib.import_module(name)


class SkewBound(unittest.TestCase):
    """Item 1: the page-clock bound moves from 2 ms to 5 ms everywhere."""

    def test_the_validator_default_is_five_ms(self):
        witness = _load("perf.runner.witness")
        self.assertEqual(float(witness.DEFAULT_SKEW_BOUND_MS), 5.0)

    def test_the_producer_default_is_five_ms(self):
        source = WITNESS_MJS.read_text(encoding="utf-8")
        match = re.search(r"export const DEFAULT_SKEW_BOUND_MS = ([0-9.]+);", source)
        self.assertIsNotNone(match, "witness.mjs must export DEFAULT_SKEW_BOUND_MS")
        self.assertEqual(float(match.group(1)), 5.0)

    def test_the_document_lane_bound_is_five_ms(self):
        document = _load("perf.runner.benchmark_document")
        self.assertEqual(float(document._CLOCK_SKEW_BOUND_MS), 5.0)

    def test_a_four_ms_skew_no_longer_refuses_a_document_sample(self):
        document = _load("perf.runner.benchmark_document")
        self.assertFalse(document._clock_skew_exceeds({"clock_skew_ms": 4.0}))
        self.assertTrue(document._clock_skew_exceeds({"clock_skew_ms": 6.0}))
        self.assertTrue(document._clock_skew_exceeds({"clock_skew_acceptable": False}))


class AnchorLagBound(unittest.TestCase):
    """Item 6: the anchor lag floor moves from 100 ms to 250 ms."""

    def test_the_validator_floor_is_two_hundred_fifty_ms(self):
        witness = _load("perf.runner.witness")
        self.assertEqual(float(witness.LAG_BOUND_MIN_MS), 250.0)
        self.assertEqual(int(witness.LAG_BOUND_INTERVALS), 3)

    def test_the_producer_floor_is_two_hundred_fifty_ms(self):
        source = WITNESS_MJS.read_text(encoding="utf-8")
        match = re.search(r"export const ANCHOR_LAG_BOUND_MIN_MS = ([0-9.]+);", source)
        self.assertIsNotNone(match, "witness.mjs must export ANCHOR_LAG_BOUND_MIN_MS")
        self.assertEqual(float(match.group(1)), 250.0)

    def test_a_150_ms_anchor_lag_passes_the_recomputed_rule(self):
        """HF evidence: wordcraft frame lags 101.3-151.8 ms refused C10/C11
        under the 100 ms floor; the owner's 250 ms floor keeps them
        checkable while the bound itself is still recorded on the record."""
        from perf.tests.witness_records import publishable_witness_record
        from perf.runner.witness import validate_witness

        record = publishable_witness_record(
            clock_check={
                "change_page_ms": 67.0,
                "frame_page_ms": 217.0,
                "frame_lag_ms": 150.0,
                "lag_bound_ms": 250.0,
                "lag_bound_rule": "max(3 frame intervals, 250 ms)",
                "conversion": {
                    "formula": "page_ms = timestamp * 1000 - performance.timeOrigin",
                    "error_lower_ms": -2.0,
                    "error_lower_why": "causality: a frame cannot show a change before it was made (2 ms slop for the change timestamp)",
                    "error_upper_ms": 250.0,
                    "error_upper_why": "the anchor lag bound: a positive conversion error is caught once it pushes the anchor past it",
                    "published": "[-2 ms, +250 ms] (never \"±2 ms\")",
                },
            },
        )
        verdict = validate_witness(record)
        self.assertFalse(verdict.get("refused"), verdict)


class LoadTimeouts(unittest.TestCase):
    """Item 2: 300 s ready/navigation waits, 600 s on prose-250kw."""

    def test_the_timeout_policy_module_exists(self):
        path = REPO / "perf" / "runner" / "load_timeouts.py"
        self.assertTrue(path.is_file(), "perf/runner/load_timeouts.py must exist")
        timeouts = _load("perf.runner.load_timeouts")
        self.assertEqual(timeouts.DEFAULT_LOAD_TIMEOUT_MS, 300_000)
        self.assertEqual(timeouts.load_timeout_ms("prose-500w"), 300_000)
        self.assertEqual(timeouts.load_timeout_ms("prose-250kw"), 600_000)
        self.assertEqual(
            timeouts.load_timeout_env("prose-250kw"),
            {"PERF_LOAD_TIMEOUT_MS": "600000"},
        )

    def test_the_probe_environment_carries_the_timeout(self):
        timeouts = _load("perf.runner.load_timeouts")
        self.assertEqual(
            timeouts.load_timeout_env("prose-500w"),
            {"PERF_LOAD_TIMEOUT_MS": "300000"},
        )

    def test_every_trial_environment_records_the_load_timeout(self):
        from perf.fixtures.profiles import size_ladder
        from perf.runner.benchmark_ci_contract import _host_base

        row = next(r for r in size_ladder() if r["workload_id"] == "prose-500w")
        env = _host_base(
            editor_id="plate",
            editor_version="test",
            execution_profile="ci_broad",
            fixture_sha256="a" * 64,
            workload_row=row,
            docx_size=1234,
            cache_state="process_cold_fs_warm",
            repetition_unit="fresh_process",
            run_kind="timing",
            feature_profile_name="P0",
        )
        self.assertEqual(env["load_timeout_ms"], 300_000)

    def test_the_mjs_timeout_helper_exists(self):
        path = REPO / "perf" / "runner" / "load_timeout.mjs"
        self.assertTrue(path.is_file(), "perf/runner/load_timeout.mjs must exist")
        source = path.read_text(encoding="utf-8")
        self.assertIn("export const DEFAULT_LOAD_TIMEOUT_MS = 300_000", source)
        self.assertIn("PERF_LOAD_TIMEOUT_MS", source)

    def test_no_probe_still_waits_a_hardcoded_120_seconds(self):
        for name, what in PROBES.items():
            source = (REPO / "perf" / "runner" / name).read_text(encoding="utf-8")
            with self.subTest(probe=name):
                self.assertNotIn(
                    "120_000", source, "%s must not hardcode a 120 s %s" % (name, what)
                )
                self.assertNotIn(
                    "120000", source, "%s must not hardcode a 120 s %s" % (name, what)
                )
                self.assertIn(
                    "loadTimeoutMs(",
                    source,
                    "%s must take its %s timeout from the shared policy" % (name, what),
                )

    def test_the_mjs_timeout_helper_node_suite_passes(self):
        result = subprocess.run(
            ["node", "--test", str(REPO / "perf" / "tests" / "test_load_timeout.mjs")],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ThrottleTolerance(unittest.TestCase):
    """Item 4: max(1 ms, 1 % of the sample's span) of cgroup throttling is
    tolerated, recorded on every kept sample, and refused above."""

    def test_the_tolerance_rule(self):
        api = _load("perf.runner.browser_throttle")
        self.assertEqual(float(api.THROTTLE_TOLERANCE_MIN_USEC), 1000.0)
        self.assertEqual(float(api.THROTTLE_TOLERANCE_SPAN_FRACTION), 0.01)
        self.assertEqual(api.throttle_tolerance_usec(None), 1000.0)
        self.assertEqual(api.throttle_tolerance_usec(50.0), 1000.0)
        self.assertEqual(api.throttle_tolerance_usec(10_000.0), 100_000.0)

    def test_within_tolerance_decision(self):
        api = _load("perf.runner.browser_throttle")
        self.assertTrue(api.throttled_within_tolerance({"throttled_usec": 900}, None))
        self.assertTrue(api.throttled_within_tolerance({"throttled_usec": 90_000}, 10_000.0))
        self.assertFalse(api.throttled_within_tolerance({"throttled_usec": 5_000}, None))
        self.assertFalse(api.throttled_within_tolerance({"throttled_usec": 200_000}, 1_000.0))
        self.assertTrue(api.throttled_within_tolerance({}, None))

    def _run(self, reader):
        from perf.runner.browser_run import BrowserRun

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return BrowserRun(
            tmp.name, "fake", seed=7, run_id="lax", snapshot=lambda: {}, accounting_reader=reader
        )

    def test_a_small_throttle_is_kept_and_recorded(self):
        state = {
            "n": 2,
            "usec": 10,
            "t": 1_000.0,
        }

        def reader():
            return dict(
                available=True,
                nr_periods=10 + state["n"],
                nr_throttled=state["n"],
                throttled_usec=state["usec"],
                cpu_ticks=dict(total=100, steal=1),
                loadavg=[2.0, 3.0, 4.0],
                cpu_max="800000 100000",
                cpu_count_visible=64,
                cgroup_path="/fake/cgroup",
                monotonic_ms=state["t"],
            )

        run = self._run(reader)
        run.begin_sample()
        state.update(n=3, usec=910, t=1_200.0)  # 900 usec over a 200 ms span
        path = run.sample("kept", dict(outcome="measured", samples_ms=[12]))
        row = json.loads(path.read_text())
        self.assertEqual(row["outcome"], "measured")
        self.assertEqual(row["throttled_usec"], 900)
        self.assertEqual(row["nr_throttled"], 1)
        self.assertEqual(row["samples_ms"], [12])
        summary = run.finish({"publishable": True})["cpu_accounting"]
        self.assertEqual(summary["samples_refused"], 0)
        self.assertEqual(summary["samples_throttled_kept"], 1)

    def test_throttling_above_one_percent_of_the_span_still_refuses(self):
        state = {"n": 2, "usec": 10, "t": 1_000.0}

        def reader():
            return dict(
                available=True,
                nr_periods=10 + state["n"],
                nr_throttled=state["n"],
                throttled_usec=state["usec"],
                cpu_ticks=dict(total=100, steal=1),
                loadavg=[2.0, 3.0, 4.0],
                cpu_max="800000 100000",
                cpu_count_visible=64,
                cgroup_path="/fake/cgroup",
                monotonic_ms=state["t"],
            )

        run = self._run(reader)
        run.begin_sample()
        state.update(n=3, usec=21_000, t=1_200.0)  # 20 ms over a 200 ms span = 10 %
        path = run.sample("refused", dict(outcome="measured", samples_ms=[12]))
        row = json.loads(path.read_text())
        self.assertEqual((row["outcome"], row["failure_reason"]), ("failed", "cpu_throttled"))
        self.assertNotIn("samples_ms", row)
        self.assertIn("rejected_evidence_directory", row)

    def test_the_c10_gate_applies_the_same_tolerance(self):
        c10 = _load("perf.runner.adversarial_c10_scroll")
        kept = {"cpu_accounting": {"available": True, "span_ms": 10_000.0,
                                   "delta": {"nr_throttled": 2, "throttled_usec": 90_000}}}
        self.assertIsNone(c10.throttle_refusal_reason(kept))
        refused = {"cpu_accounting": {"available": True, "span_ms": 10_000.0,
                                      "delta": {"nr_throttled": 2, "throttled_usec": 900_000}}}
        self.assertEqual(c10.throttle_refusal_reason(refused), "cpu_throttled")
        no_span = {"cpu_accounting": {"available": True,
                                      "delta": {"nr_throttled": 1, "throttled_usec": 5_000}}}
        self.assertEqual(c10.throttle_refusal_reason(no_span), "cpu_throttled")
        labelled = {"failure_reason": "cpu_throttled"}
        self.assertEqual(c10.throttle_refusal_reason(labelled), "cpu_throttled")


if __name__ == "__main__":
    unittest.main()


class UnavailableAccountingDisclosure(unittest.TestCase):
    """A sample whose CPU accounting is unavailable stays measurable with the
    refusal named; a publishable=False row carries its block reason (darwin
    local runs at ``--host-class dedicated`` hit this on every sample)."""

    def test_unavailable_accounting_rows_carry_a_block_reason(self):
        from perf.runner.browser_run import BrowserRun

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        run = BrowserRun(
            tmp.name, "fake", seed=8, run_id="lax2", snapshot=lambda: {},
            accounting_reader=lambda: {"available": False, "reason": "cgroup v2 CPU accounting unavailable on darwin"},
        )
        run.begin_sample()
        path = run.sample("kept", dict(outcome="measured", samples_ms=[12]))
        row = json.loads(path.read_text())
        self.assertEqual(row["outcome"], "measured")
        self.assertEqual(row["refusal_code"], "cpu_accounting_unavailable")
        self.assertFalse(row["publishable"])
        self.assertEqual(row["publication_block_reason"], "cpu_accounting_unavailable")
        self.assertEqual(row["samples_ms"], [12])
