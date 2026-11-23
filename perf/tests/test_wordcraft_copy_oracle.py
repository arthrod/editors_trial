"""WordCraft's select all + copy oracle stays out of timed work (#196, #197).

The copy read clicks WordCraft's canvas, selects the whole document and puts it
on WordCraft's own clipboard. Where timed work follows in the same page (C04 and
C07 in the input lane, C14's frame witness), the surface reads as it did before
#196: no text, no keystroke. C08 pastes on a fresh load, because WordCraft pastes
its own clipboard with the system clipboard's text (measured: 5,720 characters
for a 1,500-character block after the oracle's copy; 1,500 on a fresh load).
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "perf" / "runner"
EDIT_SURFACE = RUNNER / "edit_surface.mjs"


def node(body: str) -> dict:
    script = f"""
import assert from 'node:assert/strict';
const mod = await import({json.dumps(str(EDIT_SURFACE))});
{body}
"""
    proc = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


class NoCopyRead(unittest.TestCase):
    def test_no_copy_reads_as_the_old_unavailable_surface_and_presses_nothing(self):
        payload = node(
            """
const calls = [];
const page = {
  evaluate: async (fn, arg) => { calls.push(['evaluate', arg]); return fn(arg); },
  keyboard: { press: async (k) => calls.push(['press', k]) },
  mouse: { click: async () => calls.push(['click']) },
  context: () => ({ grantPermissions: async () => calls.push(['grant']) }),
  url: () => 'http://127.0.0.1:1/',
};
const read = await mod.readEditorDocumentText(page, 'wordcraft', { noCopy: true });
process.stdout.write(JSON.stringify({ read, calls }));
"""
        )
        self.assertEqual(payload["read"]["oracle"], "absent")
        self.assertEqual(payload["read"]["text"], "")
        self.assertEqual([c[0] for c in payload["calls"]], ["evaluate"])

    def test_without_no_copy_wordcraft_reads_through_its_copy(self):
        payload = node(
            """
const calls = [];
let clip = '';
const page = {
  evaluate: async (fn, arg) => {
    const src = String(fn);
    if (src.includes('writeText')) { clip = arg; return; }
    if (src.includes('readText')) return clip === arg ? clip : clip;
    return fn(arg);
  },
  keyboard: { press: async (k) => { calls.push(k); if (k.endsWith('+C')) clip = 'THE WHOLE DOCUMENT'; } },
  mouse: { click: async () => {} },
  locator: () => ({ count: async () => 1,
                    first: () => ({ scrollIntoViewIfNeeded: async () => {},
                                    boundingBox: async () => ({ x: 0, y: 0, width: 10, height: 10 }) }) }),
  waitForTimeout: async () => {},
  context: () => ({ grantPermissions: async () => {} }),
  url: () => 'http://127.0.0.1:1/',
};
const read = await mod.readEditorDocumentText(page, 'wordcraft', { copyWaitMs: 500 });
process.stdout.write(JSON.stringify({ read, calls }));
"""
        )
        self.assertEqual(payload["read"]["source"], "select_all_copy")
        self.assertIn("ControlOrMeta+A", payload["calls"])
        self.assertIn("ControlOrMeta+C", payload["calls"])


class CopyStaysOutOfTimedWork(unittest.TestCase):
    def test_the_input_lane_ready_does_no_copy_read(self):
        src = (RUNNER / "warm_cold_browser.mjs").read_text()
        session = src[src.index("async function runCriteriaSession"):src.index("async function coldOnlyFreshContext")]
        ready_calls = re.findall(r"waitForReady\(page[^\n]*\)", session)
        self.assertEqual(len(ready_calls), 1, ready_calls)
        self.assertIn("noCopy: true", ready_calls[0])

    def test_c14_scale_mode_snapshot_does_no_copy_read(self):
        src = (RUNNER / "document_probe.mjs").read_text()
        scale = src[src.index("async function runScale"):]
        first = scale[: scale.index("stateSnapshot(") + 60]
        self.assertIn("stateSnapshot(ctx.page, { noCopy: true })", first)

    def test_c08_pastes_on_a_fresh_load_after_the_before_read(self):
        src = (RUNNER / "criteria_input.mjs").read_text()
        body = src[src.index("async function measureBulkInsertCopyOracle"):src.index("async function measureUndo(")]
        before = body.index("readCopyOracleText(page, options)")
        reload = body.index("await options.reloadPage()")
        paste = body.index("+V`)")
        self.assertLess(before, reload)
        self.assertLess(reload, paste)

    def test_c09_undo_runs_on_a_caret(self):
        src = (RUNNER / "criteria_input.mjs").read_text()
        body = src[src.index("async function measureUndoCopyOracle"):src.index("async function measureBulkInsertCopyOracle")]
        typed = body.index("const typed = await readCopyOracleText")
        collapse = body.index("await collapseCopySelection(page, point)", typed)
        undo = body.index("+Z`)")
        self.assertLess(collapse, undo)

    def test_only_wordcraft_is_a_copy_surface(self):
        payload = node(
            """
