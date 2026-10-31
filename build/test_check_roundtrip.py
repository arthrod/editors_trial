#!/usr/bin/env python3
"""Fairness checks for the shipped round-trip scorer.

These call build/check_roundtrip.py. They do not reimplement it.
"""
import io
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_roundtrip as sc

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
DGM = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
O = "urn:schemas-microsoft-com:office:office"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
W16DU = "http://schemas.microsoft.com/office/word/2023/wordml/word16du"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
FIXTURE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "fixture", "complex.docx")


def package(parts):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in parts.items():
            z.writestr(name, data.encode("utf-8") if isinstance(data, str) else data)
    return buf.getvalue()


def checks(parts_in, parts_out=None):
    if parts_out is None:
        parts_out = parts_in
    inp = sc.Pkg(data=package(parts_in))
    out = sc.Pkg(data=package(parts_out))
    return {c[0]: c for c in sc.build_checks(inp, out)}


def rels(rows):
    body = "".join(
        '<Relationship Id="%s" Type="%s" Target="%s"%s/>'
        % (rid, typ, target, mode)
        for rid, typ, target, mode in rows
    )
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="%s">%s</Relationships>' % (REL, body))


def document(inner, extra_ns=""):
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="%s" xmlns:r="%s" %s>'
        "<w:body>%s</w:body></w:document>" % (W, R, extra_ns, inner)
    )


