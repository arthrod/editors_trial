"""E2: C10 by pixels for OnlyOffice, and only for OnlyOffice.

OnlyOffice has no DOM scroller: its scrollbar is a canvas widget, its wheel
is handled in its own JavaScript and its document is redrawn on a canvas, so
the DOM probe found no container and recorded "does not apply" (after its
whole 300 s load bound). The owner decided (2026-11-22) to build a pixel
probe: one real wheel notch over the document canvas, timed with the same
witness to the first frame whose canvas pixels changed, and accepted only when
the editor's scroll position moved and that frame shows the canvas shifted
by the move (c10_canvas_pixels.mjs).

A1  the gate names OnlyOffice and no other browser target.
A2  a DOM editor id (plate) on the plain fake host keeps the DOM probe: it
    measures and its payload carries no detection.
A3  the pixel path on an OnlyOffice-shaped fake host (``oo-canvas.html``)
    measures, says ``detection: canvas_pixels``, finds the 45 px shift and
    hides the blinking caret div.
A4  a wheel that moves the scroll position but repaints the canvas in place
    is refused: the pixels, not the editor's word, decide.
A5  a wheel that moves nothing is refused.
A6  the Python verdict refuses a pixel sample whose shift record is not
    shifted, and judges a DOM sample exactly as before.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.tests import test_e2_c10_late_mount as late  # noqa: E402

_FakeHost, _node, _playwright_dir = late._FakeHost, late._node, late._playwright_dir
GATE = REPO / "perf" / "runner" / "c10_canvas_pixels.mjs"


class CanvasPixelGateTests(unittest.TestCase):
    def test_the_gate_names_onlyoffice_and_no_other_target(self):
        if _node() is None:
            raise unittest.SkipTest("node is not on PATH")
        from perf.runner.benchmark_warm_cold import BROWSER_TARGETS

        ids = sorted(BROWSER_TARGETS)
        self.assertIn("onlyoffice", ids)
        script = (
            "import(process.argv[1]).then((m) => {"
            " const ids = JSON.parse(process.argv[2]);"
            " console.log(JSON.stringify(ids.filter((id) => m.canvasPixelScroll(id) !== null)));"
            "}).catch((e) => { console.error(e); process.exit(1); });"
        )
        proc = subprocess.run(
            [_node(), "-e", script, GATE.as_uri(), json.dumps(ids)],
            capture_output=True, text=True, timeout=60, cwd=str(REPO),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), ["onlyoffice"])


class CanvasPixelProbeTests(unittest.TestCase):
    base = ""

    @classmethod
    def setUpClass(cls):
        if _node() is None:
            raise unittest.SkipTest("node is not on PATH")
        if _playwright_dir() is None:
            raise unittest.SkipTest("harness/ui has no playwright package")
        cls.base = _FakeHost.start()

    @classmethod
    def tearDownClass(cls):
        _FakeHost.stop()

    probe = late.LateMountScrollTests.probe

    def _as(self, editor: str, page: str) -> dict:
        return self.probe(
            page, extra=("--editor", editor, "--usable-js", "window.__docxReady === true"),
        )

    def test_a_dom_editor_keeps_the_dom_probe(self):
        payload = self._as("plate", "prose.html")
        self.assertEqual(payload.get("outcome"), "measured", payload.get("reason"))
        self.assertNotIn("detection", payload)
        sample = payload["samples"][0]
        self.assertNotIn("detection", sample)
        self.assertEqual(sample["container"]["selector"], "#doc")
        self.assertNotIn("canvas_pixels", json.dumps(payload))

    def test_onlyoffice_is_measured_by_pixels(self):
        payload = self._as("onlyoffice", "oo-canvas.html?mode=shift")
        self.assertEqual(payload.get("outcome"), "measured", payload.get("reason"))
        self.assertEqual(payload.get("detection"), "canvas_pixels")
        sample = payload["samples"][0]
        self.assertEqual(sample["detection"], "canvas_pixels")
        self.assertEqual(sample["scroll_top_delta"], 45)
        shift = sample["content"]["shift"]
        self.assertTrue(shift["shifted"], shift)
        self.assertLessEqual(abs(shift["best_dy_px"] - 45), 2, shift)
        self.assertGreater(sample["content"]["moved_px"], 0)
        self.assertEqual(sample["caret_mask_in_canvas_editor"]["matched"], 1)
        self.assertEqual(sample["input"]["kind"], "wheel")
        self.assertGreater(sample["scroll_frame_ms"], 0)
        # The Python side accepts it as a measurement.
        from perf.runner.adversarial_c10_scroll import scroll_sample_verdict

        outcome, reason, value = scroll_sample_verdict(sample)
        self.assertEqual(outcome, "measured", reason)
        self.assertEqual(value, sample["scroll_frame_ms"])

    def test_a_repaint_in_place_is_refused(self):
        payload = self._as("onlyoffice", "oo-canvas.html?mode=repaint")
        self.assertEqual(payload.get("outcome"), "failed")
        self.assertIn("does not show it moved by the scroll", payload.get("reason") or "")
        self.assertIn("canvas_pixels", payload.get("reason") or "")

    def test_a_wheel_that_moves_nothing_is_refused(self):
        payload = self._as("onlyoffice", "oo-canvas.html?mode=still")
        self.assertEqual(payload.get("outcome"), "failed")
        self.assertIn("the scroll did not move", payload.get("reason") or "")


class CanvasPixelVerdictTests(unittest.TestCase):
    def _measured_dom_sample(self) -> dict:
        rect = {"x": 0.0, "y": 0.0, "width": 800.0, "height": 600.0}
        return {
            "outcome": "measured",
            "witness": {"document_region": {"rect_css_px": rect}, "region_pixels": 480000, "changed_pixels": 10},
            "container": {"selector": "#doc", "region_rect": rect},
            "scroll_top_delta": 600,
            "content": {"moved_px": 600},
            "scroll_frame_ms": 12.5,
        }

    def _verdict(self, sample):
        from perf.runner import adversarial_c10_scroll as lane

        original = lane.validate_witness
        lane.validate_witness = lambda witness, bound_ms=None: {"refused": False}
        try:
            return lane.scroll_sample_verdict(sample)
        finally:
            lane.validate_witness = original

    def test_a_dom_sample_is_judged_as_before(self):
        self.assertEqual(self._verdict(self._measured_dom_sample()), ("measured", None, 12.5))

    def test_a_pixel_sample_without_a_shift_is_refused(self):
        sample = self._measured_dom_sample()
        sample["detection"] = "canvas_pixels"
        sample["content"]["shift"] = {"shifted": False, "reason": "the canvas changed but is not shifted"}
        outcome, reason, value = self._verdict(sample)
        self.assertEqual(outcome, "failed")
        self.assertIn("not shifted", reason)
        self.assertIsNone(value)
        sample["content"]["shift"] = {"shifted": True}
        self.assertEqual(self._verdict(sample), ("measured", None, 12.5))


if __name__ == "__main__":
    unittest.main()
