"""Extract plain text from a minimal DOCX for cheap correctness checks."""

from __future__ import annotations

import html
import re
import zipfile


_W_T = re.compile(rb"<w:t[^>]*>([^<]*)</w:t>", re.I)
_W_P = re.compile(rb"<w:p\b[^>]*/>|<w:p\b[^>]*>.*?</w:p>", re.I | re.S)


def _run_text(run: bytes) -> str:
    # ``w:t`` content is XML-escaped: &quot; &apos; &amp; &lt; &gt; and
    # numeric references all stand for the typed character.
    return html.unescape(run.decode("utf-8", errors="replace"))


def docx_body_text(path, paragraph_separator: str = "") -> str:
    """Return ``w:t`` text runs from ``word/document.xml``.

    With ``paragraph_separator`` the runs of each ``w:p`` join into one
    segment and the separator joins the segments; without it every run
    concatenates, gluing the last word of a paragraph to the first word of
    the next.
    """
    with zipfile.ZipFile(path, "r") as zf:
        data = zf.read("word/document.xml")
    if not paragraph_separator:
        return "".join(_run_text(p) for p in _W_T.findall(data))
    paragraphs = (
        "".join(_run_text(run) for run in _W_T.findall(block))
        for block in _W_P.findall(data)
    )
    return paragraph_separator.join(paragraphs)
