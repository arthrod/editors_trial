"""The shared edit adapter (#155.1) and the resources lane's use of it.

Browser-backed: a small page stands in for each kind of editor surface.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from perf.runner.benchmark_resources import SESSION, _Bridge, collect_phases
from perf.tests.test_b8_fixres import SCRATCH, _chromium_ready
from perf.tests.test_resources import (
    EDIT_BURST, SHORT_QUIESCENCE, ManualClock, PhaseSession, World, make_sampler,
)

DOM_PAGE = """<!doctype html><meta charset="utf-8"><body style="margin:0">
<div id="editor">
  <div class="superdoc-page">
    <div class="superdoc-page-header"><span class="superdoc-line">Header text that must never take the caret</span></div>
    <div id="body" contenteditable="true" style="margin-top:40px">
      <p class="superdoc-line">First body paragraph of the document under test.</p>
      <p class="superdoc-line">Second body paragraph of the document under test.</p>
    </div>
  </div>
</div>
<script>
const PARA1 = "First body paragraph of the document under test.";
const PARA2 = "Second body paragraph of the document under test.";
let landed = "";
window.__SUPERDOC_E2E__ = {
  activeEditor: { doc: { getText: async () => PARA1 + landed + String.fromCharCode(10) + PARA2 } }
};
LATE
</script>
</body>"""

FLAG_PAGE = """<!doctype html><meta charset="utf-8"><body style="margin:0">
<canvas id="wordcraft_canvas" tabindex="0" width="600" height="400"></canvas>
<script>
window.__WORDCRAFT_HOST__ = { titles: [{ t: 1, title: 'corpus - WordCraft' }] };
document.getElementById('wordcraft_canvas').addEventListener('keydown', () => {
  DIRTY
});
</script></body>"""

ERROR_PAGE = """<!doctype html><meta charset="utf-8"><body><div id="editor"></div>
<script>setTimeout(() => { window.__DOCX_ERROR__ = 'TypeError: computeRowColInfo'; }, 200);</script></body>"""


@unittest.skipUnless(_chromium_ready(), "playwright chromium is required")
class EditSurfaceTest(unittest.TestCase):
    def session(self, html, launch):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(dir=SCRATCH))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "corpus.docx").write_bytes(b"fake")
        (root / "index.html").write_text(html)

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(root), **kwargs)

            def log_message(self, *args):
                pass

        host = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=host.serve_forever, daemon=True).start()
        self.addCleanup(host.shutdown)
        proc = subprocess.Popen(["node", str(SESSION)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        errors = []
        threading.Thread(target=lambda: errors.extend(proc.stderr.readlines()), daemon=True).start()
        bridge = _Bridge(proc, errors)

        def close():
            try:
                bridge.request("close", timeout=15)
            except Exception:
                pass
            proc.terminate()
            proc.wait(timeout=10)

        self.addCleanup(close)
        bridge.request("launch", {
            "url": "http://127.0.0.1:%d/index.html" % host.server_address[1],
            "profileDir": str(root / "profile"),
            "corpusPath": str(root / "corpus.docx"),
            **launch,
        }, timeout=90)
        return bridge

    def burst(self, bridge, editor_id, selector):
        params = {"editorId": editor_id, "selector": selector, "text": "B8", "repetitions": 2,
                  "preTypeSettleMs": 100, "pollBoundMs": 3000, "pollIntervalMs": 50}
        prepared = bridge.request("edit_prepare", params, timeout=60)
        bridge.request("edit_type", params, timeout=60)
        return prepared, bridge.request("edit_verify", {**params, "prepared": prepared}, timeout=60)

    def test_caret_goes_to_the_first_body_line_never_the_header(self):
        # The click still uses the painted body line. The burst oracle is the
        # model (d82b9e0c): paint is not evidence that the keys landed.
        mirror = """document.getElementById('body').addEventListener('beforeinput', (e) => {
          if (e.data) landed += e.data;
        });"""
        bridge = self.session(DOM_PAGE.replace("LATE", mirror), {"readySelector": "#editor", "editorId": "superdoc"})
        bridge.request("load", timeout=60)
        bridge.request("enter_edit_mode", timeout=60)
        prepared, result = self.burst(bridge, "superdoc", "#editor")
        self.assertEqual(prepared["line"], "First body paragraph of the document under test.")
        self.assertNotIn("Header text", prepared["line"])
        oracle = result["oracle"]
        self.assertEqual(oracle["status"], "verified", oracle)
        self.assertEqual(oracle["mode"], "editor_model_text")
        self.assertEqual(oracle["text_delta"], 2)
        self.assertIn("First body paragraph of the document under test.B8B8", result["editorText"])
        self.assertIn("Second body paragraph of the document under test.", result["editorText"])
        self.assertNotIn("Header text", result["editorText"])

    def test_a_burst_painted_late_is_still_verified(self):
        # Paint and the model both gain the burst 600ms after the key. The
        # oracle polls the model, so a late landing is still verified.
        late = """document.getElementById('body').addEventListener('beforeinput', (e) => {
          e.preventDefault(); const d = e.data; setTimeout(() => {
            const p = document.querySelector('#body p'); p.textContent = p.textContent + d;
            landed += d; }, 600); });"""
        bridge = self.session(DOM_PAGE.replace("LATE", late), {"readySelector": "#editor", "editorId": "superdoc"})
        bridge.request("load", timeout=60)
        _, result = self.burst(bridge, "superdoc", "#editor")
        self.assertEqual(result["oracle"]["status"], "verified", result["oracle"])
        self.assertEqual(result["oracle"]["mode"], "editor_model_text")
        self.assertGreaterEqual(result["oracle"]["poll_attempts"], 2)
        self.assertIn("B8B8", result["editorText"])

    def test_modified_flag_verifies_a_canvas_editor_without_text(self):
        dirty = "window.__WORDCRAFT_HOST__.titles.push({ t: 2, title: 'corpus \u2022 - WordCraft' });"
        bridge = self.session(FLAG_PAGE.replace("DIRTY", dirty), {"readySelector": "#wordcraft_canvas", "editorId": "wordcraft"})
        bridge.request("load", timeout=60)
        _, result = self.burst(bridge, "wordcraft", "#wordcraft_canvas")
        self.assertEqual(result["oracle"]["status"], "verified", result["oracle"])
        self.assertEqual(result["oracle"]["mode"], "editor_modified_flag")
        self.assertIn("\u2022", result["oracle"]["scope_after"])

    def test_keys_that_do_not_modify_the_document_are_not_an_edit(self):
        bridge = self.session(FLAG_PAGE.replace("DIRTY", ""), {"readySelector": "#wordcraft_canvas", "editorId": "wordcraft"})
        bridge.request("load", timeout=60)
        _, result = self.burst(bridge, "wordcraft", "#wordcraft_canvas")
        self.assertEqual(result["oracle"]["status"], "edit_not_applied")
        self.assertFalse(result["applied"])

    def test_an_editor_that_throws_on_load_fails_fast_with_its_own_error(self):
        bridge = self.session(ERROR_PAGE, {"readyJs": "window.__NEVER__ === true",
                                           "errorJs": "window.__DOCX_ERROR__", "editorId": "canvas"})
        started = time.monotonic()
        with self.assertRaises(RuntimeError) as caught:
            bridge.request("load", timeout=60)
        self.assertLess(time.monotonic() - started, 20)
        self.assertIn("editor_load_failed", str(caught.exception))
        self.assertIn("computeRowColInfo", str(caught.exception))


class LoadFailureIsAFinding(unittest.TestCase):
    def test_editor_load_failure_is_a_named_refusal_with_the_editors_error(self):
        world = World()

        class Crashing(PhaseSession):
            def load(self):
                raise RuntimeError("Error: editor_load_failed: TypeError: computeRowColInfo")

        clock = ManualClock(world, disturb=False)
        trial = collect_phases(
            make_sampler(world, clock=clock), Crashing(world, mode="measure"), clock,
            quiescence=SHORT_QUIESCENCE, edit_burst=EDIT_BURST, editor_id="canvas",
            workload_id="complex-corpus",
            workload_meta={"sha256": "c" * 64, "byte_size": 10, "paragraph_count": 1, "word_count": 1},
            execution_profile="ci_broad", host_class="ci_coarse",
        )
        self.assertEqual(trial["outcome"], "refused")
        self.assertEqual(trial["refusal_code"], "editor_load_failed")
        self.assertIn("computeRowColInfo", trial["editor_error"])


class EditorCrashIsAFinding(unittest.TestCase):
    def crash(self, method):
        world = World()

        class Crashing(PhaseSession):
            pass

        def boom(self, *args):
            raise RuntimeError("keyboard.type: Target crashed \n    at typeResourceBurst (x.mjs:1:1)")

        setattr(Crashing, method, boom)
        clock = ManualClock(world, disturb=False)
        return collect_phases(
            make_sampler(world, clock=clock), Crashing(world, mode="measure"), clock,
            quiescence=SHORT_QUIESCENCE, edit_burst=EDIT_BURST, editor_id="canvas",
            workload_id="prose-250kw",
            workload_meta={"sha256": "c" * 64, "byte_size": 10, "paragraph_count": 1, "word_count": 1},
            execution_profile="ci_broad", host_class="ci_coarse",
        )

    def test_a_tab_that_dies_while_typing_is_the_editors_result(self):
        # canvas-editor at 250k words: the renderer dies on the first keys.
        trial = self.crash("type_edit")
        self.assertEqual(trial["outcome"], "refused")
        self.assertEqual(trial["refusal_code"], "editor_crashed")
        self.assertEqual(trial["editor_error"], "renderer crashed during edit")
        self.assertEqual(trial["edit_cpu_publication"], "withheld")

    def test_a_tab_that_dies_while_opening_is_the_editors_result(self):
        trial = self.crash("load")
        self.assertEqual(trial["refusal_code"], "editor_crashed")
        self.assertEqual(trial["editor_error"], "renderer crashed during load")

    def test_any_other_harness_error_still_raises(self):
        world = World()

        class Broken(PhaseSession):
            def type_edit(self, burst):
                raise RuntimeError("bridge closed")

        clock = ManualClock(world, disturb=False)
        with self.assertRaises(RuntimeError):
            collect_phases(
                make_sampler(world, clock=clock), Broken(world, mode="measure"), clock,
                quiescence=SHORT_QUIESCENCE, edit_burst=EDIT_BURST, editor_id="canvas",
                workload_id="prose-250kw",
                workload_meta={"sha256": "c" * 64, "byte_size": 10, "paragraph_count": 1, "word_count": 1},
                execution_profile="ci_broad", host_class="ci_coarse",
            )


if __name__ == "__main__":
    unittest.main()
