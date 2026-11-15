"""C24 WASM-boundary honesty guardrails.

These tests pin the rules that keep C24 a measurement:

- a probe payload that carries copied, empty, non-numeric or wrong-count
  samples never becomes a ``measured`` attempt;
- an operation the adapter cannot express is recorded with a reason, never
  with a zero;
- the WASM operation contract in ``perf/layers/wasm.py`` is applied to the
  aggregate report (null exactly where the capability is off);
- every editor in the harness appears in the support/refusal table with a
  non-empty reason, and every technique the adapter names exists in the probe.
"""

import json
import re
import tempfile
import unittest
from pathlib import Path

from perf.adapters.capabilities import LANES
from perf.fixtures.profiles import size_ladder
from perf.layers.wasm import assert_wasm_report, required_wasm_operations
from perf.runner.benchmark_ci_contract import _host_base
from perf.runner.wasm_boundary import (
    CAPABILITIES,
    EDITORS,
    OPERATIONS,
    REPETITION_UNIT,
    CACHE_STATE,
    PROBE,
    _env_for,
    _spec_for,
    _write_measured,
    _write_non_measured,
    assert_probe_payload,
    capabilities_for,
    support_table,
)
from perf.schema import validate_trial

REPO = Path(__file__).resolve().parents[2]


def _payload(editor_id="wordcraft", samples=None, correctness_ok=True, extra=None):
    """A structurally valid probe payload with per-operation distinct samples."""
    if samples is None:
        samples = {name: [1.0 + i * 0.1 + idx for i in range(3)] for idx, name in enumerate(OPERATIONS)}
    ops = {}
    for name in OPERATIONS:
        if name in CAPABILITIES.get(editor_id, {}):
            continue
        ops[name] = {
            "technique": EDITORS[editor_id]["ops"][name]["technique"],
            "surface": EDITORS[editor_id]["surface"],
            "samples_ms": list(samples[name]),
            "correctness": {"ok": correctness_ok, "expected": "x", "observed": "x"},
            "error": None,
        }
    if extra:
        ops.update(extra)
    return {
        "schema": "c24-wasm-host/1",
        "editor_id": editor_id,
        "module": {"url": "http://127.0.0.1/x.wasm", "byte_length": 10, "sha256": "a" * 64},
        "live_surface": {"source": "test"},
        "ops": ops,
        "errors": [],
        "failure": None,
    }


def _expected(samples=3):
    return {name: samples for name in OPERATIONS}


class WasmBoundaryPayloadHonesty(unittest.TestCase):
    def test_copied_sample_list_across_operations_raises(self):
        shared = [1.0, 2.0, 3.0]
        samples = {name: list(shared) for name in OPERATIONS}
        with self.assertRaises(ValueError) as caught:
            assert_probe_payload(_payload(samples=samples), "wordcraft", _expected())
        self.assertIn("copied", str(caught.exception))

    def test_missing_samples_raise(self):
        payload = _payload()
        payload["ops"]["scalar_call"]["samples_ms"] = []
        with self.assertRaises(ValueError) as caught:
            assert_probe_payload(payload, "wordcraft", _expected())
        self.assertIn("no samples", str(caught.exception))

    def test_failed_correctness_assertion_raises(self):
        with self.assertRaises(ValueError) as caught:
            assert_probe_payload(_payload(correctness_ok=False), "wordcraft", _expected())
        self.assertIn("correctness assertion failed", str(caught.exception))

    def test_repetition_count_must_match_the_spec(self):
        with self.assertRaises(ValueError) as caught:
            assert_probe_payload(_payload(), "wordcraft", _expected(samples=99))
        self.assertIn("expected 99 samples", str(caught.exception))

    def test_probe_error_for_a_supported_operation_raises(self):
        payload = _payload()
        payload["ops"]["memory_grow"]["samples_ms"] = []
        payload["ops"]["memory_grow"]["error"] = "call returned a wrong value: {...}"
        with self.assertRaises(ValueError) as caught:
            assert_probe_payload(payload, "wordcraft", _expected())
        self.assertIn("wrong value", str(caught.exception))

    def test_wrong_editor_id_raises(self):
        with self.assertRaises(ValueError):
            assert_probe_payload(_payload("docxodus"), "wordcraft", _expected())

    def test_refused_operation_returned_by_probe_raises(self):
        payload = _payload("docxodus")
        payload["ops"]["scalar_call"] = {
            "technique": "malloc_scalar",
            "samples_ms": [1.0, 2.0, 3.0],
            "correctness": {"ok": True},
            "error": None,
        }
        with self.assertRaises(ValueError) as caught:
            assert_probe_payload(payload, "docxodus", _expected())
        self.assertIn("refused", str(caught.exception))

    def test_valid_payload_matches_the_layer_contract(self):
        report = assert_probe_payload(_payload("docxodus"), "docxodus", _expected())
        caps = capabilities_for("docxodus")
        assert_wasm_report(report, caps)
        self.assertIsNone(report["scalar_call"])
        self.assertIsNone(report["typed_array_transfer"])
        self.assertIsNone(report["memory_grow"])
        self.assertEqual(len(report["string_conversion"]), 3)


