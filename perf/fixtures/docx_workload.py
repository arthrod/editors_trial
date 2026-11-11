"""Realistic, deterministic DOCX workloads for the speed report (editors_trial#100).

The older ladder (``perf/fixtures/generate.py``) describes paragraphs of
spaces and, through ``docx_zip_bytes``, used to fold them into one
``<w:p>``. That is enough to check a contract and far too little to time an
editor: a 1 KB file of whitespace measures process start, not parsing or
layout. This module builds the documents the speed report times.

Every prose rung is the same shape at a different size:

- body paragraphs of exactly ``PARAGRAPH_WORDS`` real words, in sentences;
- a Heading 1 every 50 body paragraphs and a Heading 2 every 10 (styled
  through ``word/styles.xml``, so a styles part has to be read);
- bold and italic spans inside paragraphs, so a paragraph is several runs;
- Letter pages with one-inch margins, so editors with a page model lay out
  the same geometry;
- the four correctness paragraphs (Unicode, emoji, bidi, IME) and a final
  sentinel paragraph naming the rung, so a probe can prove the whole
  document arrived.

The text comes from a fixed vocabulary through a SplitMix64 generator written
here, not ``random``, so the bytes do not depend on the Python version. Zip
entries carry a fixed timestamp and fixed attributes: the same rung has the
same sha256 on every call. The sha256 is still recorded on every trial,
because a different zlib could compress differently.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

from perf.fixtures.generate import build_workload, correctness_fixtures, docx_zip_bytes

BUILDER_VERSION = "prose-docx/1"
SENTINEL_PREFIX = "ZZ-END-OF-DOCUMENT"
PARAGRAPH_WORDS = 50
HEADING1_EVERY = 50
HEADING2_EVERY = 10
SEED = 20261109

_REPO = Path(__file__).resolve().parents[2]
CORPUS_RELPATH = "fixture/complex.docx"
_FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def _prose_row(workload_id: str, words: int) -> dict:
    return {
        "workload_id": workload_id,
        "words": words,
        "paragraph_words": PARAGRAPH_WORDS,
        "paragraphs": words // PARAGRAPH_WORDS,
        "unicode_class": "ascii",
        "match_count": 0,
        "seed": SEED,
        "shape": "prose",
    }


PROSE_LADDER: list[dict] = [
    _prose_row("prose-500w", 500),
    _prose_row("prose-5kw", 5_000),
    _prose_row("prose-50kw", 50_000),
    _prose_row("prose-250kw", 250_000),
]

CORPUS_ROW: dict = {
    "workload_id": "complex-corpus",
    "paragraphs": None,  # read from the file by workload_docx
    "unicode_class": "mixed",
    "match_count": 0,
    "seed": 0,
    "shape": "corpus",
    "source": CORPUS_RELPATH,
}

# Common English and contract vocabulary. Fixed: changing it changes every sha.
_VOCABULARY = tuple(
    """
    the of and to in for that is on with as by this be are from or at an not
    which shall will may any all such other each under its their has have been
    agreement party parties section article clause term terms notice written
    consent payment amount date period event default breach obligation right
    rights remedy remedies law laws court jurisdiction dispute claim claims loss
    damages liability indemnity confidential information disclosure purpose
    property intellectual license grant scope use services goods delivery price
    invoice tax taxes fee fees schedule exhibit annex appendix provision
    provisions effect force majeure termination renewal assignment successor
    affiliate subsidiary employee contractor representative officer director
    company corporation partnership person entity government authority approval
    regulation compliance standard reasonable material adverse change control
    warranty warranties representation covenant condition precedent subsequent
    closing completion transfer title risk insurance audit record records report
    reports budget plan project milestone acceptance test specification
    requirement requirements quality security data privacy personal processing
    controller processor breach incident response cure waiver amendment
    severability counterpart counterparts entire whole understanding prior
    contemporaneous oral negotiation execution signature signatory witness
    deed instrument document documents copy original electronic delivered
    received business day month year calendar first second third last final
    within before after during upon until unless except including without
    limitation respect relation connection accordance pursuant hereto hereof
    herein thereof therein whereas provided however further also only either
    neither both same different new existing current future past annual monthly
    weekly daily general specific particular relevant applicable appropriate
    necessary sufficient prompt timely full partial direct indirect special
    consequential incidental punitive exemplary maximum minimum total aggregate
    """.split()
)


class _SplitMix64:
    """Deterministic 64-bit generator, independent of ``random``'s internals."""

    _MASK = (1 << 64) - 1

    def __init__(self, seed: int) -> None:
        self.state = seed & self._MASK

    def next(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & self._MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & self._MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & self._MASK
        return z ^ (z >> 31)

    def below(self, n: int) -> int:
        return self.next() % n

    def between(self, lo: int, hi: int) -> int:
        return lo + self.below(hi - lo + 1)

    def word(self) -> str:
        return _VOCABULARY[self.below(len(_VOCABULARY))]


def _paragraph_words(rng: _SplitMix64, count: int) -> list[str]:
    """``count`` words in sentences: capitalised, commas, a period at the end."""
    words: list[str] = []
    while len(words) < count:
        length = min(rng.between(6, 18), count - len(words))
        sentence = [rng.word() for _ in range(length)]
        sentence[0] = sentence[0].capitalize()
        for i in range(length - 1):
            if rng.below(9) == 0:
                sentence[i] += ","
        sentence[-1] += "."
        words.extend(sentence)
    return words


def _spans(rng: _SplitMix64, words: list[str]) -> list[tuple[str, str]]:
    """Split a paragraph into (format, text) runs: plain, bold, or italic."""
    spans: list[tuple[str, list[str]]] = []
    i = 0
    while i < len(words):
        roll = rng.below(40)
        if roll < 2:
            fmt, n = "b", rng.between(2, 4)
        elif roll < 4:
            fmt, n = "i", rng.between(1, 3)
        else:
            fmt, n = "", 1
        chunk = words[i : i + n]
        i += len(chunk)
        if spans and spans[-1][0] == fmt == "":
            spans[-1][1].extend(chunk)
        else:
            spans.append((fmt, list(chunk)))
    out = []
    for index, (fmt, chunk) in enumerate(spans):
        text = " ".join(chunk)
        if index < len(spans) - 1:
            text += " "
        out.append((fmt, text))
    return out


def _run(fmt: str, text: str) -> str:
    rpr = {"b": "<w:rPr><w:b/></w:rPr>", "i": "<w:rPr><w:i/></w:rPr>"}.get(fmt, "")
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, escape(text))


