"""r3c12i: the C12 fixture pair is two consecutive plain body paragraphs.

The pair is taken from the docx, the same two strings for every editor. A
paragraph qualifies only when it is a direct ``w:body/w:p``, not a heading,
plain text (runs and text, formatting, bookmarks), non-empty after NFC and
whitespace normalization, and its text occurs once among the body paragraphs.
The two paragraphs are adjacent. A census miss keeps the refusal code and
puts the normalized census in the attempt's refusal_detail.
"""

from __future__ import annotations

import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from perf.runner import benchmark_document as bd
from perf.tests.test_schema import _env

REPO = Path(__file__).resolve().parents[2]
LANE = REPO / "perf" / "runner" / "lane_edit_burst.mjs"

PROSE_CARET = (
    "In property property each completion indirect tax completion use exhibit year incident laws "
    "any instrument new obligation has. Majeure partial license of damages as documents delivered "
    "person completion, requirement. Last accordance thereof condition, processing calendar, "
    "controller cure after may month. Renewal different therein that its relation fee clause except remedies."
)
PROSE_ANCHOR = (
    "Director partial connection timely also respect. Year its, is audit breach, controller "
    "requirements project any been project limitation rights minimum further records. Calendar timely "
    "provision loss herein current regulation. Have, records within requirement party waiver "
    "information payment, signature laws price daily whole. Appendix specification assignment "
    "signatory damages incident prompt instrument."
)
CORPUS_CARET = "run with unknown w14 attributes and w14 elements"
CORPUS_ANCHOR = "custom namespace attribute: cs complex-script text"

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def _pack(body: str) -> bytes:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="%s" xmlns:mc="%s"><w:body>%s</w:body></w:document>'
        % (_W_NS, _MC_NS, body)
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml.encode("utf-8"))
    return buffer.getvalue()


def _p(inner: str, style: str | None = None) -> str:
    ppr = '<w:pPr><w:pStyle w:val="%s"/></w:pPr>' % style if style else ""
    return "<w:p>%s%s</w:p>" % (ppr, inner)


def _t(text: str) -> str:
    return '<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % text


def _pair(body: str) -> tuple[str, str]:
    return bd.c12_fixture_body_pair(_pack(body))


def _node(body: str) -> dict:
    script = "import assert from 'node:assert/strict';\nconst mod = await import(%s);\n%s\n" % (
        json.dumps(str(LANE)),
        body,
    )
    proc = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


def _proc(stdout="", stderr="", returncode=0):
    from types import SimpleNamespace

    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode, args=["node"])


def test_prose_pair_is_unchanged_on_every_rung():
    from perf.fixtures.docx_workload import workload_for_lane

    for workload_id in ("prose-500w", "prose-5kw", "prose-50kw", "prose-250kw"):
        docx = workload_for_lane(workload_id, "document")["docx"]
        assert bd.c12_fixture_body_pair(docx) == (PROSE_CARET, PROSE_ANCHOR)


def test_complex_corpus_pair_is_the_first_adjacent_plain_paragraphs():
    from perf.fixtures.docx_workload import workload_for_lane

    caret, anchor = bd.c12_fixture_body_pair(workload_for_lane("complex-corpus", "document")["docx"])
    assert (caret, anchor) == (CORPUS_CARET, CORPUS_ANCHOR)
    assert "\u2011" not in anchor and "\u00ad" not in anchor and "\u2713" not in anchor


def test_symbol_tab_and_field_paragraphs_do_not_split_or_supply_the_pair():
    opening = _p(_t("Chapter"), style="Heading1") + _p(_t("Alpha plain unique."))
    bad = (
        "<w:r><w:tab/></w:r>"
        + _t("Tab separated")
        + '<w:r><w:br w:type="page"/></w:r>'
        + '<w:r><w:noBreakHyphen/></w:r>'
        + '<w:r><w:softHyphen/></w:r>'
        + '<w:r><w:sym w:font="Wingdings" w:char="F0FE"/></w:r>'
        + "<w:r><w:cr/></w:r>"
        + '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        + "<w:hyperlink>" + _t("linked") + "</w:hyperlink>"
        + "<mc:AlternateContent><mc:Fallback>" + _t("fallback") + "</mc:Fallback></mc:AlternateContent>"
    )
    plain = _p(_t("Beta plain unique.")) + _p(_t("Gamma plain unique."))
    assert _pair(opening + _p(bad) + plain) == ("Beta plain unique.", "Gamma plain unique.")
    # Adjacent requirement: a disqualified paragraph between two plain ones is not skipped over.
    with pytest.raises(bd.ProbeRefusal) as caught:
        _pair(opening + _p(bad) + _p(_t("Beta plain unique.")))
    assert caught.value.refusal_code == "fixture_body_pair_absent"


