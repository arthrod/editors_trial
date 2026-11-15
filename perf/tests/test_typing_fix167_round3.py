"""Issue #167 round 3 — list-line indexes, GenOffice markers, symbol autocorrect.

Fixtures are trimmed from the 700-word DOM captures in
.scratch/typingfix2-mine/dom (not committed). The line index of
"a. Under the Immigration" is measured against the reader's own text,
because innerText inserts blank lines the sibling counter skips.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from perf.runner.benchmark_typing import prefix_marker_rest
from perf.tests.test_typing_fix167 import _type

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "typingfix3"
SURFACE = REPO / "perf/runner/edit_surface.mjs"


def _function_source(export_name, until_export):
    source = SURFACE.read_text()
    marker = f"export const {export_name}"
    if marker not in source:
        return None
    start = source.index(marker)
    end = source.index(until_export, start)
    return source[start:end].replace(f"export const {export_name} = ", f"const {export_name} = ")


def _dom_reader_js():
    body = _function_source("READ_DOM_TEXT_WITH_MARKERS", "export async function armTrustedKeyCounter")
    assert body is not None
    return (
        "(selector) => {\n"
        + body
        + "\nreturn READ_DOM_TEXT_WITH_MARKERS(selector);\n}"
    )


def _read_html(html, selector):
    from playwright.async_api import async_playwright

    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page()
            await page.set_content("<!doctype html><html><body>" + html + "</body></html>")
            result = await page.evaluate(_dom_reader_js(), selector)
            await browser.close()
            return result

    return asyncio.run(run())


def _line_of(text, needle):
    lines = text.split("\n")
    hits = [i for i, line in enumerate(lines) if needle in line]
    assert len(hits) == 1, hits
    return hits[0]


def test_folio_list_item_index_is_its_own_text_line():
    """Real Folio capture: data-list-marker on the paragraph, innerText blank lines between <p>s."""
    html = (FIXTURES / "folio-list.html").read_text()
    read = _read_html(html, ".ProseMirror")
    hit = _line_of(read["text"], "a. Under the Immigration")
    assert read["absorbed_markers"] == [
        {"index": hit, "marker": "%1.", "empty": False}
    ]


def test_folio_template_marker_uses_the_list_format_class():
    """Folio's data-list-marker stays the lvlText template %1. The format is the class.

    A lower-alpha item is not a decimal 1. Reporting %1. makes b. fail same_marker_class.
    """
    html = """
    <div class="ProseMirror" contenteditable="true">
      <p class="docx-list-numbered docx-list-lower-roman docx-list-level-0" data-list-marker="%1.">The foreign-country clause</p>
      <p class="docx-list-numbered docx-list-lower-alpha docx-list-level-0" data-list-marker="%1.">The INA defines an aggravated felony</p>
      <p class="docx-list-numbered docx-list-upper-roman docx-list-level-0" data-list-marker="%1.">Petitioner Toledo-Flores</p>
      <p class="docx-list-numbered docx-list-upper-alpha docx-list-level-0" data-list-marker="%1.)">The Statutory Definition</p>
      <p class="docx-list-numbered docx-list-decimal docx-list-level-0" data-list-marker="%1.">Petitioner Lopez</p>
    </div>
    """
    read = _read_html(html, ".ProseMirror")
    by_text = {entry["marker"]: entry for entry in read["absorbed_markers"]}
    assert by_text["i."]["index"] == _line_of(read["text"], "The foreign-country clause")
    assert by_text["a."]["index"] == _line_of(read["text"], "The INA defines")
    assert by_text["I."]["index"] == _line_of(read["text"], "Petitioner Toledo-Flores")
    assert by_text["A)"]["index"] == _line_of(read["text"], "The Statutory Definition")
    assert by_text["%1."]["index"] == _line_of(read["text"], "Petitioner Lopez")
    assert all(entry["empty"] is False for entry in read["absorbed_markers"])


def test_one_letter_roman_matches_a_longer_roman_marker():
    """I. is one letter, so the style helper calls it alpha. II. is roman.

    Folio's upper-roman item reports I. That label has to excuse II. at its
    own line. A non-roman letter, and a decimal, still must not.
    """
    excused_ii = _type(
        "II. The plain text of the relevant statut\n",
        "The plain text of the relevant statut\n",
        absorbed=[{"index": 0, "marker": "I.", "empty": False}],
    )
    assert excused_ii["failure_reason"] is None, excused_ii
    excused_i = _type(
        "I. Petitioner Toledo-Flores\n",
        "Petitioner Toledo-Flores\n",
        absorbed=[{"index": 0, "marker": "I.", "empty": False}],
    )
    assert excused_i["failure_reason"] is None, excused_i
    excused_lower = _type(
        "ii. The foreign-country clause\n",
        "The foreign-country clause\n",
        absorbed=[{"index": 0, "marker": "i.", "empty": False}],
    )
    assert excused_lower["failure_reason"] is None, excused_lower
    refused_letter = _type(
        "II. The plain text\n",
        "The plain text\n",
        absorbed=[{"index": 0, "marker": "A.", "empty": False}],
    )
    assert refused_letter["failure_reason"] == "text_mismatch", refused_letter
    refused_decimal = _type(
        "1. Body\n",
        "Body\n",
        absorbed=[{"index": 0, "marker": "I.", "empty": False}],
    )
    assert refused_decimal["failure_reason"] == "text_mismatch", refused_decimal


def test_decimal_template_does_not_excuse_an_alpha_marker():
    """%1. is decimal. It must not answer for b. — that is the different-class rule."""
    refused = _type(
        "b. The INA defines\n",
        "The INA defines\n",
        absorbed=[{"index": 0, "marker": "%1.", "empty": False}],
    )
    assert refused["failure_reason"] == "text_mismatch"
    excused = _type(
        "b. The INA defines\n",
        "The INA defines\n",
        absorbed=[{"index": 0, "marker": "a.", "empty": False}],
    )
    assert excused["failure_reason"] is None, excused


def test_plate_selector_uses_the_same_line_match():
    """Plate reads one contenteditable. The same margined paragraphs must not use sibling counts."""
    html = (FIXTURES / "folio-list.html").read_text()
    read = _read_html(html, '[contenteditable="true"]')
    hit = _line_of(read["text"], "a. Under the Immigration")
    assert read["absorbed_markers"] == [
        {"index": hit, "marker": "%1.", "empty": False}
    ]


def test_genoffice_data_marker_item_is_on_its_text_line():
    """Real GenOffice capture: div.doc-li[data-marker=1.] is the list item."""
    html = (FIXTURES / "genoffice-list.html").read_text()
    read = _read_html(html, ".doc-page.ProseMirror")
    hit = _line_of(read["text"], "a. Under the Immigration")
    assert read["absorbed_markers"] == [
        {"index": hit, "marker": "1.", "empty": False}
    ]


def test_docxodus_joined_blocks_keep_the_list_line():
    """Docxodus is one contenteditable per block. Joined lines, not sibling counts inside a block."""
    html = """
    <div id="editorHost">
      <div contenteditable="true" style="margin-bottom:12px">STATUTORY PROVISIONS INVOLVED</div>
      <div contenteditable="true" style="margin-bottom:12px"><br></div>
      <div contenteditable="true" style="margin-bottom:12px">The relevant statutory provisions are set out.</div>
      <div contenteditable="true" data-list-marker="%1." style="margin-bottom:12px">a. Under the Act</div>
    </div>
    """
    read = _read_html(html, '#editorHost [contenteditable="true"]')
    hit = _line_of(read["text"], "a. Under the Act")
    assert {"index": hit, "marker": "%1.", "empty": False} in read["absorbed_markers"]
    assert all(entry["index"] == hit for entry in read["absorbed_markers"])


def test_eigenpal_joined_paragraphs_keep_the_list_line():
    """Eigenpal's document read is one element per paragraph, joined in order."""
    html = """
    <div class="docx-page-content">
      <div data-paragraph-id="a" data-start="0" style="margin-bottom:12px">STATUTORY PROVISIONS INVOLVED</div>
      <div data-paragraph-id="b" data-start="0" style="margin-bottom:12px"><br></div>
      <div data-paragraph-id="c" data-start="0" style="margin-bottom:12px">The relevant statutory provisions are set out.</div>
      <div data-paragraph-id="d" data-start="0" data-list-marker="%1." style="margin-bottom:12px">a. Under the Act</div>
    </div>
    """
    read = _read_html(html, ".docx-page-content [data-paragraph-id][data-start]")
    hit = _line_of(read["text"], "a. Under the Act")
    assert read["absorbed_markers"] == [
        {"index": hit, "marker": "%1.", "empty": False}
    ]


