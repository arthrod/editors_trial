"""B9 fix — marker-only paragraphs and the shared edit adapter (#148, #155).

review-typing2-report.md BLOCKER: ``normalize_marked`` strips a
paragraph-leading marker on both sides; a paragraph that IS only a marker
(the brief's four caption ``v.`` lines, fixture lines 7, 13, 43, 51)
therefore contributes nothing, so an editor that drops it still passes.
The fix: marker-only lines leave no flat text but are collected; every
expected marker-only paragraph must be answered by a marker-only line or
by an absorbed empty list item (``data-list-marker`` with no text —
folio's absorbed markers), and nothing may manufacture a surplus.

#155.1: the typing lane drives the shared edit adapter
(``edit_surface.mjs``): enter edit mode (docxodus's ``#modeEditor``), the
caret click waits for editor focus, and the correctness read comes from
the adapter's surface kind — DOM innerText plus the absorbed-marker
census, a model text for canvas/docen, and for WordCraft only the
modified flag plus the trusted key count (no text claim).
"""

import asyncio
import io
import re
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]


def _sampler(page):
    from perf.tests.test_typing_marathon import FakeCDP, ResourceSampler

    def processes():
        return []

    resources = SimpleNamespace(
        clock=lambda: 0, process_snapshot=processes, profile_size=lambda: 0, network={}
    )
    return ResourceSampler(resources, page, FakeCDP(page))


def _type(page, text, **kwargs):
    from perf.runner.benchmark_typing import type_document

    async def witness(char):
        await page.type(char)
        from perf.tests.test_typing_marathon import no_frame

        return no_frame()

    return asyncio.run(
        type_document(
            page,
            _sampler(page),
            witness,
            text,
            selector=kwargs.pop("selector", "#editor"),
            witness_every=10**9,
            **kwargs,
        )
    )


CAPTION = (
    "IN THE SUPREME COURT\n"
    "LOPEZ\n"
    "v.\n"
    "UNITED STATES\n"
    "TOLEDO-FLORES\n"
    "v.\n"
    "UNITED STATES\n"
    "1. a. Under the Act, an alien may be removed.\n"
    "End of brief."
)


class DropMarkersPage:
    """A page that drops every ``v.`` paragraph from the correctness read.

    ``blank=True`` leaves the empty paragraph slot behind — the shape a real
    absorbed list item takes — instead of removing the line outright."""

    def __init__(self, drop="v.", absorbed=None, blank=False):
        self.text = ""
        self.sent = 0
        self.drop = drop
        self.absorbed = absorbed or []
        self.blank = blank
        self.keyboard = self

    async def type(self, char):
        self.sent += 1
        self.text += char

    async def press(self, key):
        assert key == "Enter"
        await self.type("\n")

    async def evaluate(self, script, arg=None):
        if "navigator.storage" in script:
            return {"longtaskCount": 0, "longtaskSumMs": 0, "usage": 0, "usageDetails": {}}
        if "data-list-marker" in script:
            return list(self.absorbed)
        if self.blank:
            return "\n".join("" if line.strip() == self.drop else line
                             for line in self.text.split("\n"))
        return "\n".join(line for line in self.text.split("\n") if line.strip() != self.drop)


def test_marker_only_paragraph_drop_fails_correctness():
    """The review's planted case: the editor loses the caption ``v.``
    paragraphs and the session must refuse, not publish."""
    result = _type(DropMarkersPage(), CAPTION)
    assert result["failure_reason"] == "text_mismatch", result
    assert result["refusal_code"] == "correctness_failure"


def test_marker_only_drop_inside_real_brief_fails():
    """Drop the four real ``v.`` caption lines out of the campaign brief."""
    from perf.runner.benchmark_typing import marker_only_strings, normalize_marked

    lines = (REPO / "perf/fixtures/briefs/sg-brief-13000w.txt").read_text().rstrip().split("\n")
    assert sum(1 for line in lines if line.strip() == "v.") == 4
    expected, _ = normalize_marked("\n".join(lines))
    actual, _ = normalize_marked("\n".join(line for line in lines if line.strip() != "v."))
    assert actual != expected or Counter(marker_only_strings("\n".join(lines))) != Counter(
        marker_only_strings("\n".join(l for l in lines if l.strip() != "v."))
    )
    result = _type(DropMarkersPage(), "\n".join(lines[:60]))
    assert result["failure_reason"] == "text_mismatch", result.get("failure_reason")


