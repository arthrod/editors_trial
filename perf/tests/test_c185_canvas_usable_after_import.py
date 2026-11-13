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

from perf.tests import test_b3_document as b3

IMPORT_AT_MS = 700
READY = "window.__DOCX_IMPORTED__ === true"


class CanvasUsableWaitsForTheDocument(unittest.TestCase):
    setUpClass = classmethod(b3.FakeHostMeasurers.setUpClass.__func__)
    tearDownClass = classmethod(b3.FakeHostMeasurers.tearDownClass.__func__)

    def _probe(self, mode: str, extra: list) -> dict:
        cmd = [b3._node(), str(b3.PROBE), "--mode", mode, "--url", "%s/c185_canvas_chrome_first.html" % self.base_url,
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


if __name__ == "__main__":
    unittest.main()
