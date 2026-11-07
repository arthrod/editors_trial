"""Adversarial C10 scroll probe wiring."""

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class AdversarialC10(unittest.TestCase):
    def test_scroll_runner_files_exist(self):
        py = REPO / "perf" / "runner" / "adversarial_c10_scroll.py"
        mjs = REPO / "perf" / "runner" / "adversarial_c10_scroll.mjs"
        self.assertTrue(py.is_file())
        self.assertTrue(mjs.is_file())
        self.assertIn("scroll_frame_ms", mjs.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
