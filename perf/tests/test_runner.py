import unittest

from perf.runner.schedule import enqueue_cache_states, plan_attempts, profile_rank
from perf.scenarios.catalog import scenarios


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
        env = {
            "execution_profile": "dedicated_publish",
            "host_class": "dedicated",
            "headless": False,
        }
        self.assertIn("os_cache_cold", enqueue_cache_states(startup, env))

    def test_long_session_not_run_on_ci_broad(self):
        soak = next(row for row in scenarios() if row["id"] == "C20")
        env = {
            "execution_profile": "ci_broad",
            "host_class": "ci_coarse",
            "headless": False,
            "repetition_unit": "fresh_process",
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
        }
        decision = plan_attempts(load, env, "folio", "headless")
        self.assertTrue(decision["run"])
        self.assertEqual(decision["sample_budget"], 1)


if __name__ == "__main__":
    unittest.main()
