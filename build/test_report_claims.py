#!/usr/bin/env python3
"""Published claims that have to match the fixture and the shipped scorer."""
import os
import re
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_roundtrip as sc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "fixture", "complex.docx")
WP14 = "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
FALSE = (
    "never declared",
    "not declared",
    "is undeclared",
    "undeclared in the corpus",
    "never bound",
    "prefix that does not exist",
)
SLUGS = (
    "plate",
    "docxodus",
    "superdoc",
    "folio",
    "genoffice",
    "eigenpal",
    "officeopen",
    "docen",
    "wordcraft",
    "fidus",
    "canvas",
    "docsplus",
    "lo_baseline",
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _paragraphs_md(path):
    return [ln.strip() for ln in _read(path).splitlines() if ln.strip()]


def _paragraphs_docx(path):
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "replace")
    plain = re.sub(r"</w:p>", "\n", xml)
    plain = re.sub(r"<[^>]+>", "", plain)
    plain = (
        plain.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return [ln.strip() for ln in plain.splitlines() if ln.strip()]


def _active_reports():
    found = []
    for folder in (ROOT, os.path.join(ROOT, "reports"), os.path.join(ROOT, "reports", "extras")):
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if name.startswith("~$"):
                continue
            if name.endswith(".md") or name.endswith(".docx"):
                found.append(path)
    return found


class ReportClaimsTest(unittest.TestCase):
    def test_fixture_declares_wp14_wherever_it_is_mentioned(self):
        mentioned = declared = 0
        with zipfile.ZipFile(FIXTURE) as zf:
            for name in zf.namelist():
                if not name.endswith((".xml", ".rels")):
                    continue
                raw = zf.read(name).decode("utf-8", "replace")
                if "wp14" not in raw:
                    continue
                mentioned += 1
                self.assertIn(f'xmlns:wp14="{WP14}"', raw, name)
                declared += 1
        self.assertEqual(mentioned, 14)
        self.assertEqual(declared, mentioned)

    def test_active_reports_do_not_call_wp14_undeclared(self):
        hits = 0
        for path in _active_reports():
            paras = _paragraphs_docx(path) if path.endswith(".docx") else _paragraphs_md(path)
            for para in paras:
                if "wp14" not in para:
                    continue
                hits += 1
                low = para.lower()
                for pat in FALSE:
                    self.assertNotIn(pat, low, f"{path}: {para[:160]}")
        self.assertGreater(hits, 0)

    def test_fixture_has_one_diagram_and_reports_do_not_invent_another(self):
        with zipfile.ZipFile(FIXTURE) as zf:
            rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
            self.assertNotIn("diagrams/drawing1.xml", rels)
        data = re.findall(r"relationships/diagramData\" Target=\"([^\"]+)\"", rels)
        self.assertEqual(data, ["diagrams/data1.xml"])
        claim = re.compile(r"\b(?:second SmartArt|two SmartArts?|second diagram|two diagrams)\b", re.I)
        negated = re.compile(r"\b(no|not|never|without)\b", re.I)
        for path in _active_reports():
            if f"{os.sep}archive{os.sep}" in path:
                continue
            paras = _paragraphs_docx(path) if path.endswith(".docx") else _paragraphs_md(path)
            for para in paras:
                if claim.search(para) and not negated.search(para):
                    self.fail(f"unmeasured second diagram in {path}: {para[:180]}")

    def test_extras_and_vendors_cover_every_measured_tool(self):
        text = _read(os.path.join(ROOT, "build", "score_all.py"))
        slugs = re.findall(r'\("[^"]+", "([^"]+)", (?:True|False)\)', text)
        self.assertEqual(tuple(slugs), SLUGS)
        extras = os.path.join(ROOT, "reports", "extras")
        vendors = _read(os.path.join(ROOT, "reports", "vendors.md"))
        self.assertIn("trivia that is not a score", vendors)
        for slug in slugs:
            path = os.path.join(extras, slug + ".md")
            self.assertTrue(os.path.isfile(path), slug)
            body = _read(path)
            self.assertIn("## Trivia", body)
            self.assertNotIn("api_key", body.lower())
        names = (
            "Plate.js",
            "Docxodus",
            "SuperDoc",
            "Folio",
            "GenOffice",
            "eigenpal",
            "office-open",
            "Docen",
            "WordCraft",
            "Fidus Writer",
            "canvas-editor",
            "docs.plus",
            "LibreOffice",
        )
        for name in names:
            self.assertIn(name, vendors)
        archived = os.path.join(
            ROOT,
            "reports",
            "archive",
            "Report A - Serialized vs Pass-Through vs Rendered (2026).md",
        )
        self.assertTrue(os.path.isfile(archived))
        self.assertFalse(
            os.path.exists(
                os.path.join(
                    ROOT,
                    "reports",
                    "Report A - Serialized vs Pass-Through vs Rendered (2026).md",
                )
            )
        )

    def test_lane_reports_quote_the_shipped_scorer(self):
        lanes = {
            os.path.join(ROOT, "out", "folio", "complex.docx"): "folio.md",
            os.path.join(ROOT, "out", "folio-editor", "complex.docx"): "folio.md",
            os.path.join(ROOT, "out", "eigenpal", "complex.docx"): "eigenpal.md",
            os.path.join(ROOT, "out", "eigenpal-editor", "complex.docx"): "eigenpal.md",
        }
        inp = sc.Pkg(FIXTURE)
        for out_path, report_name in lanes.items():
            self.assertTrue(os.path.isfile(out_path), out_path)
            checks = sc.build_checks(inp, sc.Pkg(out_path))
            failed = [c[0] for c in checks if not c[4]]
            weighted = "%s%%" % sc.score(checks)["weighted"]
            body = _read(os.path.join(ROOT, "reports", "extras", report_name))
            self.assertIn("failed-check-ids: " + " ".join(failed), body)
            self.assertIn(weighted, body)
            self.assertIn(f"{os.path.getsize(out_path)} bytes", body)

    def test_safety_report_records_each_vector_as_not_run(self):
        body = _read(
            os.path.join(
                ROOT,
                "reports",
                "Report D - Safety, Resource Bombs and Hostile Input (2026).md",
            )
        )
        for n in range(1, 11):
            self.assertIn(f"B{n} SKIP not-run:", body)
        self.assertIn(
            "preserving a hostile payload is not the same single result as a crash",
            body,
        )
        self.assertIn("NTLM credential leak cannot be measured on macOS", body)

    def test_rendering_note_labels_raw_refusals(self):
        body = _read(os.path.join(ROOT, "reports", "rendering-openability.md"))
        for name in ("Folio", "office-open", "Docen", "Fidus Writer"):
            self.assertIn(name, body)
        self.assertIn("build/folio_deltext_test.py", body)
        self.assertIn("build/officeopen_rels_test.py", body)
        self.assertIn("were not produced by opening a file after", body)
        self.assertNotIn("%", body)
        self.assertNotIn("bytes", body.lower())


if __name__ == "__main__":
    unittest.main()
