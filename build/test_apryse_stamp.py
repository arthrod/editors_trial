#!/usr/bin/env python3
"""The Apryse trial stamp is identified in the output, never removed from it."""
import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apryse_stamp  # noqa: E402

STAMP = '<w:hdr><w:p><w:r><w:drawing><wp:docPr id="1" name="trn_d_stamp"/><a:blip r:embed="rId1"/></w:drawing></w:r></w:p></w:hdr>'
PLAIN = '<w:hdr><w:p><w:r><w:t>Default header</w:t></w:r></w:p></w:hdr>'
RELS = '<Relationships><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image2.png"/></Relationships>'


def docx(parts: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, body in parts.items():
            zf.writestr(name, body)
    return buf.getvalue()


class StampParts(unittest.TestCase):
    def test_finds_stamped_headers_and_their_images(self):
        data = docx({
            "word/document.xml": "<w:document/>",
            "word/header1.xml": PLAIN,
            "word/header3.xml": STAMP,
            "word/_rels/header3.xml.rels": RELS,
            "word/media/image2.png": "png",
        })
        self.assertEqual(apryse_stamp.stamp_parts(data),
                         ["word/_rels/header3.xml.rels", "word/header3.xml", "word/media/image2.png"])

    def test_an_unstamped_file_has_none(self):
        self.assertEqual(apryse_stamp.stamp_parts(docx({"word/header1.xml": PLAIN})), [])


class Attribution(unittest.TestCase):
    CHECKS = [
        {"id": "ref.headerTrackedChange", "label": "tracked change inside header kept", "pass": False},
        {"id": "pkg.word_header2.xml", "label": "part kept: header (first page)", "pass": False},
        {"id": "pkg.word_footer2.xml", "label": "part kept: footer (first page)", "pass": False},
        {"id": "sec.landscape", "label": "landscape section kept", "pass": False},
        {"id": "pkg.opens", "label": "ZIP package opens", "pass": True},
    ]

    def test_header_checks_cannot_be_separated_and_the_rest_are_the_editors(self):
        got = apryse_stamp.attribute(self.CHECKS, stamped=True)
        self.assertEqual(got["unseparable"], ["ref.headerTrackedChange", "pkg.word_header2.xml"])
        self.assertEqual(got["own"], ["pkg.word_footer2.xml", "sec.landscape"])

    def test_without_a_stamp_every_failure_is_the_editors(self):
        got = apryse_stamp.attribute(self.CHECKS, stamped=False)
        self.assertEqual(got["unseparable"], [])
        self.assertEqual(len(got["own"]), 4)


if __name__ == "__main__":
    unittest.main()
