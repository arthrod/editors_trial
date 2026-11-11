"""Shared whole-document reader and content-gate regressions (#146/#152)."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from perf.runner import benchmark_document as bd
from perf.runner import benchmark_warm_cold as bw
from perf.tests import test_b3_fix3 as helpers

REPO = Path(__file__).resolve().parents[2]
EDIT_SURFACE = REPO / "perf/runner/edit_surface.mjs"
WARM_COLD = REPO / "perf/runner/warm_cold_browser.mjs"
HOSTS = REPO / "perf/tests/fixtures/hosts"


class DocumentReaderContract(unittest.TestCase):
    def node(self, body: str) -> dict:
        script = f"""
import assert from 'node:assert/strict';
const mod = await import({json.dumps(str(EDIT_SURFACE))});
{body}
"""
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def test_eigenpal_reader_aggregates_every_document_root(self):
        payload = self.node(
            """
assert.equal(typeof mod.READ_EDITOR_DOCUMENT_TEXT, 'function');
const roots = [
  { textContent: 'REAL DOCUMENT CONTENT\\nFirst paragraph of the document.' },
  { textContent: 'Second paragraph of the document.' },
];
roots.forEach((r) => { r.childNodes = []; });
globalThis.document = {
  querySelectorAll(selector) {
    assert.equal(selector, '.docx-page-content');
    return roots;
  },
};
const result = mod.READ_EDITOR_DOCUMENT_TEXT({
  kind: 'dom', root: '.docx-page-content',
});
assert.equal(result.text, 'REAL DOCUMENT CONTENT\\nFirst paragraph of the document.\\nSecond paragraph of the document.');
assert.equal(result.chars, result.text.length);
assert.equal(result.oracle, 'dom');
console.log(JSON.stringify(result));
"""
        )
        self.assertEqual(payload["oracle"], "dom")
        self.assertIn("Second paragraph", payload["text"])

    def test_eigenpal_reader_uses_the_full_editor_model(self):
        payload = self.node(
            """
assert.equal(typeof mod.READ_EDITOR_DOCUMENT_TEXT, 'function');
globalThis.window = {
  __DOCX_EDITOR_E2E__: {
    getEditor() {
      return {
        surface: {
          session: {
            bodyText() { return 'REAL DOCUMENT CONTENT complete model text'; },
          },
        },
      };
    },
  },
};
const result = mod.READ_EDITOR_DOCUMENT_TEXT({ kind: 'model', model: 'eigenpal' });
assert.equal(result.text, 'REAL DOCUMENT CONTENT complete model text');
assert.equal(result.oracle, 'perf_model');
assert.equal(result.source, 'eigenpal_model');
console.log(JSON.stringify(result));
"""
        )
        self.assertEqual(payload["oracle"], "perf_model")
        self.assertIn("complete model text", payload["text"])

    def test_dom_reader_prefers_text_content_without_forcing_layout(self):
        payload = self.node(
            """
assert.equal(typeof mod.READ_EDITOR_DOCUMENT_TEXT, 'function');
globalThis.document = {
  querySelectorAll() {
    return [{ textContent: 'Document model text', innerText: 'Layout-dependent text', childNodes: [] }];
  },
};
const result = mod.READ_EDITOR_DOCUMENT_TEXT({ kind: 'dom', root: '#document' });
assert.equal(result.text, 'Document model text');
console.log(JSON.stringify(result));
"""
        )
        self.assertEqual(payload["text"], "Document model text")

    def test_dom_reader_never_falls_back_to_layout_dependent_inner_text(self):
        payload = self.node(
            """
assert.equal(typeof mod.READ_EDITOR_DOCUMENT_TEXT, 'function');
let innerTextReads = 0;
const element = {
  get textContent() { return ''; },
  get innerText() { innerTextReads += 1; return 'Layout-dependent text'; },
};
globalThis.document = { querySelectorAll() { return [element]; } };
const result = mod.READ_EDITOR_DOCUMENT_TEXT({ kind: 'dom', root: '#document' });
assert.equal(innerTextReads, 0);
assert.equal(result.text, '');
console.log(JSON.stringify(result));
"""
        )
        self.assertEqual(payload["text"], "")

    def test_docen_reader_uses_the_complete_prosemirror_document(self):
        payload = self.node(
            """
