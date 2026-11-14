"""Document lane: the probe's own surface scan must stay linear in the page (#206).

``openingHeadings`` walked six ancestors of every matched node, asked each for
its headings, and tested each heading against every matched node. On Plate's
250,000-word page that scan took about 1,140 s of a load whose own scripts ran
21 s, inside the timed interval of C11 and C14.

The scan runs in the page, so it is tested in a page: the init script is taken
from ``document_probe.mjs`` as it ships.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

PROBE = Path(__file__).resolve().parents[1] / "runner" / "document_probe.mjs"
START = "const INIT_SCRIPT = "
END = "\n};\n\nasync function newPage"

# The scan as it was before #206, kept as the oracle for the text it returns.
REFERENCE = """
(selector) => {
  const matched = Array.from(document.querySelectorAll(selector));
  if (!matched.length) return [];
  const seen = new Set();
  const out = [];
  const takeHeading = (heading) => {
    if (!heading || seen.has(heading)) return;
    const tag = heading.tagName || '';
    if (tag.length !== 2 || tag[0] !== 'H' || tag[1] < '1' || tag[1] > '6') return;
    if (matched.some((node) => node === heading || node.contains(heading) || heading.contains(node))) return;
    seen.add(heading);
    out.push(heading.id);
  };
  for (const node of matched) {
    let parent = node.parentElement;
    for (let depth = 0; parent && depth < 6; depth += 1, parent = parent.parentElement) {
      for (const heading of parent.querySelectorAll('h1,h2,h3,h4,h5,h6')) takeHeading(heading);
    }
  }
  return out;
}
"""

COUNTERS = """
() => {
  window.__calls = { contains: 0, qsa: 0 };
  const contains = Node.prototype.contains;
  Node.prototype.contains = function (other) { window.__calls.contains += 1; return contains.call(this, other); };
  const qsa = Element.prototype.querySelectorAll;
  Element.prototype.querySelectorAll = function (sel) { window.__calls.qsa += 1; return qsa.call(this, sel); };
}
"""


def init_script() -> str:
    source = PROBE.read_text()
    start = source.index(START) + len(START)
    end = source.index(END, start) + 2
    return source[start:end]


def install(page, selector: str) -> None:
    args = {"docSel": selector, "pageSel": "", "minTextChars": 8, "signal": "dom_text",
            "documentSelector": "", "textWaitBudgetMs": 0, "canvasReadyExpr": ""}
    page.evaluate("(%s)(%s)" % (init_script(), json.dumps(args)))


def flat_page(paragraphs: int, headings: int) -> str:
    """Plate's shape: paragraphs and headings are siblings in one editor element."""
    every = max(1, paragraphs // headings)
    parts = []
    for index in range(paragraphs):
        if index % every == 0 and index // every < headings:
            parts.append('<h2 id="h%d">Heading %d</h2>' % (index // every, index // every))
        parts.append('<p class="doc-paragraph">Paragraph %d of the document body.</p>' % index)
    return '<div id="app"><div class="editor"><div class="slate">%s</div></div></div>' % "".join(parts)


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as pw:
        chromium = pw.chromium.launch()
        try:
            yield chromium
        finally:
            chromium.close()


def scan_calls(browser, paragraphs: int, headings: int) -> dict:
    page = browser.new_page()
    try:
        page.set_content(flat_page(paragraphs, headings))
        install(page, ".doc-paragraph")
        page.evaluate(COUNTERS)
        chars = page.evaluate("window.__docProbeSurface('dom_text').documentText.length")
        assert chars > 0
        return page.evaluate("window.__calls")
    finally:
        page.close()


def test_the_scan_does_not_grow_with_the_square_of_the_page(browser):
    small = scan_calls(browser, 500, 25)
    large = scan_calls(browser, 2000, 100)
    # Four times the page: a linear scan makes about four times the calls. The
    # scan before #206 made 2 x paragraphs x headings contains() calls (16 times).
    for name in ("contains", "qsa"):
        assert large[name] <= 6 * max(small[name], 1), (name, small, large)
    assert large["contains"] + large["qsa"] <= 20 * (2000 + 100), large


def test_the_headings_found_are_those_of_the_scan_it_replaces(browser):
    """Random small pages: same headings, same order, as the quadratic scan."""
    rng = random.Random(206)
    page = browser.new_page()
    try:
        for trial in range(60):
            counter = [0]

            def node(depth: int) -> str:
                counter[0] += 1
                ident = counter[0]
                kind = rng.choice(["p", "p", "h", "div", "div", "hp", "ph"])
                if depth >= 5 or kind == "p":
                    return '<p class="m" id="n%d">text %d</p>' % (ident, ident)
                if kind == "h":
                    return '<h%d id="n%d">head %d</h%d>' % (1 + ident % 6, ident, ident, 1 + ident % 6)
                if kind == "hp":  # a heading that holds a matched node
                    return '<h3 id="n%d">head %d <span class="m">in %d</span></h3>' % (ident, ident, ident)
                if kind == "ph":  # a matched node that holds a heading
                    return '<div class="m" id="n%d">text %d <h4 id="x%d">inner %d</h4></div>' % (ident, ident, ident, ident)
                return '<div id="n%d">%s</div>' % (ident, "".join(node(depth + 1) for _ in range(rng.randint(1, 4))))

            page.set_content("<div>%s</div>" % "".join(node(0) for _ in range(rng.randint(1, 6))))
            install(page, ".m")
            expected = page.evaluate("(%s)('.m')" % REFERENCE)
            # The scan is defined by a surface read (it closes over that read's selector).
            got = page.evaluate("(window.__docProbeSurface('dom_text'), window.__docProbeOpeningHeadings().map((h) => h.id))")
            assert got == expected, "trial %d" % trial
    finally:
        page.close()


def test_the_document_text_still_starts_with_the_opening_heading(browser):
    page = browser.new_page()
    try:
        page.set_content('<div class="editor"><h1>Article 1. Title</h1><p class="doc-paragraph">In property each completion.</p></div>')
        install(page, ".doc-paragraph")
        surface = page.evaluate("window.__docProbeSurface('dom_text')")
        assert surface["documentText"] == "Article 1. Title In property each completion."
        assert surface["text"] == "In property each completion."
    finally:
        page.close()


def test_one_surface_read_walks_each_element_once(browser):
    """``take`` read the element's text twice (once for timing, once for content)."""
    page = browser.new_page()
    try:
        page.set_content(flat_page(200, 10))
        install(page, ".doc-paragraph")
        # Counted inside one task, so the probe's own animation-frame tick is not in it.
        rects = page.evaluate("""() => {
          let count = 0;
          const rects = Element.prototype.getClientRects;
          Element.prototype.getClientRects = function () { count += 1; return rects.call(this); };
          try { window.__docProbeSurface('dom_text'); } finally { Element.prototype.getClientRects = rects; }
          return count;
        }""")
        # One text node per paragraph and per heading; one getClientRects each.
        assert rects <= 200 + 10 + 5
    finally:
        page.close()
