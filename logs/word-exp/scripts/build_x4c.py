"""X4c: X4's package with the customXml item's DOCTYPE removed (the control for X4)."""
import zipfile
from pathlib import Path
FIX = Path(__file__).resolve().parent.parent / "fixtures"
with zipfile.ZipFile(FIX / "X4_dtd_customxml.docx") as src, zipfile.ZipFile(FIX / "X4c_customxml_control.docx", "w", zipfile.ZIP_DEFLATED) as out:
    for info in src.infolist():
        data = src.read(info.filename)
        if info.filename == "customXml/item1.xml":
            data = b'<?xml version="1.0"?><vendor>1</vendor>'
        out.writestr(info.filename, data)
print((FIX / "X4c_customxml_control.docx").stat().st_size)
