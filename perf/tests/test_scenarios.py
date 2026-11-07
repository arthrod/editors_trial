import json
import unittest
from pathlib import Path

from perf.scenarios.catalog import scenarios
from perf.scenarios.coverage import matrix_gaps


class Catalog(unittest.TestCase):
    def test_ids_are_exactly_the_twenty_four_criteria(self):
        ids = [row["id"] for row in scenarios()]
        self.assertEqual(ids, ["C%02d" % n for n in range(1, 25)])

    def test_startup_keeps_three_cache_states(self):
        startup = scenarios()[0]
        self.assertEqual(startup["id"], "C01")
        self.assertEqual(startup["cache_states"], [
            "process_cold_fs_warm",
            "os_cache_cold",
            "warm_steady",
        ])
        self.assertEqual(startup["repetition_unit"], "fresh_process")

    def test_visible_scenarios_do_not_use_a_raf_callback(self):
        for row in scenarios():
            if row["layer"] == "browser_visible":
                forbidden = {"raf_callback", "constructor_return", "model_ready"}
                for field in ("boundary", "evidence"):
                    self.assertNotIn(row[field], forbidden)


class Clocks(unittest.TestCase):
    def test_scroll_evidence_is_frame_time(self):
        scroll = next(row for row in scenarios() if row["id"] == "C10")
        self.assertEqual(scroll["evidence"], "frame_time")
        self.assertNotEqual(scroll["evidence"], "event_timing_wheel")

    def test_allocation_scenario_is_diagnostic(self):
        allocation = next(row for row in scenarios() if row["id"] == "C18")
        self.assertEqual(allocation["run_kind"], "diagnostic")

    def test_long_session_is_dedicated_and_at_least_one_hour(self):
        soak = next(row for row in scenarios() if row["id"] == "C20")
        self.assertEqual(soak["host_class"], "dedicated")
        self.assertGreaterEqual(soak["min_seconds"], 3600)

    def test_model_load_does_not_claim_user_visible(self):
        load = next(row for row in scenarios() if row["id"] == "C02")
        self.assertEqual(load["layer"], "model")
        self.assertEqual(load["boundary"], "model_ready")
        self.assertNotIn("user_visible", load.get("claims", []))

    def test_wasm_scenario_names_the_boundary_operations(self):
        wasm = next(row for row in scenarios() if row["id"] == "C24")
        self.assertEqual(wasm["operations"], [
            "compile_and_instantiate",
            "empty_call",
            "scalar_call",
            "string_conversion",
            "typed_array_transfer",
            "batched_call",
            "memory_grow",
        ])
        self.assertIs(wasm["operations_required"], False)

    def test_feature_overhead_names_every_profile(self):
        overhead = next(row for row in scenarios() if row["id"] == "C22")
        self.assertEqual(overhead["feature_profiles"], ["P0", "P1", "P2", "P3"])

    def test_startup_records_every_phase(self):
        startup = next(row for row in scenarios() if row["id"] == "C01")
        self.assertEqual(startup["marks"], [
            "process_spawn",
            "presented_frame",
            "input_ready",
            "deferred_quiescence",
        ])

    def test_first_content_requires_document_text_and_a_usable_edit(self):
        visible = next(row for row in scenarios() if row["id"] == "C03")
        self.assertEqual(visible["marks"], ["document_text_visible", "first_usable"])
        self.assertNotEqual(visible["evidence"], "first_contentful_paint")

    def test_search_records_each_phase(self):
        search = next(row for row in scenarios() if row["id"] == "C15")
        self.assertEqual(search["measurements"], [
            "first_match",
            "search_complete",
            "replace_all",
            "index_quiescence",
        ])

    def test_save_labels_rereadable_separately_from_durable(self):
        save = next(row for row in scenarios() if row["id"] == "C16")
        self.assertEqual(save["evidence"], "rereadable_bytes")
        self.assertEqual(save["durability"], "durable_only_when_data_and_directory_are_synced")


class ExecutionProfile(unittest.TestCase):
    def test_every_scenario_names_a_minimum_profile(self):
        for row in scenarios():
            self.assertIn(row["min_execution_profile"], ("ci_contract", "ci_broad", "dedicated_publish"))

    def test_model_and_wasm_scenarios_run_on_ci_contract(self):
        for criterion_id in ("C02", "C04", "C13", "C15", "C16", "C17", "C19", "C21", "C24"):
            row = next(item for item in scenarios() if item["id"] == criterion_id)
            self.assertEqual(row["min_execution_profile"], "ci_contract")

    def test_visible_interaction_requires_ci_broad(self):
        for criterion_id in ("C05", "C06", "C07", "C08", "C09", "C10"):
            row = next(item for item in scenarios() if item["id"] == criterion_id)
            self.assertEqual(row["min_execution_profile"], "ci_broad")

    def test_large_document_scaling_requires_dedicated_publish(self):
        scaling = next(row for row in scenarios() if row["id"] == "C14")
        self.assertEqual(scaling["min_execution_profile"], "dedicated_publish")

    def test_long_session_requires_dedicated_publish(self):
        soak = next(row for row in scenarios() if row["id"] == "C20")
        self.assertEqual(soak["min_execution_profile"], "dedicated_publish")


class Matrix(unittest.TestCase):
    def test_catalog_covers_the_normative_criteria_and_conditions(self):
        matrix = json.loads(Path(
            "docs/superpowers/specs/2026-11-05-editor-performance-coverage.json"
        ).read_text())
        self.assertEqual(matrix_gaps(matrix, scenarios()), [])

    def test_a_missing_condition_is_reported(self):
        matrix = {"criteria": [{"id": "C01"}], "interpretation_conditions": [{"id": "I12"}]}
        rows = [{"id": "C01", "correctness": []}]
        self.assertEqual(matrix_gaps(matrix, rows), ["I12"])

    def test_unknown_correctness_id_is_rejected(self):
        matrix = {
            "criteria": [{"id": "C01"}],
            "interpretation_conditions": [{"id": "I12"}],
        }
        rows = [{"id": "C01", "correctness": ["I12", "I99"]}]
        with self.assertRaises(ValueError) as caught:
            matrix_gaps(matrix, rows)
        self.assertIn("I99", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
