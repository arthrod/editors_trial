import json
import tempfile
import unittest
from pathlib import Path

from perf.runner.artifacts import write_attempt
from perf.runner.memory import validate_memory_sample
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
        env = {"execution_profile": "ci_broad", "host_class": "ci_coarse", "headless": False, "repetition_unit": "fresh_process"}
        decision = plan_attempts(soak, env, "docxodus", "browser")
        self.assertFalse(decision["run"])
        self.assertEqual(decision["failure_reason"], "execution_profile")

    def test_model_load_runs_on_ci_contract(self):
        load = next(row for row in scenarios() if row["id"] == "C02")
        env = {"execution_profile": "ci_contract", "host_class": "ci_coarse", "headless": True, "repetition_unit": "fresh_process"}
        decision = plan_attempts(load, env, "folio", "headless")
        self.assertTrue(decision["run"])
        self.assertEqual(decision["sample_budget"], 1)
        self.assertTrue(decision["publishable"])

    def test_dedicated_publish_on_ci_coarse_drops_os_cache_cold(self):
        startup = next(row for row in scenarios() if row["id"] == "C01")
        env = {"execution_profile": "dedicated_publish", "host_class": "ci_coarse", "headless": True}
        self.assertNotIn("os_cache_cold", enqueue_cache_states(startup, env))

    def test_ci_contract_skips_browser_visible_scenarios(self):
        typing = next(row for row in scenarios() if row["id"] == "C05")
        env = {"execution_profile": "ci_contract", "host_class": "ci_coarse", "headless": True, "repetition_unit": "fresh_process"}
        decision = plan_attempts(typing, env, "plate", "browser")
        self.assertFalse(decision["run"])
        self.assertEqual(decision["failure_reason"], "execution_profile")
        self.assertFalse(decision["publishable"])

    def test_diagnostic_native_run_is_not_publishable(self):
        allocation = next(row for row in scenarios() if row["id"] == "C18")
        env = {"execution_profile": "ci_broad", "host_class": "ci_coarse", "headless": True, "repetition_unit": "fresh_process"}
        decision = plan_attempts(allocation, env, "docxodus", "browser")
        self.assertTrue(decision["run"])
        self.assertFalse(decision["publishable"])

    def test_not_run_decision_is_not_publishable(self):
        soak = next(row for row in scenarios() if row["id"] == "C20")
        env = {"execution_profile": "ci_broad", "host_class": "ci_coarse", "headless": False, "repetition_unit": "fresh_process"}
        decision = plan_attempts(soak, env, "docxodus", "browser")
        self.assertFalse(decision["run"])
        self.assertFalse(decision["publishable"])


from perf.runner.exclusive import assert_exclusive_editor


class ExclusiveEditor(unittest.TestCase):
    def test_ci_coarse_allows_no_active_editor_groups(self):
        assert_exclusive_editor("ci_coarse", 0)

    def test_ci_coarse_allows_one_active_editor_group(self):
        assert_exclusive_editor("ci_coarse", 1)

    def test_ci_coarse_rejects_parallel_editor_groups(self):
        with self.assertRaises(ValueError) as caught:
            assert_exclusive_editor("ci_coarse", 2)
        self.assertIn("ci_coarse", str(caught.exception))

    def test_dedicated_host_allows_parallel_groups(self):
        assert_exclusive_editor("dedicated", 3)


from perf.runner.cgroup_limits import cgroup_limit_sweep


class CgroupLimits(unittest.TestCase):
    def test_sweep_is_diagnostic_on_dedicated_publish(self):
        limits = {"cpu_max": "200000", "memory_max": "4G"}
        result = cgroup_limit_sweep("dedicated_publish", limits)
        self.assertEqual(result["run_kind"], "diagnostic")
        self.assertFalse(result["publishable"])
        self.assertEqual(result["limits"], limits)

    def test_sweep_is_rejected_off_dedicated_publish(self):
        with self.assertRaises(ValueError):
            cgroup_limit_sweep("ci_broad", {"cpu_max": "100000"})


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


if __name__ == "__main__":
    unittest.main()
