"""Honesty guardrails for the C11/C12/C14/C15 document suite.

These tests pin the rules that make the suite's refusal rows trustworthy: a
sample exists only when its clock exists, a refusal names its reason and carries
no number, and the size ladder is never pooled.
"""

import json
import tempfile
import unittest
from pathlib import Path

import perf.runner.benchmark_document as bd
import perf.runner.benchmark_warm_cold as warm_cold
from perf.fixtures.profiles import size_ladder
from perf.scenarios.catalog import scenarios
from perf.schema import validate_trial
from perf.tests import test_witness


def _fixture(workload_id="micro-paragraphs"):
    row = next(item for item in size_ladder() if item["workload_id"] == workload_id)
    return bd.build_fixture(row)


def _env(fixture=None, cache_state="process_cold_fs_warm"):
    fixture = fixture or _fixture()
    return bd._env_for(
        editor_id="plate",
        editor_version="test-pin",
        fixture=fixture,
        cache_state=cache_state,
    )


def _measured_diagnostic(**fields):
    """Two sample witnesses satisfying the B3 observed-interval handoff."""
    return {**fields, "samples": [
        {"witness": test_witness.WitnessValidatorTests.good_record()} for _ in range(2)
    ]}


class CatalogAlignment(unittest.TestCase):
    def test_runner_repeats_the_catalog_layers_and_boundaries(self):
        bd.assert_catalog_alignment(scenarios())

    def test_a_drifted_layer_is_rejected(self):
        rows = [dict(row) for row in scenarios()]
        for row in rows:
            if row["id"] == "C12":
                row["layer"] = "model"
        with self.assertRaises(ValueError) as caught:
            bd.assert_catalog_alignment(rows)
        self.assertIn("C12", str(caught.exception))

    def test_a_dropped_c15_measurement_is_rejected(self):
        rows = [dict(row) for row in scenarios()]
        for row in rows:
            if row["id"] == "C15":
                row["measurements"] = ["first_match"]
        with self.assertRaises(ValueError) as caught:
            bd.assert_catalog_alignment(rows)
        self.assertIn("search_complete", str(caught.exception))

    def test_hosts_come_from_the_warm_cold_targets(self):
        """One registry, not a second copy of the ports and servers."""
        self.assertIs(bd.BROWSER_TARGETS, warm_cold.BROWSER_TARGETS)


class C11RequiresAPaintEntry(unittest.TestCase):
    def test_missing_paint_entries_are_a_refusal(self):
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c11_measured_samples({"paints": [], "fcp_ms": 120.0})
        self.assertIn("first-contentful-paint", caught.exception.reason)

    def test_paint_entry_without_a_start_time_is_a_refusal(self):
        with self.assertRaises(bd.ProbeRefusal):
            bd.c11_measured_samples(
                {"paints": [{"name": "first-contentful-paint", "start_ms": None}], "fcp_ms": None}
            )

    def test_dom_check_never_becomes_the_sample(self):
        probe = {
            "paints": [
                {"name": "first-paint", "start_ms": 40.0},
                {"name": "first-contentful-paint", "start_ms": 56.0},
            ],
            "fcp_ms": 56.0,
            "first_element_ms": 4321.0,
        }
        self.assertEqual(bd.c11_measured_samples(probe), [56.0])

    def test_negative_paint_time_is_a_refusal(self):
        with self.assertRaises(bd.ProbeRefusal):
            bd.c11_measured_samples(
                {"paints": [{"name": "first-contentful-paint", "start_ms": -1.0}], "fcp_ms": -1.0}
            )


