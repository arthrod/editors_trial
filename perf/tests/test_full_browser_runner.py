import json
import unittest
from pathlib import Path

from perf.runner import benchmark_full_browser as bfb

REPO = Path(__file__).resolve().parents[2]


class FullBrowserRunner(unittest.TestCase):
    def test_dry_run_writes_summary_skeleton(self):
        out = REPO / "perf/out/_test_full_browser_dry"
        if out.is_dir():
            for p in out.rglob("*"):
                if p.is_file():
                    p.unlink()
        code = bfb.main(["--dry-run", "--out-root", str(out)])
        self.assertEqual(code, 0)
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["suite"], "full_browser")


if __name__ == "__main__":
    unittest.main()
