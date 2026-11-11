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


def docx_zip_bytes(body: bytes, *, section_properties: bool = False) -> bytes:
    """Minimal OOXML package: one ``<w:p>`` per line of ``body``.

    Each newline-terminated line of ``body`` becomes its own paragraph (an
    empty line is an empty ``<w:p/>``). Entries carry a fixed timestamp, so
    the same body always zips to the same bytes (editors_trial#88, #100).

    ``section_properties`` appends a ``<w:sectPr>`` body tail — required by
    paginated renderers (docxodus) to place body paragraphs inside a page
    box; without it the lone paragraph mounts outside the paginated edit
    root and is never wired editable.
    """
    from perf.fixtures.docx_workload import _SECT_PR, deterministic_zip

    inner = body.decode("utf-8", errors="replace")
    lines = inner.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    paragraphs = []
    for line in lines:
        if not line:
            paragraphs.append("<w:p/>")
            continue
        escaped = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        paragraphs.append('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % escaped)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>%s%s</w:body></w:document>"
    ) % ("".join(paragraphs), _SECT_PR if section_properties else "")
    return deterministic_zip(
        [
            ("[Content_Types].xml", _CONTENT_TYPES.encode("utf-8")),
            ("_rels/.rels", _RELS_ROOT.encode("utf-8")),
            ("word/_rels/document.xml.rels", _RELS_DOC.encode("utf-8")),
            ("word/document.xml", document_xml.encode("utf-8")),
        ]
    )


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
