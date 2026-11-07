import unittest

from perf.runner.schedule import plan_attempts
from perf.scenarios.catalog import scenarios


class C20SoakSchedule(unittest.TestCase):
    def test_c20_runs_on_laboratory_dedicated_publish(self):
        c20 = next(r for r in scenarios() if r["id"] == "C20")
        env = {
            "execution_profile": "dedicated_publish",
            "host_class": "laboratory",
            "workload_id": "short-paragraphs",
            "repetition_unit": "fresh_process",
        }
        plan = plan_attempts(c20, env, "plate", "editor")
        self.assertTrue(plan["run"])


if __name__ == "__main__":
    unittest.main()
