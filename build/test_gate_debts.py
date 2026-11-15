#!/usr/bin/env python3
"""#215: two release-gate checks that failed on 0.9.3 leftovers."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_report_consistency as gate  # noqa: E402
import verify_findings as findings  # noqa: E402


class ScorecardRow(unittest.TestCase):
    ROWS = {
        "Apryse WebViewer 12.2.1 (closed source, trial key)": ["apryse row"],
        "SuperDoc V2": ["superdoc row"],
        "Docen": ["docen row"],
        "Docentric": ["another tool"],
    }

    def test_a_row_named_with_a_version_is_found(self):
        self.assertEqual(findings.scorecard_row(self.ROWS, "Apryse WebViewer"), ["apryse row"])

    def test_the_exact_name_wins(self):
        self.assertEqual(findings.scorecard_row(self.ROWS, "Docen"), ["docen row"])

    def test_a_longer_word_is_not_the_tool(self):
        rows = {"Docentric": ["another tool"]}
        self.assertIsNone(findings.scorecard_row(rows, "Docen"))

    def test_a_missing_row_is_missing(self):
        self.assertIsNone(findings.scorecard_row(self.ROWS, "GenOffice"))

    def test_two_candidate_rows_are_not_guessed(self):
        rows = {"Apryse WebViewer 12.2.1": ["a"], "Apryse WebViewer (trial)": ["b"]}
        self.assertIsNone(findings.scorecard_row(rows, "Apryse WebViewer"))


class CellNumber(unittest.TestCase):
    def test_a_count_with_a_note_states_the_count(self):
        self.assertEqual(findings.cell_number("9 (1 cannot be separated from the trial stamp)"), "9")
        self.assertEqual(findings.cell_number("**0**"), "0")

    def test_words_before_or_after_are_not_a_number(self):
        self.assertIsNone(findings.cell_number("about 9"))
        self.assertIsNone(findings.cell_number("9 of 99"))
        self.assertIsNone(findings.cell_number("9 (a) 3"))


class VariantDeltas(unittest.TestCase):
    def _write(self, data):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, ignore_errors=True))
        path = folder / "ab_compare.json"
        path.write_text(json.dumps(data))
        return path

    def test_each_variant_delta_is_in_the_corpus(self):
        path = self._write({"corpus_bytes": 161459,
                            "variants": {"no_w14": {"bytes": 150473}, "no_pic": {"bytes": 161258}}})
        sizes = gate.variant_deltas(path)
        self.assertIn("10,986 bytes", sizes)
        self.assertIn("10986 bytes", sizes)
        self.assertIn("201 bytes", sizes)
        self.assertNotIn("202 bytes", sizes)

    def test_no_file_no_figures(self):
        self.assertEqual(gate.variant_deltas(Path("/nonexistent/ab_compare.json")), [])

    def test_a_variant_without_bytes_adds_nothing(self):
        path = self._write({"corpus_bytes": 100, "variants": {"broken": {}}})
        self.assertEqual(gate.variant_deltas(path), [])


if __name__ == "__main__":
    unittest.main()