assert.equal(typeof mod.READ_EDITOR_DOCUMENT_TEXT, 'function');
let readRange = null;
globalThis.window = {
  __DOCEN__: {
    editor: {
      state: {
        doc: {
          content: { size: 23 },
          textBetween(from, to, separator) {
            readRange = { from, to, separator };
            return 'REAL DOCUMENT CONTENT complete model text';
          },
        },
      },
    },
  },
};
const result = mod.READ_EDITOR_DOCUMENT_TEXT({ kind: 'model', model: 'docen' });
assert.deepEqual(readRange, { from: 0, to: 23, separator: ' ' });
assert.equal(result.text, 'REAL DOCUMENT CONTENT complete model text');
assert.equal(result.chars, 41);
assert.equal(result.oracle, 'perf_model');
console.log(JSON.stringify(result));
"""
        )
        self.assertEqual(payload["oracle"], "perf_model")
        self.assertIn("complete model text", payload["text"])

    def test_each_editor_has_one_document_text_descriptor(self):
        payload = self.node(
            """
assert.equal(typeof mod.documentTextSurface, 'function');
assert.equal(typeof mod.hasDocumentTextSurface, 'function');
assert.equal(mod.hasDocumentTextSurface('eigenpal'), true);
assert.equal(mod.hasDocumentTextSurface('apryse'), false);
const expected = {
  plate: { kind: 'dom', root: '[contenteditable="true"]', whole: true },
  docxodus: { kind: 'dom', root: '#pages', whole: false },
  superdoc: { kind: 'dom', root: '#editor .superdoc-page', whole: false, domText: 'innerText' },
  genoffice: { kind: 'dom', root: '.doc-page.ProseMirror:not(.mp-page)', whole: false },
  eigenpal: { kind: 'model', model: 'eigenpal' },
  folio: { kind: 'dom', root: '[data-page-number]', whole: false },
  canvas: { kind: 'model', model: 'canvas_editor' },
  docen: { kind: 'model', model: 'docen' },
  wordcraft: { kind: 'unavailable' },
};
const actual = Object.fromEntries(Object.keys(expected).map((id) => [id, mod.documentTextSurface(id)]));
assert.deepEqual(actual, expected);
console.log(JSON.stringify(actual));
"""
        )
        self.assertEqual(set(payload), {"plate", "docxodus", "superdoc", "genoffice", "eigenpal", "folio", "canvas", "docen", "wordcraft"})


class CorpusLengthBaseline(unittest.TestCase):
    def corpus(self, workload_id: str) -> Path:
        from perf.fixtures.docx_workload import workload_docx

        path = Path(tempfile.mkdtemp(dir=REPO / ".scratch" / "tmp")) / f"{workload_id}.docx"
        path.write_bytes(workload_docx(workload_id)["docx"])
        self.addCleanup(path.parent.rmdir)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_prose_keeps_the_two_percent_mass_band(self):
        meta = bd.corpus_content_expectations(self.corpus("prose-500w"))
        self.assertIn("length_check", meta)
        self.assertEqual(meta["length_check"], "applied")
        self.assertIsNone(meta["length_check_reason"])
        self.assertGreater(meta["text_chars"], 4000)
        flags = bd.corpus_content_expectation_flags(self.corpus("prose-500w"))
        self.assertIn("--fixture-text-chars", flags)

    def test_complex_corpus_uses_coarse_band_with_fixture_chars(self):
        path = self.corpus("complex-corpus")
        meta = bd.corpus_content_expectations(path)
        self.assertIn("length_check", meta)
        self.assertEqual(meta["length_check"], "coarse")
        self.assertGreater(meta["text_chars"], 1000)
        self.assertIn("revision", meta["length_check_reason"])
        self.assertIn("field", meta["length_check_reason"])
        self.assertIn("alternate", meta["length_check_reason"].lower())
        self.assertIn("coarse", meta["length_check_reason"].lower())
        self.assertEqual(meta["closing"], "Last paragraph.")
        flags = bd.corpus_content_expectation_flags(path)
        self.assertIn("--fixture-text-chars", flags)
        self.assertIn("--length-check-mode", flags)
        self.assertEqual(flags[flags.index("--length-check-mode") + 1], "coarse")
        self.assertIn("--expected-closing-sentinel", flags)
        self.assertEqual(flags[flags.index("--expected-closing-sentinel") + 1], "Last paragraph.")


class WarmColdNamedRefusal(unittest.TestCase):
    def test_content_length_disclosure_is_shared_by_every_warm_attempt(self):
        self.assertTrue(hasattr(bw, "_content_length_diagnostic"))
        self.assertEqual(
            bw._content_length_diagnostic(
                {"length_check": "not_applicable", "length_check_reason": "editor-dependent model"}
            ),
            {
                "content_length_check": "not_applicable",
                "content_length_check_reason": "editor-dependent model",
            },
        )

    def test_content_refusal_writes_named_c03_c05_c06_attempts(self):
        from perf.fixtures.profiles import size_ladder

        self.assertTrue(hasattr(bw, "_write_content_refusals"))
        workload = next(row for row in size_ladder() if row["workload_id"] == "prose-500w")
        with tempfile.TemporaryDirectory(dir=REPO / ".scratch" / "tmp") as tmp:
            rows = bw._write_content_refusals(
                attempt_dir=Path(tmp),
                editor_id="wordcraft",
                lane="wasm_ui",
                editor_version="test-version",
                workload_row=workload,
                fixture_sha256="0" * 64,
                docx_size=1234,
                criteria_map={
                    "C03": ("first_usable", "browser_visible"),
                    "C05": ("presented_frame", "browser_visible"),
                    "C06": ("input_to_next_paint", "browser_visible"),
                },
                content_refusal={"surface_reason": "document_content_unverifiable", "editor_error": None},
                content_meta={"length_check": "applied", "length_check_reason": None},
            )
            attempts = [json.loads(path.read_text()) for path in Path(tmp).glob("*.json")]
        self.assertEqual(len(rows), 6)
        self.assertEqual({row["outcome"] for row in rows}, {"unverified"})
        self.assertEqual({row["failure_reason"] for row in rows}, {"document_content_unverifiable"})
        self.assertEqual({trial["criterion_id"] for trial in attempts}, {"C03", "C05", "C06"})
        self.assertEqual({trial["refusal_code"] for trial in attempts}, {"unverified"})

    def test_content_refusal_is_persisted_as_unverified_not_a_crash(self):
        from perf.tests.test_schema import _env

        with tempfile.TemporaryDirectory(dir=REPO / ".scratch" / "tmp") as tmp:
            path = bw._write_unverified(
                attempt_dir=Path(tmp),
                criterion_id="C03",
                layer="browser_visible",
                boundary="first_usable",
                editor_id="wordcraft",
                lane="wasm_ui",
                env=_env(),
                failure_reason="document_content_unverifiable",
                diagnostic={"content_refusal": {"surface_reason": "document_content_unverifiable"}},
            )
            trial = json.loads(path.read_text())
        self.assertEqual(trial["outcome"], "unverified")
        self.assertEqual(trial["refusal_code"], "unverified")
        self.assertEqual(trial["failure_reason"], "document_content_unverifiable")
        self.assertEqual(trial["samples_ms"], [])


class WarmColdDocumentReader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, _thread, cls.base_url = helpers._load_server().serve(HOSTS)
        cls._corpus_dir = tempfile.TemporaryDirectory(dir=REPO / ".scratch" / "tmp")
        cls.corpus = Path(cls._corpus_dir.name) / "corpus.docx"
        cls.corpus.write_bytes(b"PK\x03\x04fixture")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._corpus_dir.cleanup()

    def probe(self, host: str, editor: str, ready: str, edit_selector: str) -> dict:
        cmd = [
            "node",
            str(WARM_COLD),
            "--driver",
            "playwright",
            "--editor",
            editor,
            "--url",
            f"{self.base_url}/{host}",
            "--corpus",
            str(self.corpus),
            "--corpus-route",
            "/corpus.docx",
            "--ready-selector",
            ready,
            "--edit-selector",
            edit_selector,
            "--pairs",
            "1",
            "--skip-edit",
            "true",
            "--fresh-context-probe",
            "false",
            "--expected-opening-text",
            "REAL DOCUMENT CONTENT",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired as exc:
            self.fail("warm/cold content probe did not terminate: %s" % exc)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def test_eigenpal_reads_the_document_not_the_first_edit_fragment(self):
        payload = self.probe(
            "b3_eigenpal_document.html",
            "eigenpal",
            '#host[data-ready="1"]',
            ".docx-page-content [data-paragraph-id][data-start]",
        )
        check = payload["pairs"][0]["cold"]["content_check"]
        self.assertTrue(check["content_verified"], check)
        self.assertIsNone(check["surface_reason"])
        self.assertIn("Second paragraph", check["document_text"])

    def test_docen_reads_the_model_behind_its_shadow_root(self):
        payload = self.probe(
            "b3_docen_document.html",
            "docen",
            '#host[data-ready="1"]',
            "docen-document .canvas-pages > div:first-child",
        )
        check = payload["pairs"][0]["cold"]["content_check"]
        self.assertTrue(check["content_verified"], check)
        self.assertIsNone(check["surface_reason"])
        self.assertIn("complete model text", check["document_text"])

    def test_non_trial_editor_keeps_the_generic_shadow_text_path(self):
        cmd = [
            "node",
            str(REPO / "perf/runner/document_probe.mjs"),
            "--mode",
            "load",
            "--editor",
            "apryse",
            "--url",
            f"{self.base_url}/b3_shadow_canvas_text.html",
            "--corpus",
            str(self.corpus),
            "--corpus-route",
            "/corpus.docx",
            "--doc-selector",
            "#host",
            "--document-selector",
            "#pageContainer1",
            "--usable-signal",
            "shadow_text",
            "--timeout-ms",
            "4000",
            "--expected-opening-text",
            "REAL DOCUMENT CONTENT",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["content_verified"], payload)
        self.assertIn("REAL DOCUMENT CONTENT", payload["document_text"])

    def test_non_trial_editor_warm_keeps_the_open_shadow_text_path(self):
        payload = self.probe(
            "b3_shadow_canvas_text.html",
            "apryse",
            "#host",
            "#pageContainer1",
        )
        check = payload["pairs"][0]["cold"]["content_check"]
        self.assertTrue(check["content_verified"], check)
        self.assertIsNone(check["surface_reason"])

    def test_complex_corpus_truncation_is_still_refused_by_the_closing_witness(self):
        from perf.fixtures.docx_workload import workload_docx

        corpus = Path(tempfile.mkdtemp(dir=REPO / ".scratch" / "tmp")) / "complex.docx"
        corpus.write_bytes(workload_docx("complex-corpus")["docx"])
        self.addCleanup(corpus.parent.rmdir)
        self.addCleanup(corpus.unlink, missing_ok=True)
        meta = bd.corpus_content_expectations(corpus)
        cmd = [
            "node",
            str(REPO / "perf/runner/document_probe.mjs"),
            "--mode",
            "load",
            "--editor",
            "canvas",
            "--url",
            f"{self.base_url}/b3_complex_model_truncated.html",
            "--corpus",
            str(corpus),
            "--corpus-route",
            "/corpus.docx",
            "--doc-selector",
            "#doc",
            "--usable-signal",
            "screencast_ink",
            "--timeout-ms",
            "4000",
            "--expected-opening-text",
            meta["opening"],
            *bd.corpus_content_expectation_flags(corpus),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["content_verified"], payload)
        self.assertEqual(payload["surface_reason"], "document_content_mismatch", payload)

    def test_wordcraft_unavailable_text_is_a_named_refusal_not_a_throw(self):
        payload = self.probe(
            "b3_wordcraft_unavailable.html",
            "wordcraft",
            '#host[data-ready="1"]',
            "#wordcraft_canvas",
        )
        check = payload["pairs"][0]["cold"]["content_check"]
        self.assertFalse(check["content_verified"], check)
        self.assertEqual(check["surface_reason"], "document_content_unverifiable")
        self.assertEqual(bw._content_refusal(payload)["surface_reason"], "document_content_unverifiable")


class ContentGatePlants(DocumentReaderContract):
    def node_model(self, body: str) -> dict:
        script = f"""
