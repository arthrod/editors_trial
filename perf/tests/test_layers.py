import unittest

from perf.layers.classify import assert_run_instruments, assert_visible_evidence, classify_mark
from perf.layers.event_timing import (
    aggregate_inp,
    effective_duration_threshold,
    event_timing_status,
    rounded_duration_ms,
)
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


class Instruments(unittest.TestCase):
    def test_timing_run_allows_a_clock_and_a_memory_sample(self):
        assert_run_instruments("timing", ["clock", "memory_sample"])

    def test_timing_run_rejects_a_chrome_trace(self):
        with self.assertRaises(ValueError) as caught:
            assert_run_instruments("timing", ["clock", "chrome_trace"])
        self.assertIn("chrome_trace", str(caught.exception))

    def test_timing_run_rejects_playwright_trace_on(self):
        with self.assertRaises(ValueError) as caught:
            assert_run_instruments("timing", ["playwright_trace_on"])
        self.assertIn("playwright_trace_on", str(caught.exception))

    def test_diagnostic_run_may_record_gc_events(self):
        assert_run_instruments("diagnostic", ["gc_events", "chrome_trace"])


class EventTiming(unittest.TestCase):
    def test_threshold_cannot_drop_below_16(self):
        self.assertEqual(effective_duration_threshold(None), 104)
        self.assertEqual(effective_duration_threshold(0), 16)
        self.assertEqual(effective_duration_threshold(8), 16)
        self.assertEqual(effective_duration_threshold(16), 16)

    def test_duration_uses_an_8_millisecond_quantum(self):
        self.assertEqual(rounded_duration_ms(20), 24)
        self.assertEqual(rounded_duration_ms(12), 16)

    def test_buffered_history_stays_at_104(self):
        got = event_timing_status(40, 16, buffered_default=True)
        self.assertEqual(got["status"], "censored")
        self.assertIsNone(got["duration_ms"])

    def test_a_censored_edit_is_not_zero(self):
        got = event_timing_status(10, 16, buffered_default=False)
        self.assertEqual(got["status"], "censored")
        self.assertIsNone(got["duration_ms"])
        self.assertNotEqual(got["duration_ms"], 0)

    def test_inp_groups_one_interaction_id(self):
        entries = [
            {"interaction_id": 7, "duration_ms": 24, "name": "keydown"},
            {"interaction_id": 7, "duration_ms": 40, "name": "input"},
            {"interaction_id": 7, "duration_ms": 24, "name": "keyup"},
            {"interaction_id": 0, "duration_ms": 80, "name": "keydown"},
            {"interaction_id": 8, "duration_ms": 16, "name": "keydown"},
        ]
        self.assertEqual(aggregate_inp(entries), 40)


if __name__ == "__main__":
    unittest.main()


class EventTimingB1(unittest.TestCase):
    def test_raw_twelve_is_censored_before_rounding(self):
        got = event_timing_status(12, 16)
        self.assertEqual(got['status'], 'censored')
        self.assertIsNone(got['duration_ms'])
        self.assertIsNone(got['rounded_ms'])
        self.assertTrue(got['below_16_ms'])

    def test_raw_zero_is_censored_not_zero(self):
        got = event_timing_status(0, 16)
        self.assertIsNone(got['rounded_ms'])
        self.assertTrue(got['below_16_ms'])

    def test_censored_entries_never_enter_samples(self):
        from perf.layers import event_timing
        self.assertTrue(hasattr(event_timing, 'samples_ms'), 'missing censored sample filter')
        entries = [event_timing_status(raw, 16) for raw in [0, 12, 16, 20]]
        self.assertEqual(event_timing.samples_ms(entries), [16, 24])
        self.assertEqual(aggregate_inp([dict(row, interaction_id=1) for row in entries]), 24)
