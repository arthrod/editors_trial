"""B8 resources lane fixes (fixres round)."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
SESSION = REPO / "perf" / "runner" / "resources_session.mjs"
SCRATCH = REPO / ".scratch"


class WordcraftPortTest(unittest.TestCase):
    def test_target_copy_wordcraft_port_env_matches_url(self):
        from perf.runner.benchmark_resources import _target_copy

        target = _target_copy("wordcraft")
        port = urlsplit(target["url"]).port
        self.assertIsNotNone(port)
        env = target.get("env") or {}
        self.assertEqual(str(port), env.get("PORT"))


class LegacyHostPidTest(unittest.TestCase):
    def test_live_session_records_subprocess_server_pid(self):
        from types import SimpleNamespace

        from perf.runner.benchmark_resources import LiveSession

        SCRATCH.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(dir=SCRATCH))
        try:
            fixture = root / "fixture.docx"
            fixture.write_bytes(b"fixture")
            ctx = {
                "editor_id": "plate",
                "fixture_path": str(fixture),
                "execution_profile": "ci_contract",
                "host_class": "ci_coarse",
            }
            run = SimpleNamespace(directory=root / "run", hosts={})
            run.directory.mkdir()
            server = SimpleNamespace(pid=424242)
            proc = SimpleNamespace(
                stdin=io.StringIO(),
                stdout=io.StringIO(),
                stderr=io.StringIO(),
                poll=lambda: 0,
            )
            bridge = SimpleNamespace(request=lambda method, params: {"browserPid": 12345})
            with (
                mock.patch("perf.runner.benchmark_resources._start_server", return_value=server),
                mock.patch("perf.runner.benchmark_resources.subprocess.Popen", return_value=proc),
                mock.patch("perf.runner.benchmark_resources._Bridge", return_value=bridge),
            ):
                session = LiveSession(ctx)
                session.launch(run)
            self.assertEqual(session.server_pid, 424242)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class EditAppliedWitnessTest(unittest.TestCase):
    def test_paint_without_model_text_is_not_applied(self):
        from perf.runner.benchmark_resources import EDIT_BURST, _edit_applied

        result = {
            "applied": True,
            "witness": "paint_ink",
            "kind": "keyboard.type",
            "beforeText": "B8" * 8,
            "editorText": "B8" * 16,
            "oracle": {
                "mode": "paint_ink",
                "status": "edit_unverified",
                "model_hook": False,
                "text_delta": None,
                "trusted_keys": 16,
            },
        }
        self.assertFalse(_edit_applied(object(), EDIT_BURST, result))


class BurstEditContractTest(unittest.TestCase):
    def test_edit_burst_uses_real_keyboard_type(self):
        from perf.runner.benchmark_resources import EDIT_BURST

        self.assertEqual(EDIT_BURST["kind"], "keyboard.type")
        session_source = (REPO / "perf" / "runner" / "resources_session.mjs").read_text()
        self.assertNotIn("keyboard.insertText", session_source)

    def test_edit_witness_per_editor(self):
        from perf.runner.benchmark_resources import _edit_witness

        self.assertEqual(_edit_witness("plate"), {"mode": "dom_text"})
        self.assertEqual(_edit_witness("superdoc"), {"mode": "paint_ink"})
        self.assertEqual(_edit_witness("canvas"), {"mode": "canvas_model"})
        self.assertEqual(_edit_witness("wordcraft"), {"mode": "paint_ink"})


def _playwright_ui() -> bool:
    ui = REPO / "harness" / "ui" / "node_modules" / "playwright" / "index.mjs"
    return ui.is_file() and shutil.which("node")


def _chromium_ready() -> bool:
    root = Path.home() / "Library" / "Caches" / "ms-playwright"
    found = sorted(root.glob("chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"))
    return bool(found) and _playwright_ui()


class _Bridge:
    def __init__(self, proc, errors):
        self._proc = proc
        self._errors = errors
        self._lock = threading.Lock()
        self._next_id = 1

    def request(self, method, params=None, timeout=60):
        with self._lock:
            req_id = self._next_id
            self._next_id += 1
            payload = json.dumps({"id": req_id, "method": method, "params": params or {}})
            self._proc.stdin.write(payload + "\n")
            self._proc.stdin.flush()
        deadline = os.times()[4] + timeout
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise RuntimeError(self._errors[-3:])
            row = json.loads(line)
            if row.get("id") != req_id:
                continue
            if "error" in row:
                raise RuntimeError(row["error"])
            return row.get("result")


@unittest.skipUnless(_chromium_ready(), "playwright chromium is required")
class KeyboardOnlyBurstTest(unittest.TestCase):
    def test_keyboard_only_surface_accepts_burst(self):
        """insertText never reaches a keydown-only editor; keyboard.type must."""
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

        SCRATCH.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(dir=SCRATCH))
        try:
            (root / "corpus.docx").write_bytes(b"fake")
            (root / "index.html").write_text(
                """<!doctype html><meta charset="utf-8">
