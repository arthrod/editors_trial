#!/usr/bin/env python3
"""The UI hosts added on 2026-11-21 (react-docx, BetterOffice, OpenDoc, OnlyOffice,
Nutrient): every editor the capture runs has a recipe, each host pins exact
versions, the shared static server stays inside its folders, and OnlyOffice's
control documents remove exactly the construct they are named for."""
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "harness" / "ui"
CAPTURE = (ROOT / "build" / "capture_ui.sh").read_text()
NEW = ("reactdocx", "betteroffice", "opendoc", "onlyoffice", "nutrient")


class CaptureRecipes(unittest.TestCase):
    def test_every_editor_in_the_default_run_has_a_recipe(self):
        listed = re.search(r"^ALL=\((.*?)\)", CAPTURE, re.S | re.M).group(1).split()
        recipes = set(re.findall(r"^cap_(\w+)\(\)", CAPTURE, re.M))
        self.assertEqual(sorted(set(listed) - recipes), [])
        self.assertEqual(sorted(recipes - set(listed)), [])
        for slug in NEW:
            self.assertIn(slug, listed)

    def test_every_probe_a_recipe_names_exists(self):
        for probe in set(re.findall(r"--probe (\S+\.mjs)", CAPTURE)):
            self.assertTrue((UI / probe).is_file(), probe)

    def test_the_new_recipes_start_nothing_with_npx(self):
        # pnpm for the hosts added from 2026-11-21 on; the older recipes keep their commands.
        tail = CAPTURE[CAPTURE.index("cap_reactdocx()"):]
        self.assertNotIn("npx ", tail)


class Pins(unittest.TestCase):
    def test_package_hosts_pin_exact_versions(self):
        want = {
            "react-docx": {"@extend-ai/react-docx": "0.15.0"},
            "betteroffice": {"@betteroffice/docx": "0.5.1", "@betteroffice/docx-react": "0.5.1",
                             "@betteroffice/fonts": "0.4.2"},
            "univer": {"@univerjs/presets": "1.5.2", "@univerjs/preset-docs-core": "1.5.2"},
        }
        for host, pins in want.items():
            deps = json.loads((UI / host / "package.json").read_text())["dependencies"]
            for name, version in pins.items():
                self.assertEqual(deps.get(name), version, f"{host}: {name}")
            self.assertTrue((UI / host / "pnpm-lock.yaml").is_file(), host)
            self.assertIn("minimumReleaseAge: 7200", (UI / host / "pnpm-workspace.yaml").read_text(), host)

    def test_archive_and_commit_pins_are_content_addressed(self):
        fetch = (UI / "onlyoffice" / "fetch.py").read_text()
        self.assertEqual(len(re.findall(r'"sha512": "[0-9a-f]{128}"', fetch)), 2)
        self.assertEqual(re.findall(r'"tag": "(v[^"]+)"', fetch), ["v9.3.2+3", "v9.3.2+4"])
        engine = (UI / "opendoc" / "fetch_engine.py").read_text()
        self.assertRegex(engine, r'PIN = "[0-9a-f]{40}"')
        self.assertEqual(len(re.findall(r'": "[0-9a-f]{64}"', engine)), 2)

    def test_nutrient_is_loaded_without_a_key(self):
        main = (UI / "nutrient" / "main.js").read_text()
        self.assertIn("const VERSION = '1.25.0'", main)
        self.assertNotRegex(main, r"licenseKey\s*:")


class StaticServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        (root / "site" / "fonts" / "fonts").mkdir(parents=True)
        (root / "site" / "index.html").write_text("<p>root</p>")
        (root / "site" / "fonts" / "fonts" / "a.ttf").write_bytes(b"font")
        (root / "mount").mkdir()
        (root / "mount" / "x.wasm").write_bytes(b"\0asm")
        (root / "secret.txt").write_text("outside")
        # A link inside a served folder that leads out of it, as a file and as a folder.
        (root / "site" / "leak.txt").symlink_to(root / "secret.txt")
        (root / "site" / "up").symlink_to(root, target_is_directory=True)
        cls.proc = subprocess.Popen(
            ["node", "static_server.mjs", "0", str(root / "site"), f"/vendor/x2t={root / 'mount'}"],
            cwd=UI, stdout=subprocess.PIPE, text=True)
        cls.base = None

    @classmethod
    def tearDownClass(cls):
        cls.proc.kill()
        cls.proc.wait()
        cls.proc.stdout.close()
        cls.tmp.cleanup()

    def get(self, path):
        if StaticServer.base is None:
            line = self.proc.stdout.readline()
            StaticServer.base = re.search(r"http://127\.0\.0\.1:\d+", line).group(0)
        try:
            with urllib.request.urlopen(StaticServer.base + path, timeout=10) as r:
                return r.status, r.headers.get("content-type"), r.read()
        except urllib.error.HTTPError as e:
            return e.code, None, b""

    def test_serves_the_root_a_mount_and_doubled_slashes(self):
        self.assertEqual(self.get("/")[2], b"<p>root</p>")
        self.assertEqual(self.get("/vendor/x2t/x.wasm")[:2], (200, "application/wasm"))
        self.assertEqual(self.get("/fonts//fonts/a.ttf")[2], b"font")

    def test_a_link_that_leaves_its_folder_is_not_followed(self):
        self.assertEqual(self.get("/leak.txt")[0], 404)
        self.assertEqual(self.get("/up/secret.txt")[0], 404)
        # The server is still answering afterwards.
        self.assertEqual(self.get("/")[0], 200)

    def test_a_path_outside_its_folders_is_not_served(self):
        self.assertEqual(self.get("/%2e%2e/secret.txt")[0], 404)
        self.assertEqual(self.get("/vendor/x2t/%2e%2e/%2e%2e/secret.txt")[0], 404)
        self.assertEqual(self.get("/missing.js")[0], 404)


class OnlyOfficeControls(unittest.TestCase):
    def test_each_control_removes_only_what_it_is_named_for(self):
        corpus = ROOT / "fixture" / "complex.docx"
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, "-I", str(UI / "onlyoffice" / "make_controls.py"), str(corpus), d],
                           check=True, capture_output=True)
            doc = lambda p: zipfile.ZipFile(p).read("word/document.xml").decode("utf-8")
            src, a, b = doc(corpus), doc(Path(d) / "no_altchunk.docx"), doc(Path(d) / "no_altchunk_no_dgm.docx")
            self.assertEqual(sorted(zipfile.ZipFile(corpus).namelist()),
                             sorted(zipfile.ZipFile(Path(d) / "no_altchunk.docx").namelist()))
        self.assertIn("<w:altChunk", src)
        self.assertNotIn("<w:altChunk", a)
        self.assertEqual(len(src) - len(a), len(re.search(r"<w:altChunk\b[^>]*/>", src).group(0)))
        self.assertIn("rIdDgmData", a)
        self.assertNotIn("rIdDgmData", b)
        self.assertNotIn("<w:altChunk", b)
        for kept in ("rIdChart", "<w:object", "Text box content"):
            self.assertIn(kept, b)


if __name__ == "__main__":
    unittest.main()