def test_duplicate_and_equivalent_text_is_not_the_pair():
    unique = _p(_t("Only once alpha.")) + _p(_t("Only once beta."))
    assert _pair(_p(_t("Dup text.")) + _p(_t("Dup text.")) + unique) == ("Only once alpha.", "Only once beta.")
    assert _pair(_p(_t("Alpha  beta")) + _p(_t("Alpha beta")) + unique) == ("Only once alpha.", "Only once beta.")
    nfd = "cafe\u0301 once"
    nfc = "caf\u00e9 once"
    assert _pair(_p(_t(nfd)) + _p(_t(nfc)) + unique) == ("Only once alpha.", "Only once beta.")


def test_empty_and_heading_break_adjacency_and_bookmarks_do_not():
    unique = _p(_t("Beta plain unique.")) + _p(_t("Gamma plain unique."))
    assert _pair(_p(_t("Alpha plain unique.")) + _p("") + unique) == ("Beta plain unique.", "Gamma plain unique.")
    assert _pair(
        _p(_t("Alpha plain unique.")) + _p(_t("A heading"), style="Heading2") + unique
    ) == ("Beta plain unique.", "Gamma plain unique.")
    bookmarked = (
        '<w:bookmarkStart w:id="1" w:name="Target"/>'
        + _t("Book marked text.")
        + '<w:bookmarkEnd w:id="1"/>'
    )
    assert _pair(_p(bookmarked) + _p(_t("Next plain text."))) == ("Book marked text.", "Next plain text.")


def test_table_paragraphs_are_not_body_paragraphs():
    table = "<w:tbl><w:tr><w:tc>" + _p(_t("Inside the table.")) + _p(_t("Also inside.")) + "</w:tc></w:tr></w:tbl>"
    assert _pair(table + _p(_t("After the table one.")) + _p(_t("After the table two."))) == (
        "After the table one.",
        "After the table two.",
    )


def test_census_miss_keeps_its_code_and_lands_in_refusal_detail(tmp_path, monkeypatch):
    detail = "fixture_paragraph_not_in_census: n=2 | Alpha paragraph | Beta paragraph"
    assert bd._c12_error_refusal_code(detail) == "fixture_paragraph_not_in_census"
    with pytest.raises(bd.ProbeRefusal) as caught:
        bd.c12_measured_sample({"error": detail})
    assert caught.value.refusal_code == "fixture_paragraph_not_in_census"
    assert "Alpha paragraph" in caught.value.reason

    payload = {"error": detail}
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _proc(stdout=json.dumps(payload)))
    with pytest.raises(bd.ProbeRefusal) as probed:
        bd._run_probe(["node", "probe"], editor_id="docxodus")
    assert probed.value.refusal_code == "fixture_paragraph_not_in_census"
    path = bd._write_refusal(
        attempt_dir=tmp_path,
        criterion_id="C12",
        editor_id="docxodus",
        lane="browser",
        env=_env(cache_state="warm_steady"),
        outcome="failed",
        failure_reason=probed.value.reason,
        refusal_code=probed.value.refusal_code,
    )
    trial = json.loads(path.read_text(encoding="utf-8"))
    assert trial["refusal_code"] == "fixture_paragraph_not_in_census"
    assert trial["refusal_detail"] == probed.value.reason
    assert "Alpha paragraph" in trial["refusal_detail"]
    assert "Beta paragraph" in trial["refusal_detail"]