def _plain_paragraph(text: str) -> str:
    if not text:
        return "<w:p/>"
    return "<w:p>%s</w:p>" % _run("", text)


def _heading(style: str, text: str) -> str:
    return '<w:p><w:pPr><w:pStyle w:val="%s"/></w:pPr>%s</w:p>' % (style, _run("", text))


_SECT_PR = (
    "<w:sectPr>"
    '<w:pgSz w:w="12240" w:h="15840"/>'
    '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
    'w:header="720" w:footer="720" w:gutter="0"/>'
    "</w:sectPr>"
)

_DOCUMENT_HEAD = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body>"
)
_DOCUMENT_TAIL = _SECT_PR + "</w:body></w:document>"

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults>
<w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="en-US"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="259" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>
<w:style w:type="character" w:default="1" w:styleId="DefaultParagraphFont"><w:name w:val="Default Paragraph Font"/><w:uiPriority w:val="1"/><w:semiHidden/></w:style>
</w:styles>
"""

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"""

_RELS_ROOT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

_RELS_DOC = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""


def deterministic_zip(entries: list[tuple[str, bytes]]) -> bytes:
    """Zip ``entries`` in order with a fixed timestamp and fixed attributes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=_FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            zf.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    return buf.getvalue()


def _package(document_xml: str) -> bytes:
    return deterministic_zip(
        [
            ("[Content_Types].xml", _CONTENT_TYPES.encode("utf-8")),
            ("_rels/.rels", _RELS_ROOT.encode("utf-8")),
            ("word/document.xml", document_xml.encode("utf-8")),
            ("word/_rels/document.xml.rels", _RELS_DOC.encode("utf-8")),
            ("word/styles.xml", _STYLES.encode("utf-8")),
        ]
    )


def _correctness_lines() -> list[str]:
    fixtures = correctness_fixtures()
    return [fixtures[k].decode("utf-8").rstrip("\n") for k in ("unicode", "emoji", "bidi", "ime_committed")]


def _title(rng: _SplitMix64) -> str:
    return " ".join(rng.word().capitalize() for _ in range(rng.between(3, 6)))


def build_prose_docx(row: dict) -> dict:
    """Build one prose rung. Returns the docx bytes and their metadata."""
    words_total = int(row["words"])
    per = int(row.get("paragraph_words", PARAGRAPH_WORDS))
    if words_total < per or words_total % per:
        raise ValueError("prose rung words must be a positive multiple of %d" % per)
    rng = _SplitMix64(int(row.get("seed", SEED)))
    body_paragraphs = words_total // per
    parts: list[str] = [_DOCUMENT_HEAD]
    text_lines: list[str] = []
    headings = runs = 0
    article = section = 0
    for index in range(body_paragraphs):
        if index % HEADING1_EVERY == 0:
            article += 1
            section = 0
            title = "Article %d. %s" % (article, _title(rng))
            parts.append(_heading("Heading1", title))
            text_lines.append(title)
            headings += 1
            runs += 1
        elif index % HEADING2_EVERY == 0:
            section += 1
            title = "Section %d.%d %s" % (article, section, _title(rng))
            parts.append(_heading("Heading2", title))
            text_lines.append(title)
            headings += 1
            runs += 1
        words = _paragraph_words(rng, per)
        spans = _spans(rng, words)
        parts.append("<w:p>%s</w:p>" % "".join(_run(fmt, text) for fmt, text in spans))
        text_lines.append("".join(text for _, text in spans))
        runs += len(spans)
    for line in _correctness_lines():
        parts.append(_plain_paragraph(line))
        text_lines.append(line)
        runs += 1
    sentinel = "%s %s" % (SENTINEL_PREFIX, row["workload_id"])
    parts.append(_plain_paragraph(sentinel))
    text_lines.append(sentinel)
    runs += 1
    parts.append(_DOCUMENT_TAIL)
    docx = _package("".join(parts))
    text = "\n".join(text_lines)
    return {
        "workload_id": row["workload_id"],
        "docx": docx,
        "sha256": hashlib.sha256(docx).hexdigest(),
        "byte_size": len(docx),
        "word_count": words_total,
        "paragraph_count": body_paragraphs + headings + len(_correctness_lines()) + 1,
        "body_paragraph_count": body_paragraphs,
        "heading_count": headings,
        "run_count": runs,
        "sentinel": sentinel,
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "match_count": 0,
        "search_term": None,
        "unicode_class": "ascii",
        "shape": "prose",
        "builder_version": BUILDER_VERSION,
    }


_W_P = re.compile(rb"<w:p[ >/]")
_WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_paragraph_texts(document_xml: bytes) -> list[str]:
    """The text of every paragraph of ``word/document.xml``, in document order.

    The one extractor for both sides of the speed runner's check: the
    expectation is read from the input with it, the saved file is read with
    it. Namespace-aware (any prefix), entities decoded, ``w:delText`` is not
    text, and a paragraph nested in another (a text box) is its own entry, so
    no text is counted twice.
    """
    root = ET.fromstring(document_xml)
    out: list[str] = []

    def walk(elem, buf):
        for child in elem:
            if child.tag == _WNS + "p":
                own: list[str] = []
                slot = len(out)
                out.append("")
                walk(child, own)
                out[slot] = "".join(own)
            elif child.tag == _WNS + "t":
                if buf is not None:
                    buf.append(child.text or "")
            else:
                walk(child, buf)

    walk(root, None)
    return out


def _corpus(repo_root: Path) -> dict:
    path = repo_root / CORPUS_RELPATH
    docx = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(docx)) as zf:
        document = zf.read("word/document.xml")
    text = "\n".join(docx_paragraph_texts(document))
    return {
        "workload_id": "complex-corpus",
        "docx": docx,
        "sha256": hashlib.sha256(docx).hexdigest(),
        "byte_size": len(docx),
        "word_count": len(text.split()),
        "paragraph_count": len(_W_P.findall(document)),
        "body_paragraph_count": None,
        "heading_count": None,
        "run_count": None,
        "sentinel": None,
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "match_count": 0,
        "search_term": None,
        "unicode_class": "mixed",
        "shape": "corpus",
        "builder_version": "fixture/complex.docx",
    }


def _legacy(row: dict) -> dict:
    built = build_workload(row)
    fixtures = correctness_fixtures()
    body = built["body"] + fixtures["unicode"] + fixtures["emoji"] + fixtures["bidi"] + fixtures["ime_committed"]
    docx = docx_zip_bytes(body)
    lines = body.decode("utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return {
        "workload_id": row["workload_id"],
        "docx": docx,
        "sha256": hashlib.sha256(docx).hexdigest(),
        "byte_size": len(docx),
        "word_count": len(body.decode("utf-8").split()),
        "paragraph_count": len(lines),
        "body_paragraph_count": int(row["paragraphs"]),
        "heading_count": 0,
        "run_count": len(lines),
        "sentinel": None,
        "text": "\n".join(lines),
        "text_sha256": hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest(),
        "match_count": built["match_count"],
        "search_term": built["search_term"],
        "unicode_class": row["unicode_class"],
        "shape": str(row.get("shape") or "unknown"),
        "builder_version": "legacy-docx_zip_bytes/2",
    }


def ladder_row_for_env(row: dict) -> dict:
    """Describe a prose/corpus rung by the paragraphs of the DOCX actually served.

    The ladder's ``paragraphs`` is the prose body count; the package also holds
    headings, correctness lines and the sentinel (document and scroll already
    record the package count).
    """
    if row.get("shape") in ("prose", "corpus"):
        return {**row, "paragraphs": workload_docx(row["workload_id"])["paragraph_count"]}
    return row


# Edit lanes (input, resources) drop only this element. Load-only lanes keep
# the original complex-corpus package, protection and all.
_DOCUMENT_PROTECTION = re.compile(
    br"<w:documentProtection\b[^>]*/>|<w:documentProtection\b[^>]*>.*?</w:documentProtection>",
    re.DOTALL,
)
EDIT_LANES = frozenset({"input", "resources", "memory", "document", "warm_cold"})
EDIT_VARIANT = "complex-corpus-without-document-protection"


def strip_document_protection(docx: bytes) -> bytes:
    """Return a deterministic package with only ``w:documentProtection`` removed.

    Every other part is copied uncompressed-identical. ``word/settings.xml``
    loses that one element and nothing else. The zip is rewritten with the
    fixed timestamp used for prose packages, so the sha256 does not move
    between calls.
    """
    src = zipfile.ZipFile(io.BytesIO(docx))
    names = src.namelist()
    if "word/settings.xml" not in names:
        raise ValueError("complex fixture has no word/settings.xml")
    entries: list[tuple[str, bytes]] = []
    for name in names:
        data = src.read(name)
        if name == "word/settings.xml":
            data = _remove_document_protection(data)
        entries.append((name, data))
    return deterministic_zip(entries)


def _remove_document_protection(xml: bytes) -> bytes:
    updated, removed = _DOCUMENT_PROTECTION.subn(b"", xml, count=1)
    if removed != 1 or b"w:documentProtection" in updated:
        raise ValueError("expected exactly one w:documentProtection element")
    if updated == xml:
        raise ValueError("documentProtection strip did not change settings.xml")
    return updated


def workload_for_lane(workload_id: str, lane: str, repo_root=None) -> dict:
    """Bytes a lane loads.

    Input and resources load complex-corpus with document protection removed.
    Every other lane, and every other workload, gets ``workload_docx``.
    """
    meta = workload_docx(workload_id, repo_root)
    if lane not in EDIT_LANES or workload_id != "complex-corpus":
        return meta
    variant = strip_document_protection(meta["docx"])
    return {
        **meta,
        "docx": variant,
        "sha256": hashlib.sha256(variant).hexdigest(),
        "byte_size": len(variant),
        "fixture_variant": EDIT_VARIANT,
        "fixture_source_sha256": meta["sha256"],
    }


def workload_docx(workload_id: str, repo_root=None) -> dict:
    """Return the DOCX bytes and metadata for any size-ladder id.

    Runners put ``paragraph_count``, ``byte_size``, ``shape``,
    ``unicode_class`` and ``match_count`` from this result into the trial
    environment; they do not recompute them from the ladder row.
    """
    from perf.fixtures.profiles import size_ladder

    root = Path(repo_root) if repo_root is not None else _REPO
    row = next((r for r in size_ladder() if r["workload_id"] == workload_id), None)
    if row is None:
        raise ValueError("unknown workload %r" % (workload_id,))
    if row.get("shape") == "prose":
        return build_prose_docx(row)
    if row.get("shape") == "corpus":
        return _corpus(root)
    return _legacy(row)
