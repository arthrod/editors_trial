"""Issue #152: DOM hosts, Apryse text layers, and whole-document model gates."""
import json
import subprocess
import unittest
from pathlib import Path

from perf.runner import benchmark_document as bd
from perf.tests import test_b3_fix5 as helpers
from perf.tests.test_b3_fix3 import PROBE, REPO

WARM_COLD = REPO / "perf/runner/warm_cold_browser.mjs"


class CanvasOracleFix152Hosts(helpers.DocumentQuietHosts):
    def corpus_docx(self, body: str) -> None:
        self.corpus.write_bytes(bd.docx_paragraph_bytes(body.encode("utf-8")))

    def load_probe(self, host: str, expected: str, *, selector="#doc", extra=None, signal="screencast_ink"):
        cmd = [
            "node",
            str(PROBE),
            "--mode",
            "load",
            "--url",
            self.base_url + "/" + host,
            "--corpus",
            str(self.corpus),
            "--doc-selector",
            selector,
            "--usable-signal",
            signal,
            "--timeout-ms",
            "4000",
            "--expected-opening-text",
            expected,
        ]
        if extra:
            cmd.extend(extra)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def warm_cold_probe(self, host: str, expected: str):
        cmd = [
            "node",
            str(WARM_COLD),
            "--driver",
            "playwright",
            "--url",
            self.base_url + "/" + host,
            "--corpus",
            str(self.corpus),
            "--corpus-route",
            "/corpus.docx",
            "--ready-selector",
            ".status-ok",
            "--edit-selector",
            "#doc",
            "--pairs",
            "1",
            "--skip-edit",
            "true",
            "--expected-opening-text",
            expected,
            *bd.corpus_content_expectation_flags(self.corpus),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        return json.loads(proc.stdout)


class CanvasOracleFix152Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CanvasOracleFix152Hosts.setUpClass()

    @classmethod
    def tearDownClass(cls):
        CanvasOracleFix152Hosts.tearDownClass()

    def setUp(self):
        self.hosts = CanvasOracleFix152Hosts()

    def test_warm_cold_dom_host_passes_verify_canvas_opening(self):
        body = "REAL DOCUMENT CONTENT for warm cold gate\n"
        self.hosts.corpus_docx(body)
        opening = bd.corpus_opening_text(self.hosts.corpus)
        payload = self.hosts.warm_cold_probe("b3_warm_cold_dom.html", opening)
        pair = payload["pairs"][0]["cold"]
        self.assertIsNotNone(pair.get("first_usable_ms"), pair)

    def test_apryse_shaped_surface_keeps_shadow_text_for_c11(self):
        opening = "REAL DOCUMENT CONTENT"
        self.hosts.corpus_docx(f"{opening} in the text layer\n")
        payload = self.hosts.load_probe(
            "b3_shadow_canvas_text.html",
            opening,
            selector="#host",
            signal="shadow_text",
            extra=["--document-selector", "#pageContainer1"],
        )
        self.assertTrue(payload["content_verified"], payload)
        self.assertIn("REAL DOCUMENT CONTENT", payload["document_text"])

    def test_canvas_model_whole_document_refuses_short_hook(self):
        opening = "REAL DOCUMENT CONTENT"
        body = f"{opening} for a complete fixture\nZZ-END-OF-DOCUMENT probe\n"
        self.hosts.corpus_docx(body)
        flags = bd.corpus_content_expectation_flags(self.hosts.corpus)
        payload = self.hosts.load_probe("b3_canvas_model_truncated.html", opening, extra=flags)
        self.assertFalse(payload["content_verified"], payload)
        self.assertEqual(payload["surface_reason"], "document_content_mismatch", payload)
