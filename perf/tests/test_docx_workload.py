"""Contract for the realistic DOCX workload ladder (arthrod/editors_trial#100).

The speed report needs documents an editor has to parse and lay out: real
words, one ``<w:p>`` per paragraph, styles and runs, at sizes that separate
fixed process overhead from per-document cost. These tests are the spec.
"""

from __future__ import annotations

import hashlib
import io
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from perf.fixtures.docx_workload import (
    BUILDER_VERSION,
    PROSE_LADDER,
    SENTINEL_PREFIX,
    build_prose_docx,
    workload_docx,
)
from perf.fixtures.generate import correctness_fixtures, docx_zip_bytes
from perf.fixtures.profiles import allowed_workloads, size_ladder

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
REPO = Path(__file__).resolve().parents[2]


def _document(docx: bytes) -> ET.Element:
    with zipfile.ZipFile(io.BytesIO(docx)) as zf:
        return ET.fromstring(zf.read("word/document.xml"))


def _paragraph_texts(docx: bytes) -> list[str]:
    root = _document(docx)
    return ["".join(t.text or "" for t in p.iter(W + "t")) for p in root.iter(W + "p")]


def _row(workload_id: str) -> dict:
    return next(r for r in PROSE_LADDER if r["workload_id"] == workload_id)


