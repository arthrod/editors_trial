import unittest
from pathlib import Path

from perf.runner import benchmark_pixels_lo as bpl


REPO = Path(__file__).resolve().parents[2]


class PixelsLoRunnerPaths(unittest.TestCase):
    def test_default_lo_baseline_is_repo_local(self):
        raw = str(bpl.DEFAULT_LO_BASELINE)
        self.assertNotIn("/Users/", raw)
        self.assertTrue(bpl.DEFAULT_LO_BASELINE.is_relative_to(REPO))

    def test_runner_source_has_no_mac_home_default(self):
        src = (REPO / "perf/runner/benchmark_pixels_lo.py").read_text(encoding="utf-8")
        self.assertNotIn("/Users/", src)


if __name__ == "__main__":
    unittest.main()
