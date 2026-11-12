"""#169 F2: a supplied caret paragraph must be readable.

verifyCaretAtParagraphStart used to pass when the reader returned offset 0
and a null or empty paragraphText. That read never checked the paragraph.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SURFACE = REPO / "perf" / "runner" / "edit_surface.mjs"


def _node():
    return shutil.which("node")


class UnreadableParagraphText(unittest.TestCase):
    def verdict(self, read, expected):
        script = """
import assert from 'node:assert/strict';
const surface = await import(%s);
const read = %s;
const page = {
  async evaluate() { return read; },
  async waitForTimeout() {},
  async waitForFunction() {},
};
const verdict = await surface.verifyCaretAtParagraphStart(page, 'plate', {
  expectedParagraphText: %s,
});
console.log(JSON.stringify(verdict));
""" % (
            json.dumps(str(SURFACE)),
            json.dumps(read),
            json.dumps(expected),
        )
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    @unittest.skipUnless(_node(), "node required")
    def test_null_paragraph_text_refuses_when_expected_text_was_supplied(self):
        verdict = self.verdict(
            {"offset": 0, "paragraphText": None, "focused": True},
            "Alpha body paragraph here",
        )
        self.assertFalse(verdict["ok"], verdict)
        self.assertEqual(verdict["reason"], "caret_not_at_paragraph_start")
        self.assertEqual(verdict["detail"], "paragraph_text_unreadable")

    @unittest.skipUnless(_node(), "node required")
    def test_empty_paragraph_text_refuses_when_expected_text_was_supplied(self):
        verdict = self.verdict(
            {"offset": 0, "paragraphText": "", "focused": True},
            "Alpha body paragraph here",
        )
        self.assertFalse(verdict["ok"], verdict)
        self.assertEqual(verdict["reason"], "caret_not_at_paragraph_start")
        self.assertEqual(verdict["detail"], "paragraph_text_unreadable")

    @unittest.skipUnless(_node(), "node required")
    def test_a_different_paragraph_is_still_a_mismatch(self):
        verdict = self.verdict(
            {"offset": 0, "paragraphText": "Other paragraph", "focused": True},
            "Alpha body paragraph here",
        )
        self.assertFalse(verdict["ok"], verdict)
        self.assertEqual(verdict["detail"], "paragraph_text_mismatch")

    @unittest.skipUnless(_node(), "node required")
    def test_the_expected_paragraph_still_passes(self):
        verdict = self.verdict(
            {"offset": 0, "paragraphText": "Alpha body paragraph here", "focused": True},
            "Alpha body paragraph here",
        )
        self.assertTrue(verdict["ok"], verdict)

    @unittest.skipUnless(_node(), "node required")
    def test_null_text_without_an_expected_paragraph_is_unchanged(self):
        verdict = self.verdict(
            {"offset": 0, "paragraphText": None, "focused": True},
            None,
        )
        self.assertTrue(verdict["ok"], verdict)
