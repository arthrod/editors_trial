"""Re-review regressions for B3 (#135 round 2). Each test fails until the fix."""

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
TIMEOUT_S = 90


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
    spec = importlib.util.spec_from_file_location("b3_fix2_server", WITNESS_SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _env():
    row = next(
        item
        for item in __import__("perf.fixtures.profiles", fromlist=["size_ladder"]).size_ladder()
        if item["workload_id"] == "micro-paragraphs"
    )
    fixture = bd.build_fixture(row)
    return bd._env_for(
        editor_id="plate",
        editor_version="test-pin",
        fixture=fixture,
        cache_state="process_cold_fs_warm",
    )


def _good_witness(**overrides) -> dict:
    from perf.tests.witness_records import publishable_witness_record
    frame = overrides.pop('frame_page_ms', 1808)
    return publishable_witness_record(frame, 1000, **overrides)


def _region(payload: dict) -> dict:
    witness = payload.get("witness") or {}
    return ((witness.get("document_region") or {}).get("rect_css_px")) or {}


class ReviewRulesRound2(unittest.TestCase):
    """Pure readers. No browser."""

    def test_c14_witness_refusal_keeps_the_attempt_facts(self):
        from perf.tests.witness_records import publishable_witness_record

        probe = {
            "mode": "scale",
            "usable_ms": 100,
            "frames_total": 5,
            "frames_after_usable": 2,
            "mechanism": "document_damage",
            "presented_frame_ms": 700,
            "witness": publishable_witness_record(700, 100, clock_check={
                "acceptable": False, "reason": "anchor_lag_above_bound",
            }),
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c14_measured_sample(probe)
        self.assertEqual(caught.exception.reason, "witness refused: clock_check_not_acceptable")
        self.assertEqual(caught.exception.facts.get("usable_ms"), 100, caught.exception.facts)
        self.assertEqual(caught.exception.facts.get("frames_total"), 5)
        self.assertEqual(caught.exception.facts.get("frames_after_usable"), 2)
        with tempfile.TemporaryDirectory() as tmp:
            path = bd.write_c14_outcome(
                attempt_dir=Path(tmp),
                editor_id="plate",
                lane="browser_slate",
                env=_env(),
                probe=probe,
                label="micro",
                workload_id="micro-paragraphs",
            )
            trial = json.loads(Path(path).read_text(encoding="utf-8"))
        diagnostic = trial["diagnostic"]
        self.assertEqual(diagnostic.get("usable_ms"), 100, diagnostic)
        self.assertEqual(diagnostic.get("frames_total"), 5, diagnostic)
        self.assertEqual(diagnostic.get("frames_after_usable"), 2, diagnostic)

    def test_c12_refuses_a_frame_that_precedes_the_anchor_shift(self):
        probe = {
            "mode": "reflow",
            "moved": True,
            "window_excludes_forced_layout": True,
            "input_page_ms": 1000.0,
            "observed_shift_page_ms": 1800.0,
            "presented_frame_ms": 8.0,
            "clock_skew_ms": 0.2,
            "clock_skew_acceptable": True,
            "witness": _good_witness(frame_page_ms=1008.0),
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(probe)
        self.assertIn("reflow", caught.exception.reason.lower())


class Fix2Hosts(unittest.TestCase):
    """The re-review fixtures, through the production probe."""

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

    def test_shadow_chrome_is_not_document_text_or_the_region(self):
        payload = self.probe(
            "load",
            "b3_shadow_chrome.html",
            ["--usable-signal", "shadow_text", "--document-selector", "#paper", "--timeout-ms", "12000"],
        )
        text = payload.get("document_text") or ""
        rect = _region(payload)
        self.assertGreaterEqual(payload.get("document_text_at_ms") or 0, 7000, (text, rect, payload.get("document_text_at_ms")))
        self.assertNotIn("Print", text, text)
        self.assertIn("Actual document", text, text)
        self.assertLess(rect.get("width") or 0, 800, rect)
        self.assertLess(rect.get("height") or 0, 400, rect)
        self.assertEqual(payload.get("document_selector"), "#paper", payload.get("document_selector"))

    def test_shadow_chrome_damage_is_not_the_toolbar(self):
        payload = self.probe(
            "scale",
            "b3_shadow_chrome.html",
            ["--usable-signal", "shadow_text", "--document-selector", "#paper", "--timeout-ms", "14000"],
        )
        rect = _region(payload)
        self.assertGreaterEqual(payload.get("usable_ms") or 0, 7000, payload.get("usable_ms"))
        self.assertNotIn("Print", payload.get("document_text") or "", payload.get("document_text"))
        self.assertLess(rect.get("width") or 0, 800, rect)
        self.assertLess(rect.get("height") or 0, 400, rect)
        if payload.get("mechanism") == "document_damage":
            self.assertGreaterEqual(payload.get("presented_frame_ms") or 0, 7000, payload.get("presented_frame_ms"))

    def test_apryse_document_is_inside_the_webviewer_shadow(self):
        cfg = bd.DOCUMENT_TARGETS["apryse"]
        extra = [
            "--usable-signal",
            cfg.get("usable_signal") or "shadow_text",
            "--doc-selector",
            cfg["doc_selector"],
            "--timeout-ms",
            "3000",
        ]
        if cfg.get("document_selector"):
            extra.extend(["--document-selector", cfg["document_selector"]])
        payload = self.probe("load", "b3_apryse_nested.html", extra)
        text = payload.get("document_text") or ""
        rect = _region(payload)
        self.assertIn("apryse-webviewer", cfg["doc_selector"], cfg["doc_selector"])
        self.assertIn("pageContainer1", cfg.get("document_selector") or "", cfg.get("document_selector"))
        self.assertIsNotNone(payload.get("document_text_at_ms"), payload.get("surface_reason"))
        self.assertIn("Actual visible document text", text, text)
        self.assertNotIn("Print", text, text)
        self.assertLess(rect.get("height") or 9999, 400, rect)
        self.assertLess(rect.get("width") or 9999, 760, rect)

    def test_c12_ends_on_the_anchor_reflow(self):
        payload = self.probe(
            "reflow",
            "b3_reflow_late.html",
            ["--edit-selector", ".doc-paragraph", "--timeout-ms", "12000"],
        )
        rect = _region(payload)
        presented = payload.get("presented_frame_ms")
        self.assertTrue(payload.get("moved"), payload.get("error") or payload.get("anchor_after_top"))
        self.assertGreaterEqual(presented or 0, 700, presented)
        self.assertGreater(rect.get("height") or 0, 80, rect)
        sample = bd.c12_measured_sample(payload)
        self.assertGreaterEqual(sample, 700, sample)

    def test_async_prefix_reply_does_not_complete_the_full_query(self):
        payload = self.probe(
            "find",
            "b3_find_prefix_async.html",
            [
                "--find-input-selector",
                "input.find",
                "--find-query",
                "NEEDLE",
                "--find-count-selector",
                ".find-count",
                "--find-expected-matches",
                "2",
                "--timeout-ms",
                "8000",
            ],
        )
        text = payload.get("observed_count_text") or ""
        self.assertEqual(payload.get("status"), "measured", payload.get("reason"))
        self.assertNotIn("prefix", text, text)
        self.assertIn("full query", text, text)
        self.assertGreaterEqual(payload.get("search_complete_ms") or 0, 1500, payload.get("search_complete_ms"))
        self.assertGreaterEqual(payload.get("first_match_ms") or 0, 1500, payload.get("first_match_ms"))

    def test_sync_prefix_does_not_stamp_first_match(self):
        payload = self.probe(
            "find",
            "b3_find_prefix.html",
            [
                "--find-input-selector",
                "input.find",
                "--find-query",
                "NEEDLE",
                "--find-count-selector",
                ".find-count",
                "--find-expected-matches",
                "2",
                "--timeout-ms",
                "8000",
            ],
        )
        self.assertEqual(payload.get("status"), "measured", payload.get("reason"))
        self.assertIn("full query", payload.get("observed_count_text") or "", payload.get("observed_count_text"))
        self.assertGreaterEqual(payload.get("search_complete_ms") or 0, 1000, payload.get("search_complete_ms"))
        self.assertGreaterEqual(payload.get("first_match_ms") or 0, 1000, payload.get("first_match_ms"))

    def test_canvas_signal_sees_ink_past_the_margin(self):
        payload = self.probe(
            "load",
            "b3_canvas_margin.html",
            ["--usable-signal", "canvas_pixel", "--timeout-ms", "2500"],
        )
        self.assertIsNotNone(payload.get("document_text_at_ms"), payload.get("surface_reason"))
        self.assertGreaterEqual(payload.get("document_text_at_ms") or 0, 300, payload.get("document_text_at_ms"))
        samples = bd.c11_measured_samples(payload)
        self.assertGreaterEqual(samples[0], 300, samples)
