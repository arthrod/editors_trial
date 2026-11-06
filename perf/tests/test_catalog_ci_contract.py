"""Full C01–C24 catalog coverage for ci_contract runner."""

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import perf.runner.benchmark_ci_contract as bcc


class CatalogContract(unittest.TestCase):
    def test_dry_run_emits_all_criteria_and_editors(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with patch.object(bcc, "date") as mock_date:
                mock_date.today = lambda: date(2099, 1, 1)
                argv = ["prog", "--dry-run", "--out-root", str(out)]
                with patch.object(sys, "argv", argv):
                    rc = bcc.main()
            self.assertEqual(rc, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        editors = {r["editor_id"] for r in summary["editors"]}
        crit = {(r["criterion_id"], r["editor_id"]) for r in summary["editors"]}
        self.assertEqual(editors, set(bcc.EDITORS))
        self.assertEqual(len(crit), 24 * 14)
        for cid in [f"C{i:02d}" for i in range(1, 25)]:
            for ed in bcc.EDITORS:
                self.assertIn((cid, ed), crit)

    def test_load_timing_parses_perf_line(self):
        from perf.runner.load_timing import parse_perf_lines

        perf = parse_perf_lines("", "noise\nPERF model_ready_ms=12.5\n")
        self.assertEqual(perf["model_ready_ms"], 12.5)


if __name__ == "__main__":
    unittest.main()
