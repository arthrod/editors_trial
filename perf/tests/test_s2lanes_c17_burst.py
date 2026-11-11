"""C17 burst verify: superdoc and eigenpal read the editor model, not painted DOM alone."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class BurstVerifyUsesEditorModel(unittest.TestCase):
    def test_edit_surface_exposes_burst_verify_readers(self):
        text = (REPO / "perf" / "runner" / "edit_surface.mjs").read_text(encoding="utf-8")
        self.assertIn("readBurstVerifyText", text)
        self.assertIn("__SUPERDOC_E2E__", text)
        self.assertIn("__DOCX_EDITOR_E2E__", text)
        self.assertIn("BURST_VERIFY_MODEL", text)
        self.assertIn("superdoc", text)
        self.assertIn("eigenpal", text)

    def test_resource_burst_calls_read_burst_verify_text(self):
        text = (REPO / "perf" / "runner" / "resource_burst_edit.mjs").read_text(encoding="utf-8")
        self.assertIn("readBurstVerifyText", text)
        self.assertNotIn(
            "readCaretScope(page, opts.editorId, prepared.point)",
            text.split("verifyOnSurface")[1],
        )


class InsertedOnceStillRejectsReplacedBlock(unittest.TestCase):
    def test_inserted_once_unchanged(self):
        module = REPO / "perf" / "runner" / "edit_surface.mjs"
        script = (
            "import {insertedOnce as f} from %s;"
            "console.log(JSON.stringify(f('Article one','B8B8','B8B8')));"
        ) % repr(module.as_uri())
        out = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(out.stdout.strip(), "false")


if __name__ == "__main__":
    unittest.main()
