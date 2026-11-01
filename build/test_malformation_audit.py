#!/usr/bin/env python3
"""malformation_audit resolves relationship targets the way OPC does: a target that
starts with "/" is a part name from the package root (Apryse writes them so), not a
file-system path. v0.9.2's audit flagged 18 such targets in Apryse's output as missing."""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import malformation_audit as ma  # noqa: E402

RELS = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="t" Target="%s"/></Relationships>')


class Targets(unittest.TestCase):
    def audit(self, target, parts):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.docx"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("[Content_Types].xml",
                           '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                           '<Default Extension="xml" ContentType="application/xml"/>'
                           '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                           '</Types>')
                z.writestr("word/document.xml", "<w:document xmlns:w='w'/>")
                z.writestr("word/_rels/document.xml.rels", RELS % target)
                for part in parts:
                    z.writestr(part, "<x/>")
            return [f for f in ma.audit(str(p)) if f[0] == "MISSING-TARGET"]

    def test_an_absolute_target_to_a_present_part_is_not_missing(self):
        self.assertEqual(self.audit("/word/header3.xml", ["word/header3.xml"]), [])

    def test_a_relative_target_to_a_present_part_is_not_missing(self):
        self.assertEqual(self.audit("header3.xml", ["word/header3.xml"]), [])

    def test_an_absolute_target_to_an_absent_part_is_missing(self):
        self.assertEqual(len(self.audit("/word/header9.xml", [])), 1)


if __name__ == "__main__":
    unittest.main()
