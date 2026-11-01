#!/usr/bin/env python3
"""Report B's XSD and package-integrity columns come from the scripts that measure
them (validate_all_outputs.py, malformation_audit.py), never typed: v0.9.2 published
Plate.js as schema-clean when its output has a w:sectPr before the first paragraph."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates/reports/Report B - Malformed Parts, Causes and Repair (2026).md"


class IntegrityFacts(unittest.TestCase):
    def test_counts_and_labels_come_from_the_measurement_files(self):
        with tempfile.TemporaryDirectory() as d:
            x, p = Path(d) / "xsd.json", Path(d) / "pkg.json"
            x.write_text(json.dumps({"plate": 1, "superdoc": 0}))
            p.write_text(json.dumps({"plate": {}, "officeopen": {"DANGLING-REL": 5}}))
            f = {}
            facts.integrity_facts(x, p, f)
        self.assertEqual(f["xsd.plate.real"], 1)
        self.assertEqual(f["xsd.superdoc.real"], 0)
        self.assertEqual(f["pkg.plate"], "clean")
        self.assertEqual(f["pkg.officeopen"], "**5 dangling relationship ids**")


class ReportBTable(unittest.TestCase):
    def test_no_typed_figure_in_the_xsd_table_and_apryse_has_a_row(self):
        s = TEMPLATE.read_text()
        head = s.index("| Editor | Real XSD violations |")
        rows = s[head:s.index("\n\n", head)].splitlines()[2:]
        self.assertTrue(any("Apryse" in r for r in rows))
        for r in rows:
            cells = [c.strip() for c in r.strip("|").split("|")]
            self.assertRegex(cells[1], r"\{\{xsd\.[a-z_]+\.real\}\}", r)
            self.assertRegex(cells[2], r"\{\{pkg\.[a-z_]+\}\}", r)
            self.assertRegex(cells[3], r"\{\{word\.[a-z_]+\.cell\}\}", r)


if __name__ == "__main__":
    unittest.main()
