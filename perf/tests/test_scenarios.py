import unittest

from perf.scenarios.catalog import scenarios


class ExecutionProfile(unittest.TestCase):
    def test_every_scenario_names_a_minimum_profile(self):
        for row in scenarios():
            self.assertIn(
                row["min_execution_profile"],
                ("ci_contract", "ci_broad", "dedicated_publish"),
            )

    def test_model_and_wasm_scenarios_run_on_ci_contract(self):
        for criterion_id in ("C02", "C04", "C13", "C15", "C16", "C17", "C19", "C21", "C24"):
            row = next(item for item in scenarios() if item["id"] == criterion_id)
            self.assertEqual(row["min_execution_profile"], "ci_contract")

    def test_visible_interaction_requires_ci_broad(self):
        for criterion_id in ("C05", "C06", "C07", "C08", "C09", "C10"):
            row = next(item for item in scenarios() if item["id"] == criterion_id)
            self.assertEqual(row["min_execution_profile"], "ci_broad")

    def test_long_session_requires_dedicated_publish(self):
        soak = next(row for row in scenarios() if row["id"] == "C20")
        self.assertEqual(soak["min_execution_profile"], "dedicated_publish")


if __name__ == "__main__":
    unittest.main()
