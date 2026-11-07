import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class PlateBrowserCriteria(unittest.TestCase):
    def test_browser_interactions_exports_c07(self):
        text = (REPO / "perf/runner/browser_interactions.mjs").read_text(encoding="utf-8")
        self.assertIn("c07_caret", text)
        self.assertIn("c08_paste", text)


if __name__ == "__main__":
    unittest.main()
