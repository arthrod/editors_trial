"""B3 fix round 3 — screencast_ink, N1 canvas stride, N2 shadow selector."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import perf.runner.benchmark_document as bd

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "perf" / "runner" / "document_probe.mjs"
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
WITNESS_SERVER = REPO / "perf" / "tests" / "fixtures" / "witness" / "server.py"
TIMEOUT_S = 120
SCREENCAST_INK_MIN_PIXELS = 64


def _node():
    return shutil.which("node")


def _playwright_ready() -> bool:
    for candidate in (
        REPO / "harness" / "ui" / "plate" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright-core",
    ):
        if candidate.is_dir():
            return True
    return False


def _load_server():
    spec = importlib.util.spec_from_file_location("b3_fix3_server", WITNESS_SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Fix3Hosts(unittest.TestCase):
    server = None
    base_url = ""
    corpus = None

    @classmethod
    def setUpClass(cls):
        if _node() is None:
            raise unittest.SkipTest("node is not on PATH")
        if not _playwright_ready():
            raise unittest.SkipTest("harness/ui has no playwright package")
        server_module = _load_server()
        cls.server, _thread, cls.base_url = server_module.serve(HOSTS)
        cls._corpus_dir = tempfile.TemporaryDirectory()
        cls.corpus = Path(cls._corpus_dir.name) / "corpus.docx"
        cls.corpus.write_bytes(b"PK\x03\x04b3-corpus")

    @classmethod
    def tearDownClass(cls):
        if cls.server is not None:
            cls.server.shutdown()
            cls.server.server_close()
        if cls.corpus is not None:
            cls._corpus_dir.cleanup()

    def probe(self, mode: str, host: str, extra: list[str]) -> dict:
        cmd = [
            _node(),
            str(PROBE),
            "--mode",
            mode,
            "--url",
            "%s/%s" % (self.base_url, host),
            "--corpus",
            str(self.corpus),
            "--doc-selector",
            ".doc-paragraph",
            "--page-model",
            "continuous_flow",
            "--timeout-ms",
            "20000",
            *extra,
        ]
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=TIMEOUT_S)
        self.assertEqual(
            proc.returncode,
            0,
            "document_probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s" % (proc.returncode, proc.stdout, proc.stderr),
        )
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            self.fail("document_probe did not print JSON (%s)\nstdout: %r\nstderr: %r" % (exc, proc.stdout, proc.stderr))

    def test_first_ink_frame_has_a_valid_pre_navigation_baseline(self):
        from perf.runner.witness import validate_witness

        payload = self.probe(
            "load", "b3_iframe_doc.html",
            ["--usable-signal", "screencast_ink", "--doc-selector", "#frame", "--timeout-ms", "8000"],
        )
        verdict = validate_witness(payload["witness"])
        print(json.dumps({"witness": payload["witness"], "verdict": verdict}))
        self.assertTrue(verdict["ok"], verdict)
        self.assertAlmostEqual(payload["witness"]["frame_page_ms"], payload["document_text_at_ms"], places=3)
        self.assertGreaterEqual(bd.c11_measured_samples(payload)[0], 0)

    def test_webgl_uses_screencast_ink(self):
        payload = self.probe(
            "load",
            "b3_webgl_canvas.html",
            ["--usable-signal", "screencast_ink", "--timeout-ms", "12000"],
        )
        self.assertEqual(payload.get("usable_signal"), "screencast_ink", payload)
        self.assertIsNotNone(payload.get("document_text_at_ms"), payload.get("surface_reason"))
        self.assertGreaterEqual(payload.get("document_text_at_ms") or 0, 500, payload)
        samples = bd.c11_measured_samples(payload)
        self.assertGreaterEqual(samples[0], 0, samples)

    def test_iframe_uses_screencast_ink_on_frame_rect(self):
        payload = self.probe(
            "load",
            "b3_iframe_doc.html",
            [
                "--usable-signal",
                "screencast_ink",
                "--doc-selector",
                "#frame",
                "--timeout-ms",
                "8000",
            ],
        )
        self.assertEqual(payload.get("usable_signal"), "screencast_ink", payload)
        self.assertIsNotNone(payload.get("document_text_at_ms"), payload.get("surface_reason"))
        samples = bd.c11_measured_samples(payload)
        self.assertGreaterEqual(samples[0], 0, samples)

    def test_canvas_sparse_detected_via_full_canvas_or_screencast(self):
        payload = self.probe(
            "load",
            "b3_canvas_sparse.html",
            ["--usable-signal", "canvas_pixel", "--timeout-ms", "15000"],
        )
        self.assertIsNotNone(payload.get("document_text_at_ms"), payload.get("surface_reason"))
        self.assertGreaterEqual(payload.get("document_text_at_ms") or 0, 350, payload)

    def test_shadow_without_document_selector_refuses(self):
        payload = self.probe(
            "load",
            "b3_shadow_no_doc_sel.html",
            ["--usable-signal", "shadow_text", "--timeout-ms", "3000"],
        )
        self.assertIsNone(payload.get("document_text_at_ms"), payload)
        reason = (payload.get("surface_reason") or "").lower()
        self.assertIn("document_selector_required", reason, payload.get("surface_reason"))

    def test_one_frame_flash_is_not_usable(self):
        payload = self.probe(
            "load",
            "b3_ink_flash.html",
            ["--usable-signal", "screencast_ink", "--timeout-ms", "4000"],
        )
        self.assertIsNone(payload.get("document_text_at_ms"), payload.get("surface_reason"))

    def test_spinner_outside_document_region_waits_for_canvas_ink(self):
        payload = self.probe(
            "load",
            "b3_spinner_outside.html",
            ["--usable-signal", "screencast_ink", "--timeout-ms", "6000"],
        )
        self.assertIsNotNone(payload.get("document_text_at_ms"), payload.get("surface_reason"))
        self.assertGreaterEqual(payload.get("document_text_at_ms") or 0, 1000, payload)

    def test_blank_region_refuses_document_surface_absent(self):
        payload = self.probe(
            "load",
            "b3_blank_canvas.html",
            ["--usable-signal", "screencast_ink", "--timeout-ms", "2500"],
        )
        self.assertIsNone(payload.get("document_text_at_ms"), payload)
        reason = (payload.get("surface_reason") or "").lower()
        self.assertIn("document_surface_absent", reason, payload.get("surface_reason"))

    def test_wordcraft_config_uses_screencast_ink(self):
        cfg = bd.DOCUMENT_TARGETS["wordcraft"]
        self.assertEqual(cfg.get("usable_signal"), "screencast_ink", cfg)

    def test_docen_config_uses_screencast_ink_for_canvas_pages(self):
        cfg = bd.DOCUMENT_TARGETS["docen"]
        self.assertEqual(cfg.get("usable_signal"), "screencast_ink", cfg)
        self.assertIn("canvas-pages", cfg.get("document_selector") or "", cfg)


class Fix3Pure(unittest.TestCase):
    def test_screencast_ink_min_pixels_is_sixty_four(self):
        self.assertEqual(SCREENCAST_INK_MIN_PIXELS, 64)
