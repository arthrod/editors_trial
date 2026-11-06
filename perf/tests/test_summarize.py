import unittest

from perf.analysis.summarize import bootstrap_median_ci, median_absolute_deviation, percentile


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


if __name__ == "__main__":
    unittest.main()