def test_marker_only_kept_literal_still_passes():
    """An editor that types ``v.`` literally sees no change in verdict."""
    from perf.tests.test_typing_marathon import FakePage

    result = _type(FakePage(), CAPTION)
    assert result["failure_reason"] is None, result
    assert result["marker_only"]["expected"] == ["v.", "v."]


def test_marker_only_absorbed_into_empty_list_items_passes():
    """Folio-shaped absorption: the ``v.`` text is gone from innerText but
    every paragraph survives as an empty list item AT ITS OWN POSITION
    carrying ``data-list-marker`` — the marker is evidence, not text."""
    absorbed = [{"index": 2, "marker": "v."}, {"index": 5, "marker": "v."}]
    page = DropMarkersPage(drop="v.", absorbed=absorbed, blank=True)
    result = _type(page, CAPTION)
    assert result["failure_reason"] is None, result
    assert result["marker_only"]["absorbed"] == absorbed


def test_marker_only_absorbed_with_renumbered_label_is_tolerated():
    """An absorbed marker-only item may carry the list's own label: the
    paragraph exists at the same index, and tolerance matches the
    marker+text class."""
    absorbed = [{"index": 2, "marker": "i."}, {"index": 5, "marker": "i."}]
    page = DropMarkersPage(drop="v.", absorbed=absorbed, blank=True)
    result = _type(page, CAPTION)
    assert result["failure_reason"] is None, result


def test_marker_only_surplus_line_fails():
    """An editor manufacturing a marker-only paragraph is not absorption."""

    class Surplus(DropMarkersPage):
        async def evaluate(self, script, arg=None):
            text = await super().evaluate(script, arg)
            if isinstance(text, str) and "data-list-marker" not in script:
                text += "\n12."
            return text

    result = _type(Surplus(drop=None), CAPTION)
    assert result["failure_reason"] == "text_mismatch"


def test_marker_only_partial_drop_fails():
    """Dropping one of two marker-only paragraphs still fails."""

    class DropOne(DropMarkersPage):
        async def evaluate(self, script, arg=None):
            text = await super().evaluate(script, arg)
            if isinstance(text, str) and "data-list-marker" not in script:
                parts = text.split("\n")
                if "v." in parts:
                    parts.insert(parts.index("v."), "v.")
                text = "\n".join(parts)
            return text

    result = _type(DropOne(), CAPTION)
    assert result["failure_reason"] == "text_mismatch"


def test_marker_only_strings_collects_the_caption_markers():
    from perf.runner.benchmark_typing import marker_only_strings

    assert marker_only_strings(CAPTION) == ["v.", "v."]
    assert marker_only_strings("12.\n1. a.\nrest") == ["12.", "a."]
    assert marker_only_strings("1. a. Under the Act\nrest") == []


def test_tolerated_marker_strings_record_absorbed_markers():
    """The attempt row records WHICH markers tolerance covered, not a bare
    count (review fix direction: strings, not tallies)."""
    import re as _re

    from perf.tests.test_typing_marathon import FakePage

    class AutoNumber(FakePage):
        async def evaluate(self, script, arg=None):
            text = await super().evaluate(script, arg)
            if isinstance(text, str):
                return _re.sub(r"\n1\. ", "\n", text)
            return text

    result = _type(AutoNumber(), "STATEMENT\n1. a. Under the Act\nEnd")
    assert result["failure_reason"] is None, result
    assert "1." in result["tolerated_marker_strings"]


# --- #155.1: the typing lane drives the shared edit adapter -----------------


def test_typing_bridge_imports_the_shared_edit_adapter():
    source = (REPO / "perf/runner/typing_session.mjs").read_text()
    assert "./edit_surface.mjs" in source
    for name in ("prepareEditSurface", "placeCaret", "readModifiedFlag"):
        assert name in source, name


def test_typing_bridge_exposes_adapter_operations():
    source = (REPO / "perf/runner/typing_session.mjs").read_text()
    for op in ("place_caret", "read_document", "modified_flag", "arm_trusted_keys", "trusted_key_count"):
        assert re.search(r"op === '%s'" % op, source), op


def test_type_document_accepts_oracle_overrides():
    import inspect

    from perf.runner.benchmark_typing import type_document

    params = inspect.signature(type_document).parameters
    assert "read_document" in params
    assert "flag_verifier" in params


