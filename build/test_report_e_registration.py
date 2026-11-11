"""Report E is published like Reports A-D: a template, a DOCX twin, a Word-checked deliverable.

Run: python3 -m unittest build.test_report_e_registration
"""
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT))

import render_reports  # noqa: E402
import verify_deliverables  # noqa: E402
from perf.analysis.anti_ranking import assert_markdown_no_editor_speed_ranking  # noqa: E402

NAME = "Report E - Speed, Opening and Saving a Document (2026)"
REL = f"reports/{NAME}.md"


class ReportERegistration(unittest.TestCase):
    def test_the_template_exists(self):
        self.assertTrue((render_reports.TEMPLATES / REL).is_file())

    def test_it_ships_a_docx_twin(self):
        self.assertIn(REL, render_reports.TWINS)

    def test_word_opens_its_twin_at_the_gate(self):
        paths = [os.path.basename(p) for p, _ in verify_deliverables.DELIVERABLES]
        self.assertIn(f"{NAME}.docx", paths)

    def test_every_placeholder_is_a_perf_e_fact(self):
        text = (render_reports.TEMPLATES / REL).read_text()
        keys = re.findall(r"\{\{\s*([^}\s]+)\s*\}\}", text)
        self.assertTrue(keys)
        self.assertEqual([k for k in keys if not k.startswith("perf.e.")], [])

    def test_the_template_claims_no_untraced_cause_for_a_save(self):
        # #124 finding 2, pi's #126 F1: where an editor does its export work was not traced
        text = (render_reports.TEMPLATES / REL).read_text()
        self.assertNotIn("during load", text)
        self.assertNotIn("prepared during", text)

    def test_the_template_prose_does_not_rank(self):
        text = (render_reports.TEMPLATES / REL).read_text()
        assert_markdown_no_editor_speed_ranking(text)


if __name__ == "__main__":
    unittest.main()
