"""Document-lane measurement fixes from the HF publication round.

C11 must accept the opening heading and ignore whitespace, and must still
refuse a different document. C12 must accept a downward anchor move. C14 must
measure when no document damage follows load, and must still refuse a rejected
clock.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import perf.runner.benchmark_document as bd
from perf.tests.witness_records import publishable_witness_record

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "perf" / "runner" / "document_probe.mjs"
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
WITNESS_SERVER = REPO / "perf" / "tests" / "fixtures" / "witness" / "server.py"
TIMEOUT_S = 90
HEADING = "Article 1. Incidental Taxes Title Force Effect Without"


def _node():
    return shutil.which("node")


def _playwright_ready() -> bool:
    for candidate in (
        REPO / "harness" / "ui" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright-core",
    ):
        if candidate.is_dir():
            return True
    return False


def _load_server():
    spec = importlib.util.spec_from_file_location("fixdoc2_fixture_server", WITNESS_SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _downward_probe(**overrides):
    witness = publishable_witness_record(40.0, 20.0)
    probe = {
        "mode": "reflow",
        "moved": False,
        "window_excludes_forced_layout": True,
        "before": {"anchor_top": 1708.703125},
        "anchor_top_after": 1768.265625,
        "presented_frame_ms": 40.0,
        "clock_skew_ms": 0.2,
        "clock_skew_acceptable": True,
        "witness": witness,
    }
    probe.update(overrides)
    return probe


class C12DownwardMove(unittest.TestCase):
    def test_hf_downward_anchor_is_a_sample(self):
        sample = bd.c12_measured_sample(_downward_probe())
        self.assertEqual(sample, 40.0)

    def test_equal_top_still_refuses(self):
        probe = _downward_probe(anchor_top_after=1708.703125)
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(probe)
        self.assertIn("did not move down", caught.exception.reason)

    def test_upward_move_still_refuses(self):
        probe = _downward_probe(anchor_top_after=1600.0)
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(probe)
        self.assertIn("did not move down", caught.exception.reason)

    def test_missing_after_still_refuses(self):
        probe = _downward_probe(anchor_top_after=None)
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(probe)
        self.assertIn("did not move down", caught.exception.reason)


class C14NoDamage(unittest.TestCase):
    def test_forced_repaint_measures_the_document_surface(self):
        probe = {
            "mode": "scale",
            "mechanism": "forced_repaint",
            "usable_ms": 140.0,
            "presented_frame_ms": None,
            "frames_total": 11,
            "frames_after_usable": 4,
            "clock_skew_ms": 0.2,
            "clock_skew_acceptable": True,
            "witness": {"outcome": "no_frame"},
            "forced_witness": {"outcome": "no_frame"},
        }
        self.assertEqual(bd.c14_measured_sample(probe), 140.0)
        self.assertTrue(bd._c14_facts(probe)["no_damage_followed"])

    def test_scale_diagnostics_record_that_no_damage_followed(self):
        payload = {
            "mechanism": "forced_repaint",
            "usable_ms": 140.0,
            "presented_frame_ms": None,
            "clock_skew_ms": 0.2,
            "clock_skew_acceptable": True,
            "witness": {"outcome": "no_frame", "clock_check": {"frame_interval_ms": 16.7}},
            "document_text": "In property",
        }

        def fake(_cmd, *, editor_id):
            del editor_id
            return payload

        with mock.patch.object(bd, "_run_probe", fake):
            samples, diagnostics = bd._run_scale_samples(
                editor_id="plate",
                target={"url": "http://127.0.0.1/", "corpus_route": "/corpus.docx"},
                cfg={
                    "doc_selector": ".doc-paragraph",
                    "edit_selector": ".doc-paragraph",
                    "page_model": "continuous_flow",
                },
                fixture_path=Path("unused.docx"),
                count=1,
            )
        self.assertEqual(samples, [140.0])
        self.assertIs(diagnostics[0]["no_damage_followed"], True)

    def test_rejected_clock_still_refuses(self):
        probe = {
            "mode": "scale",
            "mechanism": "forced_repaint",
            "usable_ms": 140.0,
            "presented_frame_ms": None,
            "clock_skew_ms": -0.7,
            "clock_skew_acceptable": False,
            "witness": {"outcome": "no_frame"},
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c14_measured_sample(probe)
        self.assertIn("clock skew", caught.exception.reason)

    def test_missing_surface_still_refuses(self):
        probe = {"mode": "scale", "mechanism": "forced_repaint", "usable_ms": None}
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c14_measured_sample(probe)
        self.assertIn("no DOM usability mark", caught.exception.reason)


class DocumentProbeHosts(unittest.TestCase):
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
        cls.corpus.write_bytes(b"PK\x03\x04fixdoc2")

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
        started = time.monotonic()
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=TIMEOUT_S)
        elapsed = time.monotonic() - started
        self.assertEqual(
            proc.returncode,
            0,
            "document_probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s" % (proc.returncode, proc.stdout, proc.stderr),
        )
        payload = json.loads(proc.stdout)
        payload["_elapsed_s"] = elapsed
        return payload

    def test_heading_outside_the_paragraph_selector_verifies(self):
        payload = self.probe(
            "load",
            "b3_fixdoc2_heading.html",
            ["--expected-opening-text", HEADING],
        )
        self.assertTrue(payload.get("content_verified"), payload)
        self.assertIn("Article 1.", payload.get("document_text") or "")
        self.assertNotEqual(payload.get("surface_reason"), "document_content_mismatch")

    def test_space_before_punctuation_still_matches(self):
        payload = self.probe(
            "load",
            "b3_fixdoc2_space.html",
            ["--expected-opening-text", "Chapter 1: Heading with mixed formatting."],
        )
        self.assertTrue(payload.get("content_verified"), payload)
        self.assertNotEqual(payload.get("surface_reason"), "document_content_mismatch")

    def test_wrong_document_stays_a_mismatch(self):
        payload = self.probe(
            "load",
            "b3_fixdoc2_wrong.html",
            ["--expected-opening-text", HEADING],
        )
        self.assertIs(payload.get("content_verified"), False, payload)
        self.assertEqual(payload.get("surface_reason"), "document_content_mismatch")

    def test_replaced_anchor_that_moved_down_is_a_sample(self):
        payload = self.probe(
            "reflow",
            "b3_fixdoc2_replaced_anchor.html",
            ["--edit-selector", ".doc-paragraph"],
        )
        before = (payload.get("before") or {}).get("anchor_top")
        after = payload.get("anchor_top_after")
        self.assertIsInstance(before, (int, float), payload)
        self.assertIsInstance(after, (int, float), payload)
        self.assertGreater(after, before, payload)
        sample = bd.c12_measured_sample(payload)
        self.assertIsInstance(sample, float)
