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

    def test_the_same_input_gives_the_same_bytes(self):
        # sync:demos runs this on every site release; a clock in the zip made every run a new file.
        import time
        time.sleep(2.1)   # past the zip format's two-second clock resolution
        again, _ = m.sanitize(FIXTURE.read_bytes(), m.BASE_STEPS)
        self.assertEqual(again, self.out)

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

    def test_the_read_only_lock_is_lifted_and_nothing_else_in_settings_changes(self):
        src = self.src["word/settings.xml"].decode()
        dst = self.dst["word/settings.xml"].decode()
        lock = re.search(r"<w:documentProtection\b[^>]*/>", src).group(0)
        self.assertIn('w:edit="readOnly"', lock)
        self.assertNotIn("w:documentProtection", dst)
        self.assertEqual(dst, src.replace(lock, ""))

    def test_nothing_else_changes(self):
        changed = {"word/document.xml", "word/_rels/document.xml.rels", "word/settings.xml"}
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
        self.assertEqual([r["step"] for r in self.removed], ["altchunk_to_paragraphs", "ole_to_picture", "unlock_read_only"])
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
                self.assertEqual([r["step"] for r in man["removed"]], ["altchunk_to_paragraphs", "ole_to_picture", "unlock_read_only"])

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


def _docx(body: str) -> bytes:
    """A minimal package whose document body is `body`."""
    ct = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    doc = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           + body + '</w:body></w:document>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
    return out.getvalue()


def _tc(text: str, pr: str = "") -> str:
    return f"<w:tc>{'<w:tcPr>' + pr + '</w:tcPr>' if pr else ''}<w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>"


class OrphanVMergeEdges(unittest.TestCase):
    """Review comments on editors_trial#20: 4434885194 (gitar) and 4434897634 (CodeRabbit)."""

    def run_step(self, rows: list[str]) -> str:
        data, _ = m.sanitize(_docx("<w:tbl>" + "".join(rows) + "</w:tbl>"), ["orphan_vmerge_to_cell"])
        return parts(data)["word/document.xml"].decode()

    def test_a_chain_of_orphans_is_repaired_in_one_pass(self):
        doc = self.run_step([
            "<w:tr>" + _tc("A1") + "</w:tr>",
            "<w:tr>" + _tc("A2", "<w:vMerge/>") + "</w:tr>",
            "<w:tr>" + _tc("A3", "<w:vMerge/>") + "</w:tr>",
        ])
        self.assertNotIn("<w:vMerge", doc)

    def test_a_valid_chain_is_kept_whole(self):
        doc = self.run_step([
            "<w:tr>" + _tc("A1", '<w:vMerge w:val="restart"/>') + "</w:tr>",
            "<w:tr>" + _tc("A2", "<w:vMerge/>") + "</w:tr>",
            "<w:tr>" + _tc("A3", "<w:vMerge/>") + "</w:tr>",
        ])
        self.assertEqual(doc.count("<w:vMerge/>"), 2)

    def test_grid_before_shifts_the_row_columns(self):
        # Row 2 skips grid column 0, so its first cell sits in column 1, under the restart.
        doc = self.run_step([
            "<w:tr>" + _tc("A1") + _tc("B1", '<w:vMerge w:val="restart"/>') + "</w:tr>",
            '<w:tr><w:trPr><w:gridBefore w:val="1"/></w:trPr>' + _tc("B2", "<w:vMerge/>") + "</w:tr>",
        ])
        self.assertIn("<w:vMerge/>", doc)


class NoForeignPayload(unittest.TestCase):
    """Review comment 4434816580 and the VBA prompt in review 5727029260 (CodeRabbit, editors_trial#20): every
    published copy is checked for an external non-hyperlink relationship and for a VBA project."""

    def test_no_published_copy_carries_an_external_target_or_a_macro(self):
        with tempfile.TemporaryDirectory() as d:
            m.build(FIXTURE, Path(d), m.EDITORS)
            for f in sorted(Path(d).glob("*.docx")):
                p = parts(f.read_bytes())
                for name, data in p.items():
                    if name.endswith(".rels"):
                        for rel in re.findall(r"<Relationship\b[^>]*>", data.decode()):
                            if 'TargetMode="External"' in rel:
                                self.assertRegex(rel, r'Type="[^"]*/hyperlink"', f"{f.name} {name}")
                self.assertFalse([n for n in p if "vbaProject" in n], f.name)
