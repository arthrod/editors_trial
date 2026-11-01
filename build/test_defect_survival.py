#!/usr/bin/env python3
"""Report B's defect-survival table is generated from out_broken/ and Word's verdicts, never typed."""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import defect_survival as ds  # noqa: E402

DOC = ('<w:document><w:body><w:p/><m:oMathPara/>'
       '<w:fldChar w:dirty="true"/><w:moveFrom><w:delText>x</w:delText></w:moveFrom>'
       '<w:sectPr><w:cols/><w:pgNumType/></w:sectPr></w:body></w:document>')
SETTINGS = '<w:settings><w:evenAndOddHeaders/><w:documentProtection/></w:settings>'


def package(path: Path, doc: str, settings: str | None = None, ole: bytes | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", doc)
        if settings:
            z.writestr("word/settings.xml", settings)
        if ole is not None:
            z.writestr("word/embeddings/embedded1.docx", ole)
    return path


class Survival(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_defects_are_read_from_each_output_package(self):
        package(self.root / "superdoc" / "complex.docx", DOC, SETTINGS, b"\0" * 64)
        r = ds.survival(self.root, [("SuperDoc", "superdoc")])["superdoc"]
        self.assertEqual(r[1], "YES")
        self.assertEqual(r[9], "YES")
        self.assertEqual(r[10], "YES")
        self.assertEqual(r[12], "YES")
        self.assertEqual(r[6], "no")

    def test_a_dropped_ole_part_is_DROP(self):
        package(self.root / "canvas" / "complex.docx", "<w:document><w:body/></w:document>")
        self.assertEqual(ds.survival(self.root, [("canvas", "canvas")])["canvas"][9], "DROP")

    def test_an_editor_with_no_output_has_no_row_of_cells(self):
        self.assertIsNone(ds.survival(self.root, [("Plate.js", "plate")])["plate"])


class Table(unittest.TestCase):
    def setUp(self):
        self.rows = {"superdoc": {k: "YES" for k in ds.DEFECTS}, "plate": None}
        self.editors = [("SuperDoc", "superdoc"), ("Plate.js", "plate")]

    def test_the_word_column_comes_from_the_verdicts(self):
        t = ds.table(self.rows, {"superdoc": "REFUSED"}, "16.0", self.editors)
        self.assertIn("| Word 16.0 |", t.splitlines()[0])
        self.assertTrue(t.splitlines()[2].startswith("| SuperDoc | YES |"))
        self.assertTrue(t.splitlines()[2].endswith("| **REFUSED** |"))

    def test_an_editor_with_no_output_says_so_in_every_cell(self):
        line = ds.table(self.rows, {}, "16.0", self.editors).splitlines()[3]
        self.assertEqual(line.count("—"), len(ds.DEFECTS))
        self.assertTrue(line.endswith("| no output |"))

    def test_an_output_word_did_not_open_in_this_run_is_not_given_a_verdict(self):
        line = ds.table(self.rows, {}, "16.0", self.editors).splitlines()[2]
        self.assertTrue(line.endswith("| not measured |"))

    def test_a_failed_word_run_is_not_shown_as_a_verdict(self):
        line = ds.table(self.rows, {"superdoc": "FAILED: timeout"}, "16.0", self.editors).splitlines()[2]
        self.assertTrue(line.endswith("| not measured |"))

    def test_every_editor_measured_has_a_row(self):
        self.assertEqual({d for _, d in ds.EDITORS} - {"plate"},
                         {p.parent.name for p in (ds.ROOT / "out_broken").glob("*/complex.docx")} - {"plate"})


if __name__ == "__main__":
    unittest.main()
