"""Extract plain text from a minimal DOCX for cheap correctness checks."""

from __future__ import annotations

import re
import zipfile


_W_T = re.compile(rb"<w:t[^>]*>([^<]*)</w:t>", re.I)


def docx_body_text(path) -> str:
    """Return concatenated ``w:t`` text runs from ``word/document.xml``."""
    with zipfile.ZipFile(path, "r") as zf:
        data = zf.read("word/document.xml")
    parts = _W_T.findall(data)
    return "".join(p.decode("utf-8", errors="replace") for p in parts)