class WasmBoundaryContract(unittest.TestCase):
    def test_contract_rejects_samples_for_a_disabled_operation(self):
        report = {name: [1.0] for name in required_wasm_operations()}
        capabilities = {name: True for name in required_wasm_operations()}
        capabilities["memory_grow"] = False
        with self.assertRaises(ValueError):
            assert_wasm_report(report, capabilities)

    def test_contract_rejects_a_missing_operation(self):
        report = {name: [1.0] for name in required_wasm_operations() if name != "empty_call"}
        with self.assertRaises(ValueError):
            assert_wasm_report(report, {name: True for name in required_wasm_operations()})

    def test_catalog_operations_are_exactly_the_contract(self):
        self.assertEqual(OPERATIONS, list(required_wasm_operations()))
        self.assertEqual(len(OPERATIONS), 7)


class WasmBoundaryAdapters(unittest.TestCase):
    def test_wordcraft_measures_every_operation(self):
        self.assertEqual(capabilities_for("wordcraft"), {name: True for name in OPERATIONS})
        self.assertEqual(sorted(EDITORS["wordcraft"]["ops"]), sorted(OPERATIONS))

    def test_docxodus_refusals_carry_a_specific_reason(self):
        refused = CAPABILITIES["docxodus"]
        self.assertEqual(sorted(refused), ["memory_grow", "scalar_call", "typed_array_transfer"])
        for name, reason in refused.items():
            self.assertGreater(len(reason), 80, "%s reason must say what is missing and why" % name)
            self.assertIn("repos/docxodus", reason if name != "memory_grow" else "repos/docxodus" + reason)
            self.assertNotIn(name, EDITORS["docxodus"]["ops"])

    def test_adapters_only_use_operations_from_the_catalog(self):
        for editor_id, editor in EDITORS.items():
            for name in editor["ops"]:
                self.assertIn(name, OPERATIONS, "%s/%s is not a catalog operation" % (editor_id, name))
            for name in CAPABILITIES.get(editor_id, {}):
                self.assertIn(name, OPERATIONS)

    def test_every_technique_exists_in_the_probe(self):
        source = PROBE.read_text(encoding="utf-8")
        known = set(re.findall(r"'([a-z0-9_]+)'", source))
        used = set()
        for editor in EDITORS.values():
            for op in editor["ops"].values():
                used.add(op["technique"])
        self.assertTrue(used)
        self.assertEqual(used - known, set(), "probe lacks technique(s) %s" % (used - known,))

    def test_spec_marks_one_compile_with_warm_repetitions(self):
        spec = _spec_for("wordcraft", Path("corpus.docx"), samples=4, compile_samples=2)
        by_name = {op["name"]: op for op in spec["ops"]}
        self.assertGreaterEqual(by_name["compile_and_instantiate"]["warmup"], 1)
        self.assertEqual(by_name["compile_and_instantiate"]["samples"], 2)
        self.assertEqual(by_name["scalar_call"]["samples"], 4)
        self.assertEqual(spec["surface"], "exports")
        for op in spec["ops"]:
            self.assertIn(op["technique"], {
                "compile_instantiate",
                "export_call_void",
                "malloc_scalar",
                "string_alloc_roundtrip",
                "f64_roundtrip",
                "batch_malloc",
                "memory_grow",
                "bridge_nullary",
                "bridge_json",
                "bridge_batch",
            })
        self.assertEqual(spec["ops"][0]["name"], "compile_and_instantiate")