def test_probe_refusal_keeps_the_census_texts_at_the_indexes(monkeypatch):
    payload = {
        "error": "caret_not_at_paragraph_start",
        "caret_placement": {
            "caretIndex": 4,
            "anchorIndex": 5,
            "caretText": "Caret words from the census",
            "anchorText": "Anchor words from the census",
        },
    }
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _proc(stdout=json.dumps(payload)))
    with pytest.raises(bd.ProbeRefusal) as caught:
        bd._run_probe(["node", "probe"], editor_id="folio")
    assert caught.value.refusal_code == "caret_not_at_paragraph_start"
    assert caught.value.facts["caret_index"] == 4
    assert caught.value.facts["anchor_index"] == 5
    assert caught.value.facts["caret_text"] == "Caret words from the census"
    assert caught.value.facts["anchor_text"] == "Anchor words from the census"


def test_locate_refusal_quotes_the_normalized_census():
    payload = _node(
        r"""
const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const nfd = '  cafe\u0301   double   space  ';
const long = 'HEAD' + 'B'.repeat(76) + 'TAIL20CHARSAREHERE!';
const entries = [
  { text: nfd },
  { text: long },
  ...Array.from({ length: 59 }, (_, i) => ({ text: 'row-' + i })),
];
const fn = (0, eval)(`(function(){ ${mod.C12_LOCATE_PAGE_SRC}; return c12LocateFixtureParagraphs; })()`);
const missing = fn(entries, 'not in the census', 'also missing', norm);
const matched = fn(
  [{ text: 'cafe\u0301 line' }, { text: 'Anchor line.' }],
  'caf\u00e9 line',
  'Anchor line.',
  norm,
);
console.log(JSON.stringify({ reason: missing.reason, ok: matched.ok, caretIndex: matched.caretIndex }));
"""
    )
    reason = payload["reason"]
    assert reason.startswith("fixture_paragraph_not_in_census: n=61 | ")
    assert "caf\u00e9 double space" in reason
    assert "cafe\u0301" not in reason
    assert "  double" not in reason
    assert "HEAD" + "B" * 76 in reason
    assert "TAIL20CHARSAREHERE!" not in reason
    assert "row-57" in reason
    assert "row-58" not in reason
    assert payload["ok"] is True
    assert payload["caretIndex"] == 0


def test_viewport_refusal_keeps_the_placed_census(monkeypatch):
    """A before-pass that finds the pair and then refuses (anchor off screen)
    still records the census text. The probe return has to carry the placement
    the caret step already resolved."""
    probe = (REPO / "perf" / "runner" / "document_probe.mjs").read_text(encoding="utf-8")
    start = probe.index("if (!before.ok)")
    block = probe[start:probe.index("const frameDeadline", start)]
    assert "caret_placement: bodyCaret" in block
    assert "before," in block
    lane = LANE.read_text(encoding="utf-8")
    assert "anchorTop: top" in lane
    assert "viewportHeight: Number(window.innerHeight)" in lane
    # The placed caret records only the caret. The viewport refusal's `before`
    # object carries the anchor in the page function's camelCase.
    payload = {
        "error": "anchor paragraph is off the viewport; a y-shift could not be attributed",
        "caret_placement": {
            "ok": True,
            "caretIndex": 7,
            "caretText": CORPUS_CARET,
        },
        "before": {
            "ok": False,
            "caretIndex": 7,
            "anchorIndex": 12,
            "caretText": CORPUS_CARET,
            "anchorText": CORPUS_ANCHOR,
            "anchorTop": 1307.890625,
            "viewportHeight": 900,
        },
    }
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _proc(stdout=json.dumps(payload)))
    with pytest.raises(bd.ProbeRefusal) as caught:
        bd._run_probe(["node", "probe"], editor_id="docxodus")
    assert caught.value.refusal_code is None
    assert caught.value.facts["caret_index"] == 7
    assert caught.value.facts["anchor_index"] == 12
    assert caught.value.facts["caret_text"] == CORPUS_CARET
    assert caught.value.facts["anchor_text"] == CORPUS_ANCHOR
    assert caught.value.facts["anchor_top"] == 1307.890625
    assert caught.value.facts["viewport_height"] == 900
