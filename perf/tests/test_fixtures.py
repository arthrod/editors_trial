import unittest

from perf.fixtures.profiles import allowed_workloads, assert_workload_allowed, size_ladder


class WorkloadCaps(unittest.TestCase):
    def test_contract_allows_micro_only(self):
        allowed = allowed_workloads("ci_contract")
        self.assertEqual(allowed, frozenset({"micro-paragraphs", "micro-search"}))
        assert_workload_allowed("ci_contract", "micro-paragraphs")
        with self.assertRaises(ValueError) as caught:
            assert_workload_allowed("ci_contract", "short-paragraphs")
        self.assertIn("workload cap", str(caught.exception))

    def test_dedicated_allows_the_full_ladder(self):
        ladder_ids = {row["workload_id"] for row in size_ladder()}
        self.assertEqual(allowed_workloads("dedicated_publish"), frozenset(ladder_ids))


if __name__ == "__main__":
    unittest.main()