class C12RequiresTheShiftAndAFrame(unittest.TestCase):
    def _probe(self, **overrides):
        payload = {
            "moved": True,
            "before": {"anchor_top": 118.0},
            "anchor_top_after": 144.0,
            "presented_frame_ms": 83.0,
            "first_frame_after_input_ms": 12.0,
        }
        payload.update(overrides)
        return payload

    def test_a_missing_shift_is_a_refusal(self):
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(self._probe(moved=False, presented_frame_ms=None, anchor_top_after=None))
        self.assertIn("text-shift", caught.exception.reason)

    def test_a_shift_without_a_frame_is_a_refusal(self):
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(self._probe(presented_frame_ms=None, first_frame_after_input_ms=12.0))
        self.assertIn("compositor frame", caught.exception.reason)

    def test_a_frame_before_the_shift_is_not_used(self):
        """The early frame is recorded, but the sample is the post-shift frame."""
        self.assertEqual(bd.c12_measured_sample(self._probe(presented_frame_ms=83.0)), 83.0)

    def test_negative_frame_time_is_a_refusal(self):
        with self.assertRaises(bd.ProbeRefusal):
            bd.c12_measured_sample(self._probe(presented_frame_ms=-4.0))

    def test_the_anchor_is_not_a_bare_block_index(self):
        """Inserting at the top renumbers blocks; an index anchor reports no shift.

        Pinned after a real probe bug: Enter at the document start created a block
        (9 -> 10) and every index moved, while the index-based anchor read the same
        y position and the probe refused a reflow that had happened.
        """
        source = (Path(__file__).resolve().parents[1] / "runner" / "document_probe.mjs").read_text(
            encoding="utf-8"
        )
        self.assertIn("__c12AnchorEl", source)
        self.assertIn("PICK_ANCHOR_BELOW", source)
        self.assertIn("__c12AnchorText", source)
        self.assertNotIn("const byIndex", source)

    def test_the_frame_clock_is_a_compositor_frame_not_a_raf_callback(self):
        source = (Path(__file__).resolve().parents[1] / "runner" / "document_probe.mjs").read_text(
            encoding="utf-8"
        )
        self.assertIn("Page.startScreencast", source)
        self.assertIn("Page.screencastFrame", source)
        self.assertIn("frame_source: 'cdp_screencast'", source)
        self.assertNotIn("presented_frame_ms = raf", source)


class C14RequiresUsableThenAFrame(unittest.TestCase):
    def test_no_usability_mark_is_a_refusal(self):
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c14_measured_sample({"usable_ms": None, "presented_frame_ms": 900.0})
        self.assertIn("usability", caught.exception.reason)

    def test_no_frame_is_a_refusal(self):
        with self.assertRaises(bd.ProbeRefusal):
            bd.c14_measured_sample({"usable_ms": 800.0, "presented_frame_ms": None})

    def test_a_frame_before_usability_is_a_clock_mismatch(self):
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c14_measured_sample({"usable_ms": 800.0, "presented_frame_ms": 500.0})
        self.assertIn("clock mismatch", caught.exception.reason)

    def test_a_frame_after_usability_is_the_sample(self):
        self.assertEqual(bd.c14_measured_sample({"usable_ms": 800.0, "presented_frame_ms": 812.5}), 812.5)


class C14LadderIsNeverPooled(unittest.TestCase):
    def test_identical_samples_on_two_rungs_are_rejected(self):
        rows = [
            {"workload_id": "micro-paragraphs", "samples_ms": [800.0, 820.0]},
            {"workload_id": "short-paragraphs", "samples_ms": [820.0, 800.0]},
        ]
        with self.assertRaises(ValueError) as caught:
            bd.assert_distinct_c14_rungs(rows)
        self.assertIn("pooled or copied", str(caught.exception))

    def test_distinct_rungs_pass(self):
        bd.assert_distinct_c14_rungs(
            [
                {"workload_id": "micro-paragraphs", "samples_ms": [800.0]},
                {"workload_id": "short-paragraphs", "samples_ms": [1240.0]},
            ]
        )

    def test_one_rung_needs_no_comparison(self):
        bd.assert_distinct_c14_rungs([{"workload_id": "micro-paragraphs", "samples_ms": [800.0]}])


