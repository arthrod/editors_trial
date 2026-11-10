"""A quantized-equality is a recorded flag, not a run-killing crash.

``assert_warm_cold_distinct`` stays strict: identical cold/warm sample arrays
are a copy signal and raise. But the browser probe stamps with integer
``Date.now()`` milliseconds, so for a fast edit the arrays can be *legitimately*
equal (all 83 ms). The runner therefore catches that verdict, records
``warm_equals_cold`` in the summary row, and keeps going — a five-minute pass
must not be destroyed by a millisecond-level coincidence, and a real copy is
still visible in the artifact.
"""

import unittest

from perf.runner.cause_attribution import assert_warm_cold_distinct


class StrictGuardTest(unittest.TestCase):
    def test_identical_arrays_still_raise(self):
        with self.assertRaises(ValueError):
            assert_warm_cold_distinct([10.0, 11.0, 12.0], [10.0, 11.0, 12.0])
        with self.assertRaises(ValueError):
            assert_warm_cold_distinct([83, 83, 83], [83, 83, 83])

    def test_different_arrays_pass(self):
        assert_warm_cold_distinct([100.0, 110.0, 120.0], [12.0, 13.0, 14.0])


class RunnerFlagTest(unittest.TestCase):
    def test_runner_helper_reports_equality_instead_of_raising(self):
        from perf.runner.benchmark_warm_cold import warm_equals_cold

        self.assertTrue(warm_equals_cold([83, 84, 83], [83, 84, 83]))
        self.assertFalse(warm_equals_cold([83, 84, 83], [90, 84, 83]))


if __name__ == "__main__":
    unittest.main()