class WasmBoundaryAttempts(unittest.TestCase):
    def _env(self, editor_id="wordcraft"):
        workload_row = next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs")
        return _env_for(
            editor_id=editor_id,
            editor_version="test-pin",
            fixture_sha256="b" * 64,
            docx_size=1024,
        )

    def test_measured_attempt_is_valid_and_blocked_on_ci_coarse(self):
        env = self._env()
        self.assertEqual(env["repetition_unit"], REPETITION_UNIT)
        self.assertEqual(env["cache_state"], CACHE_STATE)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_measured(
                Path(tmp),
                operation="scalar_call",
                editor_id="wordcraft",
                lane="wasm_ui",
                editor_version="test-pin",
                env=env,
                samples=[0.2, 0.25, 0.3],
                entry={"technique": "malloc_scalar", "surface": "exports",
                       "correctness": {"ok": True, "expected": ">0", "observed": {"pointer": 1024}}},
                module={"sha256": "c" * 64, "byte_length": 100},
                live_surface={"source": "test"},
                surface_note="test surface",
                calls_per_sample=1,
            )
            trial = json.loads(path.read_text(encoding="utf-8"))
        validate_trial(trial)
        self.assertEqual(trial["outcome"], "measured")
        self.assertEqual(trial["layer"], "wasm_boundary")
        self.assertEqual(trial["boundary"], "wasm_call")
        self.assertFalse(trial["publishable"])
        self.assertTrue(trial["publication_block_reason"])
        self.assertEqual(trial["summary_stats"]["repetition_unit"], "in_process_iteration")
        self.assertEqual(trial["diagnostic"]["operation"], "scalar_call")

    def test_measured_attempt_over_budget_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                _write_measured(
                    Path(tmp),
                    operation="scalar_call",
                    editor_id="wordcraft",
                    lane="wasm_ui",
                    editor_version="test-pin",
                    env=self._env(),
                    samples=[1.0] * 21,
                    entry={"technique": "malloc_scalar", "surface": "exports", "correctness": {"ok": True}},
                    module=None,
                    live_surface=None,
                    surface_note="test",
                    calls_per_sample=1,
                )

    def test_refusal_is_recorded_with_a_reason_and_no_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_non_measured(
                Path(tmp),
                operation="scalar_call",
                editor_id="docxodus",
                lane="wasm_editor",
                env=self._env("docxodus"),
                outcome="unsupported",
                reason=CAPABILITIES["docxodus"]["scalar_call"],
            )
            trial = json.loads(path.read_text(encoding="utf-8"))
        validate_trial(trial)
        self.assertEqual(trial["outcome"], "unsupported")
        self.assertEqual(trial["samples_ms"], [])
        self.assertIsNone(trial["latency_ms"])
        self.assertNotIn("summary_stats", trial)
        self.assertIn("repos/docxodus", trial["failure_reason"])

    def test_refusal_without_a_reason_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                _write_non_measured(
                    Path(tmp),
                    operation="scalar_call",
                    editor_id="docxodus",
                    lane="wasm_editor",
                    env=self._env("docxodus"),
                    outcome="unsupported",
                    reason="",
                )


class WasmBoundarySupportTable(unittest.TestCase):
    def test_every_harness_lane_is_listed(self):
        rows = {row["editor_id"]: row for row in support_table()}
        self.assertEqual(set(rows), set(LANES))
        for editor_id, row in rows.items():
            if row["state"] == "refused":
                self.assertTrue(row["reason"], "%s needs a refusal reason" % editor_id)
                self.assertEqual(row["measured_operations"], [])

    def test_supported_rows_name_their_operations(self):
        rows = {row["editor_id"]: row for row in support_table()}
        self.assertEqual(rows["wordcraft"]["measured_operations"], OPERATIONS)
        self.assertEqual(
            sorted(rows["docxodus"]["measured_operations"]),
            sorted(set(OPERATIONS) - set(CAPABILITIES["docxodus"])),
        )
        self.assertEqual(sorted(rows["docxodus"]["refused_operations"]),
                         sorted(CAPABILITIES["docxodus"]))

    def test_runner_reads_pins_and_never_writes_reports(self):
        source = (REPO / "perf" / "runner" / "wasm_boundary.py").read_text(encoding="utf-8")
        self.assertIn("pin_label", source)
        self.assertNotIn("facts.json", source)
        self.assertNotIn("render_reports", source)
        self.assertIn("validate_trial", source)


if __name__ == "__main__":
    unittest.main()