class C15Refusals(unittest.TestCase):
    def test_a_refusal_needs_a_reason(self):
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.find_outcomes({"status": "not_applicable", "reason": "   "})
        self.assertIn("without a reason", caught.exception.reason)

    def test_a_refusal_must_not_carry_a_timing(self):
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.find_outcomes(
                {"status": "not_applicable", "reason": "no widget", "first_match_ms": 12.0}
            )
        self.assertIn("carries", caught.exception.reason)

    def test_a_refusal_names_every_measurement(self):
        outcomes = bd.find_outcomes({"status": "not_applicable", "reason": "no find widget appears"})
        self.assertEqual(set(outcomes), set(bd.C15_MEASUREMENTS))
        for name, (outcome, value, reason) in outcomes.items():
            self.assertEqual(outcome, "not_applicable")
            self.assertIsNone(value)
            self.assertEqual(reason, "no find widget appears")

    def test_a_measured_widget_still_refuses_the_undriven_measurements(self):
        outcomes = bd.find_outcomes(
            {"status": "measured", "first_match_ms": 41.0, "search_complete_ms": 190.0}
        )
        self.assertEqual(outcomes["first_match"], ("measured", 41.0, None))
        self.assertEqual(outcomes["search_complete"], ("measured", 190.0, None))
        self.assertEqual(outcomes["replace_all"][0], "not_applicable")
        self.assertEqual(outcomes["index_quiescence"][0], "not_applicable")
        self.assertTrue(outcomes["replace_all"][2])

    def test_a_widget_that_acknowledges_nothing_is_refused(self):
        with self.assertRaises(bd.ProbeRefusal):
            bd.find_outcomes({"status": "measured", "first_match_ms": None, "search_complete_ms": None})


