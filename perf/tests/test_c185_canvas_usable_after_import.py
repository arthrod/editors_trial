"""canvas-editor's usable frame waits for the document (#185).

The ``canvas_pixel`` signal took the first frame with any non-white pixel.
canvas-editor paints its empty page's margin marks at once, so C11 and C14
timed the empty page: about 130 ms at every rung while the import took 51 s
at 250,000 words. A canvas holds no text to check against the document, so
for this signal the usable frame is the first one in which the editor's own
ready condition holds and the canvas has ink.
"""

from __future__ import annotations

import json
import subprocess
import unittest

import perf.runner.benchmark_document as bd
from perf.tests import test_b3_document as b3

IMPORT_AT_MS = 700
READY = "window.__DOCX_IMPORTED__ === true"


class CanvasUsableWaitsForTheDocument(unittest.TestCase):
    setUpClass = classmethod(b3.FakeHostMeasurers.setUpClass.__func__)
    tearDownClass = classmethod(b3.FakeHostMeasurers.tearDownClass.__func__)

    def _probe(self, mode: str, extra: list, host: str = "c185_canvas_chrome_first.html") -> dict:
        cmd = [b3._node(), str(b3.PROBE), "--mode", mode, "--url", "%s/%s" % (self.base_url, host),
               "--corpus", str(self.corpus), "--doc-selector", ".doc-paragraph", "--page-model", "continuous_flow",
               "--usable-signal", "canvas_pixel", "--ready-js", READY, "--timeout-ms", "8000", *extra]
        proc = subprocess.run(cmd, cwd=str(b3.REPO), capture_output=True, text=True, timeout=120)
        return json.loads(proc.stdout)

    def test_load_usable_is_not_before_the_import(self):
        payload = self._probe("load", [])
        at = payload.get("document_text_at_ms")
        self.assertIsNotNone(at, payload.get("surface_reason"))
        self.assertGreaterEqual(at, IMPORT_AT_MS, payload)

    def test_scale_usable_is_not_before_the_import(self):
        payload = self._probe("scale", [])
        self.assertIsNotNone(payload.get("usable_ms"), payload.get("reason"))
        self.assertGreaterEqual(payload["usable_ms"], IMPORT_AT_MS, payload.get("usable_ms"))


    def test_the_usable_frame_shows_the_document_not_the_empty_page(self):
        payload = self._probe("scale", [])
        self.assertIs(payload.get("canvas_ink_changed"), True, payload.get("canvas_ink_changed"))

    def test_a_ready_flag_before_the_document_ink_waits_for_the_ink(self):
        # glm-5.3 review of 31805ef7, finding 1: the empty page already has ink, so
        # "ready and ink" was "ready" alone. canvas-editor flips its flag a frame or
        # two before its lazy render draws the page. The usable frame is the first
        # one after the flag whose page canvas differs from the empty page.
        for mode, key in (("scale", "usable_ms"), ("load", "document_text_at_ms")):
            payload = self._probe(mode, [], host="c185_canvas_ready_first.html")
            self.assertGreaterEqual(payload.get(key) or 0, 690, (mode, payload.get(key)))
            self.assertIs(payload.get("canvas_ink_changed"), True, (mode, payload.get("canvas_ink_changed")))

    def test_a_canvas_cleared_at_the_flag_is_not_the_document(self):
        payload = self._probe("scale", [], host="c185_canvas_cleared_then_drawn.html")
        self.assertGreaterEqual(payload.get("usable_ms") or 0, 690, payload.get("usable_ms"))


if __name__ == "__main__":
    unittest.main()
