"""Unit checks for perf_model_text.mjs opening gate."""
import json
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "perf/runner/perf_model_text.mjs"


class PerfModelText(unittest.TestCase):
    def verdict(self, **kwargs):
        script = f"""
import {{ openingContentVerdict }} from {json.dumps(str(MODULE))};
const verdict = openingContentVerdict({json.dumps(kwargs)});
console.log(JSON.stringify(verdict));
"""
        proc = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_dom_editor_still_verifies(self):
        v = self.verdict(expected="Alpha bravo", actual="Alpha bravo charlie", canvasPresent=False, modelOracle="dom")
        self.assertTrue(v["content_verified"])
        self.assertIsNone(v["surface_reason"])

    def test_canvas_without_hook_is_unverifiable(self):
        v = self.verdict(expected="Alpha bravo", actual="", modelOracle="absent")
        self.assertFalse(v["content_verified"])
        self.assertEqual(v["surface_reason"], "document_content_unverifiable")

    def test_canvas_with_dom_text_layer_verifies(self):
        v = self.verdict(
            expected="Alpha bravo",
            actual="Alpha bravo in shadow text",
            modelOracle="dom",
        )
        self.assertTrue(v["content_verified"])
        self.assertIsNone(v["surface_reason"])

    def test_canvas_model_requires_whole_document_check(self):
        v = self.verdict(
            expected="Alpha bravo",
            actual="Alpha bravo",
            modelOracle="perf_model",
            modelDocumentCheck={"ok": False, "surface_reason": "document_content_mismatch"},
        )
        self.assertFalse(v["content_verified"])
        self.assertEqual(v["surface_reason"], "document_content_mismatch")

    def test_editor_error_is_a_named_unverifiable_refusal(self):
        v = self.verdict(
            expected="Alpha bravo",
            actual="",
            modelOracle="absent",
            editorError="TypeError: model read failed",
        )
        self.assertFalse(v["content_verified"])
        self.assertEqual(v["surface_reason"], "document_content_unverifiable")
        self.assertEqual(v["editor_error"], "TypeError: model read failed")

    def test_canvas_model_mismatch(self):
        v = self.verdict(
            expected="Alpha bravo",
            actual="Wrong",
            modelOracle="dom",
            domDocumentCheck={"ok": False, "surface_reason": "document_content_mismatch"},
        )
        self.assertEqual(v["surface_reason"], "document_content_mismatch")

    def test_dom_opening_only_passes_without_closing(self):
        v = self.verdict(
            expected="Alpha bravo",
            actual="Alpha bravo opening slice",
            modelOracle="dom",
            domDocumentCheck={"ok": True},
        )
        self.assertTrue(v["content_verified"])
