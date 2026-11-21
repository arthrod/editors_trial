#!/usr/bin/env python3
"""Published claims that have to match the fixture and the shipped scorer."""
import os
import re
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_report_consistency as gate
import check_roundtrip as sc
import measure_alternate_content as mac
import outreach_issues as outreach

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
    "apryse",
    "lo_baseline",
)
# Each measured tool's heading in reports/vendors.md, in driver order.
VENDOR_HEADINGS = dict(zip(SLUGS, (
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
    "Apryse",
    "LibreOffice",
)))
# On editors.benchmarks.law, not yet in the trial's round-trip reports.
PENDING_HEADINGS = (
    "react-docx",
    "Univer",
    "OpenDoc",
    "BetterOffice",
    "OnlyOffice (CryptPad build)",
    "Nutrient",
)
PENDING_SENTENCE = "The trial's own lanes for %s are being measured and are not in the reports yet."
VENDOR_SUBHEADINGS = ("What the benchmark runs", "Trivia", "Pros", "Cons")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _paragraphs_md(path):
    return [ln.strip() for ln in _read(path).splitlines() if ln.strip()]


def _paragraphs_docx(path):
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", "replace")
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


def _vendor_sections(text):
    """Map each ``## heading`` of the vendors page to its body, in page order."""
    parts = re.split(r"^##[ \t]+(.+?)[ \t]*$", text, flags=re.M)
    return {parts[i].strip(): parts[i + 1] for i in range(1, len(parts), 2)}


def _subsections(body):
    """Map each ``### heading`` of one vendor section to its body."""
    parts = re.split(r"^###[ \t]+(.+?)[ \t]*$", body, flags=re.M)
    return {parts[i].strip(): parts[i + 1] for i in range(1, len(parts), 2)}


def _github_anchor(heading):
    """The anchor GitHub gives a heading: lower case, punctuation dropped, spaces to hyphens."""
    kept = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return kept.replace(" ", "-")


def _bullets(body):
    return [ln[2:].strip() for ln in body.splitlines() if ln.startswith("- ")]


