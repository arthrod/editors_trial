"""E2 OpenDoc: a reader of OpenDoc's engine returns the whole document or nothing.

CodeRabbit and CodeAnt on #283 (2026-11-23): the three readers of
``opendoc.ai.read`` returned a shorter text as if it were the document when a
page was truncated with no cursor, when a table's page was refused, or (the
C07/C08 snapshot) when the read rejected; and the C07/C08 snapshot left table
cells out. The pinned engine always gives a cursor with a truncated page, and
no table in the campaign's documents needed a second page, so no recorded
figure came from these paths; the readers now refuse them anyway.

R1  A paragraph, a two-page table and a paragraph read whole by every reader
    (the census lists paragraphs only, as before).
R2  A truncated page with no cursor: no text from any reader.
R3  A refused table page: no text from the snapshot or the oracle.
R4  A rejected read: the snapshot and the census say unavailable, they do not throw.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@unittest.skipIf(shutil.which("node") is None, "node is not on PATH")
class OpenDocReaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(["node", str(REPO / "perf" / "tests" / "e2_opendoc_readers_repro.mjs")],
                              cwd=str(REPO), capture_output=True, text=True, timeout=120)
        if proc.returncode:
            raise AssertionError(proc.stderr)
        cls.out = json.loads(proc.stdout)

    def test_a_whole_document_is_read_with_its_table_cells(self):
        row = self.out["whole"]
        self.assertEqual(row["state"], {"text": "Alpha\nA1\nB1\nA2\nB2\nOmega", "error": None})
        self.assertEqual(row["oracle"]["text"], "Alpha\nA1\nB1\nA2\nB2\nOmega")
        self.assertEqual(row["oracle"]["oracle"], "perf_model")
        self.assertEqual(row["census"], ["Alpha", "Omega"])

    def test_a_truncated_page_without_a_cursor_gives_no_text(self):
        row = self.out["no_cursor"]
        self.assertEqual(row["state"]["error"], "editor_model_unavailable")
        self.assertEqual(row["state"]["text"], "")
        self.assertEqual(row["oracle"]["oracle"], "absent")
        self.assertEqual(row["oracle"]["text"], "")
        self.assertIsNone(row["census"])

    def test_a_refused_table_page_gives_no_text(self):
        row = self.out["table_refused"]
        self.assertEqual(row["state"]["error"], "editor_model_unavailable")
        self.assertEqual(row["oracle"]["oracle"], "absent")
        self.assertIn("busy", row["oracle"]["error"])

    def test_a_rejected_read_is_unavailable_not_thrown(self):
        row = self.out["rejected"]
        self.assertEqual(row["state"]["error"], "editor_model_unavailable")
        self.assertEqual(row["oracle"]["oracle"], "absent")
        self.assertIsNone(row["census"])


if __name__ == "__main__":
    unittest.main()
