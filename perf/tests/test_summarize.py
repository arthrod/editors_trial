import unittest

from perf.analysis.summarize import median_absolute_deviation, percentile


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


if __name__ == "__main__":
    unittest.main()
