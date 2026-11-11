"""B9 fix — model reads + the auto-numbering-tolerant correctness check.

Adversarial review (e2-logs/review-c10typ-report.md, BLOCKERs 1-2 on
``e22b689``): eigenpal's ``.docx-pages`` correctness surface is a virtualized
paint window, so a brief longer than the materialized pages can never match;
folio's correct auto-numbering removes typed ``1.``/``a.``/``(i)`` triggers
from the text, which the character-identical rule scored as content loss.

The repair this file pins:

- ``docx_body_text`` gains a paragraph separator so a save/export read (the
  model) produces paragraph-aware plaintext instead of glued runs.
- ``typing_model_js`` lets a target declare a model adapter for the
  correctness read (eigenpal: ``__DOCX_EDITOR_E2E__.saveBytes()`` → docx
  bytes → paragraph-aware text); the DOM innerText stays the default.
- ``normalize_marked`` is the single normaliser on BOTH sides: it ignores
  paragraph-leading auto-numbering markers ("1.", "a.", "(i)") and reports
  how many it ignored; the session records ``tolerated_list_markers`` as the
  count present on exactly one side (the tolerance actually exercised).
- ``typing_load_click_selector`` is the lazy-mount click inside the load
  measurement, separate from ``typing_click_selector`` (the focus click
  after load): an editor whose editable already exists is not clicked
  inside its ``load_ms``.
"""

import asyncio
import io
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


def test_docx_body_text_paragraph_separator():
    from perf.fixtures.generate import docx_zip_bytes
    from perf.runner.docx_plaintext import docx_body_text

    package = docx_zip_bytes(b"first para\n\n1. third para\n")
    assert docx_body_text(io.BytesIO(package)) == "first para1. third para"
    separated = docx_body_text(io.BytesIO(package), paragraph_separator="\n")
    assert separated == "first para\n\n1. third para"


def test_docx_body_text_decodes_xml_entities():
    """Serializers escape w:t content (&quot; &apos; &amp; &lt; &gt; &#x…;);
    the correctness read must see the typed characters, not the escapes."""
    import zipfile

    from perf.runner.docx_plaintext import docx_body_text

    document_xml = (
        '<w:document><w:body>'
        '<w:p><w:r><w:t>He said &quot;yes&quot; &amp; left &lt;now&gt;</w:t></w:r></w:p>'
        "<w:p><w:r><w:t>alien&apos;s &#x201C;quoted&#x201D; &#8212; done</w:t></w:r></w:p>"
        '</w:body></w:document>'
    ).encode()
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as zf:
        zf.writestr("word/document.xml", document_xml)
    package.seek(0)
    expected = "He said \"yes\" & left <now>\nalien's “quoted” — done"
    assert docx_body_text(package, paragraph_separator="\n") == expected


def test_normalize_marked_strips_auto_numbering_markers_only():
    from perf.runner.benchmark_typing import normalize_marked

    for marker in ("1.", "12.", "a.", "Z.", "i.", "iv.", "(i)", "(iv)", "(a)", "(12)", "1)", "b)"):
        text, count = normalize_marked(marker + " rest of paragraph")
        assert (text, count) == ("rest of paragraph", 1), marker
    for not_marker in (
        "Nos. 05-547 and 05-7664",
        "No. 05-547",
        "1a-11a. STATEMENT",
        "8 U.S.C. 1101(a)(43)",
        "mid 1. paragraph",
        "(ab) not a marker",
        "A- not a marker",
        "In the Supreme Court",
    ):
        text, count = normalize_marked(not_marker)
        assert count == 0, not_marker
        assert text == " ".join(not_marker.split())


def test_normalize_marked_counts_one_sided_tolerance():
    from perf.runner.benchmark_typing import normalize_marked

    expected, expected_markers = normalize_marked("STATEMENT\n1. a. Under the Act\nEnd")
    actual, actual_markers = normalize_marked("STATEMENT\na. Under the Act\nEnd")
    assert expected == actual == "STATEMENT Under the Act End"
    assert abs(expected_markers - actual_markers) == 1
    literal, same = normalize_marked("STATEMENT\n1. a. Under the Act\nEnd")
    assert abs(same - expected_markers) == 0


def test_normalize_still_collapses_whitespace():
    from perf.runner.benchmark_typing import normalize

    assert normalize("a\r\n\n b c") == "a b c"


def test_docx_model_read_beats_the_paint_window():
    """The virtualized-paint read fails while the model read passes — the
    exact BLOCKER 1 shape, through the real comparator."""
    from perf.tests.test_typing_marathon import FakePage
    from perf.fixtures.generate import docx_zip_bytes

    class VirtualizedPage(FakePage):
        async def evaluate(self, script, arg=None):
            if "saveBytes" in script:
                return {"docx_bytes": list(docx_zip_bytes(self.text.encode()))}
            # `.docx-pages` innerText: only the last paragraph is materialized.
            return self.text.split("\n")[-1]

    text = "first paragraph\nsecond paragraph\n1. third paragraph"
    result = _type(VirtualizedPage(), text)
    assert result["failure_reason"] == "text_mismatch"
    result = _type(VirtualizedPage(), text, model_js="saveBytes()")
    assert result["failure_reason"] is None
    assert result["tolerated_list_markers"] == 0