import assert from 'node:assert/strict';
const gate = await import({json.dumps(str(REPO / "perf/runner/perf_model_text.mjs"))});
{body}
"""
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def test_closing_witness_must_be_at_end_not_includes(self):
        out = self.node_model("""
const opening = 'REAL DOCUMENT CONTENT';
const closing = 'Last paragraph.';
const endsOnly = gate.evaluatePerfModelDocument({
  text: closing,
  expectedOpening: opening,
  expectedClosing: closing,
  fixtureChars: 0,
});
const withBoth = gate.evaluatePerfModelDocument({
  text: `${opening} middle only text here. ${closing}`,
  expectedOpening: opening,
  expectedClosing: closing,
  fixtureChars: 0,
});
assert.equal(endsOnly.ok, false);
assert.equal(withBoth.ok, true);
console.log(JSON.stringify({ endsOnly: endsOnly.ok, withBoth: withBoth.ok }));
""")
        self.assertFalse(out["endsOnly"])
        self.assertTrue(out["withBoth"])

    def test_coarse_band_refuses_half_length(self):
        out = self.node_model("""
const check = gate.evaluatePerfModelDocument({
  text: 'x'.repeat(600),
  expectedOpening: 'REAL',
  expectedClosing: 'Last paragraph.',
  fixtureChars: 1202,
  lengthCheckMode: 'coarse',
});
assert.equal(check.lengthOk, false);
assert.equal(check.ok, false);
console.log(JSON.stringify({ lengthOk: check.lengthOk }));
""")
        self.assertFalse(out["lengthOk"])

    def test_dom_virtualized_is_opening_only(self):
        out = self.node_model("""
