import unittest

from perf.adapters.capabilities import capability, capability_evidence, lanes
from perf.adapters.protocol import refusal_trial, trial_or_refusal
from perf.schema import validate_trial


class Refusal(unittest.TestCase):
    def test_not_applicable_has_null_latency(self):
        trial = refusal_trial("office-open", "library", "hit_testing", "not_applicable", "C07")
        validate_trial(trial)
        self.assertIsNone(trial["latency_ms"])
        self.assertEqual(trial["samples_ms"], [])
        self.assertEqual(trial["outcome"], "not_applicable")
        self.assertEqual(trial["criterion_id"], "C07")

    def test_measured_is_not_a_refusal_outcome(self):
        with self.assertRaises(ValueError) as caught:
            refusal_trial("plate", "browser_slate", "typing", "measured", "C05")
        self.assertIn("refusal", str(caught.exception))

    def test_zero_cannot_be_smuggled_in(self):
        trial = refusal_trial("wordcraft", "native_ui", "collaboration", "unverified", "C23")
        self.assertNotIn(0, trial["samples_ms"])
        self.assertIsNone(trial["latency_ms"])

    def test_failed_refusal_requires_a_reason(self):
        with self.assertRaises(ValueError) as caught:
            refusal_trial("plate", "browser_slate", "typing", "failed", "C05")
        self.assertIn("failure_reason", str(caught.exception))


class Capabilities(unittest.TestCase):
    def test_every_design_editor_has_a_lane(self):
        self.assertEqual(
            set(lanes()),
            {
                "plate",
                "docxodus",
                "apryse",
                "superdoc",
                "folio",
                "genoffice",
                "eigenpal",
                "office-open",
                "docen",
                "wordcraft",
                "fidus",
                "canvas",
                "docsplus",
                "libreoffice",
            },
        )

    def test_office_open_has_no_hit_testing_surface(self):
        self.assertEqual(capability("office-open", "library", "hit_testing"), "not_applicable")
        self.assertEqual(capability("office-open", "library", "typing"), "not_applicable")
        self.assertEqual(capability("office-open", "library", "save"), "supported")

    def test_plate_flow_is_not_a_page_model(self):
        self.assertEqual(capability("plate", "browser_slate", "pagination"), "not_applicable")
        self.assertEqual(capability("plate", "browser_slate", "collaboration"), "supported")
        self.assertEqual(capability("plate", "headless_docx", "visible_paint"), "not_applicable")

    def test_docsplus_collaboration_is_the_app_lane(self):
        self.assertEqual(capability("docsplus", "app", "collaboration"), "supported")
        self.assertEqual(capability("docsplus", "conversion", "collaboration"), "not_applicable")

    def test_canvas_crdt_branch_is_not_the_pin(self):
        self.assertEqual(capability("canvas", "editor", "collaboration"), "unverified")
        self.assertEqual(capability("canvas", "editor", "hit_testing"), "supported")

    def test_wordcraft_native_claims_ime_and_not_collaboration(self):
        self.assertEqual(capability("wordcraft", "native_ui", "ime"), "supported")
        self.assertEqual(capability("wordcraft", "native_ui", "undo"), "supported")
        self.assertEqual(capability("wordcraft", "native_ui", "collaboration"), "unverified")
        self.assertEqual(capability("wordcraft", "docx_crate", "visible_paint"), "not_applicable")

    def test_docxodus_session_undo_is_a_documented_api(self):
        self.assertEqual(capability("docxodus", "session", "undo"), "supported")
        self.assertEqual(capability("plate", "browser_slate", "undo"), "supported")

    def test_docxodus_and_apryse_expose_wasm(self):
        self.assertEqual(capability("docxodus", "wasm_editor", "wasm"), "supported")
        self.assertEqual(capability("apryse", "webviewer", "wasm"), "supported")

    def test_superdoc_sdk_is_not_a_paint_clock(self):
        self.assertEqual(capability("superdoc", "sdk", "visible_paint"), "not_applicable")
        self.assertEqual(capability("superdoc", "browser", "pagination"), "supported")

    def test_headless_libreoffice_does_not_type(self):
        self.assertEqual(capability("libreoffice", "headless", "typing"), "not_applicable")
        self.assertEqual(capability("libreoffice", "gui", "typing"), "unverified")

    def test_unknown_lane_is_an_error(self):
        with self.assertRaises(ValueError) as caught:
            capability("plate", "imaginary", "typing")
        self.assertIn("lane", str(caught.exception))

    def test_unknown_feature_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            capability("plate", "browser_slate", "typo_feature")
        self.assertIn("unknown feature", str(caught.exception))

    def test_evidence_is_tied_to_the_pin(self):
        plate = capability_evidence("plate", "browser_slate", "collaboration")
        self.assertEqual(plate["pin"], "64123fe51")
        self.assertIn("optional", plate["note"])
        canvas = capability_evidence("canvas", "editor", "collaboration")
        self.assertIn("68f1a4175", canvas["note"])
        paint = capability_evidence("plate", "browser_slate", "visible_paint")
        self.assertIn("not a verified measurement hook", paint["note"])
        apryse = capability_evidence("apryse", "webviewer", "wasm")
        self.assertEqual(apryse["pin"], "npm 12.2.1")
        self.assertIn("closed", apryse["note"])


class Dispatch(unittest.TestCase):
    def test_missing_adapter_is_not_run_rather_than_zero(self):
        trial = trial_or_refusal("plate", "browser_slate", "typing", "C05")
        self.assertEqual(trial["outcome"], "not_run")
        self.assertEqual(trial["failure_reason"], "adapter-not-implemented")
        self.assertIsNone(trial["latency_ms"])

    def test_not_applicable_feature_uses_the_registry(self):
        trial = trial_or_refusal("office-open", "library", "hit_testing", "C07")
        self.assertEqual(trial["outcome"], "not_applicable")
        self.assertIsNone(trial["latency_ms"])

    def test_unverified_collaboration_stays_unverified(self):
        trial = trial_or_refusal("wordcraft", "native_ui", "collaboration", "C23")
        self.assertEqual(trial["outcome"], "unverified")
        self.assertIsNone(trial["latency_ms"])


class ProfileNote(unittest.TestCase):
    def test_profile_is_stored_and_does_not_invent_a_surface(self):
        trial = trial_or_refusal("office-open", "library", "typing", "C06", feature_profile="P3")
        self.assertEqual(trial["feature_profile"], "P3")
        self.assertEqual(trial["outcome"], "not_applicable")

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            trial_or_refusal("plate", "browser_slate", "typing", "C05", feature_profile="fast")
        self.assertIn("feature_profile", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