def test_absorbed_marker_passes_and_is_counted():
    """Folio-shaped: the editor converts a typed "1. " trigger into a real
    list marker, so the digits never reach the text."""
    import re

    from perf.tests.test_typing_marathon import FakePage

    class AutoNumberPage(FakePage):
        async def evaluate(self, script, arg=None):
            text = await super().evaluate(script, arg)
            if isinstance(text, str):
                return re.sub(r"\n1\. ", "\n", text)
            return text

    result = _type(AutoNumberPage(), "STATEMENT\n1. a. Under the Act\nEnd")
    assert result["failure_reason"] is None
    assert result["tolerated_list_markers"] == 1


def test_dropped_paragraph_still_fails_on_both_surfaces():
    from perf.tests.test_typing_marathon import FakePage
    from perf.fixtures.generate import docx_zip_bytes

    class DropDomParagraph(FakePage):
        async def evaluate(self, script, arg=None):
            text = await super().evaluate(script, arg)
            if isinstance(text, str):
                lines = text.split("\n")
                if len(lines) > 1:
                    del lines[1]
                return "\n".join(lines)
            return text

    class DropModelParagraph(FakePage):
        async def evaluate(self, script, arg=None):
            if "saveBytes" in script:
                lines = self.text.split("\n")
                del lines[1]
                return {"docx_bytes": list(docx_zip_bytes("\n".join(lines).encode()))}
            return ""

    # DOM correctness read (plate's path): a paragraph gone from innerText.
    result = _type(DropDomParagraph(), "first\nsecond paragraph\nthird")
    assert result["failure_reason"] == "text_mismatch"
    assert result["refusal_code"] == "correctness_failure"
    # Model correctness read (eigenpal's path): a paragraph gone from the docx.
    result = _type(DropModelParagraph(), "first\nsecond paragraph\nthird", model_js="saveBytes()")
    assert result["failure_reason"] == "text_mismatch"
    assert result["refusal_code"] == "correctness_failure"


def test_missing_model_adapter_is_a_refusal_not_a_mismatch():
    from perf.tests.test_typing_marathon import FakePage

    class NoHook(FakePage):
        async def evaluate(self, script, arg=None):
            if "saveBytes" in script:
                return None
            return await super().evaluate(script, arg)

    result = _type(NoHook(), "abc", model_js="saveBytes()")
    assert result["failure_reason"] == "no_correctness_adapter"


def test_model_js_also_accepts_plaintext_payloads():
    from perf.tests.test_typing_marathon import FakePage

    class TextHook(FakePage):
        async def evaluate(self, script, arg=None):
            if "model" in script:
                return {"text": self.text}
            return await super().evaluate(script, arg)

    result = _type(TextHook(), "abc", model_js="model()")
    assert result["failure_reason"] is None


def test_session_passes_load_click_and_model_overrides(tmp_path):
    """Integration: the lazy editable mounts via typing_load_click_selector
    inside load; the model_js adapter drives the correctness read."""
    pytest.importorskip("playwright.async_api")
    pytest.importorskip("psutil")
    from perf.runner.browser_hosts import StaticHost
    from perf.runner.benchmark_typing import session

    host = StaticHost(Path(__file__).parent / "fixtures")
    try:
        result, _rows = asyncio.run(
            session(
                {
                    "url": host.url + "/typing_lazy_editable.html",
                    "edit_selector": "[data-page-number]",
                    "typing_edit_selector": ".paged-editor__hidden-pm .ProseMirror",
                    "typing_present_selector": ".paged-editor__pages",
                    "typing_click_selector": "[data-page-number]",
                    "typing_load_click_selector": "[data-page-number]",
                    "ready_selector": "[data-page-number]",
                },
                "abc def",
                SimpleNamespace(budget_s=60, cadence_ms=0, sample_s=5,
                                witness_every=100, quiescence_s=0),
                tmp_path,
            )
        )
    finally:
        host.stop()
    assert result["failure_reason"] is None, result
    assert result["characters_typed"] == 7
    assert result["tolerated_list_markers"] == 0


def test_targets_declare_model_and_load_click_contracts():
    from perf.runner.benchmark_warm_cold import BROWSER_TARGETS

    eigenpal = BROWSER_TARGETS["eigenpal"]
    assert "saveBytes" in eigenpal["typing_model_js"]
    assert "__DOCX_EDITOR_E2E__" in eigenpal["typing_model_js"]
    # The editable exists without a click: none belongs inside load_ms.
    assert "typing_load_click_selector" not in eigenpal
    folio = BROWSER_TARGETS["folio"]
    assert folio["typing_load_click_selector"] == "[data-page-number]"
    assert folio["typing_click_selector"] == "[data-page-number]"


def test_dropped_paragraph_in_real_brief_still_fails():
    """A paragraph removed from the campaign fixture still diverges after
    marker-tolerant normalisation on both sides."""
    from perf.runner.benchmark_typing import divergence, normalize_marked

    lines = (REPO / "perf/fixtures/briefs/sg-brief-13000w.txt").read_text().rstrip().split("\n")
    assert any(line.startswith(("1.", "a.", "A.", "I.", "v.")) for line in lines)
    expected, expected_markers = normalize_marked("\n".join(lines))
    dropped = [line for index, line in enumerate(lines) if index != 200]
    actual, _ = normalize_marked("\n".join(dropped))
    assert expected_markers > 0
    assert actual != expected
    assert 0 < divergence(expected, actual) < len(expected)