const check = gate.evaluateDomDocument({
  text: 'REAL DOCUMENT CONTENT visible only',
  expectedOpening: 'REAL DOCUMENT CONTENT',
  expectedClosing: 'Last paragraph.',
  fixtureChars: 4213,
  whole: false,
});
assert.equal(check.ok, true);
assert.equal(check.content_check, 'opening_only');
const half = gate.evaluateDomDocument({
  text: 'REAL DOCUMENT CONTENT',
  expectedOpening: 'REAL DOCUMENT CONTENT',
  expectedClosing: 'Last paragraph.',
  fixtureChars: 4213,
  whole: false,
});
assert.equal(half.ok, true);
console.log(JSON.stringify({ content_check: check.content_check, half: half.ok }));
""")
        self.assertEqual(out["content_check"], "opening_only")

    def test_dom_whole_document_refuses_opening_only(self):
        out = self.node_model("""
const check = gate.evaluateDomDocument({
  text: 'REAL DOCUMENT CONTENT',
  expectedOpening: 'REAL DOCUMENT CONTENT',
  expectedClosing: 'Last paragraph.',
  fixtureChars: 4213,
  whole: true,
  lengthCheckMode: 'applied',
});
assert.equal(check.ok, false);
console.log(JSON.stringify({ ok: check.ok }));
""")
        self.assertFalse(out["ok"])

    def test_visible_dom_reader_skips_aria_hidden(self):
        payload = self.node(
            """
