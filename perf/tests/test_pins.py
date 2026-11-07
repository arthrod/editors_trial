"""Facts-driven editor pins."""

import json
import tempfile
import unittest
from pathlib import Path

from perf.pins import load_editor_pins


class FactsPins(unittest.TestCase):
    def test_loads_pins_from_fixture_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "facts.json"
            path.write_text(
                json.dumps(
                    {
                        "ver.plate.commit": "aaaabbbbccccddddeeeeffff00001111",
                        "ver.docxodus.commit": "bbbbcccc",
                        "ver.npm.docxodus": "9.9.9",
                        "ver.npm.apryse": "1.0.0",
                        "ver.superdoc.commit": "ccc",
                        "ver.npm.superdoc_sdk": "1.0.0",
                        "ver.npm.superdoc_engine": "2.0.0",
                        "ver.folio.commit": "ddd",
                        "ver.genoffice.commit": "eee",
                        "ver.eigenpal-docx-editor.commit": "fff",
                        "ver.office-open.commit": "111",
                        "ver.docen.commit": "222",
                        "ver.wordcraft.commit": "333",
                        "ver.fiduswriter.commit": "444",
                        "ver.fiduswriter-document-ts.commit": "555",
                        "ver.canvas-editor.commit": "666",
                        "ver.canvas-editor-plugin.commit": "777",
                        "ver.docs-plus.commit": "888",
                    }
                ),
                encoding="utf-8",
            )
            pins = load_editor_pins(path)
        self.assertIn("plate", pins)
        self.assertIn("aaaabbbbccccddddeeeeffff00001111", pins["plate"])
        self.assertIn("9.9.9", pins["docxodus"])
        self.assertIn("system soffice", pins["libreoffice"])


if __name__ == "__main__":
    unittest.main()