def test_symbol_autocorrect_is_tolerated_and_disclosed():
    """(c) (r) (tm) become © ® ™. Count the glyphs. Do not treat them as a body edit."""
    expected = "section 924(c) of title 18, mark (r), brand (tm)."
    actual = "section 924\u00a9 of title 18, mark \u00ae, brand \u2122."
    result = _type(expected, actual)
    assert result["failure_reason"] is None, result
    assert result["tolerated_symbol_autocorrect_chars"] == 3


def test_uppercase_parenthetical_symbol_matches_the_same_glyph():
    """GenOffice turns (C) into the same © as (c). The typed case is the text."""
    result = _type("U.S.S.G. § 2L1.2(b)(1)(C) and 924(c).", "U.S.S.G. § 2L1.2(b)(1)\u00a9 and 924\u00a9.")
    assert result["failure_reason"] is None, result
    assert result["tolerated_symbol_autocorrect_chars"] == 2


def test_plain_case_change_without_a_symbol_still_refuses():
    result = _type("2L1.2(b)(1)(C)", "2L1.2(b)(1)(c)")
    assert result["failure_reason"] == "text_mismatch"
    assert result["tolerated_symbol_autocorrect_chars"] == 0


def test_other_symbol_change_still_refuses():
    """(d) → đ is not one of the three symbol autocorrects."""
    result = _type("section 924(d) of title 18", "section 924\u0111 of title 18")
    assert result["failure_reason"] == "text_mismatch"
    assert result["tolerated_symbol_autocorrect_chars"] == 0
    assert "divergence_expected_excerpt" in result
    assert "divergence_actual_excerpt" in result


