#!/usr/bin/env python3
"""A participant joins every lane: a measurement script that reads one editor's
output reads every editor's. v0.9.2 added Apryse to the round trip but not to the
scripts behind six tables in Reports A, A2, B and C, which went out without its row."""
import re
import unittest
from pathlib import Path

BUILD = Path(__file__).resolve().parent
# An output path per tool, as the scripts write it.
OUT = {"superdoc": "out/superdoc/complex.docx", "apryse": "out/apryse/complex.docx"}


class EveryLane(unittest.TestCase):
    def test_a_script_reading_superdoc_output_reads_apryse_output(self):
        missing = []
        for py in sorted(BUILD.glob("*.py")):
            # test_* are tests; *_patch* scripts are one-off historical edits, not measurements
            # superdoc_detail.py re-derives SuperDoc-only claims by design
            if py.name.startswith("test_") or "_patch" in py.name or py.name == "superdoc_detail.py":
                continue
            s = py.read_text()
            reads = lambda t: (OUT[t] in s
                               or re.search(r'"out",\s*"%s"' % t, s)
                               or re.search(r'"out"\s*/\s*"%s"' % t, s)
                               # an editor list of (label, slug) pairs, joined to out/<slug> later
                               or re.search(r'\(\s*"[^"]+",\s*"%s"\s*\)' % t, s))
            if reads("superdoc") and not reads("apryse"):
                missing.append(py.name)
        self.assertEqual(missing, [])

    def test_an_editor_list_with_docxodus_has_apryse(self):
        """Scripts that read page images by label (construct_presence.py) or an
        inventory by key never name out/<tool>/complex.docx, so the test above
        misses them. Any list literal of editors that names the participant before
        Apryse names Apryse too."""
        # retired: nothing runs them and no report reads them (render_report.py and
        # visual_signatures.py predate the templates; ns_group_tables.py patched a
        # rendered report, which AGENTS.md section 5 forbids; ns_tables.py replaced it)
        retired = {"render_report.py", "visual_signatures.py", "ns_group_tables.py"}
        missing = []
        for py in sorted(BUILD.glob("*.py")):
            if py.name.startswith("test_") or "_patch" in py.name or py.name in retired:
                continue
            for m in re.finditer(r"\[[^\[\]]*\]", py.read_text()):
                lst = m.group(0)
                if re.search(r'"docxodus"', lst) and re.search(r'"libreoffice"', lst) and '"apryse"' not in lst:
                    missing.append(py.name)
                    break
        self.assertEqual(missing, [])

    def test_a_script_that_lists_the_participants_takes_the_pending_lanes(self):
        """A lane that runs but is not published (build/lanes.py) is half-wired if one
        script that lists the participants does not pass its list through lanes.join
        (or read lanes.requested). The next participant starts as a pending lane, so
        this is the check that it reaches every script from its first commit."""
        # Each exemption says where the lane joins instead.
        exempt = {
            "lanes.py": "the registry itself",
            "defect_survival.py": "its rows need committed publication outputs in out_broken/ "
                                  "(test_defect_survival); a lane joins EDITORS at the release that publishes it "
                                  "(the four of v0.11.0 are in the list itself)",
            "outreach_issues.py": "vendor anchors, held to vendors.md by test_report_claims",
        }
        retired = {"render_report.py", "visual_signatures.py", "ns_group_tables.py", "superdoc_detail.py"}
        missing = []
        for py in sorted(BUILD.glob("*.py")):
            if py.name.startswith("test_") or "_patch" in py.name or py.name in retired or py.name in exempt:
                continue
            s = py.read_text()
            lists_them = ('"apryse"' in s and ('"docxodus"' in s or '"superdoc"' in s)) or "/apryse/complex.docx" in s
            if lists_them and "lanes." not in s:
                missing.append(py.name)
        self.assertEqual(missing, [])

    def test_report_c_package_table_is_generated_with_apryse(self):
        import sys
        sys.path.insert(0, str(BUILD))
        import inventory_table
        head = inventory_table.table().splitlines()[0]
        self.assertIn("apryse", head)
        t = (BUILD.parent / "templates/reports/Report C - Rendering Versus Word (2026).md").read_text()
        self.assertIn("{{inventory.table}}", t)
        self.assertNotIn("| Construct | In the corpus | Word draws it | superdoc", t)


class PartMatrix(unittest.TestCase):
    def test_report_a2_prints_the_generated_matrix_with_every_editor(self):
        import sys
        sys.path.insert(0, str(BUILD))
        import part_matrix_md
        md = part_matrix_md.markdown()
        self.assertIn("Apryse", md)
        self.assertEqual(md.count("| Package part |"), 4)
        t = (BUILD.parent / "templates/reports/Report A2 - Pass-Through (2026).md").read_text()
        self.assertIn("{{parts.matrix}}", t)
        self.assertNotIn("| Package part | Plate.js |", t)


if __name__ == "__main__":
    unittest.main()