class AttemptShape(unittest.TestCase):
    def test_a_refusal_is_validate_trial_clean_and_carries_no_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = bd._write_refusal(
                attempt_dir=Path(tmp),
                criterion_id="C15",
                editor_id="plate",
                lane="browser_slate",
                env=_env(cache_state="warm_steady"),
                outcome="not_applicable",
                failure_reason="no find widget: Ctrl+F and Meta+F leave no find surface",
                diagnostic={"measurement": "first_match"},
            )
            trial = json.loads(path.read_text(encoding="utf-8"))
        validate_trial(trial)
        self.assertEqual(trial["outcome"], "not_applicable")
        self.assertEqual(trial["samples_ms"], [])
        self.assertIsNone(trial["latency_ms"])
        self.assertIn("no find widget", trial["failure_reason"])

    def test_a_refusal_without_a_reason_is_a_bug(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                bd._write_refusal(
                    attempt_dir=Path(tmp),
                    criterion_id="C11",
                    editor_id="plate",
                    lane="browser_slate",
                    env=_env(),
                    outcome="not_run",
                    failure_reason="  ",
                )
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_schema_rejects_samples_on_a_refusal(self):
        trial = {
            "schema_version": 1,
            "criterion_id": "C11",
            "layer": "browser_visible",
            "boundary": "first_contentful_paint",
            "outcome": "not_applicable",
            "claims": [],
            "samples_ms": [12.0],
            "latency_ms": None,
            "environment": _env(),
        }
        with self.assertRaises(ValueError):
            validate_trial(trial)

    def test_a_measured_cell_is_blocked_on_this_host_with_a_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, trial = bd._write_measured(
                attempt_dir=Path(tmp),
                criterion_id="C11",
                editor_id="plate",
                lane="browser_slate",
                env=_env(),
                samples=[56.0, 61.5],
                diagnostic=_measured_diagnostic(suite="document"),
            )
            on_disk = json.loads(path.read_text(encoding="utf-8"))
        validate_trial(trial)
        validate_trial(on_disk)
        self.assertEqual(trial["outcome"], "measured")
        self.assertFalse(trial["publishable"])
        self.assertTrue(trial["publication_block_reason"])
        self.assertIn("ci_coarse", trial["publication_block_reason"])

    def test_c14_attempt_carries_one_rung_and_no_pooled_figure(self):
        fixture = _fixture("short-paragraphs")
        with tempfile.TemporaryDirectory() as tmp:
            _path, trial = bd._write_measured(
                attempt_dir=Path(tmp),
                criterion_id="C14",
                editor_id="plate",
                lane="browser_slate",
                env=_env(fixture, cache_state="process_cold_fs_warm"),
                samples=[1240.0, 1310.0],
                diagnostic=_measured_diagnostic(
                    suite="document", size_rung="short", workload_id="short-paragraphs",
                    no_pooled_figure=True,
                    curve_medians_ms={"micro-paragraphs": {"n": 2, "median_ms": 830.0}},
                ),
            )
        self.assertEqual(trial["outcome"], "measured")
        self.assertEqual(trial["diagnostic"]["size_rung"], "short")
        self.assertTrue(trial["diagnostic"]["no_pooled_figure"])
        self.assertEqual(trial["environment"]["workload_id"], "short-paragraphs")

    def test_c14_correctness_gap_is_named_in_the_block_reason(self):
        """A load-only C14 trial cannot show I01–I03 text preservation."""
        fixture = _fixture("micro-paragraphs")
        with tempfile.TemporaryDirectory() as tmp:
            _path, trial = bd._write_measured(
                attempt_dir=Path(tmp),
                criterion_id="C14",
                editor_id="plate",
                lane="browser_slate",
                env=_env(fixture, cache_state="process_cold_fs_warm"),
                samples=[830.0, 840.0],
                diagnostic=_measured_diagnostic(suite="document", size_rung="micro", workload_id="micro-paragraphs"),
            )
        self.assertEqual(trial["outcome"], "measured")
        reason = trial["publication_block_reason"]
        self.assertIn("interpretation:", reason)
        self.assertIn("I01", reason)

    def test_c14_correctness_gate_is_live_on_the_rendered_text(self):
        """Rendered text that loses a ZWJ family must block on I02, not pass."""
        fixture = _fixture("micro-paragraphs")
        good = "cafe\u0301 \U0002000b family \U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466 tone \U0001f44d\U0001f3fb Hello \u0645\u0631\u062d\u0628\u0627"
        broken = good.replace("\u200d", " ")
        with tempfile.TemporaryDirectory() as tmp:
            _path, ok_trial = bd._write_measured(
                attempt_dir=Path(tmp),
                criterion_id="C14",
                editor_id="plate",
                lane="browser_slate",
                env=_env(fixture),
                samples=[830.0, 840.0],
                doc_output_text=good,
                diagnostic=_measured_diagnostic(suite="document", size_rung="micro", workload_id="micro-paragraphs"),
            )
            _path, broken_trial = bd._write_measured(
                attempt_dir=Path(tmp),
                criterion_id="C14",
                editor_id="plate",
                lane="browser_slate",
                env=_env(fixture),
                samples=[830.0, 840.0],
                doc_output_text=broken,
                diagnostic=_measured_diagnostic(suite="document", size_rung="micro", workload_id="micro-paragraphs"),
            )
        self.assertEqual(ok_trial["outcome"], "measured")
        self.assertEqual(broken_trial["outcome"], "measured")
        self.assertNotIn("interpretation:", ok_trial["publication_block_reason"])
        self.assertIn("I02", broken_trial["publication_block_reason"])


class FixtureRecords(unittest.TestCase):
    def test_a_blocked_rung_never_names_a_written_fixture_file(self):
        source = (Path(__file__).resolve().parents[1] / "runner" / "benchmark_document.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('if fixture["path"].is_file() else None', source)
        self.assertIn("never reach an editor", source)

    def test_the_fixture_carries_the_correctness_paragraphs(self):
        fixture = _fixture("micro-paragraphs")
        self.assertEqual(fixture["paragraph_count"], 5 + 4)
        self.assertEqual(fixture["augmented_paragraphs"], 4)
        self.assertGreater(fixture["byte_size"], 0)


class SupportTable(unittest.TestCase):
    def test_every_browser_host_is_either_configured_or_named(self):
        for editor_id in bd.BROWSER_TARGETS:
            configured = editor_id in bd.DOCUMENT_TARGETS
            named = editor_id in bd.STRUCTURE_NOTES
            self.assertTrue(configured or named, "%s has no support statement" % editor_id)
            self.assertFalse(configured and named, "%s is both configured and refused" % editor_id)

    def test_a_configured_host_declares_every_selector_the_probe_needs(self):
        for editor_id, cfg in bd.DOCUMENT_TARGETS.items():
            self.assertTrue(cfg["doc_selector"], editor_id)
            self.assertTrue(cfg["edit_selector"], editor_id)
            self.assertIn(cfg["page_model"], ("page", "continuous_flow"), editor_id)
            if cfg["page_model"] == "page":
                self.assertTrue(cfg.get("page_selector"), editor_id)
            self.assertTrue(
                cfg.get("find_input_selector") or cfg.get("find_source_note"),
                "%s must either wire a find widget or name why not" % editor_id,
            )
            if cfg.get("find_input_selector"):
                self.assertTrue(cfg.get("find_query"), "%s wires a find widget without a query" % editor_id)

    def test_every_refused_host_names_the_missing_surface(self):
        for editor_id, note in bd.STRUCTURE_NOTES.items():
            self.assertGreater(len(note), 30, editor_id)


if __name__ == "__main__":
    unittest.main()