def test_nbsp_after_a_dom_label_is_a_space():
    """SuperDoc paints NBSP after the list label. Marker parsing treats it as a space."""
    markers, rest = prefix_marker_rest("1.\xa0a. Under the Act")
    assert markers == ["1.", "a."]
    assert rest == "Under the Act"
    result = _type("1. a. Under the Act\n", "1.\xa0a. Under the Act\n")
    assert result["failure_reason"] is None, result


def test_superdoc_typing_read_uses_model_text_and_list_paragraphs():
    """Painted DOM is a decoy. getText glues paragraphs; newline-joined blocks are the read.

    A live probe (empty sectPr doc, type Hello / Enter / 1. a. Under the Act / Enter / Bye)
    returned getText 'Helloa. Under the ActBye' and one blocks.list entry per paragraph.
    The list label is numbering.marker, not part of the paragraph text. 'a. ' stayed.
    """
    body = _function_source("READ_SUPERDOC_TYPING_TEXT", "export async function prepareEditSurface")
    assert body is not None, "READ_SUPERDOC_TYPING_TEXT is not exported"
    session = (REPO / "perf/runner/typing_session.mjs").read_text()
    read_op = session.split("command.op === 'read_document'")[1].split("command.op === 'modified_flag'")[0]
    assert "editor_id" in read_op and "superdoc" in read_op
    assert "READ_SUPERDOC_TYPING_TEXT" in read_op
    surface = SURFACE.read_text()
    assert "superdoc: {\n    kind: 'dom'," in surface
    script = (
        "async () => {\n"
        + body
        + r"""
  const all = [
    { ordinal: 0, nodeType: 'paragraph', text: 'Hello', isEmpty: false },
    { ordinal: 1, nodeType: 'listItem', text: '', isEmpty: true,
      paragraphNumbering: { numId: 1, level: 0 },
      numbering: { marker: 'v.', kind: 'ordered', path: [5] } },
    { ordinal: 2, nodeType: 'listItem', text: 'a. Under the Act', isEmpty: false,
      paragraphNumbering: { numId: 2, level: 0 },
      numbering: { marker: '241.', kind: 'ordered', path: [241] } },
    { ordinal: 3, nodeType: 'paragraph', text: 'Bye', isEmpty: false },
  ];
  document.body.innerHTML = '<div class="superdoc-page">05-\n7664 judg\u00a0ment PAINTED</div>';
  const doc = {
    getText: async () => 'Helloa. Under the ActBye',
    blocks: { list: async (opts) => {
      const offset = Number(opts && opts.offset) || 0;
      const limit = Math.min(Number(opts && opts.limit) || 2, 2);
      return { total: all.length, blocks: all.slice(offset, offset + limit) };
    } },
  };
  window.__SUPERDOC_E2E__ = { activeEditor: { doc } };
  const good = await READ_SUPERDOC_TYPING_TEXT();
  doc.getText = async () => 'NOT THE BLOCKS';
  const bad = await READ_SUPERDOC_TYPING_TEXT();
  return { good, bad };
}
"""
    )
    from playwright.async_api import async_playwright

    async def run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page()
            await page.set_content("<!doctype html><html><body></body></html>")
            result = await page.evaluate(script)
            await browser.close()
            return result

    result = asyncio.run(run())
    assert result["bad"] is None
    good = result["good"]
    assert good["text"] == "Hello\n\na. Under the Act\nBye"
    assert "PAINTED" not in good["text"]
    assert good["absorbed_items"] == [
        {"index": 1, "marker": "v.", "empty": True},
        {"index": 2, "marker": "241.", "empty": False},
    ]
