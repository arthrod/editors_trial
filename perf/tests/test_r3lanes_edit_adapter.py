"""Lanes memory, document, warm_cold share perf/runner/edit_surface.mjs (#155.1, r3lanes)."""
from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class LaneEditBurstModule(unittest.TestCase):
    def test_reflow_block_selector_uses_editor_dom_for_docxodus(self):
        text = (REPO / "perf" / "runner" / "lane_edit_burst.mjs").read_text(encoding="utf-8")
        self.assertIn("reflowBlockSelector", text)
        self.assertIn("#editorHost", text)

    def test_reflow_selectors_match_document_lane_hosts(self):
        text = (REPO / "perf" / "runner" / "lane_edit_burst.mjs").read_text(encoding="utf-8")
        self.assertIn("'.doc-paragraph'", text)
        self.assertIn("'.layout-page-content [data-block-id]'", text)
        self.assertIn("gatherReflowBefore", text)

    def test_superdoc_edit_surface_uses_live_document_class(self):
        text = (REPO / "perf" / "runner" / "edit_surface.mjs").read_text(encoding="utf-8")
        self.assertIn("superdoc__document", text)

    def test_the_callers_timeout_bounds_the_text_line_wait(self):
        # No cap of its own: the resources lane allows 600 s for a 250k-word document.
        text = (REPO / "perf" / "runner" / "edit_surface.mjs").read_text(encoding="utf-8")
        self.assertNotIn("120_000", text)
        self.assertIn("polling: 100", text)
        self.assertIn("textLineTimeoutMs === null ? timeoutMs : textLineTimeoutMs", text)

    def test_lane_edit_burst_exists_and_reexports_prepare_edit_surface(self):
        path = REPO / "perf" / "runner" / "lane_edit_burst.mjs"
        self.assertTrue(path.is_file(), "lane_edit_burst.mjs is the shared entry for editing lanes")
        text = path.read_text(encoding="utf-8")
        self.assertIn("prepareEditSurface", text)
        self.assertIn("prepareResourceBurst", text)


class MemoryProbeUsesAdapter(unittest.TestCase):
    def test_memory_probe_imports_lane_edit_burst_and_accepts_editor(self):
        text = (REPO / "perf" / "runner" / "memory_probe.mjs").read_text(encoding="utf-8")
        self.assertIn("lane_edit_burst.mjs", text)
        self.assertIn("opt.editor", text)
        self.assertNotIn("bodyTextLength(first.page)", text.split("edit")[1] if "edit" in text else text)

    def test_memory_probe_ready_timeout_allows_big_documents(self):
        text = (REPO / "perf" / "runner" / "memory_probe.mjs").read_text(encoding="utf-8")
        self.assertIn("LANE_LOAD_TIMEOUT_MS", text)
        self.assertIn("MEMORY_EDIT_POLL_CAP_MS", text)

    def test_probe_command_passes_editor_id(self):
        import perf.runner.benchmark_memory as mem

        cmd = mem._probe_command(
            {"url": "http://127.0.0.1:5208/", "corpus_route": "/x", "edit_selector": ".x", "error_js": "window.__DOCX_ERROR__"},
            Path("/tmp/f.docx"),
            burst=12,
            quiescence_ms=10,
            reopen=True,
            editor_id="canvas",
        )
        joined = " ".join(cmd)
        self.assertIn("--editor", joined)
        self.assertIn("canvas", joined)
        self.assertIn("--poll-bound-ms", joined)


class DocumentReflowUsesAdapter(unittest.TestCase):
    def test_document_probe_reflow_prepares_edit_surface(self):
        text = (REPO / "perf" / "runner" / "document_probe.mjs").read_text(encoding="utf-8")
        self.assertIn("prepareLaneCaret", text)
        self.assertIn("opt.editor", text)
        self.assertIn("gatherReflowBefore", text)

    def test_wordcraft_c12_is_not_applicable_before_probe(self):
        text = (REPO / "perf" / "runner" / "benchmark_document.py").read_text(encoding="utf-8")
        self.assertIn('editor_id == "wordcraft"', text)
        self.assertIn("not_applicable", text)

    def test_probe_cmd_passes_editor_to_document_probe(self):
        import perf.runner.benchmark_document as doc

        cmd = doc._probe_cmd(
            mode="reflow",
            target={"url": "http://127.0.0.1:5208/", "corpus_route": "/c"},
            cfg={"doc_selector": "p", "edit_selector": ".x", "page_model": "continuous_flow"},
            corpus_path=Path("/tmp/f.docx"),
            extra=["--editor", "docxodus"],
        )
        self.assertIn("--editor", cmd)
        self.assertIn("docxodus", cmd)


class WarmColdEditUsesAdapter(unittest.TestCase):
    def test_measure_edit_uses_edit_surface_when_editor_is_set(self):
        text = (REPO / "perf" / "runner" / "warm_cold_browser.mjs").read_text(encoding="utf-8")
        self.assertIn("prepareLaneCaret", text)
        self.assertIn("confirmLaneEdit", text)
        self.assertIn("EDIT_SURFACES", text)

    def test_warm_cold_probe_passes_editor_flag(self):
        text = (REPO / "perf" / "runner" / "benchmark_warm_cold.py").read_text(encoding="utf-8")
        self.assertIn('cmd.extend(["--editor", editor_id])', text)


class EditLanesWorkload(unittest.TestCase):
    def test_memory_document_warm_cold_strip_document_protection_on_complex_corpus(self):
        from perf.fixtures.docx_workload import EDIT_LANES, workload_for_lane

        for lane in ("memory", "document", "warm_cold"):
            self.assertIn(lane, EDIT_LANES)
        meta = workload_for_lane("complex-corpus", "memory")
        self.assertEqual(meta.get("fixture_variant"), "complex-corpus-without-document-protection")


if __name__ == "__main__":
    unittest.main()
