"""Warm/cold benchmark honesty guardrails."""

import json
import unittest
from pathlib import Path

from perf.runner.cause_attribution import (
    C05_PROBE_KEY,
    C06_PROBE_KEY,
    assert_same_probe_paired,
    assert_warm_cold_distinct,
    attribute_delta,
)
from perf.schema import validate_environment


class WarmColdHonesty(unittest.TestCase):
    def test_warm_samples_must_not_copy_cold(self):
        with self.assertRaises(ValueError):
            assert_warm_cold_distinct([10.0, 11.0, 12.0], [10.0, 11.0, 12.0])
        assert_warm_cold_distinct([100.0, 110.0, 120.0], [12.0, 13.0, 14.0])

    def test_os_cache_cold_rejected_on_ci_coarse(self):
        env = {
            "host_class": "ci_coarse",
            "execution_profile": "ci_broad",
            "cache_state": "os_cache_cold",
            "page_cache_dropped": True,
            "headless": True,
            "repetition_unit": "fresh_process",
            "run_kind": "timing",
            "feature_profile": "P0",
            "feature_fallback": [],
            "ram_bytes": 1024 * 1024 * 1024,
            "cpu_model": "x",
            "os": "linux",
            "arch": "x86_64",
            "power_source": "unknown",
            "editor_id": "plate",
            "editor_version": "test",
            "workload_id": "micro-paragraphs",
            "fixture_sha256": "a" * 64,
            "fixture_byte_size": 100,
            "fixture_paragraph_count": 5,
            "paragraph_shape": "micro",
            "unicode_class": "ascii",
            "match_count": 0,
            "interpretation_conditions": ["I%02d" % n for n in range(1, 13)],
            "display_refresh_hz": None,
        }
        with self.assertRaises(ValueError) as caught:
            validate_environment(env)
        self.assertIn("os_cache_cold", str(caught.exception))

    def test_c06_must_not_hardcode_residual_steady_state_cause(self):
        runner = Path(__file__).resolve().parents[1] / "runner" / "benchmark_warm_cold.py"
        text = runner.read_text(encoding="utf-8")
        self.assertNotIn(
            'cause="residual_steady_state"',
            text,
            "C06 paired row must call attribute_delta, not hardcode residual_steady_state",
        )
        self.assertIn("attribute_delta", text)
        self.assertIn("cause_burst", text)

    def test_c06_must_not_pair_different_probe_keys(self):
        with self.assertRaises(ValueError):
            assert_same_probe_paired(C05_PROBE_KEY, C06_PROBE_KEY)
        assert_same_probe_paired(C06_PROBE_KEY, C06_PROBE_KEY)

    def test_docxodus_ready_waits_for_rendered_not_page_count_only(self):
        runner = Path(__file__).resolve().parents[1] / "runner" / "benchmark_warm_cold.py"
        text = runner.read_text(encoding="utf-8")
        self.assertIn("__docxodus.rendered", text)
        self.assertNotIn("pageCount > 0", text)

    def test_c06_large_delta_uses_attribute_delta_not_literal_residual(self):
        probes = {
            "browser_launch_only_median": 25.0,
            "document_navigation_only_median": 776.0,
            "model_ready_browser_median": 314.0,
            "document_reload_same_context_median": 821.0,
        }
        cause, breakdown = attribute_delta(128.0, 100.0, probes)
        self.assertNotEqual(
            cause,
            "residual_steady_state",
            "28 ms overhead must not be attributed via hardcoded residual_steady_state",
        )
        self.assertIn(cause, ("mixed_unresolved", "browser_launch", "document_parse", "wasm_js_compile"))
        self.assertAlmostEqual(breakdown["overhead_ms"], 28.0)

    def test_c03_reload_warm_slower_must_not_be_residual_steady_state(self):
        """C03 warm arm uses document_reload; slower warm must not look like steady state."""
        probes = {
            "browser_launch_only_median": 24.0,
            "document_navigation_only_median": 772.0,
            "model_ready_browser_median": 277.0,
            "document_reload_same_context_median": 797.0,
        }
        cause, breakdown = attribute_delta(277.0, 797.0, probes)
        self.assertNotEqual(cause, "residual_steady_state")
        self.assertEqual(cause, "document_parse")
        self.assertEqual(breakdown.get("warm_arm_probe"), "document_reload_same_context")

    def test_small_positive_overhead_may_still_be_residual_steady_state(self):
        probes = {
            "browser_launch_only_median": 24.0,
            "document_navigation_only_median": 100.0,
            "model_ready_browser_median": 90.0,
            "document_reload_same_context_median": 200.0,
        }
        cause, _breakdown = attribute_delta(100.0, 88.0, probes)
        self.assertEqual(cause, "residual_steady_state")

    def test_c06_same_probe_retains_attribute_delta_overhead_band(self):
        probes = {
            "browser_launch_only_median": 24.0,
            "document_navigation_only_median": 772.0,
            "model_ready_browser_median": 277.0,
            "document_reload_same_context_median": 797.0,
        }
        cause, breakdown = attribute_delta(100.0, 84.0, probes)
        self.assertEqual(cause, "browser_launch")
        self.assertAlmostEqual(breakdown["overhead_ms"], 16.0)

    def test_warm_cold_summary_never_labels_os_cache_cold(self):
        root = Path(__file__).resolve().parents[2] / "perf" / "out"
        for sub in root.glob("warm_cold_*"):
            summary_path = sub / "summary.json"
            if not summary_path.is_file():
                continue
            attempts = sub / "attempts"
            if attempts.is_dir():
                for path in attempts.glob("*.json"):
                    trial = json.loads(path.read_text(encoding="utf-8"))
                    env = trial.get("environment") or {}
                    self.assertNotEqual(
                        env.get("cache_state"),
                        "os_cache_cold",
                        "warm_cold attempt %s must not use os_cache_cold on CI" % path.name,
                    )


if __name__ == "__main__":
    unittest.main()