const hidden = { nodeType: 1, getAttribute(k) { return k === 'aria-hidden' ? 'true' : null; },
  childNodes: [{ nodeType: 3, nodeValue: 'REAL DOCUMENT CONTENT opening witness' }] };
const visible = { nodeType: 1, getAttribute() { return null; },
  childNodes: [{ nodeType: 3, nodeValue: 'Wrong visible document text' }] };
const root = { nodeType: 1, getAttribute() { return null; }, childNodes: [hidden, visible] };
globalThis.document = {
  querySelectorAll() { return [root]; },
};
globalThis.getComputedStyle = () => ({ display: 'block', visibility: 'visible' });
const result = mod.READ_EDITOR_DOCUMENT_TEXT({ kind: 'dom', root: '#root' });
assert.equal(result.text.includes('REAL DOCUMENT CONTENT'), false);
assert.equal(result.text.includes('Wrong visible'), true);
console.log(JSON.stringify(result));
"""
        )
        self.assertNotIn("REAL DOCUMENT CONTENT", payload["text"])


class R3lanes4ContentGate(unittest.TestCase):
    """Ruling r3lanes4 #5: honest persisted gate fields, mounted-text check,
    75-125% coarse band."""

    def node_gate(self, body: str):
        script = f"""
import assert from 'node:assert/strict';
const gate = await import({json.dumps(str(REPO / "perf/runner/perf_model_text.mjs"))});
{body}
"""
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def test_coarse_band_is_75_to_125_percent(self):
        out = self.node_gate("""
