"""OpenDoc's engine fetcher: the pinned build only, from a local copy or the site.

Run: python3 -m unittest build.test_opendoc_engine (from the repo root)
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "harness" / "ui" / "opendoc" / "fetch_engine.py"


def load():
    spec = importlib.util.spec_from_file_location("fetch_engine_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FetchEngine(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.checkout = self.base / "opendoc"
        (self.checkout / "webapp").mkdir(parents=True)
        git = ["git", "-C", str(self.checkout), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
        subprocess.run(["git", "-C", str(self.checkout), "init", "-q"], check=True)
        subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "pin"], check=True)
        head = subprocess.run(["git", "-C", str(self.checkout), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        self.m = load()
        self.m.PIN = head
        self.files = {"casual_doc_wasm.js": b"js build", "casual_doc_wasm_bg.wasm": b"\0asm build"}
        self.m.FILES = {k: hashlib.sha256(v).hexdigest() for k, v in self.files.items()}
        env = mock.patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("OPENDOC_ENGINE_DIR", None)

    def run_main(self):
        with mock.patch("sys.argv", ["fetch_engine.py", str(self.checkout)]):
            return self.m.main()

    def test_the_pinned_build_is_taken_from_the_local_copy_without_the_site(self):
        copy = self.base / "copy"
        copy.mkdir()
        for name, data in self.files.items():
            (copy / name).write_bytes(data)
        os.environ["OPENDOC_ENGINE_DIR"] = str(copy)
        with mock.patch.object(self.m.urllib.request, "urlopen", side_effect=AssertionError("the site was asked")):
            self.assertEqual(self.run_main(), 0)
        for name, data in self.files.items():
            self.assertEqual((self.checkout / "webapp" / "pkg" / name).read_bytes(), data)

    def test_a_local_copy_of_another_build_is_not_taken_and_the_site_is_checked_as_before(self):
        copy = self.base / "copy"
        copy.mkdir()
        for name in self.files:
            (copy / name).write_bytes(b"another build")
        os.environ["OPENDOC_ENGINE_DIR"] = str(copy)
        with mock.patch.object(self.m.urllib.request, "urlopen", return_value=io.BytesIO(b"the site moved on")):
            with self.assertRaisesRegex(SystemExit, "not the pinned build"):
                self.run_main()
        self.assertFalse((self.checkout / "webapp" / "pkg" / "casual_doc_wasm.js").exists())

    def test_without_a_local_copy_the_site_build_is_taken_when_its_hash_is_the_pin(self):
        served = iter(self.files.values())
        with mock.patch.object(self.m.urllib.request, "urlopen", side_effect=lambda *a, **k: io.BytesIO(next(served))):
            self.assertEqual(self.run_main(), 0)


if __name__ == "__main__":
    unittest.main()
