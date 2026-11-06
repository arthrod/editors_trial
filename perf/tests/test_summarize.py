import unittest

from perf.analysis.summarize import (
    bootstrap_median_ci,
    median_absolute_deviation,
    percentile,
    summarize,
    summarize_groups,
)


class Spread(unittest.TestCase):
    def test_median_of_five_values(self):
        self.assertEqual(percentile([1, 2, 3, 4, 100], 50), 3)

    def test_endpoints_are_min_and_max(self):
        samples = [1, 2, 3, 4, 100]
        self.assertEqual(percentile(samples, 0), 1)
        self.assertEqual(percentile(samples, 100), 100)

    def test_mad_keeps_the_tail_in_the_deviation_list(self):
        self.assertEqual(median_absolute_deviation([1, 2, 3, 4, 100]), 1)

    def test_empty_samples_are_rejected(self):
        with self.assertRaises(ValueError) as caught:
            percentile([], 50)
        self.assertIn("empty", str(caught.exception))


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
                {"cache_state": "process_cold_fs_warm", "repetition_unit": "fresh_process", "workload_id": "short-paragraphs", "samples": [1, 2]},
                {"cache_state": "warm_steady", "repetition_unit": "fresh_process", "workload_id": "short-paragraphs", "samples": [1, 2]},
            ])
        self.assertIn("cache_state", str(caught.exception))

    def test_mixed_repetition_units_are_rejected(self):
        with self.assertRaises(ValueError) as caught:
            summarize_groups([
                {"cache_state": "warm_steady", "repetition_unit": "fresh_process", "workload_id": "short-paragraphs", "samples": [1, 2]},
                {"cache_state": "warm_steady", "repetition_unit": "in_process_iteration", "workload_id": "short-paragraphs", "samples": [1, 2]},
            ])
        self.assertIn("repetition_unit", str(caught.exception))

    def test_mixed_workloads_are_rejected(self):
        with self.assertRaises(ValueError) as caught:
            summarize_groups([
                {"cache_state": "warm_steady", "repetition_unit": "fresh_process", "workload_id": "short-paragraphs", "samples": [1, 2]},
                {"cache_state": "warm_steady", "repetition_unit": "fresh_process", "workload_id": "one-paragraph", "samples": [1, 2]},
            ])
        self.assertIn("workload_id", str(caught.exception))


class Repetition(unittest.TestCase):
    def test_startup_requires_a_fresh_process(self):
        with self.assertRaises(ValueError) as caught:
            assert_interactive_repetition("C01", "in_process_iteration")
        self.assertIn("fresh_process", str(caught.exception))

    def test_startup_accepts_a_fresh_process(self):
        assert_interactive_repetition("C01", "fresh_process")

    def test_wasm_boundary_may_use_in_process_iterations(self):
        assert_interactive_repetition("C24", "in_process_iteration")

    def test_hit_testing_requires_a_fresh_process(self):
        with self.assertRaises(ValueError) as caught:
            assert_interactive_repetition("C07", "in_process_iteration")
        self.assertIn("fresh_process", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