def test_wordcraft_flag_session_records_exactly_what_is_verified():
    """WordCraft: the only oracle is the modified flag plus the trusted key
    count; the row must say exactly that and claim no text correctness.
    Since no unverified timing is publishable, the session is recorded
    ``unverified`` with the flag and key count kept as evidence."""
    from perf.tests.test_typing_marathon import FakePage

    page = FakePage()

    async def flag_verifier():
        return {"flag": {"evidence": "corpus \u2022 - WordCraft", "modified": True},
                "trusted_keys": 6, "min_keys": 6}

    result = _type(page, "abc\ndef", flag_verifier=flag_verifier)
    assert result["failure_reason"] == "document_text_not_readable", result
    assert result["outcome"] == "unverified"
    assert result["correctness_oracle"] == "editor_modified_flag"
    assert result["verified"] == ["modified_flag", "trusted_keys"]
    assert result["text_correctness"] is None
    assert result["trusted_keys"] == 6
    assert result["expected_min_keys"] == 6
    assert result["modified_flag"]["modified"] is True


def test_flag_unchanged_after_typing_records_the_flag_verdict():
    from perf.tests.test_typing_marathon import FakePage

    async def flag_verifier():
        return {"flag": {"evidence": "corpus - WordCraft", "modified": False},
                "trusted_keys": 6, "min_keys": 6}

    result = _type(FakePage(), "abc\ndef", flag_verifier=flag_verifier)
    assert result["failure_reason"] == "document_text_not_readable"
    assert result["refusal_code"] == "unverified"
    assert result["edit_refusal"] == "modified_flag_unchanged"


def test_flag_unreadable_is_unverified_not_correctness_failure():
    from perf.tests.test_typing_marathon import FakePage

    async def flag_verifier():
        return {"flag": None, "trusted_keys": 6, "min_keys": 6}

    result = _type(FakePage(), "abc\ndef", flag_verifier=flag_verifier)
    assert result["failure_reason"] == "document_text_not_readable"
    assert result["refusal_code"] == "unverified"
    assert result["edit_refusal"] == "modified_flag_unreadable"


def test_trusted_keys_below_min_is_unverified_evidence():
    from perf.tests.test_typing_marathon import FakePage

    async def flag_verifier():
        return {"flag": {"evidence": "corpus \u2022 - WordCraft", "modified": True},
                "trusted_keys": 3, "min_keys": 6}

    result = _type(FakePage(), "abc\ndef", flag_verifier=flag_verifier)
    assert result["failure_reason"] == "document_text_not_readable"
    assert result["edit_refusal"] == "trusted_keys_below_min"


def test_model_read_feeds_the_correctness_compare():
    """A model-surface oracle: the correctness read returns text plus the
    absorbed-marker census, both reaching the compare."""
    from perf.tests.test_typing_marathon import FakePage

    page = FakePage()

    async def read_document():
        return {"text": page.text, "absorbed_markers": []}

    result = _type(page, "abc\ndef", read_document=read_document)
    assert result["failure_reason"] is None, result
    assert result["correctness_oracle"] == "model_document_text"


def test_null_model_payload_is_a_labeled_refusal():
    """NIT: a None model payload names its refusal code, not a bare reason."""
    from perf.tests.test_typing_marathon import FakePage

    async def read_document():
        return {"text": None, "absorbed_markers": []}

    result = _type(FakePage(), "abc", read_document=read_document)
    assert result["failure_reason"] == "no_correctness_adapter"
    assert result["refusal_code"] == "unverified"


def test_correctness_read_is_outside_the_typing_wall():
    """NIT 1: the final read (a whole-document export on model surfaces) is
    not typing; the wall stops when the last key's work drained."""
    from perf.tests.test_typing_marathon import FakePage

    async def run():
        now = [0.0]
        page = FakePage()
        real_eval = page.evaluate

        async def evaluate(script, arg=None):
            if "setTimeout" in script:
                now[0] += 0.7
            return await real_eval(script, arg)

        page.evaluate = evaluate

        async def read_document():
            now[0] += 5.0  # an export-shaped read must not reach the wall
            return {"text": page.text, "absorbed_markers": []}

        from perf.tests.test_typing_marathon import no_frame

        async def witness(char):
            await page.type(char)
            return no_frame()

        from perf.runner.benchmark_typing import type_document

        return await type_document(
            page, _sampler(page), witness, "abc", selector="#e", clock=lambda: now[0],
            read_document=read_document,
        )

    result = asyncio.run(run())
    assert result["typing_wall_s"] == pytest.approx(0.7)
    assert result["throughput_chars_s"] == pytest.approx(3 / 0.7)


