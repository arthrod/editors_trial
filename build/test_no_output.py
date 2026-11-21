"""A lane with no output says what happened: a refusal and a call that never
returned are different outcomes (OnlyOffice's converter on the corpus, 2026-11-21)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

BUILD = Path(__file__).resolve().parent
sys.path.insert(0, str(BUILD))
import defect_survival as ds  # noqa: E402
import facts  # noqa: E402
import no_output  # noqa: E402


class Record(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_lane_with_no_record_claims_no_reason(self):
        self.assertEqual(no_output.outcome(self.d), "not-recorded")
        self.assertEqual(no_output.words("not-recorded"), "no reason recorded")

    def test_a_call_that_never_returned_is_not_a_refusal(self):
        (self.d / "no_output.json").write_text(json.dumps({"outcome": "did-not-return", "step": "doc.docx -> bin", "limit_s": 120}))
        self.assertEqual(no_output.outcome(self.d), "did-not-return")
        self.assertEqual(no_output.words("did-not-return"), "the converter did not return")
        self.assertNotIn("refused", no_output.words("did-not-return"))

    def test_a_record_beside_an_output_is_stale(self):
        (self.d / "no_output.json").write_text(json.dumps({"outcome": "did-not-return"}))
        (self.d / "complex.docx").write_bytes(b"PK")
        self.assertIsNone(no_output.read(self.d))

    def test_an_unknown_outcome_is_an_error_not_a_guess(self):
        (self.d / "no_output.json").write_text(json.dumps({"outcome": "gave up"}))
        with self.assertRaises(ValueError):
            no_output.outcome(self.d)


class Tables(unittest.TestCase):
    """Report B's tables, with one editor that refused and one whose converter did not return."""
    def setUp(self):
        yes = {k: "YES" for k in ds.DEFECTS}
        self.rows = {"superdoc": yes, "plate": None, "onlyoffice": None}
        self.ed = [("SuperDoc", "superdoc"), ("Plate.js", "plate"), ("OnlyOffice (CryptPad build)", "onlyoffice")]
        self.why = {"plate": "refused", "onlyoffice": "did-not-return"}

    def test_the_survival_table_names_each_outcome(self):
        lines = ds.table(self.rows, {}, "16.0", self.ed, self.why).splitlines()
        self.assertTrue(lines[3].endswith("| no output: the importer refused the corpus |"))
        self.assertTrue(lines[4].endswith("| no output: the converter did not return |"))

    def test_the_fatal_table_does_not_call_a_stall_a_refusal(self):
        lines = ds.fatal_table(self.rows, {}, self.ed, self.why).splitlines()
        self.assertIn("the importer refused the corpus", lines[3])
        self.assertIn("the converter did not return", lines[4])
        self.assertNotIn("refused", lines[4])

    def test_the_flip_table_does_not_call_a_stall_a_refusal(self):
        clean = {"superdoc": True, "plate": True, "onlyoffice": True}
        lines = ds.flip_table(self.rows, clean, {"superdoc": "OPENED"}, self.ed, self.why).splitlines()
        self.assertIn("**yes — the importer refused the corpus**", lines[3])
        self.assertIn("**yes — the converter did not return**", lines[4])

    def test_without_recorded_outcomes_the_published_wording_is_unchanged(self):
        # Plate's row was published before lanes recorded an outcome; its harness records none.
        lines = ds.table(self.rows, {}, "16.0", self.ed).splitlines()
        self.assertTrue(lines[3].endswith("| no output |"))
        self.assertIn("the importer refused the corpus", ds.fatal_table(self.rows, {}, self.ed).splitlines()[3])

    def test_the_scan_reads_each_lane_s_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "onlyoffice"
            d.mkdir()
            (d / "no_output.json").write_text(json.dumps({"outcome": "did-not-return"}))
            self.assertEqual(ds.outcomes(tmp, self.ed), {"onlyoffice": "did-not-return"})


class Facts(unittest.TestCase):
    def test_a_lane_with_no_output_gets_an_outcome_fact_and_no_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "onlyoffice"
            d.mkdir()
            (d / "no_output.json").write_text(json.dumps({"outcome": "did-not-return", "step": "doc.docx -> bin", "limit_s": 120}))
            f: dict = {}
            facts.outcome_facts("rt.onlyoffice", d, f)
            self.assertEqual(f["rt.onlyoffice.outcome"], "did-not-return")
            self.assertEqual(f["rt.onlyoffice.outcome_text"], "the converter did not return")
            self.assertEqual(f["rt.onlyoffice.outcome_step"], "doc.docx -> bin")
            self.assertEqual(f["rt.onlyoffice.outcome_limit_s"], 120)
            self.assertNotIn("rt.onlyoffice.weighted", f)

    def test_a_lane_with_an_output_gets_no_outcome_fact(self):
        with tempfile.TemporaryDirectory() as tmp:
            f: dict = {}
            facts.outcome_facts("rt.superdoc", Path(tmp), f)
            self.assertEqual(f, {})

    def test_the_harness_writes_the_record_and_clears_it(self):
        text = (BUILD.parent / "harness/onlyoffice/roundtrip.mjs").read_text()
        self.assertIn("no_output.json", text)
        self.assertIn("'did-not-return'", text)
        self.assertIn("rmSync", text)


if __name__ == "__main__":
    unittest.main()