class ScorerFairness(unittest.TestCase):
    def test_renamed_header_keeps_tracked_change(self):
        header = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:hdr xmlns:w="%s"><w:p><w:ins w:id="1">'
            "<w:r><w:t>added</w:t></w:r></w:ins></w:p></w:hdr>" % W
        )
        body = (
            "<w:p><w:r><w:t>Body</w:t></w:r></w:p>"
            '<w:sectPr><w:headerReference w:type="first" r:id="rIdH"/></w:sectPr>'
        )
        base = {
            "word/document.xml": document(body),
            "word/_rels/document.xml.rels": rels([
                ("rIdH",
                 "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header",
                 "header2.xml", ""),
            ]),
            "word/header2.xml": header,
        }
        renamed = dict(base)
        renamed["word/_rels/document.xml.rels"] = rels([
            ("rIdH",
             "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header",
             "header3.xml", ""),
        ])
        renamed["word/header3.xml"] = header
        del renamed["word/header2.xml"]
        got = checks(base, renamed)
        self.assertTrue(got["ref.headerTrackedChange"][4], got["ref.headerTrackedChange"])
        self.assertTrue(got["pkg.word_header2.xml"][4], got["pkg.word_header2.xml"])

    def test_rebound_prefix_keeps_uri(self):
        inner = (
            '<w:p xmlns:ns0="%s" ns0:paraId="ABCD"><w:r><w:t>Hello</w:t></w:r></w:p>'
            '<w:ins xmlns:du="%s" w:id="9" du:dateUtc="2026-01-15T09:30:00Z">'
            "<w:r><w:t>x</w:t></w:r></w:ins>"
            % (W14, W16DU)
        )
        # The conventional prefixes are absent on purpose. The URIs are not.
        raw = document(inner)
        self.assertNotIn("xmlns:w14=", raw)
        self.assertNotIn("xmlns:w16du=", raw)
        got = checks({"word/document.xml": raw})
        self.assertTrue(got["mx.unknownAttr"][4], got["mx.unknownAttr"])
        self.assertTrue(got["tc.dateUtc"][4], got["tc.dateUtc"])
        self.assertTrue(got["mx.nsW14"][4], got["mx.nsW14"])
        self.assertTrue(got["mx.nsW16du"][4], got["mx.nsW16du"])
        self.assertNotEqual(got["mx.nsW14"][3], 3)
        self.assertNotEqual(got["mx.nsW16du"][3], 3)
        self.assertEqual(got["mx.unknownAttr"][3], 3)
        self.assertEqual(got["tc.dateUtc"][3], 3)

    def test_critical_weight_is_not_stacked_for_one_namespace_fact(self):
        raw = document(
            '<w:p xmlns:w14="%s" w14:paraId="1"><w:r><w:t>t</w:t></w:r></w:p>'
            '<w:ins xmlns:w16du="%s" w:id="1" w16du:dateUtc="2026-01-15T00:00:00Z">'
            "<w:r><w:t>t</w:t></w:r></w:ins>" % (W14, W16DU)
        )
        got = checks({"word/document.xml": raw})
        self.assertFalse(got["tc.dateUtc"][3] == 3 and got["mx.nsW16du"][3] == 3)
        self.assertFalse(got["mx.unknownAttr"][3] == 3 and got["mx.nsW14"][3] == 3)

    def test_proof_err_is_not_critical(self):
        got = checks({"word/document.xml": document("<w:p><w:r><w:t>t</w:t></w:r></w:p>")})
        self.assertNotEqual(got["mx.proofErr"][3], 3)
        self.assertLess(got["mx.proofErr"][3], 3)

    def test_dangling_relationships_fail(self):
        chart = (
            '<w:r><c:chart xmlns:c="%s" xmlns:r="%s" r:id="rIdChart"/></w:r>' % (C, R)
        )
        smart = (
            '<w:r><dgm:relIds xmlns:dgm="%s" xmlns:r="%s" '
            'r:dm="rIdD" r:lo="rIdL" r:qs="rIdQ" r:cs="rIdC"/></w:r>' % (DGM, R)
        )
        image = (
            '<w:r><a:blip xmlns:a="%s" xmlns:r="%s" r:embed="rIdImage"/></w:r>' % (A, R)
        )
        ole = (
            '<w:r><o:OLEObject xmlns:o="%s" xmlns:r="%s" r:id="rIdOle"/></w:r>' % (O, R)
        )
        chunk = '<w:altChunk r:id="rIdChunk"/>'
        body = "<w:p>%s%s%s%s</w:p>%s" % (chart, smart, image, ole, chunk)
        dangling = {
            "word/document.xml": document(body),
            "word/_rels/document.xml.rels": rels([
                ("rIdChart", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart", "charts/missing.xml", ""),
                ("rIdD", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData", "diagrams/missing.xml", ""),
                ("rIdL", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramLayout", "diagrams/missing-l.xml", ""),
                ("rIdQ", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramQuickStyle", "diagrams/missing-q.xml", ""),
                ("rIdC", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramColors", "diagrams/missing-c.xml", ""),
                ("rIdImage", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", "media/missing.png", ""),
                ("rIdOle", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject", "embeddings/missing.bin", ""),
                ("rIdChunk", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/aFChunk", "missing.html", ""),
            ]),
        }
        got = checks(dangling)
        for cid in ("ref.chart", "ref.smartart", "ref.image", "ref.ole", "ref.altChunk"):
            self.assertFalse(got[cid][4], got[cid])

        kept = dict(dangling)
        kept["word/charts/missing.xml"] = "<c:chartSpace xmlns:c=\"%s\"/>" % C
        kept["word/diagrams/missing.xml"] = "<dgm:dataModel xmlns:dgm=\"%s\"/>" % DGM
        kept["word/diagrams/missing-l.xml"] = "<dgm:layoutDef xmlns:dgm=\"%s\"/>" % DGM
        kept["word/diagrams/missing-q.xml"] = "<dgm:styleDef xmlns:dgm=\"%s\"/>" % DGM
        kept["word/diagrams/missing-c.xml"] = "<dgm:colorsDef xmlns:dgm=\"%s\"/>" % DGM
        kept["word/media/missing.png"] = b"\x89PNG"
        kept["word/embeddings/missing.bin"] = b"ole"
        kept["word/missing.html"] = "<p>Imported altChunk paragraph one</p>"
        got = checks(kept)
        for cid in ("ref.chart", "ref.smartart", "ref.image", "ref.ole", "ref.altChunk"):
            self.assertTrue(got[cid][4], got[cid])

    def test_move_from_del_text_fails(self):
        bad = document(
            '<w:p><w:moveFrom w:id="1"><w:r><w:delText>gone</w:delText></w:r></w:moveFrom></w:p>'
        )
        good = document(
            '<w:p><w:moveFrom w:id="1"><w:r><w:t>moved away</w:t></w:r></w:moveFrom></w:p>'
        )
        self.assertFalse(checks({"word/document.xml": bad})["tc.moveFrom"][4])
        self.assertTrue(checks({"word/document.xml": good})["tc.moveFrom"][4])

    def test_endnote_body_and_hyperlink_targets_are_scored(self):
        endnotes = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:endnotes xmlns:w="%s"><w:endnote w:id="2"><w:p><w:r>'
            "<w:t>This is the endnote body.</w:t></w:r></w:p></w:endnote></w:endnotes>" % W
        )
        link = (
            '<w:p><w:hyperlink r:id="rH" w:anchor="Dest">'
            "<w:r><w:t>spec</w:t></w:r></w:hyperlink></w:p>"
        )
        link_rels = rels([
            ("rH", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
             "https://example.com/spec", ' TargetMode="External"'),
            ("rIdEndnotes",
             "http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes",
             "endnotes.xml", ""),
        ])
        kept = {
            "word/document.xml": document(link),
            "word/_rels/document.xml.rels": link_rels,
            "word/endnotes.xml": endnotes,
        }
        dropped = {
            "word/document.xml": document("<w:p><w:r><w:t>spec</w:t></w:r></w:p>"),
            "word/_rels/document.xml.rels": rels([]),
            "word/endnotes.xml": (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:endnotes xmlns:w="%s"></w:endnotes>' % W
            ),
        }
        good = checks(kept)
        self.assertTrue(good["ref.endnoteBody"][4], good["ref.endnoteBody"])
        self.assertTrue(good["fl.hyperlink"][4], good["fl.hyperlink"])
        bad = checks(kept, dropped)
        self.assertFalse(bad["ref.endnoteBody"][4], bad["ref.endnoteBody"])
        self.assertFalse(bad["fl.hyperlink"][4], bad["fl.hyperlink"])

    def test_fixture_round_trip_of_itself_keeps_resolved_refs(self):
        inp = sc.Pkg(FIXTURE)
        got = {c[0]: c for c in sc.build_checks(inp, inp)}
        for cid in ("ref.chart", "ref.smartart", "ref.image", "ref.ole", "ref.altChunk",
                    "ref.headerTrackedChange", "ref.endnoteBody", "tc.moveFrom", "fl.hyperlink"):
            self.assertTrue(got[cid][4], got[cid])
        self.assertNotEqual(got["mx.proofErr"][3], 3)
        self.assertNotEqual(got["mx.nsW16du"][3], 3)


if __name__ == "__main__":
    unittest.main()