def test_expected_text_override_is_recorded_in_the_row():
    """NIT 4: a session may never silently compare against a substituted
    text — the override is asserted in the trial row when set."""
    from perf.tests.test_typing_marathon import FakePage

    result = _type(FakePage(), "abc", expected_text="abc")
    assert result.get("expected_text_override") is True
    result = _type(FakePage(), "abc")
    assert "expected_text_override" not in result


def test_every_editor_has_a_surface_and_a_lane_target():
    """All nine editors resolve through the shared adapter's surface table
    and the typing lane passes each editor's id to the bridge."""
    import importlib.util
    import json
    import subprocess

    spec = subprocess.run(
        ["node", "-e",
         "import('file://%s').then(m => console.log(JSON.stringify(Object.keys(m.EDIT_SURFACES))))"
         % (REPO / "perf/runner/edit_surface.mjs")],
        capture_output=True, text=True)
    surfaces = json.loads(spec.stdout)
    from perf.runner.benchmark_warm_cold import BROWSER_TARGETS

    for editor in ("plate", "docxodus", "superdoc", "genoffice", "canvas", "docen",
                   "eigenpal", "folio", "wordcraft"):
        assert editor in surfaces, editor
        assert editor in BROWSER_TARGETS, editor


def test_docxodus_and_superdoc_declare_typing_surfaces():
    from perf.runner.benchmark_warm_cold import BROWSER_TARGETS

    assert BROWSER_TARGETS["docxodus"]["typing_edit_selector"] == '#editorHost [contenteditable="true"]'
    assert BROWSER_TARGETS["docxodus"]["typing_usable_js"] == "window.__docxodus && window.__docxodus.rendered"
    assert "textContent" not in (BROWSER_TARGETS["docxodus"].get("typing_ready_js") or "")
    assert BROWSER_TARGETS["superdoc"]["typing_edit_selector"]


def test_place_caret_empty_document_clicks_and_waits_for_focus():
    """The adapter's empty-document path: click the declared surface, then
    hold until the editor — not the page body — holds focus."""
    source = (REPO / "perf/runner/edit_surface.mjs").read_text()
    assert "emptyDocument" in source
    body = source.split("export async function placeCaret")[1].split("readCaretScope")[0]
    assert "EDITOR_HAS_FOCUS" in body


def test_typing_fixture_carries_section_properties():
    """The lane's empty DOCX must end the body with w:sectPr: docxodus's
    paginated mount drops a sectPr-less body's paragraph outside the edit
    root, leaving no editable block (real-run RED: 30s CE timeout)."""
    import io
    import zipfile

    from perf.fixtures.generate import docx_zip_bytes

    zin = zipfile.ZipFile(io.BytesIO(docx_zip_bytes(b"\n", section_properties=True)))
    document = zin.read("word/document.xml").decode("utf-8")
    assert "<w:sectPr>" in document
    # Existing callers stay byte-identical without the flag.
    plain = zipfile.ZipFile(io.BytesIO(docx_zip_bytes(b"\n")))
    assert "<w:sectPr>" not in plain.read("word/document.xml").decode("utf-8")

    source = (REPO / "perf/runner/benchmark_typing.py").read_text()
    assert "docx_zip_bytes(b'\\n', section_properties=True)" in source


def test_dom_document_read_joins_every_matching_element():
    """querySelector's first match truncates a multi-element surface at its
    first block: docxodus wires one contenteditable per paragraph, genoffice
    and folio one region per page (real-run RED: divergence at offset 23,
    first paragraph only)."""
    source = (REPO / "perf/runner/edit_surface.mjs").read_text()
    body = source.split("READ_DOM_TEXT_WITH_MARKERS")[1].split("armTrustedKeyCounter")[0]
    assert "querySelectorAll" in body
    assert "querySelector(" not in body
    session = (REPO / "perf/runner/benchmark_typing.py").read_text()
    reader = session.split("async def read_document_text")[1].split("def divergence")[0]
    assert "querySelectorAll" in reader


def test_autocorrected_quotes_fold_but_missing_quote_fails():
    """A correct word processor turns typed straight quotes curly (docen and
    genoffice diverge at the brief's first " — real-run RED offset 787). The
    fold is symmetric: a dropped quote still fails."""
    from perf.runner.benchmark_typing import normalize_marked

    expected, _ = normalize_marked('an "aggravated felony."')
    curly, _ = normalize_marked('an \u201caggravated felony.\u201d')
    assert curly == expected
    missing, _ = normalize_marked('an aggravated felony.')
    assert missing != expected


