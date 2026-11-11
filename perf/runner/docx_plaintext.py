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


_W_NUMPR = re.compile(rb"<w:numPr\b", re.I)


def docx_body_text_and_absorbed(path) -> tuple[str, int]:
    """``(text, absorbed_count)``: paragraph-joined body text plus the count
    of paragraphs that carry a list number (``w:numPr``) but no text run —
    those are marker-only paragraphs the editor absorbed into real list
    items, the only relocation the correctness compare may tolerate."""
    with zipfile.ZipFile(path, "r") as zf:
        data = zf.read("word/document.xml")
    texts, absorbed = [], 0
    for block in _W_P.findall(data):
        text = "".join(_run_text(run) for run in _W_T.findall(block))
        if not text.strip() and _W_NUMPR.search(block):
            absorbed += 1
        texts.append(text)
    return "\n".join(texts), absorbed
