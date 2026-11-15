"""Non-editable browser targets must not use the contenteditable usable default.

Apryse's #pageContainer1 lives inside <apryse-webviewer>'s shadow root and is
never contenteditable. document.querySelector plus isContentEditable is false
forever, so warm/cold and C10 stall to the usable-wait bound. Canvas, shadow,
model, and flag targets from the runners' browser lists need their own signal.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EDIT_SURFACE = REPO / "perf" / "runner" / "edit_surface.mjs"
WARM_COLD_BROWSER = REPO / "perf" / "runner" / "warm_cold_browser.mjs"
RESOURCE_BURST = REPO / "perf" / "runner" / "resource_burst_edit.mjs"
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
PROBE = REPO / "perf" / "tests" / "e2_apryse_usable_probe.mjs"

# The bare default usableExpression returns for an editor with no signal.
_DEFAULT_USABLE = re.compile(
    r'^\(\(\) => \{ const el = document\.querySelector\(.+\); '
    r'return !!\(el && el\.isContentEditable && el\.getBoundingClientRect\(\)\.height > 0\); \}\)\(\)$'
)
_CANVAS_ELEMENT = re.compile(r'(?:^|[#.\s>])canvas(?:\b|$)')

# What the runners already publish as Apryse's own ready flag.
_APRYSE_READY = "window.__aprysePerf && window.__aprysePerf.state === 'rendered'"


def _node() -> str | None:
    return shutil.which("node")


def _non_editable_class(editor_id: str, browser: dict, document: dict) -> str | None:
    """canvas, shadow, model, or flag when the target rows say a contenteditable
    probe cannot see the surface. None means the default expression is legal.
    """
    fields = " ".join(
        str(row.get(key) or "")
        for row in (browser, document)
        for key in ("edit_selector", "doc_selector", "document_selector", "ready_selector")
    )
    signal = str(document.get("usable_signal") or "")
    if "apryse-webviewer" in fields or signal == "shadow_text":
        return "shadow"
    if "docen-document" in fields:
        return "shadow"
    if signal == "canvas_pixel" or _CANVAS_ELEMENT.search(fields):
        return "canvas"
    if "_canvas" in fields:
        return "flag" if editor_id == "wordcraft" else "canvas"
    return None


class NonEditableUsableSignalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _node() is None:
            raise unittest.SkipTest("node is not on PATH")
        from perf.runner.benchmark_document import DOCUMENT_TARGETS
        from perf.runner.benchmark_warm_cold import BROWSER_TARGETS

        cls.browser_targets = BROWSER_TARGETS
        cls.document_targets = DOCUMENT_TARGETS

    def _expressions(self, selectors: dict[str, str]) -> dict:
        script = (
            "import assert from 'node:assert/strict';\n"
            "const mod = await import(%s);\n"
            "const selectors = JSON.parse(process.argv[1]);\n"
            "const expressions = {};\n"
            "for (const [id, sel] of Object.entries(selectors)) {\n"
            "  expressions[id] = mod.usableExpression(id, sel);\n"
            "}\n"
            "const caret = (id) => (typeof mod.hasCaretAdapter === 'function'\n"
            "  ? mod.hasCaretAdapter(id) : null);\n"
            "console.log(JSON.stringify({\n"
            "  expressions,\n"
            "  hasCaretAdapter: typeof mod.hasCaretAdapter,\n"
            "  caret: { apryse: caret('apryse'), folio: caret('folio'), canvas: caret('canvas'), plate: caret('plate') },\n"
            "  apryse: mod.EDIT_SURFACES.apryse || null,\n"
            "}));\n"
        ) % json.dumps(EDIT_SURFACE.as_uri())
        proc = subprocess.run(
            [_node(), "--input-type=module", "-e", script, json.dumps(selectors)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def test_noneditable_browser_targets_have_an_explicit_usable_signal(self):
        editors = sorted(set(self.browser_targets) | set(self.document_targets))
        classified = {}
        selectors = {}
        for editor_id in editors:
            browser = self.browser_targets.get(editor_id) or {}
            document = self.document_targets.get(editor_id) or {}
            kind = _non_editable_class(editor_id, browser, document)
            if kind is None:
                continue
            self.assertIn(kind, {"canvas", "shadow", "model", "flag"}, editor_id)
            classified[editor_id] = kind
            selectors[editor_id] = browser.get("edit_selector") or document.get("edit_selector") or ""
        self.assertEqual(
            classified,
            {"apryse": "shadow", "canvas": "canvas", "docen": "shadow", "wordcraft": "flag"},
            classified,
        )
        # The two runner lists name the same ready flag. The usable expression
        # must be that string, not a paraphrase.
        self.assertEqual(self.browser_targets["apryse"]["ready_js"], _APRYSE_READY)
        self.assertEqual(self.document_targets["apryse"]["ready_js"], _APRYSE_READY)

        payload = self._expressions(selectors)
        for editor_id, kind in classified.items():
            expr = payload["expressions"][editor_id]
            self.assertIsNotNone(expr, editor_id)
            self.assertNotRegex(
                expr,
                _DEFAULT_USABLE,
                "%s is %s and must not fall through to the contenteditable default: %s"
                % (editor_id, kind, expr),
            )
        self.assertEqual(payload["expressions"]["apryse"], _APRYSE_READY)
        surface = payload["apryse"]
        self.assertIsInstance(surface, dict)
        self.assertEqual(surface.get("kind"), "dom")
        self.assertIsNone(surface.get("root"))
        self.assertNotIn("model", surface)
        self.assertNotIn("block", surface)
        self.assertNotIn("enter", surface)
        self.assertNotIn("hidden", surface)
        self.assertNotIn("shadow", surface)
        # The entry is a usable signal only. Caret placement stays on the
        # shadow-piercing locator; FIND_TEXT_LINE cannot see #pageContainer1.
        self.assertEqual(payload["hasCaretAdapter"], "function")
        self.assertIs(payload["caret"]["apryse"], False)
        self.assertIs(payload["caret"]["folio"], True)
        self.assertIs(payload["caret"]["canvas"], True)
        self.assertIs(payload["caret"]["plate"], True)
        warm = WARM_COLD_BROWSER.read_text()
        burst = RESOURCE_BURST.read_text()
        self.assertIn("hasCaretAdapter(editorId)", warm)
        self.assertNotIn("if (editorId && EDIT_SURFACES[editorId])", warm)
        self.assertIn("hasCaretAdapter(opts.editorId)", burst)
        self.assertNotIn("if (EDIT_SURFACES[opts.editorId]) return prepareOnSurface", burst)


class ApryseShadowUsableTests(unittest.TestCase):
    server = None
    base = ""

    @classmethod
    def setUpClass(cls):
        if _node() is None:
            raise unittest.SkipTest("node is not on PATH")
        from perf.runner.browser_hosts import StaticHost

        cls.server = StaticHost(HOSTS)
        cls.base = cls.server.url

    @classmethod
    def tearDownClass(cls):
        if cls.server is not None:
            cls.server.stop()
            cls.server = None

    def probe(self, query: str, *, wait_ms: str) -> dict:
        proc = subprocess.run(
            [_node(), str(PROBE), "%s/e2_apryse_usable.html%s" % (self.base, query)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO),
            env={**os.environ, "PERF_USABLE_WAIT_MS": wait_ms},
        )
        self.assertEqual(
            proc.returncode,
            0,
            "apryse usable probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr),
        )
        return json.loads(proc.stdout)

    def test_booting_shadow_page_is_not_usable(self):
        payload = self.probe("?never=1", wait_ms="800")
        self.assertIs(payload["immediate"], False)
        self.assertIs(payload["shadowEditable"], False)
        self.assertIs(payload["lightDomDefault"], False)
        self.assertEqual(payload["refusal"], "usable_signal_not_observed")

    def test_rendered_flag_makes_the_shadow_page_usable(self):
        payload = self.probe("?delay=400", wait_ms="3000")
        self.assertIs(payload["immediate"], False, payload)
        self.assertIs(payload["shadowEditable"], False, payload)
        self.assertIs(payload["lightDomDefault"], False, payload)
        self.assertIsNone(payload["refusal"], payload)
        self.assertEqual(payload["expr"], _APRYSE_READY)


if __name__ == "__main__":
    unittest.main()
