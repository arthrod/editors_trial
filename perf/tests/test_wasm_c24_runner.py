"""C24 wasm runner must not emit measured samples without wasm file hash."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import perf.runner.benchmark_wasm_c24 as wasm_runner

REPO = Path(__file__).resolve().parents[2]


class WasmC24MeasuredRequiresHash(unittest.TestCase):
    def test_wasm_meta_always_includes_sha256(self):
        wasm = REPO / "harness/ui/docxodus/node_modules/docxodus/dist/wasm/_framework/dotnet.native.wasm"
        if not wasm.is_file():
            self.skipTest("docxodus wasm not installed")
        meta = wasm_runner._wasm_meta(wasm)
        self.assertGreater(meta["wasm_byte_size"], 0)
        self.assertEqual(len(meta["wasm_sha256"]), 64)

    def test_measured_attempts_carry_wasm_sha256(self):
        out_root = REPO / "perf" / "out" / "c24_wasm_2026_11_07"
        summary_path = out_root / "summary.json"
        if not summary_path.is_file():
            self.skipTest("c24_wasm summary not produced in this checkout")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertTrue(summary.get("wasm_sha256"), "summary must record wasm_sha256")
        attempt_dir = out_root / "attempts"
        for path in attempt_dir.glob("c24-docxodus-*.json"):
            trial = json.loads(path.read_text(encoding="utf-8"))
            if trial.get("outcome") != "measured":
                continue
            diag = trial.get("diagnostic") or {}
            self.assertTrue(
                diag.get("wasm_sha256"),
                "%s measured without diagnostic.wasm_sha256" % path.name,
            )
            self.assertTrue(
                trial.get("samples_ms"),
                "%s measured with empty samples_ms" % path.name,
            )


if __name__ == "__main__":
    unittest.main()