const ratio = (chars) => gate.evaluatePerfModelDocument({
  text: 'x'.repeat(chars), expectedOpening: 'x', expectedClosing: '',
  fixtureChars: 1202, lengthCheckMode: 'coarse',
});
const out = {
  at60: ratio(721).lengthOk,
  at75: ratio(902).lengthOk,
  at110: ratio(1322).lengthOk,
  at126: ratio(1515).lengthOk,
};
console.log(JSON.stringify(out));
""")
        self.assertIs(out["at60"], False)
        self.assertIs(out["at75"], True)
        self.assertIs(out["at110"], True)
        self.assertIs(out["at126"], False)

    def test_coarse_band_refuses_the_real_half_of_the_real_fixture(self):
        import io
        import zipfile
        from perf.fixtures.docx_workload import docx_paragraph_texts, workload_docx

        blob = workload_docx("complex-corpus")["docx"]
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            paragraphs = docx_paragraph_texts(archive.read("word/document.xml"))
        text = "\n".join(paragraphs)
        half = text[: len(text) // 2]
        out = self.node_gate(
            "const check = gate.evaluatePerfModelDocument({"
            f"text: {json.dumps(half)}, expectedOpening: {json.dumps(text[:24])}, expectedClosing: '',"
            f"fixtureChars: {len(text)}, lengthCheckMode: 'coarse',"
            "}); console.log(JSON.stringify({ok: check.ok, lengthOk: check.lengthOk, ratio: check.model_chars / %d}));"
            % len(text)
        )
        self.assertFalse(out["lengthOk"])
        self.assertFalse(out["ok"])
        self.assertLess(out["ratio"], 0.75)

    def test_virtualized_another_document_with_same_opening_fails(self):
        body = (
            "In property law the titled claim ascends the register. "
            "The fixture continues with its own registered paragraphs and closing "
            "words that never appear anywhere else in this string at all."
        )
        out = self.node_gate("""
const check = gate.evaluateDomDocument({
  text: 'In property law the titled claim ascends the register. ENTIRELY different body words',
  expectedOpening: 'In property law the titled claim ascends the register.',
  expectedClosing: '',
  fixtureChars: %d,
  whole: false,
  fixtureBody: %s,
});
console.log(JSON.stringify({ok: check.ok, content_check: check.content_check,
  mounted: check.mounted_text_in_fixture, reason: check.surface_reason}));
""" % (len(body), json.dumps(body))
        )
        self.assertIs(out["ok"], False)
        self.assertEqual(out["content_check"], "mounted_text_in_fixture")
        self.assertIs(out["mounted"], False)
        self.assertEqual(out["reason"], "document_content_mismatch")

    def test_virtualized_mounted_window_of_the_fixture_passes(self):
        body = (
            "In property law the titled claim ascends the register. "
            "A second paragraph carries the middle of the document. "
            "The final sentence closes the fixture."
        )
        out = self.node_gate("""
const check = gate.evaluateDomDocument({
  text: 'a second paragraph carries the MIDDLE of the document.',
  expectedOpening: 'a second paragraph',
  expectedClosing: '',
  fixtureChars: %d,
  whole: false,
  fixtureBody: %s,
});
console.log(JSON.stringify({ok: check.ok, content_check: check.content_check,
  mounted: check.mounted_text_in_fixture}));
""" % (len(body), json.dumps(body))
        )
        self.assertIs(out["ok"], True)
        self.assertEqual(out["content_check"], "mounted_text_in_fixture")
        self.assertIs(out["mounted"], True)

    def test_virtualized_without_body_keeps_opening_only(self):
        out = self.node_gate("""
const check = gate.evaluateDomDocument({
  text: 'REAL DOCUMENT CONTENT only the opening is mounted',
  expectedOpening: 'REAL DOCUMENT CONTENT',
  expectedClosing: 'Last paragraph.',
  fixtureChars: 4213,
  whole: false,
});
console.log(JSON.stringify({ok: check.ok, content_check: check.content_check}));
""")
        self.assertIs(out["ok"], True)
        self.assertEqual(out["content_check"], "opening_only")

    def test_virtualized_complex_corpus_keeps_opening_only_and_says_so(self):
        out = self.node_gate("""
const check = gate.evaluateDomDocument({
  text: 'REAL DOCUMENT CONTENT and something else entirely',
  expectedOpening: 'REAL DOCUMENT CONTENT',
  expectedClosing: '',
  fixtureChars: 1202,
  lengthCheckMode: 'coarse',
  whole: false,
  fixtureBody: 'a body that is not used on complex-corpus',
});
console.log(JSON.stringify({ok: check.ok, content_check: check.content_check,
  reason: check.content_check_reason}));
""")
        self.assertIs(out["ok"], True)
        self.assertEqual(out["content_check"], "opening_only")
        self.assertIn("ambiguous", out["reason"])

    def test_absent_oracle_records_not_run(self):
        out = self.node_gate("""