def _active_reports():
    found = []
    for folder in (ROOT, os.path.join(ROOT, "reports")):
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

    def test_vendors_page_has_a_full_section_for_every_tool(self):
        text = _read(os.path.join(ROOT, "build", "score_all.py"))
        slugs = re.findall(r'\("[^"]+", "([^"]+)", (?:True|False)\)', text)
        self.assertEqual(tuple(slugs), SLUGS)
        # The lane notes were folded into the vendors page. Issues filed on the
        # vendors' repositories link to reports/extras/<slug>.md, so each stays
        # as a stub: a title and one sentence that links to the tool's section.
        for folder in ("reports", os.path.join("templates", "reports")):
            extras = os.path.join(ROOT, folder, "extras")
            self.assertEqual(sorted(os.listdir(extras)), sorted(slug + ".md" for slug in slugs), folder)
            for slug in slugs:
                name = VENDOR_HEADINGS[slug]
                stub = _read(os.path.join(extras, slug + ".md"))
                self.assertEqual(
                    stub,
                    f"# {name}\n\nThis note moved to the [{name} section of the vendor notes]"
                    f"(../vendors.md#{_github_anchor(name)}).\n",
                    f"{folder}/extras/{slug}.md",
                )
                self.assertEqual(gate.number_tokens(stub), [], slug)
        for path in gate.active_markdown():
            self.assertNotIn(os.sep + "extras" + os.sep, str(path))
        for folder, _dirs, names in os.walk(os.path.join(ROOT, "templates")):
            if os.path.basename(folder) == "extras":
                continue
            for name in names:
                if name.endswith(".md"):
                    self.assertNotIn("extras/", _read(os.path.join(folder, name)), name)
        vendors = _read(os.path.join(ROOT, "reports", "vendors.md"))
        self.assertIn("trivia that is not a score", vendors)
        self.assertIn("This page does not rank the tools.", vendors)
        self.assertNotIn("api_key", vendors.lower())
        self.assertNotIn("{{", vendors)
        sections = _vendor_sections(vendors)
        expected = [VENDOR_HEADINGS[slug] for slug in slugs] + list(PENDING_HEADINGS)
        self.assertEqual(list(sections), expected)
        for name in expected:
            subs = _subsections(sections[name])
            for heading in VENDOR_SUBHEADINGS:
                self.assertIn(heading, subs, f"{name}: no '### {heading}'")
                self.assertTrue(subs[heading].strip(), f"{name}: empty '### {heading}'")
            for heading in ("Pros", "Cons"):
                bullets = _bullets(subs[heading])
                self.assertGreaterEqual(len(bullets), 3, f"{name} {heading}")
                self.assertLessEqual(len(bullets), 6, f"{name} {heading}")
                for bullet in bullets:
                    # Every bullet names where its figure or finding comes from.
                    self.assertRegex(bullet, r"\([^()]*(?:\([^()]*\)[^()]*)*\)\.?$", f"{name} {heading}: {bullet[:90]}")
                    self.assertRegex(
                        bullet,
                        r"\((?:[^()]|\([^()]*\))*(?:Report [A-E]\d?|main report|editors site|viewers site|project README|this page)",
                        f"{name} {heading}: {bullet[:90]}",
                    )
        for name in PENDING_HEADINGS:
            self.assertIn(PENDING_SENTENCE % name, sections[name])
        for slug in slugs:
            self.assertNotIn("are not in the reports yet", sections[VENDOR_HEADINGS[slug]])
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

    def test_per_tool_links_land_on_a_vendors_section(self):
        sections = _vendor_sections(_read(os.path.join(ROOT, "reports", "vendors.md")))
        anchors = {_github_anchor(name) for name in sections}
        self.assertEqual(len(anchors), len(sections))
        self.assertEqual(_github_anchor("Plate.js"), "platejs")
        self.assertEqual(_github_anchor("OnlyOffice (CryptPad build)"), "onlyoffice-cryptpad-build")
        for slug in SLUGS:
            self.assertEqual(outreach.VENDOR_ANCHORS[slug], _github_anchor(VENDOR_HEADINGS[slug]), slug)
            self.assertEqual(gate.VENDOR_HEADINGS[slug], VENDOR_HEADINGS[slug], slug)
        self.assertEqual(
            outreach.url(outreach.note_path("docsplus")),
            "https://github.com/arthrod/editors_trial/blob/main/reports/vendors.md#docsplus",
        )
        drafts = os.path.join(ROOT, "outreach")
        linked = 0
        for name in sorted(os.listdir(drafts)):
            if not name.endswith(".md"):
                continue
            body = _read(os.path.join(drafts, name))
            self.assertNotIn("reports/extras/", body, name)
            for anchor in re.findall(r"blob/main/reports/vendors\.md#([\w-]+)", body):
                linked += 1
                self.assertIn(anchor, anchors, name)
        self.assertGreater(linked, 0)

    def test_lane_blocks_quote_the_shipped_scorer(self):
        lanes = {
            os.path.join(ROOT, "out", "folio", "complex.docx"): "Folio",
            os.path.join(ROOT, "out", "folio-editor", "complex.docx"): "Folio",
            os.path.join(ROOT, "out", "eigenpal", "complex.docx"): "eigenpal",
            os.path.join(ROOT, "out", "eigenpal-editor", "complex.docx"): "eigenpal",
        }
        sections = _vendor_sections(_read(os.path.join(ROOT, "reports", "vendors.md")))
        inp = sc.Pkg(FIXTURE)
        for out_path, heading in lanes.items():
            self.assertTrue(os.path.isfile(out_path), out_path)
            checks = sc.build_checks(inp, sc.Pkg(out_path))
            failed = [c[0] for c in checks if not c[4]]
            weighted = "%s%%" % sc.score(checks)["weighted"]
            body = _subsections(sections[heading])["This run"]
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

    def test_report_a_numbers_match_the_packages_and_the_gate_sees_the_docx(self):
        md_rel = "reports/Report A - Serialization by Namespace (2026).md"
        docx_rel = "reports/Report A - Serialization by Namespace (2026).docx"
        texts, git_error = gate.updated_report_texts()
        self.assertEqual(git_error, "")
        scanned = dict(texts)
        self.assertIn(md_rel, scanned)
        self.assertIn(docx_rel, scanned)
        archived = (
            "reports/archive/Report A - Serialized vs Pass-Through vs Rendered (2026).md"
        )
        self.assertNotIn(archived, scanned)
        corpus_lines = []
        measured = {}
        for label, path in mac.PACKAGES:
            lengths = mac.alternate_content_lengths(path)
            self.assertEqual(len(lengths), 1, label)
            measured[label] = lengths[0]
            token = mac.format_token(lengths[0])
            self.assertIn(token, scanned[md_rel], label)
            self.assertIn(token, scanned[docx_rel], label)
            corpus_lines.append(token)
        self.assertEqual(measured["genoffice"], measured["corpus"])
        report = scanned[md_rel] + "\n" + scanned[docx_rel]
        self.assertEqual(gate.tokens_absent_from_corpus(report, "\n".join(corpus_lines)), [])
        self.assertEqual(
            gate.tokens_absent_from_corpus("weight 14% and 9 bytes", "nope"),
            ["14%", "9 bytes"],
        )
        self.assertEqual(gate.tokens_absent_from_corpus("weight 14%", "kept 14%"), [])

    def test_number_gate_fails_a_percentage_the_log_does_not_contain(self):
        self.assertEqual(gate.number_tokens("kept 97.5% and 25355 bytes"), ["97.5%", "25355 bytes"])
        self.assertEqual(
            gate.tokens_absent_from_corpus("kept 97.5% and 25355 bytes", "25355 bytes"),
            ["97.5%"],
        )


if __name__ == "__main__":
    unittest.main()
