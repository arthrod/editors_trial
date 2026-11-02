"""wordexp_table builds Report D1's table of jubarte on the 33 Word-experiment
fixtures from the measured TSV, and patches it into the template (#69)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wordexp_table as W  # noqa: E402

TSV = (
    "B6\tread\t0\t2\t0\twarning: layout failed: UNSUPPORTED_PACKAGE: input document: unsafe entry name\n"
    "B6\tread_nopm\t0\t2\t1\twrote x/view_nopm.md (md, 561 bytes)\n"
    "B6\tvalidate\t1\t1\t0\terror: DOCX refused: UNSUPPORTED_PACKAGE: unsafe entry name\n"
    "B6\tcompare\t1\t1\t0\terror: compare failed: UNSUPPORTED_PACKAGE: original document\n"
    "E3_flood60\tread\t0 KILLED>300s\t5483\t300\t\n"
    "E3_flood60\tread_nopm\t1\t136\t1\terror: cannot read: INPUT_LIMIT: word/document.xml past 2000000\n"
    "E3_flood60\tvalidate\t1\t135\t0\terror: DOCX refused: INPUT_LIMIT: elements\n"
    "E3_flood60\tcompare\t1\t136\t0\terror: compare failed: INPUT_LIMIT\n"
)


class Parse(unittest.TestCase):
    def test_rows_group_by_fixture_in_file_order(self):
        rows = W.parse(TSV)
        self.assertEqual(list(rows), ["B6", "E3_flood60"])
        self.assertEqual(rows["B6"]["validate"].exit, "1")
        self.assertEqual(rows["E3_flood60"]["read"].peak_mb, 5483)

    def test_a_missing_command_is_an_error(self):
        with self.assertRaises(ValueError):
            W.parse("B6\tread\t0\t2\t0\tok\n")


class Cell(unittest.TestCase):
    def test_success_prints_exit_and_peak(self):
        r = W.parse(TSV)["B6"]["read_nopm"]
        self.assertEqual(W.cell(r), "exit 0, 2 MB")

    def test_refusal_names_its_code(self):
        r = W.parse(TSV)["B6"]["validate"]
        self.assertEqual(W.cell(r), "exit 1, UNSUPPORTED_PACKAGE, 1 MB")

    def test_a_panic_is_named_before_any_code(self):
        r = W.Run("101", 40, 2, "thread main panicked at atomize.rs: INPUT_LIMIT")
        self.assertEqual(W.cell(r), "**panic (exit 101)**, 40 MB")

    def test_a_kill_is_never_hidden(self):
        r = W.parse(TSV)["E3_flood60"]["read"]
        self.assertEqual(W.cell(r), "**killed at 300 s**, 5,483 MB")


class Table(unittest.TestCase):
    def test_one_row_per_fixture_with_short_ids(self):
        t = W.table(W.parse(TSV))
        lines = t.splitlines()
        self.assertTrue(lines[0].startswith("| Fixture | read |"))
        self.assertEqual(len(lines), 2 + 2)
        self.assertTrue(lines[3].startswith("| E3 |"))


class Short(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(W.short("E3_flood60"), "E3")
        self.assertEqual(W.short("X4c_customxml_control"), "X4c")
        self.assertEqual(W.short("D_sdt200"), "D_sdt200")
        self.assertEqual(W.short("B10"), "B10")


class Patch(unittest.TestCase):
    def test_replaces_only_between_markers(self):
        doc = f"a\n{W.BEGIN}\nold\n{W.END}\nb\n"
        out = W.patch(doc, "NEW")
        self.assertEqual(out, f"a\n{W.BEGIN}\nNEW\n{W.END}\nb\n")

    def test_no_markers_is_an_error(self):
        with self.assertRaises(ValueError):
            W.patch("a\n", "NEW")

    def test_patch_file_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.md"
            p.write_text(f"x\n{W.BEGIN}\n{W.END}\n")
            W.patch_file(p, TSV)
            self.assertIn("| B6 |", p.read_text())


if __name__ == "__main__":
    unittest.main()