const meta = gate.documentContentGateMeta({
  documentRead: { text: '', chars: 0, oracle: 'absent', source: 'unavailable', error: null },
  whole: false,
  expectedOpening: 'REAL DOCUMENT CONTENT',
  expectedClosing: 'Last paragraph.',
  fixtureChars: 4213,
  lengthCheckMode: 'applied',
});
console.log(JSON.stringify({length_check: meta.length_check, enforced: meta.length_enforced,
  content_check: meta.content_check, verdict: meta.verdict.surface_reason}));
""")
        self.assertEqual(out["length_check"], "not_run")
        self.assertIs(out["enforced"], False)
        self.assertEqual(out["content_check"], "not_run")
        self.assertEqual(out["verdict"], "document_content_unverifiable")

    def test_virtualized_meta_reports_the_gate_it_ran(self):
        out = self.node_gate("""
const meta = gate.documentContentGateMeta({
  documentRead: { text: 'the mounted window of the fixture body', chars: 34, oracle: 'dom', source: 'dom', error: null },
  whole: false,
  expectedOpening: 'the mounted',
  expectedClosing: '',
  fixtureChars: 4213,
  lengthCheckMode: 'applied',
  fixtureBody: 'the mounted window of the fixture body and the rest of it',
});
console.log(JSON.stringify({length_check: meta.length_check, enforced: meta.length_enforced,
  content_check: meta.content_check, verdict_ok: meta.verdict.content_verified}));
""")
        self.assertEqual(out["length_check"], "opening_only")
        self.assertIs(out["enforced"], False)
        self.assertEqual(out["content_check"], "mounted_text_in_fixture")
        self.assertIs(out["verdict_ok"], True)

    def corpus(self, workload_id: str) -> Path:
        from perf.fixtures.docx_workload import workload_docx

        path = Path(tempfile.mkdtemp(dir=REPO / ".scratch" / "tmp")) / f"{workload_id}.docx"
        path.write_bytes(workload_docx(workload_id)["docx"])
        self.addCleanup(path.parent.rmdir)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_gate_length_check_profiles_per_editor(self):
        prose = bd.corpus_content_expectations(self.corpus("prose-500w"))
        complex_meta = bd.corpus_content_expectations(self.corpus("complex-corpus"))
        self.assertEqual(
            bd.gate_length_check_for("docxodus", prose),
            {"length_check": "opening_only", "length_enforced": False, "content_check": "mounted_text_in_fixture"},
        )
        self.assertEqual(
            bd.gate_length_check_for("superdoc", complex_meta),
            {"length_check": "opening_only", "length_enforced": False, "content_check": "opening_only"},
        )
        self.assertEqual(
            bd.gate_length_check_for("wordcraft", prose),
            {"length_check": "not_run", "length_enforced": False, "content_check": "not_run"},
        )
        self.assertEqual(
            bd.gate_length_check_for("plate", prose),
            {"length_check": "applied", "length_enforced": True, "content_check": "full"},
        )
        self.assertEqual(
            bd.gate_length_check_for("canvas", complex_meta)["length_check"], "coarse",
        )

    def test_warm_cold_diagnostic_prefers_the_gate_that_ran(self):
        meta = {"length_check": "applied", "length_check_reason": None}
        diagnostic = bw._content_length_diagnostic(
            meta,
            {"length_check": "opening_only", "length_enforced": False, "content_check": "mounted_text_in_fixture"},
        )
        self.assertEqual(diagnostic["content_length_check"], "opening_only")
        self.assertIs(diagnostic["content_length_enforced"], False)
        self.assertEqual(diagnostic["content_check"], "mounted_text_in_fixture")

    def test_load_result_returns_the_gate_fields(self):
        text = (REPO / "perf/runner/document_probe.mjs").read_text(encoding="utf-8")
        load_block = text.split("async function loadResult")[1].split("async function runLoad")[0]
        self.assertIn("content_length_check", load_block)
        self.assertIn("length_enforced", load_block)
        self.assertIn("content_check", load_block)

    def test_document_probe_reads_the_expected_body_path(self):
        text = (REPO / "perf/runner/document_probe.mjs").read_text(encoding="utf-8")
        self.assertIn("PERF_EXPECTED_BODY_PATH", text)
        warm = (WARM_COLD).read_text(encoding="utf-8")
        self.assertIn("PERF_EXPECTED_BODY_PATH", warm)


if __name__ == "__main__":
    unittest.main()
