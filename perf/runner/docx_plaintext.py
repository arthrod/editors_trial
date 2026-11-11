"""Extract plain text from a minimal DOCX for cheap correctness checks."""

from __future__ import annotations

import html
import re
import zipfile


_W_T = re.compile(rb"<w:t[^>]*>([^<]*)</w:t>", re.I)
_W_P = re.compile(rb"<w:p\b[^>]*/>|<w:p\b[^>]*>.*?</w:p>", re.I | re.S)
_W_NUMPR = re.compile(rb"<w:numPr\b", re.I)


def _run_text(run: bytes) -> str:
    # ``w:t`` content is XML-escaped: &quot; &apos; &amp; &lt; &gt; and
    # numeric references all stand for the typed character.
    return html.unescape(run.decode("utf-8", errors="replace"))


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1]


def _paragraphs(data: bytes):
    """Yield ``(text, has_numPr)`` per real ``w:p`` element.

    ``w:p`` nests legally (textbox ``w:txbxContent``, ``mc:AlternateContent``
    fallbacks); a regex's non-greedy ``.*?</w:p>`` splits the outer paragraph
    at the inner one's close and glues the pieces. ElementTree walks the real
    structure: a nested ``w:p`` is its own paragraph and owns its own text.
    The regex split stays only as the fallback for input that does not parse.
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        for block in _W_P.findall(data):
            yield ("".join(_run_text(run) for run in _W_T.findall(block)),
                   bool(_W_NUMPR.search(block)))
        return
    for p in root.iter():
        if _local(p.tag) != "p":
            continue
        texts, has_numpr = [], False
        stack = list(p)[::-1]
        while stack:
            el = stack.pop()
            name = _local(el.tag)
            if name == "p" and el is not p:
                continue  # a nested paragraph owns its own text
            if name == "t":
                texts.append(el.text or "")
            elif name == "numPr":
                has_numpr = True
            stack.extend(el[::-1])
        yield "".join(texts), has_numpr


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
    return paragraph_separator.join(text for text, _ in _paragraphs(data))


def docx_body_text_and_absorbed(path) -> tuple[str, list]:
    """``(text, absorbed)``: paragraph-joined body text plus the absorbed
    marker-only paragraphs. Each entry is ``{'index': i, 'marker': None}``
    where ``i`` is the paragraph's line position in ``text``: a ``w:p`` that
    carries a list number (``w:numPr``) but no text run. Evidence is
    positional on purpose — only the item AT a missing marker's index can
    answer for it, never a count or an item elsewhere."""
    with zipfile.ZipFile(path, "r") as zf:
        data = zf.read("word/document.xml")
    texts, absorbed = [], []
    for text, has_numpr in _paragraphs(data):
        if not text.strip() and has_numpr:
            absorbed.append({'index': len(texts), 'marker': None})
        texts.append(text)
    return "\n".join(texts), absorbed
