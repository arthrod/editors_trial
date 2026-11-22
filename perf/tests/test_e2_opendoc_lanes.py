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


class OpenDocC22(unittest.TestCase):
    """C22: OpenDoc's editor has P0-P3 switches (?prefs= proofing, ?aiProvider=off,
    ?room=), so its C22 is applicable and recorded not_run, not not_applicable.
    Every other editor keeps its not_applicable record."""

    def _c22(self, editor_id, lane):
        import tempfile

        from perf.runner.benchmark_memory import _c22_row
        from perf.schema import validate_trial
        from perf.tests.test_memory_criteria import _workload_row

        with tempfile.TemporaryDirectory() as tmp:
            attempt_dir = Path(tmp) / "attempts"
            args = type("Args", (), {"execution_profile": "ci_broad"})()
            row = _c22_row(editor_id=editor_id, lane=lane, attempt_dir=attempt_dir, args=args,
                           fixture_sha="a" * 64, docx_size=4096, workload_row=_workload_row(),
                           editor_version="test-pin")
            (path,) = list(attempt_dir.glob("*.json"))
            trial = json.loads(path.read_text(encoding="utf-8"))
            validate_trial(trial)
            return row, trial

    def test_opendoc_c22_is_not_run_with_its_switches(self):
        _row, trial = self._c22("opendoc", "browser")
        self.assertEqual(trial["outcome"], "not_run")
        self.assertEqual(trial["evidence"]["state"], "feature_profile_switch_not_driven")
        self.assertEqual(sorted(trial["evidence"]["profile_switches"]), ["ai_panel", "collaboration", "proofing"])
        self.assertIn("C22 applies", trial["failure_reason"])
        self.assertNotIn("no P0-P3 feature profile", trial["failure_reason"])

    def test_the_other_editors_keep_not_applicable(self):
        for editor_id, lane in (("plate", "browser_slate"), ("reactdocx", "browser"), ("canvas", "editor")):
            _row, trial = self._c22(editor_id, lane)
            self.assertEqual(trial["outcome"], "not_applicable", editor_id)
            self.assertEqual(trial["evidence"]["state"], "no_feature_profile_switch", editor_id)


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


class OpenDocResourcesPort(unittest.TestCase):
    """Resources: each session takes a free port. OpenDoc's host listens on its
    --port argument, so the command moves with the URL; others are unchanged."""

    def test_opendoc_host_listens_where_the_lane_looks(self):
        from urllib.parse import urlsplit

        from perf.runner.benchmark_resources import _target_copy

        target = _target_copy("opendoc")
        port = str(urlsplit(target["url"]).port)
        self.assertEqual(target["command"][target["command"].index("--port") + 1], port)
        self.assertEqual(target["env"]["PORT"], port)

    def test_the_other_commands_are_unchanged(self):
        from perf.runner.benchmark_resources import BROWSER_TARGETS, _target_copy

        for editor in BROWSER_TARGETS:
            if editor == "opendoc":
                continue
            self.assertEqual(_target_copy(editor).get("command"), BROWSER_TARGETS[editor].get("command"), editor)


if __name__ == "__main__":
    unittest.main()
