"""E2: the shared model readers read BetterOffice through its async editor ref.

@betteroffice/docx-react 0.5.1 keeps the document in a worker: the editor
ref's readParagraphs and readSelectionInfo are async, and its synchronous
getDocument/getPageContent throw without legacySyncApi. The readers return a
promise for model 'betteroffice' (page.evaluate awaits it). Before this
change the model fell through to canvas-editor's usable expression (never
true on BetterOffice's page) and to the DOM text read (no text: pages are
canvases).

A1  usable is the host page's ready flag (true at ?ready=1, false at ?ready=0);
A2  the whole-document reads join the body paragraphs, one line each;
A3  the caret read is the caret paragraph; the surface state has the text,
    the caret offset (paragraph start + text before the caret), focus in the
    editor and the focused caret-sized textarea as the caret;
A4  canvas-editor's and Docen's usable expressions are unchanged.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
PROBE = REPO / "perf" / "tests" / "e2_betteroffice_model_probe.mjs"

CANVAS_USABLE = (
    '!!(window.__CANVAS_EDITOR_INSTANCE__ && window.__CANVAS_EDITOR_INSTANCE__.command'
    ' && typeof window.__CANVAS_EDITOR_INSTANCE__.command.getValue === "function")'
)
DOCEN_USABLE = '!!(window.__DOCEN__ && window.__DOCEN__.editor && window.__DOCEN__.editor.state)'


class BetterOfficeModelReaders(unittest.TestCase):
    server = None
    payload = None

    @classmethod
    def setUpClass(cls):
        node = shutil.which("node")
        if node is None:
            raise unittest.SkipTest("node is not on PATH")
        from perf.runner.browser_hosts import StaticHost

        cls.server = StaticHost(HOSTS)
        proc = subprocess.run(
            [node, str(PROBE), "%s/e2_betteroffice_model.html" % cls.server.url],
            capture_output=True, text=True, timeout=60, cwd=str(REPO),
        )
        if proc.returncode != 0:
            raise AssertionError("probe failed: %s\n%s" % (proc.stdout, proc.stderr))
        cls.payload = json.loads(proc.stdout)

    @classmethod
    def tearDownClass(cls):
        if cls.server is not None:
            cls.server.stop()

    def test_usable_is_the_host_ready_flag(self):
        self.assertEqual(self.payload["usable"], {"1": True, "0": False})

    def test_whole_document_reads_join_the_body_paragraphs(self):
        doc = self.payload["document_text"]
        self.assertEqual(doc["text"], "Alpha one\nBeta two", doc)
        self.assertEqual(doc["oracle"], "perf_model")
        self.assertEqual(doc["source"], "betteroffice_model")
        self.assertEqual(self.payload["model_document"], {"text": "Alpha one\nBeta two", "absorbed_items": []})
        self.assertEqual(self.payload["paragraphs"], ["Alpha one", "Beta two"])

    def test_caret_reads(self):
        self.assertEqual(self.payload["at_caret"], "Beta two")
        state = self.payload["state"]
        self.assertNotIn("error", state, state)
        self.assertEqual(state["text"], "Alpha one\nBeta two")
        self.assertEqual(state["selection_offset"], len("Alpha one\n") + len("Be"))
        self.assertEqual(state["caret_block_text"], "Beta two")
        self.assertTrue(state["active_inside"])
        self.assertTrue(state["anchor_inside"])
        self.assertTrue(state["input_reachable"])
        self.assertEqual(state["caret"]["height"], 20)
        self.assertTrue(state["caret"]["collapsed"])

    def test_other_model_editors_are_unchanged(self):
        self.assertEqual(self.payload["canvas_usable"], CANVAS_USABLE)
        self.assertEqual(self.payload["docen_usable"], DOCEN_USABLE)


if __name__ == "__main__":
    unittest.main()
