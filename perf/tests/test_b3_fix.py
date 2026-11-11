"""Review regressions for B3 (#135). Each test fails on an assertion until the fix."""

from __future__ import annotations

import unittest

import perf.runner.benchmark_document as bd
from perf.runner.browser_run import ACTIVE
from perf.runner.witness import validate_witness


def _good_witness(**overrides) -> dict:
    from perf.tests.witness_records import publishable_witness_record
    frame = overrides.pop('frame_page_ms', 428)
    return publishable_witness_record(frame, 100, **overrides)


class ReviewRules(unittest.TestCase):
    def test_c11_refuses_a_witness_validate_witness_refuses(self):
        witness = _good_witness(document_scoped=False)
        self.assertEqual(validate_witness(witness)["reason"], "not_document_scoped")
        probe = {
            "mode": "load",
            "document_text_at_ms": 400.0,
            "presented_frame_ms": 428.0,
            "usable_signal": "dom_text",
            "clock_skew_ms": 0.2,
            "clock_skew_acceptable": True,
            "witness": witness,
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c11_measured_samples(probe)
        self.assertEqual(caught.exception.reason, "witness refused: not_document_scoped")

    def test_c11_keeps_a_sample_whose_witness_validates(self):
        witness = _good_witness()
        self.assertTrue(validate_witness(witness)["ok"], validate_witness(witness))
        probe = {
            "mode": "load",
            "document_text_at_ms": 400.0,
            "presented_frame_ms": witness["frame_page_ms"],
            "usable_signal": "dom_text",
            "clock_skew_ms": 0.2,
            "clock_skew_acceptable": True,
            "witness": witness,
        }
        self.assertEqual(bd.c11_measured_samples(probe), [428.0])

    def test_c14_document_damage_must_pass_validate_witness(self):
        probe = {
            "mode": "scale",
            "mechanism": "document_damage",
            "usable_ms": 100.0,
            "presented_frame_ms": 120.0,
            "frames_total": 5,
            "frames_after_usable": 2,
            "clock_skew_ms": 0.2,
            "clock_skew_acceptable": True,
            "witness": _good_witness(document_scoped=False, frame_page_ms=120.0),
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c14_measured_sample(probe)
        self.assertEqual(caught.exception.reason, "witness refused: not_document_scoped")

    def test_c12_must_refuse_failed_clock_check(self):
        probe = {
            "mode": "reflow",
            "moved": True,
            "window_excludes_forced_layout": True,
            "presented_frame_ms": 42,
            "clock_skew_acceptable": False,
            "clock_skew_ms": 1000,
            "witness": {
                "outcome": "witnessed",
                "document_scoped": False,
                "clock_skew_acceptable": False,
            },
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(probe)
        self.assertIn("clock", caught.exception.reason.lower())

    def test_c15_minimum_applies_per_measurement(self):
        payload = {
            "status": "measured",
            "completion": "event",
            "cap_ms": None,
            "first_match_ms": 40,
            "search_complete_ms": 90,
        }
        cell = bd.c15_samples_from_payloads([payload, dict(payload, first_match_ms=None)])
        measured = cell["measurements"]["first_match"]
        self.assertTrue(
            measured["outcome"] != "measured" or len(measured["samples_ms"]) >= bd.C15_MIN_N,
            cell,
        )

    def test_c15_later_refusal_is_not_lost(self):
        payload = {
            "status": "measured",
            "completion": "event",
            "cap_ms": None,
            "first_match_ms": 40,
            "search_complete_ms": 90,
        }
        cell = bd.c15_samples_from_payloads([payload, dict(payload, first_match_ms=None)])
        self.assertEqual(cell["measurements"]["first_match"]["outcome"], "unverified", cell)
        self.assertEqual(cell["measurements"]["search_complete"]["outcome"], "measured", cell)
        self.assertGreaterEqual(len(cell["measurements"]["search_complete"]["samples_ms"]), bd.C15_MIN_N)

    def test_c14_no_damage_keeps_forced_witness(self):
        forced = {"outcome": "witnessed", "frame_page_ms": 700}
        probe = {
            "usable_ms": 100,
            "frames_total": 5,
            "frames_after_usable": 2,
            "mechanism": "forced_repaint",
            "presented_frame_ms": 700,
            "clock_skew_ms": 0.2,
            "clock_skew_acceptable": True,
            "witness": {"outcome": "no_frame"},
            "forced_witness": forced,
        }
        self.assertEqual(bd.c14_measured_sample(probe), 100.0)
        facts = bd._c14_facts(probe)
        self.assertEqual(facts.get("forced_witness"), forced, facts)
        self.assertIn("presented_frame_ms", facts)
        self.assertIn("clock_skew_acceptable", facts)
        self.assertTrue(facts.get("no_damage_followed"))

    def test_c15_probe_failure_stays_failed(self):
        refusal = bd.ProbeRefusal("browser crashed", outcome="failed")
        cell = bd.c15_cell_after_refusal(refusal)
        for name in bd.C15_MEASUREMENTS:
            self.assertEqual(cell["measurements"][name]["outcome"], "failed", cell)
            self.assertNotEqual(cell["measurements"][name]["outcome"], "not_applicable")


class SampleBrackets(unittest.TestCase):
    def test_each_find_probe_has_its_own_bracket(self):
        class RecordingRun:
            execution_profile = 'ci_contract'

            def __init__(self):
                self.begins = 0
                self.ends = 0

            def begin_sample(self):
                self.begins += 1

            def sample(self, *args, **kwargs):
                self.ends += 1

        class FindFake:
            def __init__(self):
                self.calls = 0

            def __call__(self, **kwargs):
                self.calls += 1
                return {
                    "status": "measured",
                    "completion": "event",
                    "cap_ms": None,
                    "first_match_ms": 20,
                    "search_complete_ms": 40,
                }

        fake = FindFake()
        run = RecordingRun()
        token = ACTIVE.set(run)
        original = bd._run_find
        bd._run_find = fake
        try:
            bd._run_find_payloads(
                editor_id="plate",
                target={},
                cfg={"find_input_selector": "input"},
                fixture_path=None,
                count=1,
            )
            self.assertEqual(fake.calls, 1)
            self.assertEqual((run.begins, run.ends), (fake.calls, fake.calls), (fake.calls, run.begins, run.ends))
        finally:
            bd._run_find = original
            ACTIVE.reset(token)

    def test_each_load_reflow_and_scale_probe_has_its_own_bracket(self):
        class RecordingRun:
            def __init__(self):
                self.begins = 0
                self.ends = 0

            def begin_sample(self):
                self.begins += 1

            def sample(self, *args, **kwargs):
                self.ends += 1

        def fake_cmd(*, mode, target, cfg, corpus_path, extra, editor_id=""):
            del target, cfg, corpus_path, extra, editor_id
            return ["node", "document_probe.mjs", "--mode", mode]

        def fake_probe(cmd, *, editor_id, env=None):
            del editor_id, env
            mode = cmd[cmd.index("--mode") + 1]
            if mode == "reflow":
                return {"moved": True, "presented_frame_ms": 40, "window_excludes_forced_layout": True}
            if mode == "scale":
                return {"usable_ms": 100, "presented_frame_ms": 120, "frames_total": 3, "frames_after_usable": 1}
            return {
                "paints": [{"name": "first-contentful-paint", "start_ms": 10}],
                "fcp_ms": 10,
                "content_verified": True,
                "document_text": "Loaded document opening",
            }

        run = RecordingRun()
        token = ACTIVE.set(run)
        originals = (bd._probe_cmd, bd._run_probe, bd.corpus_opening_text, bd.corpus_content_expectation_flags)
        # This bracket unit test uses an in-memory corpus oracle, not a disk fixture.
        bd.corpus_opening_text = lambda path: "Loaded document opening"
        bd.corpus_content_expectation_flags = lambda path: []
        bd._probe_cmd = fake_cmd
        bd._run_probe = fake_probe
        try:
            target = {"url": "http://127.0.0.1/x", "corpus_route": "/corpus.docx"}
            cfg = {"doc_selector": ".doc-paragraph", "page_model": "continuous_flow", "edit_selector": ".doc-paragraph"}
            bd._run_load_samples(editor_id="plate", target=target, cfg=cfg, fixture_path="unused", count=2)
            bd._run_reflow_samples(editor_id="plate", target=target, cfg=cfg, fixture_path="unused", count=1)
            bd._run_scale_samples(editor_id="plate", target=target, cfg=cfg, fixture_path="unused", count=2)
            self.assertEqual((run.begins, run.ends), (5, 5), (run.begins, run.ends))
        finally:
            bd._probe_cmd, bd._run_probe, bd.corpus_opening_text, bd.corpus_content_expectation_flags = originals
            ACTIVE.reset(token)

    def test_a_throttled_sample_is_refused_alone(self):
        class ThrottleRun:
            def __init__(self):
                self.begins = 0
                self.samples = []

            def begin_sample(self):
                self.begins += 1

            def sample(self, name, row):
                del name, row
                self.samples.append({"outcome": "failed", "failure_reason": "cpu_throttled"})

        def fake_cmd(*, mode, target, cfg, corpus_path, extra):
            del mode, target, cfg, corpus_path, extra
            return ["node", "document_probe.mjs", "--mode", "load"]

        def fake_probe(cmd, *, editor_id, env=None):
            del cmd, editor_id, env
            return {"paints": [{"name": "first-contentful-paint", "start_ms": 10}], "fcp_ms": 10}

        run = ThrottleRun()
        token = ACTIVE.set(run)
        originals = (bd._probe_cmd, bd._run_probe, bd.corpus_opening_text, bd.corpus_content_expectation_flags)
        # This bracket unit test uses an in-memory corpus oracle, not a disk fixture.
        bd.corpus_opening_text = lambda path: "Loaded document opening"
        bd.corpus_content_expectation_flags = lambda path: []
        bd._probe_cmd = fake_cmd
        bd._run_probe = fake_probe
        try:
            with self.assertRaises(bd.ProbeRefusal) as caught:
                bd._run_load_samples(
                    editor_id="plate",
                    target={"url": "http://127.0.0.1/x", "corpus_route": "/c"},
                    cfg={"doc_selector": ".doc-paragraph", "page_model": "continuous_flow", "edit_selector": ".doc-paragraph"},
                    fixture_path="unused",
                    count=2,
                )
            self.assertEqual(caught.exception.reason, "cpu_throttled")
            self.assertEqual(run.begins, 1)
            self.assertEqual(len(run.samples), 1)
        finally:
            bd._probe_cmd, bd._run_probe, bd.corpus_opening_text, bd.corpus_content_expectation_flags = originals
            ACTIVE.reset(token)
