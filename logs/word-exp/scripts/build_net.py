#!/usr/bin/env python3
"""Network-beacon fixtures aimed at a local listener on 127.0.0.1:18009 (ports <1024 need root)."""
import zipfile
from pathlib import Path
FIX = Path(__file__).resolve().parent.parent / "fixtures"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = (f'xmlns:w="{W}" xmlns:r="{R}" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')
CT = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      '<Default Extension="xml" ContentType="application/xml"/>'
      '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
      '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/></Types>')
ROOT = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>')
U = "http://127.0.0.1:18009"
def rel(i, t, target):
    """Return an external relationship XML entry for the given ID, type and target."""
    return f'<Relationship Id="{i}" Type="{R}/{t}" Target="{target}" TargetMode="External"/>'
def pack(name, body, doc_rels, settings_body=""):
    """Write a DOCX with document and settings parts and document relationships."""
    d = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {NS}><w:body>{body}</w:body></w:document>'
    s = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="{W}" xmlns:r="{R}">{settings_body}</w:settings>'
    dr = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
          f'<Relationship Id="rIdS" Type="{R}/settings" Target="settings.xml"/>{doc_rels}</Relationships>')
    with zipfile.ZipFile(FIX / name, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in [("[Content_Types].xml", CT), ("_rels/.rels", ROOT), ("word/document.xml", d),
                     ("word/settings.xml", s), ("word/_rels/document.xml.rels", dr)]:
            z.writestr(n, b)
OK = "<w:p><w:r><w:t>BODY_OK</w:t></w:r></w:p>"
# N1: attached template (settings.xml w:attachedTemplate -> settings rels); Word's classic remote-template fetch
pack("N1_template.docx", OK, "", '<w:attachedTemplate r:id="rIdT"/>')
# settings rels must carry rIdT: add it by re-packing with a settings rels part
import io
def add_part(name, part, data):
    """Append a ZIP member to an existing fixture and rewrite the file."""
    p = FIX / name
    buf = io.BytesIO(p.read_bytes())
    with zipfile.ZipFile(buf, "a", zipfile.ZIP_DEFLATED) as z:
        z.writestr(part, data)
    p.write_bytes(buf.getvalue())
add_part("N1_template.docx", "word/_rels/settings.xml.rels",
         '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         + rel("rIdT", "attachedTemplate", f"{U}/N1_template.dotm") + "</Relationships>")
# N2: linked picture (a:blip r:link), the web-beacon shape
blip = ('<w:p><w:r><w:drawing><wp:inline><wp:extent cx="914400" cy="914400"/><wp:docPr id="1" name="p"/>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>'
        '<pic:nvPicPr><pic:cNvPr id="1" name="p"/><pic:cNvPicPr/></pic:nvPicPr>'
        '<pic:blipFill><a:blip r:link="rIdImg"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="914400" cy="914400"/></a:xfrm><a:prstGeom prst="rect"/></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
pack("N2_linked_image.docx", OK + blip, rel("rIdImg", "image", f"{U}/N2_image.png"))
# N3: INCLUDEPICTURE field with a cached result
fld = ('<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
       f'<w:r><w:instrText xml:space="preserve"> INCLUDEPICTURE "{U}/N3_field.png" \\d </w:instrText></w:r>'
       '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>FIELD_CACHE</w:t></w:r>'
       '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')
pack("N3_includepicture.docx", OK + fld, "")
# N4: subDocument + hyperlink externals (the doc's B7 shape, on the listener)
pack("N4_subdoc.docx", OK + '<w:p><w:subDoc r:id="rIdSub"/></w:p>', rel("rIdSub", "subDocument", f"{U}/N4_sub.docx"))
for p in sorted(FIX.glob("N*.docx")):
    print(p.name, p.stat().st_size)