const ids = ['plate','docxodus','superdoc','genoffice','eigenpal','folio','canvas','docen','wordcraft','apryse'];
process.stdout.write(JSON.stringify(ids.filter((id) => mod.documentTextSurface(id).kind === 'select_all_copy')));
"""
        )
        self.assertEqual(payload, ["wordcraft"])


class ScrollAdapter(unittest.TestCase):
    def test_wordcraft_scrolls_its_overlay_and_the_witness_watches_its_canvas(self):
        from perf.runner import adversarial_c10_scroll as c10

        # E2: OpenDoc names its own page scroller (test_e2_opendoc_lanes).
        self.assertEqual(c10.HOST_SCROLL_CONTAINERS, {"wordcraft": "#wc-scroll", "opendoc": "#viewport"})
        self.assertEqual(c10.adapter_selectors("wordcraft"),
                         {"container": "#wc-scroll", "document": "#wordcraft_canvas"})
        for editor in ("plate", "docxodus", "superdoc", "genoffice", "canvas", "docen", "eigenpal", "folio"):
            self.assertEqual(c10.adapter_selectors(editor), {"container": None, "document": None}, editor)

    def test_a_witness_off_the_adapters_document_is_refused(self):
        from perf.runner import adversarial_c10_scroll as c10

        doc = {"x": 0, "y": 0, "width": 1000, "height": 800}
        sample = {"container": {"container_rule": "adapter", "document_rect": doc,
                                "region_rect": {"x": 0, "y": 0, "width": 1280, "height": 900}}}
        self.assertTrue(c10._rects_within(c10._rect_of(doc), c10._rect_of(doc)))
        self.assertFalse(c10._rects_within(c10._rect_of(sample["container"]["region_rect"]), c10._rect_of(doc)))


if __name__ == "__main__":
    unittest.main()


class FlagBurst(unittest.TestCase):
    """With its content verified (#196), WordCraft's C05/C06 reach the glyph rule (r3lanes4 #1)."""

    @staticmethod
    def payload(burst_adapter):
        first = {"mechanism": "keydown", "edit_confirmation": {"adapter": {"adapter": "flag", "confirmed": True,
                                                                          "before_count": 0, "after_count": 1}}}
        burst = [{"mechanism": "keydown", "edit_confirmation": {"adapter": burst_adapter}} for _ in range(3)]
        return {"pairs": [{"cold": {**first, "burst": burst}, "warm": {**first, "burst": burst}}]}

    def test_a_flag_that_already_rose_does_not_unconfirm_the_burst(self):
        from perf.runner import benchmark_warm_cold as bw

        glyph = bw._glyph_geometry_refusal(self.payload(
            {"adapter": "flag", "confirmed": False, "before_count": 1, "after_count": 1,
             "reason": "modified_before_edit"}))
        self.assertIsNotNone(glyph)
        self.assertEqual(glyph["reason"], bw.NO_GLYPH_GEOMETRY_REASON)

    def test_an_unconfirmed_model_edit_still_keeps_the_failure(self):
        from perf.runner import benchmark_warm_cold as bw

        payload = self.payload({"adapter": "model", "confirmed": False})
        self.assertIsNone(bw._glyph_geometry_refusal(payload))

    def test_a_flag_that_never_rose_still_keeps_the_failure(self):
        from perf.runner import benchmark_warm_cold as bw

        never = {"adapter": "flag", "confirmed": False, "before_count": 0, "after_count": 0}
        payload = {"pairs": [{"cold": {"mechanism": "keydown", "edit_confirmation": {"adapter": never}}}]}
        self.assertIsNone(bw._glyph_geometry_refusal(payload))
