# build.py: spaces-in-one-w:t and words-in-paragraphs docs of N MiB, from B1's package
import sys, zipfile
src = "../fixtures/B1.docx"
z = zipfile.ZipFile(src)
parts = {n: z.read(n) for n in z.namelist() if n != "word/document.xml"}
head = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
tail = b'</w:body></w:document>'
for mib in (1, 4, 16):
    n = mib * 1024 * 1024
    for kind in ("sp", "words"):
        if kind == "sp":
            body = b'<w:p><w:r><w:t xml:space="preserve">' + b' ' * n + b'</w:t></w:r></w:p>'
        else:
            para = b'<w:p><w:r><w:t>' + b'lorem ipsum dolor sit amet ' * 40 + b'</w:t></w:r></w:p>'
            body = para * (n // len(para))
        with zipfile.ZipFile(f"{kind}{mib}.docx", "w", zipfile.ZIP_DEFLATED) as out:
            for k, v in parts.items():
                out.writestr(k, v)
            out.writestr("word/document.xml", head + body + tail)
