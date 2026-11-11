"""B3 measurers for document paint, the frame witness, and C15 (#108, #109).

The fake hosts live in ``perf/tests/fixtures/hosts/b3_*.html``. Each acceptance
criterion is one test: it drives ``document_probe.mjs`` or the pure sample
rules in ``benchmark_document.py`` and reads the JSON from outside the
implementation.
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
    spec = importlib.util.spec_from_file_location("b3_fixture_server", WITNESS_SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _env():
    row = next(item for item in __import__("perf.fixtures.profiles", fromlist=["size_ladder"]).size_ladder() if item["workload_id"] == "micro-paragraphs")
    fixture = bd.build_fixture(row)
    return bd._env_for(
        editor_id="plate",
        editor_version="test-pin",
        fixture=fixture,
        cache_state="process_cold_fs_warm",
    )


class C11SampleIsTheDocumentFrame(unittest.TestCase):
    """#108, without a browser: FCP that precedes the document is not the sample."""

    def test_fcp_before_the_document_is_not_the_sample(self):
        probe = {
            "paints": [
                {"name": "first-paint", "start_ms": 20.0},
                {"name": "first-contentful-paint", "start_ms": 30.0},
            ],
            "fcp_ms": 30.0,
            "document_text_at_ms": 400.0,
            "presented_frame_ms": 428.0,
            "usable_signal": "dom_text",
        }
        samples = bd.c11_measured_samples(probe)
        self.assertGreaterEqual(samples[0], 400.0)
        self.assertNotEqual(samples[0], 30.0)

    def test_a_missing_document_surface_does_not_publish_fcp(self):
        probe = {
            "paints": [{"name": "first-contentful-paint", "start_ms": 24.0}],
            "fcp_ms": 24.0,
            "document_text_at_ms": None,
            "presented_frame_ms": 24.0,
            "usable_signal": "dom_text",
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c11_measured_samples(probe)
        self.assertNotIn("first-contentful-paint entry has no usable", caught.exception.reason)
        self.assertIn("document", caught.exception.reason.lower())


class C14Verdict(unittest.TestCase):
    """No document damage is a sample, and a refusal keeps the witness counts."""

    def test_forced_repaint_measures_usable_and_is_not_a_missing_frame(self):
        probe = {
            "usable_ms": 140.0,
            "presented_frame_ms": 680.0,
            "frames_total": 11,
            "frames_after_usable": 4,
            "mechanism": "forced_repaint",
            "clock_skew_ms": 0.4,
            "witness": {"outcome": "witnessed", "window_ms": 500, "frames_total": 11, "frames_after": 4},
        }
        self.assertEqual(bd.c14_measured_sample(probe), 140.0)
        # r3reader4: a forced-repaint sample with no recorded page clock is refused
        unclocked = {k: v for k, v in probe.items() if k != "clock_skew_ms"}
        with self.assertRaises(bd.ProbeRefusal):
            bd.c14_measured_sample(unclocked)
        facts = bd._c14_facts(probe)
        self.assertEqual(facts.get("mechanism"), "forced_repaint")
        self.assertEqual(facts.get("usable_ms"), 140.0)
        self.assertTrue(facts.get("no_damage_followed"))
        self.assertIn("witness", facts)

    def test_a_refused_attempt_keeps_the_witness_counts(self):
        probe = {
            "usable_ms": 800.0,
            "presented_frame_ms": None,
            "frames_total": 4,
            "frames_after_usable": 1,
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c14_measured_sample(probe)
        facts = getattr(caught.exception, "facts", {}) or {}
        self.assertEqual(facts.get("usable_ms"), 800.0)
        self.assertEqual(facts.get("frames_total"), 4)
        self.assertEqual(facts.get("frames_after_usable"), 1)
        self.assertTrue(hasattr(bd, "write_c14_outcome"), "write_c14_outcome is absent")
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
        self.assertEqual(diagnostic.get("usable_ms"), 800.0)
        self.assertEqual(diagnostic.get("frames_total"), 4)
        self.assertEqual(diagnostic.get("frames_after_usable"), 1)
        self.assertNotEqual(trial["outcome"], "measured")


class C12Window(unittest.TestCase):
    def test_a_reflow_sample_must_exclude_the_probe_layout(self):
        probe = {
            "mode": "reflow",
            "moved": True,
            "before": {"anchor_top": 100.0},
            "anchor_top_after": 140.0,
            "presented_frame_ms": 40.0,
            "presented_frame_raw_ms": 48.0,
            "forced_layout_ms": 8.0,
            "window_excludes_forced_layout": False,
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(probe)
        self.assertIn("forced layout", caught.exception.reason)


class C15Minimum(unittest.TestCase):
    def test_one_event_is_below_the_minimum_n(self):
        self.assertTrue(hasattr(bd, "C15_MIN_N"), "C15_MIN_N is absent")
        self.assertGreaterEqual(bd.C15_MIN_N, 2)
        self.assertTrue(hasattr(bd, "c15_samples_from_payloads"), "c15_samples_from_payloads is absent")
        payload = {
            "status": "measured",
            "completion": "event",
            "cap_ms": None,
            "first_match_ms": 40.0,
            "search_complete_ms": 90.0,
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c15_samples_from_payloads([payload])
        self.assertEqual(getattr(caught.exception, "outcome", "failed"), "unverified")
        self.assertIn("minimum", caught.exception.reason)

    def test_two_event_completions_record_n_at_least_the_minimum(self):
        self.assertTrue(hasattr(bd, "c15_samples_from_payloads"), "c15_samples_from_payloads is absent")
        self.assertTrue(hasattr(bd, "C15_MIN_N"), "C15_MIN_N is absent")
        payload = {
            "status": "measured",
            "completion": "event",
            "cap_ms": None,
            "first_match_ms": 40.0,
            "search_complete_ms": 90.0,
        }
        cell = bd.c15_samples_from_payloads([payload, dict(payload, search_complete_ms=110.0)])
        self.assertGreaterEqual(cell["n"], bd.C15_MIN_N)
        self.assertEqual(cell["completion"], "event")
        self.assertEqual(cell["measurements"]["search_complete"]["outcome"], "measured")
        self.assertGreaterEqual(len(cell["measurements"]["search_complete"]["samples_ms"]), bd.C15_MIN_N)

    def test_a_host_without_a_widget_is_not_applicable_with_a_reason(self):
        self.assertTrue(hasattr(bd, "c15_samples_from_payloads"), "c15_samples_from_payloads is absent")
        cell = bd.c15_samples_from_payloads(
            [{"status": "not_applicable", "reason": "no find widget appears after Control+f/Meta+f"}]
        )
        self.assertEqual(cell["n"], 0)
        for name in bd.C15_MEASUREMENTS:
            outcome, value, reason = cell["outcomes"][name]
            self.assertEqual(outcome, "not_applicable")
            self.assertIsNone(value)
            self.assertIn("no find widget", reason)


class FakeHostMeasurers(unittest.TestCase):
    """The acceptance criteria, each against its own fake host."""

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
        started = time.monotonic()
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=TIMEOUT_S)
        elapsed = time.monotonic() - started
        self.assertEqual(
            proc.returncode,
            0,
            "document_probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s" % (proc.returncode, proc.stdout, proc.stderr),
        )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            self.fail("document_probe did not print JSON (%s)\nstdout: %r\nstderr: %r" % (exc, proc.stdout, proc.stderr))
        payload["_elapsed_s"] = elapsed
        return payload

    def test_shell_at_30ms_document_at_400ms_c11_is_at_least_400(self):
        payload = self.probe("load", "b3_shell_then_document.html", [])
        self.assertGreaterEqual(payload.get("document_text_at_ms") or 0, 350, payload)
        samples = bd.c11_measured_samples(payload)
        self.assertGreaterEqual(samples[0], 400.0, payload)
        fcp = payload.get("fcp_ms")
        if fcp is not None:
            self.assertLess(fcp, payload["document_text_at_ms"], payload)
            self.assertGreater(samples[0], fcp, payload)
        self.assertEqual(payload.get("usable_signal"), "dom_text")

    def test_static_host_c14_measures_when_no_damage_follows(self):
        payload = self.probe("scale", "b3_static.html", [])
        self.assertEqual(payload.get("mechanism"), "forced_repaint", payload)
        witness = payload.get("witness") or {}
        self.assertGreaterEqual(witness.get("window_ms") or 0, 500, payload)
        self.assertTrue(witness.get("document_scoped"), payload)
        self.assertEqual(witness.get("outcome"), "no_frame", payload)
        rect = ((witness.get("document_region") or {}).get("rect_css_px")) or {}
        overlaps_marker = (
            rect.get("x", 0) < 8
            and rect.get("y", 0) < 8
            and rect.get("x", 0) + rect.get("width", 0) > 0
            and rect.get("y", 0) + rect.get("height", 0) > 0
        )
        self.assertFalse(overlaps_marker, payload)
        self.assertNotEqual(witness.get("changed_pixels"), 64, payload)
        sample = bd.c14_measured_sample(payload)
        self.assertEqual(sample, payload.get("usable_ms"))
        facts = bd._c14_facts(payload)
        self.assertTrue(facts.get("no_damage_followed"))
        self.assertEqual(facts.get("usable_ms"), payload.get("usable_ms"))
        self.assertEqual(facts.get("frames_total"), payload.get("frames_total"))
        self.assertEqual(facts.get("frames_after_usable"), payload.get("frames_after_usable"))
        self.assertIsNotNone(facts.get("usable_ms"))
        self.assertIsNotNone(facts.get("frames_total"))
        self.assertIsNotNone(facts.get("frames_after_usable"))

    def test_canvas_and_shadow_record_the_signal_and_wait_for_the_document(self):
        canvas = self.probe("load", "b3_canvas.html", ["--usable-signal", "canvas_pixel"])
        self.assertEqual(canvas.get("usable_signal"), "canvas_pixel_non_blank", canvas)
        canvas_samples = bd.c11_measured_samples(canvas)
        self.assertGreaterEqual(canvas_samples[0], 400.0, canvas)
        if canvas.get("fcp_ms") is not None:
            self.assertGreater(canvas_samples[0], canvas["fcp_ms"], canvas)

        shadow = self.probe(
            "load",
            "b3_shadow.html",
            ["--usable-signal", "shadow_text", "--document-selector", "p"],
        )
        self.assertEqual(shadow.get("usable_signal"), "open_shadow_root_text", shadow)
        shadow_samples = bd.c11_measured_samples(shadow)
        self.assertGreaterEqual(shadow_samples[0], 400.0, shadow)
        if shadow.get("fcp_ms") is not None:
            self.assertGreater(shadow_samples[0], shadow["fcp_ms"], shadow)

    def test_no_find_widget_is_not_applicable_with_a_reason(self):
        payload = self.probe(
            "find",
            "b3_no_find.html",
            ["--find-input-selector", "input.find", "--find-query", "NEEDLE", "--find-count-selector", ".find-count"],
        )
        self.assertEqual(payload.get("status"), "not_applicable", payload)
        self.assertTrue(str(payload.get("reason") or "").strip(), payload)
        self.assertIn("find", payload["reason"].lower())

    def test_find_widget_completes_on_its_event_and_n_meets_the_minimum(self):
        extra = [
            "--find-input-selector",
            "input.find",
            "--find-query",
            "NEEDLE",
            "--find-count-selector",
            ".find-count",
            "--find-expected-matches",
            "2",
        ]
        first = self.probe("find", "b3_find.html", extra)
        self.assertEqual(first.get("status"), "measured", first)
        self.assertGreater(first.get("frame_interval_ms") or 0, 0, first)
        self.assertEqual(first.get("completion"), "event", first)
        self.assertIn("cap_ms", first)
        self.assertIsNone(first.get("cap_ms"), first)
        self.assertLess(first.get("completion_wait_ms"), 1500, first)
        self.assertLess(first["_elapsed_s"], 1.5, first)
        self.assertTrue(hasattr(bd, "C15_MIN_N"), "C15_MIN_N is absent")
        self.assertTrue(hasattr(bd, "c15_samples_from_payloads"), "c15_samples_from_payloads is absent")
        payloads = [first]
        while len(payloads) < bd.C15_MIN_N:
            payloads.append(self.probe("find", "b3_find.html", extra))
        for payload in payloads:
            self.assertEqual(payload.get("status"), "measured", payload)
            self.assertEqual(payload.get("completion"), "event", payload)
            self.assertIn("cap_ms", payload)
            self.assertIsNone(payload.get("cap_ms"), payload)
            self.assertLess(payload.get("completion_wait_ms"), 1500, payload)
            self.assertLess(payload["_elapsed_s"], 1.5, payload)
        cell = bd.c15_samples_from_payloads(payloads)
        self.assertGreaterEqual(cell["n"], bd.C15_MIN_N)
        self.assertEqual(cell["completion"], "event")

    def test_reflow_window_excludes_the_probe_layout(self):
        payload = self.probe("reflow", "b3_reflow.html", ["--edit-selector", ".doc-paragraph"])
        self.assertTrue(payload.get("window_excludes_forced_layout"), payload)
        self.assertIsInstance(payload.get("forced_layout_ms"), (int, float), payload)
        self.assertGreaterEqual(payload["forced_layout_ms"], 0)
        raw = payload.get("presented_frame_raw_ms")
        if payload.get("moved") and raw is not None and payload.get("presented_frame_ms") is not None:
            self.assertLessEqual(payload["presented_frame_ms"], raw + 1e-6, payload)
            sample = bd.c12_measured_sample(payload)
            self.assertLessEqual(sample, raw + 1e-6)

    def test_hidden_text_is_not_a_document_surface(self):
        payload = self.probe("load", "b3_hidden_late.html", ["--timeout-ms", "20000"])
        at = payload.get("document_text_at_ms")
        self.assertIsNotNone(at, payload)
        self.assertGreaterEqual(at, 4500, payload)
        samples = bd.c11_measured_samples(payload)
        self.assertGreaterEqual(samples[0], 4500, payload)

    def test_style_only_shadow_root_is_not_document_text(self):
        payload = self.probe(
            "load",
            "b3_shadow_style.html",
            ["--usable-signal", "shadow_text", "--document-selector", "p", "--timeout-ms", "20000"],
        )
        at = payload.get("document_text_at_ms")
        self.assertIsNotNone(at, payload)
        self.assertGreaterEqual(at, 4500, payload)
        self.assertGreaterEqual(bd.c11_measured_samples(payload)[0], 4500, payload)

    def test_ready_gate_still_presents_the_document_frame(self):
        payload = self.probe(
            "load",
            "b3_shell_then_document.html",
            ["--ready-js", "document.querySelector('.doc-paragraph')?.textContent.length>8"],
        )
        self.assertIsNotNone(payload.get("presented_frame_ms"), payload)
        self.assertGreaterEqual(payload.get("document_text_at_ms") or 0, 350, payload)
        samples = bd.c11_measured_samples(payload)
        self.assertGreaterEqual(samples[0], 400.0, payload)
        from perf.runner.witness import validate_witness

        verdict = validate_witness(payload.get("witness"))
        self.assertTrue(verdict["ok"], verdict)

    def test_prefix_count_is_not_completion_of_the_full_query(self):
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
        self.assertEqual(payload.get("status"), "measured", payload)
        self.assertEqual(payload.get("completion"), "event", payload)
        self.assertGreaterEqual(payload.get("search_complete_ms") or 0, 1000, payload)
        self.assertIn("full query", payload.get("observed_count_text") or "", payload)

    def test_find_wait_honors_the_probe_timeout(self):
        payload = self.probe(
            "find",
            "b3_find_silent.html",
            [
                "--find-input-selector",
                "input.find",
                "--find-query",
                "NEEDLE",
                "--find-count-selector",
                ".find-count",
                "--timeout-ms",
                "2500",
            ],
        )
        self.assertEqual(payload.get("status"), "unverified", payload)
        self.assertEqual(payload.get("completion"), "no_event", payload)
        self.assertLess(payload.get("completion_wait_ms"), 8000, payload)

    def test_reflow_observation_does_not_read_layout(self):
        payload = self.probe("reflow", "b3_reflow.html", ["--edit-selector", ".doc-paragraph"])
        self.assertTrue(payload.get("layout_window_armed"), payload)
        self.assertEqual(payload.get("layout_reads_during_window"), 0, payload)
        self.assertEqual(payload.get("forced_layout_ms"), 0, payload)
        self.assertTrue(payload.get("moved"), payload)
        sample = bd.c12_measured_sample(payload)
        self.assertIsInstance(sample, float)
