"""X4: a valid body plus a customXml data part whose XML carries a DOCTYPE with an
internal entity (the shape tests/inspect_paragraphs.rs::summary_reads_only_wordprocessingml_parts_for_revisions
holds jubarte to). X5: the same DOCTYPE in word/styles.xml, a WordprocessingML part. Does Word refuse either?"""
import zipfile
from pathlib import Path
FIX = Path(__file__).resolve().parent.parent / "fixtures"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT_BASE = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
  '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
  '<Default Extension="xml" ContentType="application/xml"/>'
  '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>{extra}</Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
  '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
DOC = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>'
  '<w:p><w:r><w:t>BODY_OK</w:t></w:r></w:p></w:body></w:document>')
DTD = '<!DOCTYPE {root} [<!ENTITY v "EXPANDED">]>'
def docrels(rel_type, target):
    """Return document relationship XML for the supplied type and target."""
    return ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId9" Type="{rel_type}" Target="{target}"/></Relationships>')
with zipfile.ZipFile(FIX / "X4_dtd_customxml.docx", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", CT_BASE.format(extra=""))
    z.writestr("_rels/.rels", RELS)
    z.writestr("word/document.xml", DOC)
    z.writestr("word/_rels/document.xml.rels", docrels(f"{R}/customXml", "../customXml/item1.xml"))
    z.writestr("customXml/item1.xml", '<?xml version="1.0"?>' + DTD.format(root="vendor") + "<vendor>&v;</vendor>")
with zipfile.ZipFile(FIX / "X5_dtd_styles.docx", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", CT_BASE.format(extra='<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'))
    z.writestr("_rels/.rels", RELS)
    z.writestr("word/document.xml", DOC)
    z.writestr("word/_rels/document.xml.rels", docrels(f"{R}/styles", "styles.xml"))
    z.writestr("word/styles.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + DTD.format(root="w:styles")
               + f'<w:styles xmlns:w="{W}"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>')
for n in ("X4_dtd_customxml", "X5_dtd_styles"):
    print(n, (FIX / f"{n}.docx").stat().st_size)