<div id="editor" tabindex="0" role="textbox" style="width:240px;height:40px;border:1px solid #888"></div>
<script>
const editor = document.getElementById('editor');
editor.addEventListener('keydown', (event) => {
  if (!event.isTrusted || event.key.length !== 1) return;
  event.preventDefault();
  editor.textContent += event.key;
});
</script>"""
            )
            class Handler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=str(root), **kwargs)

            host = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=host.serve_forever, daemon=True)
            thread.start()
            port = host.server_address[1]
            url = f"http://127.0.0.1:{port}/index.html"
            proc = subprocess.Popen(
                ["node", str(SESSION)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            errors = []
            threading.Thread(target=lambda: errors.extend(proc.stderr.readlines()), daemon=True).start()
            bridge = _Bridge(proc, errors)
            try:
                bridge.request(
                    "launch",
                    {
                        "url": url,
                        "profileDir": str(root / "profile"),
                        "corpusPath": str(root / "corpus.docx"),
                        "readySelector": "#editor",
                        "editSelector": "#editor",
                        "editWitness": {"mode": "dom_text"},
                    },
                    timeout=90,
                )
                bridge.request("load", timeout=60)
                result = bridge.request(
                    "edit",
                    {
                        "selector": "#editor",
                        "text": "B8",
                        "repetitions": 2,
                        "witness": {"mode": "dom_text"},
                    },
                    timeout=60,
                )
                self.assertEqual(result.get("kind"), "keyboard.type")
                self.assertTrue(result.get("applied"), result)
                self.assertEqual(result.get("editorText"), "B8B8")
            finally:
                try:
                    bridge.request("close", timeout=15)
                except Exception:
                    pass
                proc.terminate()
                proc.wait(timeout=10)
                host.shutdown()
        finally:
            shutil.rmtree(root, ignore_errors=True)


@unittest.skipUnless(_chromium_ready(), "playwright chromium is required")
class CanvasModelPollingTest(unittest.TestCase):
    def run_canvas_edit(self, html):
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

        SCRATCH.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(dir=SCRATCH))
        try:
            (root / "corpus.docx").write_bytes(b"fake")
            (root / "index.html").write_text(html)
            class Handler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=str(root), **kwargs)

            host = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=host.serve_forever, daemon=True)
            thread.start()
            port = host.server_address[1]
            url = f"http://127.0.0.1:{port}/index.html"
            proc = subprocess.Popen(
                ["node", str(SESSION)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            errors = []
            threading.Thread(target=lambda: errors.extend(proc.stderr.readlines()), daemon=True).start()
            bridge = _Bridge(proc, errors)
            try:
                bridge.request(
                    "launch",
                    {
                        "url": url,
                        "profileDir": str(root / "profile"),
                        "corpusPath": str(root / "corpus.docx"),
                        "readySelector": "#editor",
                        "editSelector": "#editor",
                        "editWitness": {"mode": "canvas_model"},
                    },
                    timeout=90,
                )
                bridge.request("load", timeout=60)
                params = {
                    "selector": "#editor",
                    "text": "B8",
                    "repetitions": 2,
                    "witness": {"mode": "canvas_model"},
                    "preTypeSettleMs": 300,
                    "pollBoundMs": 2000,
                    "pollIntervalMs": 50,
                }
                try:
                    prepared = bridge.request("edit_prepare", params, timeout=60)
                    bridge.request("edit_type", params, timeout=60)
                    time.sleep(0.5)
                    return bridge.request(
                        "edit_verify",
                        {**params, "prepared": prepared},
                        timeout=60,
                    )
                except RuntimeError as exc:
                    if "unknown method" not in str(exc):
                        raise
                    return bridge.request("edit", params, timeout=60)
            finally:
                try:
                    bridge.request("close", timeout=15)
                except Exception:
                    pass
                proc.terminate()
                proc.wait(timeout=10)
                host.shutdown()
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_canvas_model_polls_until_typed_tokens_appear(self):
        html = """<!doctype html><meta charset="utf-8">