def test_trusted_keys_count_layoutless_characters():
    """Chars with no key on the layout produce no keydown at all (the brief's
    §) — still trusted typed input, must count (real-run RED: 1933 < 1934).
    The counter needs a second channel beyond keydown: a trusted
    beforeinput/insertText observer, deduplicated so a mapped char counts once."""
    source = (REPO / "perf/runner/edit_surface.mjs").read_text()
    body = source.split("armTrustedKeyCounter")[1].split("trustedKeyCount")[0]
    assert "keydown" in body and "beforeinput" in body and "insertText" in body
    assert "pending" in body  # dedup: an insertText consumes its pending keydown


def test_flag_verifier_polls_for_the_title_frame():
    """WordCraft's dirty bullet rides the next egui frame — a single read
    right after the last key can miss it (real-run RED:
    modified_flag_unchanged with all keys trusted)."""
    source = (REPO / "perf/runner/benchmark_typing.py").read_text()
    body = source.split("async def flag_verifier")[1].split("elif surface_kind")[0]
    assert "deadline" in body and "modified" in body


def test_legacy_servers_receive_the_fixture_via_corpus_docx():
    """select_fixture only reached StaticHost: a legacy-spawned node server
    (wordcraft-host reads CORPUS_DOCX once at spawn) kept serving its own
    default corpus — wordcraft typed into fixture/complex.docx and the flag
    never flipped (real-run RED: edit_not_applied, modified=false)."""
    from perf.runner import browser_hosts

    target = {"env": {"PORT": "1"}}
    browser_hosts.select_fixture(target, Path("/tmp/zero.docx"))
    assert target["env"]["CORPUS_DOCX"] == "/tmp/zero.docx"


def test_correctness_read_waits_for_the_settled_document():
    """Worker-driven renderers commit the tail asynchronously: superdoc's
    second page mounted ~1s after the last key, so the snapshot read
    truncated the document mid-paragraph (real-run RED: divergence at
    normalized 1582, two marker-only paragraphs missing). The final read
    must poll until two reads agree before comparing."""
    source = (REPO / "perf/runner/benchmark_typing.py").read_text()
    body = source.split("read = await read_document()")[1].split("except Exception")[0]
    assert "deadline" in body and "stable_since" in body


def test_docx_paragraphs_split_on_real_elements_not_regex():
    """`_W_P`'s non-greedy `.*?</w:p>` mis-splits a w:p containing a nested
    w:p (textboxes, AlternateContent fallbacks): it glued the outer runs and
    cut the paragraph early (review NIT 5). Paragraphs now come from the
    parsed structure; a nested paragraph is its own segment."""
    import zipfile

    from perf.runner.docx_plaintext import docx_body_text, docx_body_text_and_absorbed

    document = (
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        b'<w:p><w:r><w:t>outer one</w:t></w:r><w:r><w:txbxContent>'
        b'<w:p><w:r><w:t>textbox</w:t></w:r></w:p></w:txbxContent></w:r>'
        b'<w:r><w:t> outer two</w:t></w:r></w:p>'
        b'<w:p><w:pPr><w:numPr/></w:pPr></w:p>'
        b'<w:p><w:r><w:t>last</w:t></w:r></w:p></w:body></w:document>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", document)
    buf.seek(0)
    assert docx_body_text(buf, paragraph_separator="|") == "outer one outer two|textbox||last"
    buf.seek(0)
    text, absorbed = docx_body_text_and_absorbed(buf)
    assert text == "outer one outer two\ntextbox\n\nlast"
    assert absorbed == [{"index": 2, "marker": None}]


def test_genoffice_stub_disables_autocorrect():
    """Genoffice's autocorrect rewrites typed text (`(c)` → `©`, smart quotes)
    — real-run RED divergence at normalized offset 928 was the app's own
    substitution, not a dropped key. The app persists the switches under
    `aidocs.autocorrect` and reads them per keystroke; the stub pins them off
    so the document equals the authored text."""
    stub = (REPO / "harness/ui/genoffice/desktop-stub.js").read_text()
    assert "aidocs.autocorrect" in stub
    for rule in ("smartQuotes", "symbols", "dashes", "autoLists", "ordinals"):
        assert f"{rule}: false" in stub
