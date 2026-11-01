"""Tests for make_demo_docs.py: the sanitized fixture copies behind the benchmarks.law live demos."""
import io
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

import make_demo_docs as m

FIXTURE = Path(__file__).resolve().parent.parent / "fixture" / "complex.docx"


def parts(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = parts(FIXTURE.read_bytes())
        cls.out, cls.removed = m.sanitize(FIXTURE.read_bytes(), m.BASE_STEPS)
        cls.dst = parts(cls.out)

    def test_altchunk_becomes_ordinary_paragraphs_with_the_same_text(self):
        doc = self.dst["word/document.xml"].decode()
        self.assertNotIn("w:altChunk", doc)
        self.assertNotIn("word/afchunk.html", self.dst)
        self.assertIn("<w:t>Imported altChunk paragraph one.</w:t>", doc)
        self.assertIn("<w:t>Imported altChunk paragraph two.</w:t>", doc)

    def test_ole_object_becomes_its_icon_picture(self):
        doc = self.dst["word/document.xml"].decode()
        self.assertNotIn("o:OLEObject", doc)
        self.assertNotIn("<w:object", doc)
        self.assertNotIn("word/embeddings/embedded1.docx", self.dst)
        self.assertRegex(doc, r'<w:pict><v:shape [^>]*><v:imagedata r:id="rIdOleImage"')

    def test_every_remaining_relationship_resolves_to_a_part(self):
        for name, data in self.dst.items():
            if not name.endswith(".rels"):
                continue
            base = name.replace("_rels/", "").removesuffix(".rels")
            folder = base.rsplit("/", 1)[0] if "/" in base else ""
            for r in re.finditer(r"<Relationship [^>]*>", data.decode()):
                rel = r.group(0)
                if 'TargetMode="External"' in rel:
                    self.fail(f"external relationship left in {name}: {rel}")
                target = re.search(r'Target="([^"]*)"', rel).group(1)
                path = target.lstrip("/") if target.startswith("/") else str(Path(folder, target))
                path = re.sub(r"[^/]+/\.\./", "", path)
                self.assertIn(path, self.dst, f"{name}: {rel}")

    def test_relationship_ids_used_by_the_document_still_exist(self):
        doc = self.dst["word/document.xml"].decode()
        rels = self.dst["word/_rels/document.xml.rels"].decode()
        for rid in set(re.findall(r'r:(?:id|embed|link)="([^"]+)"', doc)):
            self.assertIn(f'Id="{rid}"', rels)

    def test_nothing_else_changes(self):
        changed = {"word/document.xml", "word/_rels/document.xml.rels"}
        gone = {"word/afchunk.html", "word/embeddings/embedded1.docx"}
        self.assertEqual(set(self.src) - set(self.dst), gone)
        for name, data in self.dst.items():
            if name not in changed:
                self.assertEqual(data, self.src[name], name)

    def test_the_chart_workbook_is_kept(self):
        self.assertIn("word/embeddings/Microsoft_Excel_Worksheet.xlsx", self.dst)

    def test_content_types_is_first_and_names_no_removed_part(self):
        with zipfile.ZipFile(io.BytesIO(self.out)) as z:
            self.assertEqual(z.namelist()[0], "[Content_Types].xml")
        ct = self.dst["[Content_Types].xml"].decode()
        self.assertNotIn("afchunk.html", ct)
        self.assertNotIn("embedded1.docx", ct)

    def test_each_removal_is_listed_with_a_reason(self):
        self.assertEqual([r["step"] for r in self.removed], ["altchunk_to_paragraphs", "ole_to_picture"])
        for r in self.removed:
            self.assertTrue(r["what"] and r["why"])


def cells(doc: str, text: str) -> str:
    """The <w:tc> holding `text` (innermost)."""
    i = doc.index(f">{text}<")
    return doc[doc.rindex("<w:tc>", 0, i): doc.index("</w:tc>", i) + 7]


class OrphanVMerge(unittest.TestCase):
    """canvas-editor's docx plugin drops a vMerge continuation that has no restart above it, the row comes up
    one grid column short, and its table layout throws (TableParticle.computeRowColInfo reads colgroup[3])."""

    @classmethod
    def setUpClass(cls):
        out, cls.removed = m.sanitize(FIXTURE.read_bytes(), m.BASE_STEPS + ["orphan_vmerge_to_cell"])
        cls.doc = parts(out)["word/document.xml"].decode()
        cls.base = parts(m.sanitize(FIXTURE.read_bytes(), m.BASE_STEPS)[0])["word/document.xml"].decode()

    def test_the_fixture_has_the_orphan(self):
        self.assertIn("<w:vMerge/>", cells(self.base, "vert merged, second"))

    def test_the_orphan_becomes_an_ordinary_cell(self):
        self.assertNotIn("vMerge", cells(self.doc, "vert merged, second"))

    def test_real_merges_are_kept(self):
        self.assertIn('<w:vMerge w:val="restart"/>', cells(self.doc, "vert merged, first"))
        self.assertIn("<w:vMerge/>", cells(self.doc, "vert merged, continuation"))

    def test_only_that_cell_changes(self):
        self.assertEqual(len(self.base) - len(self.doc), len("<w:vMerge/>"))

    def test_it_is_listed(self):
        self.assertEqual(self.removed[-1]["step"], "orphan_vmerge_to_cell")
        self.assertIn("1", self.removed[-1]["what"])

    def test_canvas_editor_gets_it_and_nobody_else(self):
        self.assertEqual(m.EDITORS["canvas-editor"], ["orphan_vmerge_to_cell"])
        self.assertEqual({k for k, v in m.EDITORS.items() if v}, {"canvas-editor"})


class Build(unittest.TestCase):
    def test_writes_one_docx_and_one_manifest_per_editor(self):
        with tempfile.TemporaryDirectory() as d:
            m.build(FIXTURE, Path(d), {"superdoc": [], "plate": []})
            for slug in ("superdoc", "plate"):
                self.assertTrue(zipfile.is_zipfile(Path(d, f"{slug}.docx")))
                man = json.loads(Path(d, f"{slug}.json").read_text())
                self.assertEqual(man["source"], "fixture/complex.docx")
                self.assertEqual(len(man["source_sha256"]), 64)
                self.assertEqual([r["step"] for r in man["removed"]], ["altchunk_to_paragraphs", "ole_to_picture"])

    def test_every_site_editor_has_an_entry(self):
        self.assertEqual(
            set(m.EDITORS),
            {"superdoc", "eigenpal", "folio", "plate", "canvas-editor", "docen", "genoffice", "docxodus",
             "wordcraft", "fidus-writer", "docs-plus", "office-open"},
        )

    def test_unknown_step_is_rejected(self):
        with self.assertRaises(KeyError):
            m.sanitize(FIXTURE.read_bytes(), ["no_such_step"])


if __name__ == "__main__":
    unittest.main()
