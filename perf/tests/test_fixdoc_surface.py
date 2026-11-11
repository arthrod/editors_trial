"""B3 document lane: painted aria-hidden text, editor boot errors, probe budget.

HF recorded canvas, folio and superdoc as host-error because the Python
budget killed document_probe.mjs before it could say what happened. Folio and
SuperDoc paint the document inside aria-hidden. Canvas sets __DOCX_ERROR__
and never becomes ready.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import perf.runner.benchmark_document as bd

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "perf" / "runner" / "document_probe.mjs"
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
WITNESS_SERVER = REPO / "perf" / "tests" / "fixtures" / "witness" / "server.py"


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
    import importlib.util

    spec = importlib.util.spec_from_file_location("fixdoc_server", WITNESS_SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProbeBudget(unittest.TestCase):
    def test_timeout_is_our_wall_clock_kill_not_an_editor_crash(self):
        cmd = ["/usr/bin/node", "/app/perf/runner/document_probe.mjs", "--mode", "scale"]
        expired = subprocess.TimeoutExpired(cmd, bd.PROBE_TIMEOUT_S)
        with patch.object(bd.subprocess, "run", side_effect=expired):
            with self.assertRaises(bd.ProbeRefusal) as caught:
                bd._run_probe(cmd, editor_id="folio")
        reason = caught.exception.reason
        self.assertNotIn("host-error", reason)
        self.assertNotIn("Command [", reason)
        self.assertIn("folio", reason)
        self.assertIn(str(bd.PROBE_TIMEOUT_S), reason)
        # Our own 600 s kill has no evidence the editor crashed (review F6).
        self.assertEqual(caught.exception.refusal_code, "harness_error")


class PaintedAriaHidden(unittest.TestCase):
    server = None
    base_url = ""
    corpus = None

    @classmethod
    def setUpClass(cls):
        if _node() is None:
            raise unittest.SkipTest("node is not on PATH")
        if not _playwright_ready():
            raise unittest.SkipTest("harness/ui has no playwright package")
        cls.server, _thread, cls.base_url = _load_server().serve(HOSTS)
        cls._corpus_dir = tempfile.TemporaryDirectory()
        cls.corpus = Path(cls._corpus_dir.name) / "corpus.docx"
        cls.corpus.write_bytes(b"PK\x03\x04fixdoc")

    @classmethod
    def tearDownClass(cls):
        if cls.server is not None:
            cls.server.shutdown()
            cls.server.server_close()
        if cls.corpus is not None:
            cls._corpus_dir.cleanup()

    def _probe(self, host: str, extra: list[str]) -> tuple[subprocess.CompletedProcess, float]:
        cmd = [
            _node(),
            str(PROBE),
            "--mode",
            "load",
            "--url",
            "%s/%s" % (self.base_url, host),
            "--corpus",
            str(self.corpus),
            "--doc-selector",
            ".doc-paragraph",
            "--page-model",
            "continuous_flow",
            "--timeout-ms",
            "4000",
            *extra,
        ]
        started = time.monotonic()
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=30)
        return proc, time.monotonic() - started

    def test_painted_aria_hidden_text_is_the_document_surface(self):
        proc, elapsed = self._probe("b3_fixdoc_aria.html", [])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        text = payload.get("document_text") or ""
        self.assertIn("Visible document sentence", text, payload)
        self.assertNotIn("HIDDENONLY", text, payload)
        self.assertGreaterEqual(payload.get("document_text_chars") or 0, 8, payload)
        self.assertNotEqual(
            payload.get("surface_reason"),
            "document surface did not appear before the probe timeout",
            payload,
        )
        self.assertLess(elapsed, 3.5, payload)

    def test_editor_boot_error_is_the_probe_reason(self):
        proc, elapsed = self._probe(
            "b3_fixdoc_editor_error.html",
            [
                "--doc-selector",
                "#editor",
                "--ready-selector",
                "#editor",
                "--ready-js",
                "window.__DOCX_IMPORTED__ === true",
            ],
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        payload = json.loads(proc.stdout)
        reason = payload.get("reason") or ""
        self.assertIn("reading 'width'", reason, payload)
        self.assertNotIn("Timeout", reason, payload)
        self.assertLess(elapsed, 3.5, payload)