class ProseLadderShape(unittest.TestCase):
    def test_ladder_ids_and_word_counts(self):
        self.assertEqual(
            [(r["workload_id"], r["words"]) for r in PROSE_LADDER],
            [
                ("prose-500w", 500),
                ("prose-5kw", 5_000),
                ("prose-50kw", 50_000),
                ("prose-250kw", 250_000),
            ],
        )

    def test_rows_carry_the_static_environment_fields(self):
        for row in PROSE_LADDER:
            self.assertEqual(row["shape"], "prose")
            self.assertEqual(row["unicode_class"], "ascii")
            self.assertEqual(row["match_count"], 0)
            self.assertEqual(row["paragraph_words"], 50)
            self.assertEqual(row["paragraphs"], row["words"] // 50)

    def test_size_ladder_includes_prose_rows_and_the_corpus(self):
        ids = [r["workload_id"] for r in size_ladder()]
        for row in PROSE_LADDER:
            self.assertIn(row["workload_id"], ids)
        self.assertIn("complex-corpus", ids)

    def test_profile_caps(self):
        self.assertIn("prose-500w", allowed_workloads("ci_contract"))
        self.assertNotIn("prose-5kw", allowed_workloads("ci_contract"))
        self.assertIn("prose-5kw", allowed_workloads("ci_broad"))
        self.assertNotIn("prose-50kw", allowed_workloads("ci_broad"))
        publish = allowed_workloads("dedicated_publish")
        for wid in ("prose-50kw", "prose-250kw", "complex-corpus"):
            self.assertIn(wid, publish)


class ProseDocx(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = build_prose_docx(_row("prose-5kw"))

    def test_bytes_are_deterministic(self):
        again = build_prose_docx(_row("prose-5kw"))
        self.assertEqual(self.built["docx"], again["docx"])
        self.assertEqual(self.built["sha256"], hashlib.sha256(again["docx"]).hexdigest())

    def test_zip_entries_have_a_fixed_timestamp(self):
        with zipfile.ZipFile(io.BytesIO(self.built["docx"])) as zf:
            stamps = {info.date_time for info in zf.infolist()}
        self.assertEqual(stamps, {(1980, 1, 1, 0, 0, 0)})

    def test_package_has_styles_wired(self):
        with zipfile.ZipFile(io.BytesIO(self.built["docx"])) as zf:
            names = set(zf.namelist())
            rels = zf.read("word/_rels/document.xml.rels").decode()
            types = zf.read("[Content_Types].xml").decode()
            styles = zf.read("word/styles.xml").decode()
        self.assertTrue({"[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml"} <= names)
        self.assertIn('Target="styles.xml"', rels)
        self.assertIn('PartName="/word/styles.xml"', types)
        for style_id in ("Normal", "Heading1", "Heading2"):
            self.assertIn('w:styleId="%s"' % style_id, styles)

    def test_every_xml_part_is_well_formed(self):
        with zipfile.ZipFile(io.BytesIO(self.built["docx"])) as zf:
            for name in zf.namelist():
                if name.endswith(".xml") or name.endswith(".rels"):
                    ET.fromstring(zf.read(name))

    def test_one_w_p_per_paragraph_and_counts_match_metadata(self):
        texts = _paragraph_texts(self.built["docx"])
        self.assertEqual(len(texts), self.built["paragraph_count"])
        expected = (
            self.built["body_paragraph_count"]
            + self.built["heading_count"]
            + len(correctness_fixtures())
            + 1
        )
        self.assertEqual(self.built["paragraph_count"], expected)
        self.assertEqual(self.built["body_paragraph_count"], 100)
        self.assertGreater(self.built["heading_count"], 0)

    def test_body_word_count_is_exact(self):
        root = _document(self.built["docx"])
        words = 0
        for p in root.iter(W + "p"):
            style = p.find("%spPr/%spStyle" % (W, W))
            if style is not None:
                continue  # headings are counted separately
            text = "".join(t.text or "" for t in p.iter(W + "t"))
            if text.startswith(SENTINEL_PREFIX):
                continue
            words += len(text.split())
        correctness_words = sum(len(v.decode("utf-8").split()) for v in correctness_fixtures().values())
        self.assertEqual(words - correctness_words, 5_000)
        self.assertEqual(self.built["word_count"], 5_000)

    def test_text_is_words_not_whitespace(self):
        body = [t for t in _paragraph_texts(self.built["docx"]) if t and not t.startswith(SENTINEL_PREFIX)]
        letters = sum(ch.isalpha() for t in body for ch in t)
        total = sum(len(t) for t in body)
        self.assertGreater(letters / total, 0.7)
        vocabulary = {w.strip(".,;:").lower() for t in body for w in t.split()}
        self.assertGreater(len(vocabulary), 100)

    def test_paragraphs_have_formatted_runs(self):
        root = _document(self.built["docx"])
        bold = len(root.findall(".//%sr/%srPr/%sb" % (W, W, W)))
        italic = len(root.findall(".//%sr/%srPr/%si" % (W, W, W)))
        self.assertGreater(bold, 10)
        self.assertGreater(italic, 10)
        runs = len(root.findall(".//%sr" % W))
        self.assertGreater(runs, 2 * self.built["body_paragraph_count"])

    def test_letter_page_geometry(self):
        root = _document(self.built["docx"])
        pg = root.find(".//%ssectPr/%spgSz" % (W, W))
        self.assertEqual(pg.get(W + "w"), "12240")
        self.assertEqual(pg.get(W + "h"), "15840")

    def test_sentinel_is_the_last_paragraph_and_correctness_precedes_it(self):
        texts = _paragraph_texts(self.built["docx"])
        self.assertEqual(texts[-1], self.built["sentinel"])
        self.assertTrue(self.built["sentinel"].startswith(SENTINEL_PREFIX))
        self.assertIn("prose-5kw", self.built["sentinel"])
        joined = "\n".join(texts[-6:-1])
        for value in correctness_fixtures().values():
            self.assertIn(value.decode("utf-8").rstrip("\n"), joined)

    def test_whitespace_runs_are_preserved(self):
        root = _document(self.built["docx"])
        for t in root.iter(W + "t"):
            text = t.text or ""
            if text != text.strip():
                self.assertEqual(t.get("{http://www.w3.org/XML/1998/namespace}space"), "preserve")

    def test_metadata(self):
        self.assertEqual(self.built["workload_id"], "prose-5kw")
        self.assertEqual(self.built["byte_size"], len(self.built["docx"]))
        self.assertEqual(self.built["builder_version"], BUILDER_VERSION)
        self.assertEqual(self.built["shape"], "prose")


class WorkloadDocx(unittest.TestCase):
    def test_every_ladder_row_resolves(self):
        for row in size_ladder():
            if row["workload_id"] == "prose-250kw":
                continue  # covered by test_largest_rung_builds_fast_enough
            with self.subTest(row["workload_id"]):
                built = workload_docx(row["workload_id"])
                self.assertEqual(built["workload_id"], row["workload_id"])
                self.assertEqual(built["sha256"], hashlib.sha256(built["docx"]).hexdigest())
                self.assertGreaterEqual(built["paragraph_count"], 1)
                _document(built["docx"])

    def test_largest_rung_builds_fast_enough(self):
        import time

        start = time.perf_counter()
        built = workload_docx("prose-250kw")
        self.assertLess(time.perf_counter() - start, 30.0)
        self.assertEqual(built["word_count"], 250_000)

    def test_complex_corpus_is_the_fidelity_fixture_bytes(self):
        built = workload_docx("complex-corpus")
        self.assertEqual(built["docx"], (REPO / "fixture" / "complex.docx").read_bytes())
        self.assertEqual(built["shape"], "corpus")

    def test_legacy_rows_get_one_paragraph_per_line(self):
        built = workload_docx("short-paragraphs")
        texts = _paragraph_texts(built["docx"])
        # 100 generated lines + the four correctness lines
        self.assertEqual(len(texts), 104)
        self.assertEqual(built["paragraph_count"], 104)

    def test_legacy_bytes_are_deterministic(self):
        self.assertEqual(workload_docx("micro-paragraphs")["docx"], workload_docx("micro-paragraphs")["docx"])

    def test_unknown_workload_is_rejected(self):
        with self.assertRaises(ValueError):
            workload_docx("prose-9000kw")


class LegacyZipBytes(unittest.TestCase):
    def test_docx_zip_bytes_is_deterministic(self):
        from unittest import mock

        first = docx_zip_bytes(b"a\nb\n")
        # Ten years later: a builder that stamps the wall clock changes bytes.
        with mock.patch("time.time", return_value=2_000_000_000.0):
            later = docx_zip_bytes(b"a\nb\n")
        self.assertEqual(first, later)

    def test_docx_zip_bytes_writes_one_paragraph_per_line(self):
        texts = _paragraph_texts(docx_zip_bytes(b"alpha\nbeta\ngamma\n"))
        self.assertEqual(texts, ["alpha", "beta", "gamma"])


if __name__ == "__main__":
    unittest.main()
