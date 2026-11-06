import unittest

from perf.layers.classify import assert_visible_evidence, classify_mark
from perf.layers.wasm import assert_wasm_report, required_wasm_operations


class Classify(unittest.TestCase):
    def test_known_marks(self):
        self.assertEqual(classify_mark("rust_instant"), "native")
        self.assertEqual(classify_mark("native_present"), "browser_visible")
        self.assertEqual(classify_mark("model_ready"), "model")
        self.assertEqual(classify_mark("constructor_return"), "model")
        self.assertEqual(classify_mark("first_contentful_paint"), "browser_visible")
        self.assertEqual(classify_mark("presented_frame"), "browser_visible")
        self.assertEqual(classify_mark("external_pixel"), "browser_visible")
        self.assertEqual(classify_mark("wasm_instantiate"), "wasm_boundary")

    def test_raf_is_not_browser_visible(self):
        with self.assertRaises(ValueError) as caught:
            classify_mark("raf_callback")
        self.assertIn("raf_callback", str(caught.exception))

    def test_unknown_mark_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            classify_mark("looks_fast")
        self.assertIn("unknown mark", str(caught.exception))


class Evidence(unittest.TestCase):
    def test_first_usable_accepts_a_presented_frame(self):
        assert_visible_evidence("C03", "presented_frame")

    def test_first_usable_rejects_constructor_return(self):
        with self.assertRaises(ValueError) as caught:
            assert_visible_evidence("C03", "constructor_return")
        self.assertIn("constructor_return", str(caught.exception))

    def test_single_edit_rejects_a_raf_callback(self):
        with self.assertRaises(ValueError) as caught:
            assert_visible_evidence("C05", "raf_callback")
        self.assertIn("raf_callback", str(caught.exception))

    def test_event_timing_duration_is_not_edit_paint(self):
        with self.assertRaises(ValueError) as caught:
            assert_visible_evidence("C05", "event_timing_duration")
        self.assertIn("event_timing_duration", str(caught.exception))

    def test_unrelated_paint_does_not_complete_the_edit(self):
        with self.assertRaises(ValueError) as caught:
            assert_visible_evidence("C05", "unrelated_paint")
        self.assertIn("unrelated_paint", str(caught.exception))

    def test_raf_plus_later_paint_is_accepted(self):
        assert_visible_evidence("C05", "raf_plus_later_paint")

    def test_scroll_rejects_event_timing_wheel(self):
        with self.assertRaises(ValueError) as caught:
            assert_visible_evidence("C10", "event_timing_wheel")
        self.assertIn("event_timing_wheel", str(caught.exception))

    def test_scroll_accepts_frame_time(self):
        assert_visible_evidence("C10", "frame_time")

    def test_reflow_must_name_paint_separately_from_dirty_count(self):
        with self.assertRaises(ValueError) as caught:
            assert_visible_evidence("C12", "dirty_region_count")
        self.assertIn("dirty_region_count", str(caught.exception))


class Wasm(unittest.TestCase):
    def test_required_operations_cover_calls_and_copies(self):
        self.assertEqual(
            required_wasm_operations(),
            (
                "compile_and_instantiate",
                "empty_call",
                "scalar_call",
                "string_conversion",
                "typed_array_transfer",
                "batched_call",
                "memory_grow",
            ),
        )

    def test_an_editor_scenario_does_not_replace_the_boundary(self):
        with self.assertRaises(ValueError) as caught:
            assert_wasm_report({"editor_scenario_ms": [10.0]})
        self.assertIn("compile_and_instantiate", str(caught.exception))

    def test_a_complete_report_passes(self):
        report = {name: [1.0] for name in required_wasm_operations()}
        assert_wasm_report(report)

    def test_a_string_is_not_a_sample_list(self):
        report = {name: [1.0] for name in required_wasm_operations()}
        report["empty_call"] = "1.0"
        with self.assertRaises(ValueError) as caught:
            assert_wasm_report(report)
        self.assertIn("empty_call", str(caught.exception))

    def test_nan_is_not_a_sample(self):
        report = {name: [1.0] for name in required_wasm_operations()}
        report["scalar_call"] = [float("nan")]
        with self.assertRaises(ValueError) as caught:
            assert_wasm_report(report)
        self.assertIn("scalar_call", str(caught.exception))

    def test_closed_lane_leaves_unavailable_operations_null(self):
        names = required_wasm_operations()
        capabilities = {name: False for name in names}
        capabilities["compile_and_instantiate"] = True
        report = {name: None for name in names}
        report["compile_and_instantiate"] = [2.0]
        report["runtime"] = "proprietary"
        assert_wasm_report(report, capabilities)

    def test_a_disabled_operation_cannot_carry_samples(self):
        names = required_wasm_operations()
        capabilities = {name: False for name in names}
        report = {name: None for name in names}
        report["empty_call"] = [1.0]
        with self.assertRaises(ValueError) as caught:
            assert_wasm_report(report, capabilities)
        self.assertIn("empty_call", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
