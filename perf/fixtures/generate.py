"""Deterministic performance workload bytes and correctness fixtures."""

from __future__ import annotations

import hashlib


def build_workload(profile):
    paragraphs = int(profile["paragraphs"])
    width = int(profile["paragraph_chars"])
    if paragraphs < 1 or width < 1:
        raise ValueError("workload shape")
    unicode_class = profile["unicode_class"]
    if unicode_class not in ("ascii", "mixed"):
        raise ValueError("unicode_class")
    match_count = int(profile["match_count"])
    if match_count < 0:
        raise ValueError("match_count")
    term = profile.get("search_term", "NEEDLE")
    needle = term.encode("utf-8")
    if match_count and (not term or needle in b" \n"):
        raise ValueError("search_term")
    cells = paragraphs * width
    if match_count:
        if len(term) * match_count > cells:
            raise ValueError("match_count")
    mixed_pat = "e\u0301\U0002000b"
    chars = []
    if unicode_class == "ascii":
        chars = [" "] * cells
    else:
        while len(chars) < cells:
            for ch in mixed_pat:
                if len(chars) >= cells:
                    break
                chars.append(ch)
    if match_count:
        pos = 0
        for _ in range(match_count):
            while True:
                line_start = (pos // width) * width
                line_end = line_start + width
                if pos + len(term) <= line_end:
                    break
                pos = line_end
                if pos >= cells:
                    raise ValueError("match_count")
            for ch in term:
                chars[pos] = ch
                pos += 1
    lines_txt = []
    idx = 0
    for _ in range(paragraphs):
        chunk = "".join(chars[idx : idx + width])
        idx += width
        lines_txt.append(chunk)
    body = ("\n".join(lines_txt) + "\n").encode("utf-8")
    if match_count:
        if body.count(needle) != match_count:
            raise ValueError("match_count")
    return {
        "workload_id": profile["workload_id"],
        "sha256": hashlib.sha256(body).hexdigest(),
        "body": body,
        "paragraphs": paragraphs,
        "unicode_class": unicode_class,
        "match_count": match_count,
        "search_term": term if match_count else None,
    }


def correctness_fixtures():
    return {
        "unicode": "cafe\u0301 \U0002000b\n".encode("utf-8"),
        "emoji": (
            "family \U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466 "
            "tone \U0001f44d\U0001f3fb\n"
        ).encode("utf-8"),
        "bidi": "Hello مرحبا\n".encode("utf-8"),
        "ime_committed": "地\n".encode("utf-8"),
    }


def docx_zip_bytes(body: bytes) -> bytes:
    """Minimal OOXML package: one word/document.xml with plaintext from ``body``."""
    from io import BytesIO
    import zipfile

    inner = body.decode("utf-8", errors="replace")
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t xml:space=\"preserve\">%s</w:t></w:r></w:p></w:body></w:document>"
    ) % (
        inner.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS_ROOT)
        zf.writestr("word/_rels/document.xml.rels", _RELS_DOC)
        zf.writestr("word/document.xml", document_xml.encode("utf-8"))
    return buf.getvalue()


_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

_RELS_ROOT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

_RELS_DOC = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""
