"""E2: the rules the browser lanes gained for OpenDoc, each gated to it.

OpenDoc (harness/ui/opendoc) paints its pages on canvases and handles its
clipboard and undo keys itself. Every rule added to shared driver code for it
is checked here twice: on OpenDoc's surface it applies, and on the surfaces of
the editors already published it changes nothing.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TESTS = REPO / "perf" / "tests"


def _node(script: str) -> dict:
    proc = subprocess.run(["node", str(TESTS / script)], cwd=str(REPO), capture_output=True, text=True, timeout=120)
    if proc.returncode:
        raise AssertionError(proc.stderr)
    return json.loads(proc.stdout)


@unittest.skipIf(shutil.which("node") is None, "node is not on PATH")
class OpenDocPasteInput(unittest.TestCase):
    """C08: OpenDoc pastes from its keydown handler (async Clipboard API), so the
    page sees keydown V and no paste or beforeinput event."""

    @classmethod
    def setUpClass(cls):
        cls.out = _node("e2_opendoc_paste_repro.mjs")

    def test_on_opendoc_the_paste_input_is_the_keydown(self):
        row = self.out["opendoc"]
        self.assertEqual(row["outcome"], "measured", row)
        self.assertEqual(row["paste_input"], "keydown")
        self.assertEqual(row["input_ms"], 100)

    def test_every_other_surface_still_needs_a_paste_event(self):
        for name in ("dom", "docen"):
            row = self.out[name]
            self.assertEqual(row["paste_failure"], "paste_keystroke_did_not_reach_the_page", (name, row))
            self.assertIsNone(row["paste_input"], name)


@unittest.skipIf(shutil.which("node") is None, "node is not on PATH")
class OpenDocParagraphCensus(unittest.TestCase):
    """C12 evidence: the census lists OpenDoc's paragraphs from the engine (paged,
    async); the docen and canvas-editor lists are unchanged arrays."""

    @classmethod
    def setUpClass(cls):
        cls.out = _node("e2_opendoc_census_repro.mjs")

    def test_opendoc_paragraphs_come_from_every_page_of_the_engine_read(self):
        self.assertTrue(self.out["opendoc_is_promise"])
        self.assertEqual(self.out["opendoc"], ["First", "Second", "Third"])
        self.assertEqual(self.out["opendoc_calls"], [{"tool": "read"}, {"tool": "read", "cursor": "c1"}])

    def test_the_other_models_still_list_synchronously(self):
        self.assertTrue(self.out["docen_is_array"])
        self.assertEqual(self.out["docen"], ["D1"])
        self.assertTrue(self.out["canvas_is_array"])
        self.assertEqual(self.out["canvas"], ["C1"])
        self.assertIsNone(self.out["unknown"])


class OpenDocScroller(unittest.TestCase):
    """C10: OpenDoc's scroller is #viewport (its pages are canvases; its only DOM
    text is the off-page screen-reader mirror), named in the adapter table."""

    def test_opendoc_scrolls_its_viewport(self):
        from perf.runner import adversarial_c10_scroll as c10

        self.assertEqual(c10.adapter_selectors("opendoc"), {"container": "#viewport", "document": None})

    def test_the_other_editors_are_unchanged(self):
        from perf.runner import adversarial_c10_scroll as c10

        self.assertEqual(c10.adapter_selectors("wordcraft"), {"container": "#wc-scroll", "document": "#wordcraft_canvas"})
        for editor in ("plate", "docxodus", "superdoc", "genoffice", "canvas", "docen", "eigenpal", "folio", "reactdocx"):
            self.assertEqual(c10.adapter_selectors(editor), {"container": None, "document": None}, editor)


if __name__ == "__main__":
    unittest.main()
