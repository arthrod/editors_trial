import json
import tempfile
import unittest
from pathlib import Path

from perf.runner.artifacts import write_attempt
from perf.runner.browser_memory import detached_dom_verdict, validate_browser_memory
from perf.runner.memory import validate_memory_sample
from perf.runner.order import editor_order
from perf.runner.policy import publication_decision
from perf.runner.schedule import enqueue_cache_states, plan_attempts, profile_rank
from perf.scenarios.catalog import scenarios


def _trial():
    return {
        "outcome": "measured",
        "boundary": "handler_duration",
        "claims": [],
        "samples_ms": [1.5],
        "latency_ms": None,
    }


def _env(**overrides):
    env = {
        "host_class": "dedicated",
        "cache_state": "process_cold_fs_warm",
        "run_kind": "timing",
        "repetition_unit": "fresh_process",
    }
    env.update(overrides)
    return env


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

    def test_rejects_a_trailing_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as caught:
                write_attempt(Path(tmp), "attempt-1\n", _trial())
            self.assertIn("attempt_id", str(caught.exception))


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


class Memory(unittest.TestCase):
    def _sample(self, **overrides):
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

    def test_accepts_a_process_tree_sample(self):
        validate_memory_sample(self._sample())

    def test_rejects_a_single_missing_process(self):
        with self.assertRaises(ValueError) as caught:
            validate_memory_sample(self._sample(process_count=0))
        self.assertIn("process_count", str(caught.exception))

    def test_rejects_a_missing_cgroup_field(self):
        sample = self._sample()
        del sample["cgroup_peak_bytes"]
        with self.assertRaises(ValueError) as caught:
            validate_memory_sample(sample)
        self.assertIn("cgroup_peak_bytes", str(caught.exception))

    def test_rejects_pss_above_rss(self):
        with self.assertRaises(ValueError) as caught:
            validate_memory_sample(self._sample(pss_bytes=5000))
        self.assertIn("pss_bytes", str(caught.exception))


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


def _browser_record(**overrides):
    record = {
        "run_kind": "diagnostic",
        "cross_origin_isolated": True,
        "heap_snapshot": False,
        "js_heap": {"source": "measureUserAgentSpecificMemory", "role": "page_estimate", "status": "available"},
        "dom": {"source": "Memory.getDOMCounters", "documents": 1, "nodes": 10, "js_event_listeners": 2},
        "wasm": {"status": "available", "byte_length": 65536, "meaning": "capacity"},
    }
    record.update(overrides)
    return record


class BrowserMemory(unittest.TestCase):
    def test_used_js_heap_is_diagnostic_only(self):
        with self.assertRaises(ValueError) as caught:
            validate_browser_memory(
                _browser_record(
                    js_heap={"source": "usedJSHeapSize", "role": "page_total", "status": "available"}
                )
            )
        self.assertIn("usedJSHeapSize", str(caught.exception))

    def test_measure_memory_requires_cross_origin_isolation(self):
        with self.assertRaises(ValueError) as caught:
            validate_browser_memory(_browser_record(cross_origin_isolated=False))
        self.assertIn("cross_origin_isolated", str(caught.exception))

    def test_dom_counters_do_not_count_detached_nodes(self):
        dom = {"source": "Memory.getDOMCounters", "documents": 1, "nodes": 10, "detached_nodes": 3}
        with self.assertRaises(ValueError) as caught:
            validate_browser_memory(_browser_record(dom=dom))
        self.assertIn("getDOMCounters", str(caught.exception))

    def test_inaccessible_wasm_memory_is_null(self):
        validate_browser_memory(_browser_record(wasm={"status": "unverified", "byte_length": None, "meaning": "capacity"}))
        with self.assertRaises(ValueError) as caught:
            validate_browser_memory(_browser_record(wasm={"status": "unverified", "byte_length": 0, "meaning": "capacity"}))
        self.assertIn("byte_length", str(caught.exception))

    def test_heap_snapshot_is_not_a_timing_sample(self):
        with self.assertRaises(ValueError) as caught:
            validate_browser_memory(_browser_record(run_kind="timing", heap_snapshot=True))
        self.assertIn("diagnostic", str(caught.exception))

    def test_detached_subtree_is_red_and_a_clean_release_is_green(self):
        self.assertEqual(detached_dom_verdict({"retained_by_test": True, "detached_nodes": 4}), "red")
        self.assertEqual(detached_dom_verdict({"retained_by_test": False, "detached_nodes": 0}), "green")
        self.assertEqual(detached_dom_verdict({"retained_by_test": False, "detached_nodes": 2}), "fail")


class Schedule(unittest.TestCase):
    def test_profile_rank_orders_low_resource_first(self):
        self.assertLess(profile_rank("ci_contract"), profile_rank("ci_broad"))
        self.assertLess(profile_rank("ci_broad"), profile_rank("dedicated_publish"))

    def test_ci_contract_drops_os_cache_cold(self):
        startup = next(row for row in scenarios() if row["id"] == "C01")
        env = {"execution_profile": "ci_contract", "host_class": "ci_coarse", "headless": True}
        self.assertNotIn("os_cache_cold", enqueue_cache_states(startup, env))

    def test_dedicated_publish_keeps_os_cache_cold(self):
        startup = next(row for row in scenarios() if row["id"] == "C01")
        env = {"execution_profile": "dedicated_publish", "host_class": "dedicated", "headless": False}
        self.assertIn("os_cache_cold", enqueue_cache_states(startup, env))

    def test_long_session_not_run_on_ci_broad(self):
        soak = next(row for row in scenarios() if row["id"] == "C20")
        env = {
            "execution_profile": "ci_broad",
            "host_class": "ci_coarse",
            "headless": False,
            "repetition_unit": "fresh_process",
            "workload_id": "micro-paragraphs",
        }
        decision = plan_attempts(soak, env, "docxodus", "browser")
        self.assertFalse(decision["run"])
        self.assertEqual(decision["failure_reason"], "execution_profile")

    def test_model_load_runs_on_ci_contract(self):
        load = next(row for row in scenarios() if row["id"] == "C02")
        env = {
            "execution_profile": "ci_contract",
            "host_class": "ci_coarse",
            "headless": True,
            "repetition_unit": "fresh_process",
            "workload_id": "micro-paragraphs",
        }
        decision = plan_attempts(load, env, "folio", "headless")
        self.assertTrue(decision["run"])
        self.assertEqual(decision["sample_budget"], 1)

    def test_contract_skips_disallowed_workload(self):
        load = next(row for row in scenarios() if row["id"] == "C02")
        env = {
            "execution_profile": "ci_contract",
            "host_class": "ci_coarse",
            "headless": True,
            "repetition_unit": "fresh_process",
            "workload_id": "short-paragraphs",
        }
        decision = plan_attempts(load, env, "folio", "model")
        self.assertFalse(decision["run"])
        self.assertEqual(decision["failure_reason"], "execution_profile")

    def test_browser_visible_not_run_on_ci_contract(self):
        row = next(r for r in scenarios() if r["id"] == "C05")
        env = {
            "execution_profile": "ci_contract",
            "host_class": "ci_coarse",
            "headless": True,
            "repetition_unit": "fresh_process",
            "workload_id": "micro-paragraphs",
        }
        decision = plan_attempts(row, env, "plate", "browser_slate")
        self.assertFalse(decision["run"])
        self.assertEqual(decision["failure_reason"], "execution_profile")


if __name__ == "__main__":
    unittest.main()
