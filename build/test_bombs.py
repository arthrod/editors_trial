#!/usr/bin/env python3
"""The bomb entry must record a later sandbox run, and must not build one."""
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ROOT, "build", "run_bombs.py")
REPORT = os.path.join(
    ROOT,
    "reports",
    "Report D - Safety, Resource Bombs and Hostile Input (2026).md",
)
SKIP_DIRS = {".git", "node_modules", "repos", "__pycache__"}
FIELD = re.compile(r"(fidelity|safety): (\S+)")


def _launch():
    return subprocess.run(
        [sys.executable, ENTRY],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _packages():
    found = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
        for name in filenames:
            if not name.endswith((".docx", ".zip")):
                continue
            path = os.path.join(dirpath, name)
            st = os.stat(path)
            found[path] = (st.st_size, st.st_mtime_ns)
    return found


def _row(text, prefix):
    hits = [line for line in text.splitlines() if line.startswith(prefix)]
    if len(hits) != 1:
        raise AssertionError(f"{prefix!r} matched {len(hits)} lines")
    return hits[0]


def _fields(line):
    return dict(FIELD.findall(line))


class BombEntryTest(unittest.TestCase):
    def test_two_launches_agree_and_write_no_package(self):
        before = _packages()
        first = _launch()
        second = _launch()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first.stderr, "")
        text = first.stdout
        self.assertIn("run later, sandboxed", text)
        self.assertIn("The hostile suite was not executed.", text)
        self.assertIn(
            "preserving a hostile payload is not the same single result as a crash",
            text,
        )
        self.assertNotIn("PK\x03\x04", text)
        for n in range(1, 11):
            fields = _fields(_row(text, f"B{n} "))
            self.assertEqual(fields.get("fidelity"), "not-run", n)
            self.assertEqual(fields.get("safety"), "not-run", n)
        for name in ("Word", "LibreOffice"):
            row = _row(text, f"reference {name} ")
            fields = _fields(row)
            self.assertEqual(fields.get("fidelity"), "not-run", name)
            self.assertEqual(fields.get("safety"), "not-run", name)
            self.assertIn("was not opened on a hostile package", row)
        b7 = _row(text, "B7 ")
        self.assertIn("NTLM credential leak cannot be measured on macOS.", b7)
        self.assertIn("The hostile suite was not executed.", b7)
        for banned in (
            "fidelity: preserved",
            "fidelity: dropped",
            "fidelity: refused",
            "safety: crash",
            "safety: hang",
            "safety: leak",
            "safety: reject",
        ):
            self.assertNotIn(banned, text)
        self.assertEqual(_packages(), before)

    def test_safety_report_quotes_the_shipped_log(self):
        launched = _launch()
        self.assertEqual(launched.returncode, 0, launched.stderr)
        with open(REPORT, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn(launched.stdout.strip(), body)
        self.assertNotIn("has no fidelity result", body)
        self.assertNotIn("safety result only", body)


if __name__ == "__main__":
    unittest.main()