<div id="editor" tabindex="0"><canvas width="320" height="80"></canvas></div>
<script>
let modelText = '';
window.__CANVAS_EDITOR_INSTANCE__ = {
  command: { getValue: () => ({ data: { main: [{ value: modelText }] } }) },
};
const editor = document.getElementById('editor');
editor.addEventListener('keydown', (event) => {
  if (!event.isTrusted || event.key.length !== 1) return;
  event.preventDefault();
  setTimeout(() => { modelText = 'B8B8'; }, 750);
});
</script>"""
        result = self.run_canvas_edit(html)
        self.assertTrue(result.get("applied"), result)
        oracle = result.get("oracle") or {}
        self.assertEqual(oracle.get("status"), "verified")
        self.assertEqual(oracle.get("mode"), "canvas_model")
        self.assertEqual(oracle.get("text_delta"), 2)
        self.assertGreaterEqual(oracle.get("poll_attempts") or 0, 2)
        self.assertEqual(oracle.get("poll_bound_ms"), 2000)

    def test_canvas_model_waits_for_focus_settle_before_typing(self):
        html = """<!doctype html><meta charset="utf-8">
<div id="editor" tabindex="0"><canvas width="320" height="80"></canvas></div>
<script>
let modelText = '';
let focusedAt = 0;
window.__CANVAS_EDITOR_INSTANCE__ = {
  command: { getValue: () => ({ data: { main: [{ value: modelText }] } }) },
};
const editor = document.getElementById('editor');
editor.addEventListener('focus', () => { focusedAt = performance.now(); });
editor.addEventListener('keydown', (event) => {
  if (!event.isTrusted || event.key.length !== 1) return;
  event.preventDefault();
  modelText = performance.now() - focusedAt >= 250 ? 'B8B8' : '';
});
</script>"""
        result = self.run_canvas_edit(html)
        self.assertTrue(result.get("applied"), result)
        oracle = result.get("oracle") or {}
        self.assertEqual(oracle.get("status"), "verified")
        self.assertEqual(oracle.get("text_delta"), 2)

    def test_canvas_model_prefers_perf_model_hook_when_present(self):
        html = """<!doctype html><meta charset="utf-8">
<div id="editor" tabindex="0"><canvas width="320" height="80"></canvas></div>
<script>
let modelText = '';
window.__PERF_MODEL_TEXT__ = () => modelText;
const editor = document.getElementById('editor');
editor.addEventListener('keydown', (event) => {
  if (!event.isTrusted || event.key.length !== 1) return;
  event.preventDefault();
  setTimeout(() => { modelText = 'B8B8'; }, 100);
});
</script>"""
        result = self.run_canvas_edit(html)
        self.assertTrue(result.get("applied"), result)
        oracle = result.get("oracle") or {}
        self.assertEqual(oracle.get("status"), "verified")
        self.assertEqual(oracle.get("mode"), "perf_model")
        self.assertEqual(oracle.get("text_delta"), 2)
        self.assertTrue(oracle.get("model_hook"))

    def test_canvas_model_hook_error_is_recorded_as_unverified(self):
        html = """<!doctype html><meta charset="utf-8">
<div id="editor" tabindex="0"><canvas width="320" height="80"></canvas></div>
<script>
window.__PERF_MODEL_TEXT__ = () => { throw new Error('model hook failed'); };
</script>"""
        result = self.run_canvas_edit(html)
        self.assertFalse(result.get("applied"), result)
        oracle = result.get("oracle") or {}
        self.assertEqual(oracle.get("status"), "edit_unverified")
        self.assertEqual(oracle.get("reason"), "model_hook_error")
        self.assertTrue(oracle.get("model_hook"))

    def test_canvas_model_poll_is_bounded(self):
        html = """<!doctype html><meta charset="utf-8">
<div id="editor" tabindex="0"><canvas width="320" height="80"></canvas></div>
<script>
let modelText = '';
window.__CANVAS_EDITOR_INSTANCE__ = {
  command: { getValue: () => ({ data: { main: [{ value: modelText }] } }) },
};
</script>"""
        result = self.run_canvas_edit(html)
        self.assertFalse(result.get("applied"), result)
        oracle = result.get("oracle") or {}
        self.assertEqual(oracle.get("status"), "edit_not_applied")
        self.assertEqual(oracle.get("reason"), "poll_timeout")
        self.assertEqual(oracle.get("poll_bound_ms"), 2000)
        self.assertGreaterEqual(oracle.get("poll_elapsed_ms") or 0, 1800)
        self.assertLess(oracle.get("poll_elapsed_ms") or 0, 3000)


if __name__ == "__main__":
    unittest.main()
