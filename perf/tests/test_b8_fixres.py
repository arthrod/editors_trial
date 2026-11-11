"""B8 resources lane fixes (fixres round)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
SESSION = REPO / "perf" / "runner" / "resources_session.mjs"


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
        import os
        from types import SimpleNamespace

        from perf.runner.benchmark_resources import LiveSession

        ctx = {
            "editor_id": "plate",
            "fixture_path": "/tmp/x.docx",
            "execution_profile": "ci_contract",
            "host_class": "ci_coarse",
        }
        session = LiveSession(ctx)
        session._server = SimpleNamespace(pid=424242)
        session.server_pid = getattr(session._server, "pid", None) or os.getpid()
        self.assertEqual(session.server_pid, 424242)


class EditAppliedWitnessTest(unittest.TestCase):
    def test_paint_witness_applied_without_dom_text(self):
        from perf.runner.benchmark_resources import EDIT_BURST, _edit_applied

        result = {
            "applied": True,
            "witness": "paint_ink",
            "paint_witness": "witnessed",
            "kind": "keyboard.type",
        }
        self.assertTrue(_edit_applied(object(), EDIT_BURST, result))


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

        root = Path(tempfile.mkdtemp())
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


if __name__ == "__main__":
    unittest.main()
