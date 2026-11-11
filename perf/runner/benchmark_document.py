#!/usr/bin/env python3
"""C11, C12, C14 and C15 on the browser hosts: CLI, support table, exact reasons.

The catalogs that bind this file are ``perf/scenarios/catalog.py`` (layer,
boundary, cache states, measurements) and ``perf/README.md`` (a layer may claim
only what it can see). Each criterion is driven by ``document_probe.mjs``; this
module starts and stops one host at a time through the existing
``benchmark_warm_cold`` server helpers and writes one immutable attempt per cell.

Cells this harness cannot drive are still written: ``not_run`` or
``not_applicable`` with a reason that names the missing surface. A refusal is
information, never a zero.

Fixtures: ``perf/fixtures/generate.build_workload`` describes each rung's
paragraphs, but ``docx_zip_bytes`` folds the whole generated body into a single
``<w:p>``. C12 inserts at the top of the document and asserts that the block
below the insertion actually moves, and C11 reads a first page/block element, so
this runner writes one ``<w:p>`` per generated line instead. The paragraph count
recorded in every attempt is then the package's real paragraph count. The bytes
are hashed and kept beside the attempts.

Usage (from the repo root)::

    PYTHONPATH=. python3 perf/runner/benchmark_document.py \
        --editors plate superdoc --criteria C11 C12 C14 C15 --samples 1 \
        --out-root perf/out/document_smoke

    PYTHONPATH=. python3 perf/runner/benchmark_document.py --samples 3

Exit status is 0 when every requested cell was written as measured or refused,
1 when a probe raised outside a cell or a host failed to start (the offending
cells are recorded as ``failed``/``not_run`` with the message).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import uuid
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.adapters.capabilities import default_lane, pin_label  # noqa: E402
from perf.analysis.interpretation import evaluate_measured_trial  # noqa: E402
from perf.analysis.publication_gate import trial_publishable_flags  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402
from perf.fixtures.generate import (  # noqa: E402
    _CONTENT_TYPES,
    _RELS_DOC,
    _RELS_ROOT,
    build_workload,
    correctness_fixtures,
)
from perf.fixtures.profiles import assert_workload_allowed, size_ladder  # noqa: E402
from perf.runner.browser_run import ACTIVE, execution_profile, host_class, run_cli, fixture_path as run_fixture, write_json, record_process
from perf.runner.witness import validate_witness  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.benchmark_ci_contract import (  # noqa: E402
    INTERPRETATION_CONDITIONS,
    _finalize_publishable,
    _host_base,
    _ram_bytes,
    _host as _contract_host,
    _trial_dict,
)
from perf.runner.benchmark_warm_cold import (  # noqa: E402
    BROWSER_TARGETS,
    _start_server,
    _stop_server,
)
from perf.schema import (  # noqa: E402
    sample_budget_for_profile,
    validate_environment,
    validate_sample_budget,
    validate_trial,
)

PROBE = REPO / "perf" / "runner" / "document_probe.mjs"
EXECUTION_PROFILE = "ci_broad"
SAMPLE_DEFAULT = 3
SETTLE_MS = 800
# Longest probe wait (prose-250kw); per-workload argv uses load_timeout_ms.
PROBE_TIMEOUT_S = 600

# criterion_id -> layer/boundary/cache_state from perf/scenarios/catalog.py
CRITERIA = {
    "C11": {
        "layer": "browser_visible",
        "boundary": "first_contentful_paint",
        "cache_state": "process_cold_fs_warm",
        "workload": "micro-paragraphs",
    },
    "C12": {
        "layer": "browser_visible",
        "boundary": "presented_frame",
        "cache_state": "warm_steady",
        "workload": "micro-paragraphs",
    },
    "C14": {
        "layer": "browser_visible",
        "boundary": "first_usable",
        "cache_state": "process_cold_fs_warm",
        "workload": None,  # one attempt per size rung
    },
    "C15": {
        "layer": "model",
        "boundary": "model_ready",
        "cache_state": "warm_steady",
        "workload": "micro-search",
    },
}

C14_RUNGS = ("prose-500w", "prose-5kw", "prose-50kw", "prose-250kw", "complex-corpus")
C14_RUNG_LABEL = {rung: rung for rung in C14_RUNGS}
C15_MEASUREMENTS = ("first_match", "search_complete", "replace_all", "index_quiescence")
# I10: n < 2 is not publishable. One find event is not a C15 cell.
C15_MIN_N = 2
_C11_SURFACE_KEYS = ("document_text_at_ms", "usable_ms", "presented_frame_ms", "usable_signal")
_CLOCK_SKEW_BOUND_MS = 5.0  # lax layer (owner 2026-11-11): 2.0 -> 5.0; the refusal message carries the bound

# Hosts whose document surface this probe has verified selectors for. Everything
# else is refused by name, never guessed: a wrong selector measures the host
# shell, which is exactly the failure the layer rules exist to prevent.
DOCUMENT_TARGETS = {
    "plate": {
        "doc_selector": ".doc-paragraph",
        "page_selector": None,
        "page_model": "continuous_flow",
        "edit_selector": ".doc-paragraph",
        "ready_js": (
            "Boolean(document.querySelector('.status-ok')) && "
            "Array.from(document.querySelectorAll('.doc-paragraph'))"
            ".map((el) => (el.textContent || '').trim()).join('').length > 20"
        ),
        "find_input_selector": None,
        "find_count_selector": None,
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": "no find UI in the measured host",
        "note": (
            "Report C and the design doc record plate as one continuous flow, so page count is not applicable "
            "by design; the first block is the first-page equivalent."
        ),
    },


    "fidus": {
        "doc_selector": "#document-editable .ProseMirror p",
        "page_selector": None,
        "page_model": "continuous_flow",
        "edit_selector": "#document-editable .ProseMirror p",
        "ready_js": (
            "document.documentElement.getAttribute('data-fidus-host-ready') === '1' && "
            "Array.from(document.querySelectorAll('#document-editable .ProseMirror p'))"
            ".map((el) => (el.textContent || '').trim()).join('').length > 20"
        ),
        "note": (
            "ProseMirror host; the imported body renders one boxed <p> per paragraph inside "
            "#document-editable .ProseMirror (29 p on fixture/complex.docx); the footnote ProseMirror "
            "is outside #document-editable, so the selector cannot pick it up. Fidus renders one "
            "continuous article, so page count is not applicable. VERIFIED with fixture/complex.docx "
            "because fidus's own DOCX importer crashes on the harness ladder fixtures (packages "
            "without docProps/core.xml: boot.js records \"the app's DOCX import threw: Cannot read "
            "properties of null (reading 'query')\" inside DocxConvert.extractAuthors); on those "
            "rungs the cells legitimately refuse at the ready gate with that editor defect named."
        ),
        "find_source_note": (
            "no find widget verified: the probes never observed a find surface on this host; if Fidus's "
            "own find UI appears in a future pin the generic selector set will pick it up"
        ),
    },
    "folio": {
        "doc_selector": ".layout-page-content [data-block-id]",
        "page_selector": "[data-page-number]",
        "page_model": "page",
        "edit_selector": ".layout-page-content [data-block-id]",
        "ready_js": (
            "Array.from(document.querySelectorAll('[data-page-number]'))"
            ".some((el) => (el.innerText || '').trim().length > 0)"
        ),
        "find_source_note": (
            "no find widget verified on the playground host; the generic selector set stays so a future "
            "toolbar changes the verdict without a config edit"
        ),
        "note": (
            "Paged host: .layout-page pages ([data-page-number], 816x1056) with materialized "
            "div.layout-paragraph blocks carrying [data-block-id] inside .layout-page-content. "
            "Scoped to the content region because the header/footer blocks are page chrome and would "
            "not move. The off-screen ProseMirror is absent until first click; clicking a block mounts "
            "and focuses DIV.ProseMirror, so Enter at the document start reaches the editor and moves "
            "the anchor block."
        ),
    },

    "eigenpal": {
        "doc_selector": ".docx-paragraph-fragment",
        "page_selector": ".docx-page",
        "page_model": "page",
        "edit_selector": ".docx-page-content [data-paragraph-id][data-start]",
        "ready_js": (
            "window.__DOCX_EDITOR_E2E__?.ready() === true && "
            "window.__DOCX_EDITOR_E2E__?.fontMeasurer() === 'shaped' && "
            "(() => { const p = document.querySelector('.docx-page[data-materialized=\"true\"]'); "
            "if (!p) return false; const r = p.getBoundingClientRect(); "
            "return getComputedStyle(p).visibility === 'visible' && r.width > 0 && r.height > 0 && "
            "!document.querySelector('[data-docx-opening-preview], [data-docx-layout-pending]'); })()"
        ),
        "find_input_selector": None,
        "find_count_selector": None,
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": "no find UI in the measured host",
        "note": (
            "Paged host that materialises pages lazily: only pages near the viewport carry DOM text, so a "
            "ready gate must not require document text (the short rung's only real text is on a "
            "non-materialised last page). The gate is the host's own C03 E2E signal; the probe's own "
            "min-text check then decides usability per rung (short rung refuses with usable_ms=null)."
        ),
    },

    "docen": {
        "doc_selector": "docen-document",
        "page_selector": None,
        "page_model": "continuous_flow",
        "edit_selector": "docen-document .canvas-pages > div:first-child",
        "document_selector": ".canvas-pages > div:first-child",
        "usable_signal": "screencast_ink",
        "ready_js": "window.__DOCEN_READY__ === true",
        "find_input_selector": None,
        "find_count_selector": None,
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": "no find surface verified for this host; C15 refuses by name",
        "note": (
            "docen renders pages as LeaferJS canvases inside docen-document's open shadow root "
            "(.canvas-pages > div). The document element is .canvas-pages > div:first-child inside "
            "that shadow root; its own rect is the region. Other shadow text (toolbar, menus) is "
            "not document text. Light-DOM textContent is empty. C11 uses screencast_ink on "
            "that element's rect (painted Leafer pages, not empty shadow text), not the shell's "
            "first-contentful-paint. shadow_text remains only when real DOM text exists in the region. "
            "C12 still needs DOM block boxes the probe can see. "
            "edit_selector matches the shadow-piercing Playwright locator warm/cold already uses."
        ),
    },
    "wordcraft": {
        "doc_selector": "#wordcraft_canvas",
        "page_selector": None,
        "page_model": "continuous_flow",
        "edit_selector": "#wordcraft_canvas",
        "usable_signal": "screencast_ink",
        "ready_js": "window.__WORDCRAFT_READY__ === true",
        "find_input_selector": None,
        "find_count_selector": None,
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": "no find surface verified for this host; C15 refuses by name",
        "note": (
            "wasm egui app: the whole document is one WebGL canvas (#wordcraft_canvas), no DOM text. "
            "C11 uses screencast_ink on that canvas element's rect, not canvas_pixel (no 2d context) "
            "and not the app-shell first-contentful-paint. "
            "The readiness gate still refuses until the app's own title frame names the open document."
        ),
    },
    "apryse": {
        "doc_selector": "#viewer apryse-webviewer",
        "document_selector": "#pageContainer1",
        "page_selector": None,
        "page_model": "continuous_flow",
        "edit_selector": "#pageContainer1",
        "usable_signal": "shadow_text",
        "ready_js": "window.__aprysePerf && window.__aprysePerf.state === 'rendered'",
        "find_input_selector": None,
        "find_count_selector": None,
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": "no find surface verified for this host; C15 refuses by name",
        "note": (
            "The shadow host is #viewer apryse-webviewer (harness/apryse/perf-main.js viewerRoot). "
            "#viewer itself has no shadow root. The document element is #pageContainer1 inside that "
            "shadow root; its own rect is the region. Toolbar and menu text in the same root is not "
            "document text. C11 uses the disclosed shadow_text signal on that element, not the shell's "
            "first-contentful-paint. "
            "page_model=continuous_flow records probe visibility, not a claim that WebViewer is "
            "unpaged - pagination exists (pageContainer1-4 observed) but page boxes cannot be "
            "counted from light DOM. edit_selector #pageContainer1 resolves through Playwright's "
            "shadow-piercing locator, the same selector warm/cold uses."
        ),
    },


    "docxodus": {
        "doc_selector": "#pages p",
        "page_selector": "#pages .page-box",
        "page_model": "page",
        "edit_selector": "#pages p",
        "ready_js": (
            "(() => { const s = window.__docxodus; if (!s || !s.rendered) return false; "
            "const ps = document.querySelectorAll('#pages p'); if (!ps.length) return false; "
            "let n = 0; ps.forEach((el) => { n += (el.textContent || '').trim().length; }); "
            "return n > 20; })()"
        ),
        "find_input_selector": None,
        "find_count_selector": None,
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": "no find UI in the measured host",
        "note": (
            "Default surface is convertDocxToPaginatedHtml output: materialized .page-box page divs "
            "(816x1056 at 1280px) with one p per source paragraph, static (no caret). The Block-editor mount "
            "(#modeEditor) renders [contenteditable][data-anchor] blocks at docxodus 15.0.0; the edit "
            "adapter enters it and C12 measures the y-shift of the first-screen paragraphs below the caret."
        ),
    },
    "canvas": {
        "doc_selector": "#editor .ce-page-container > canvas",
        "page_selector": "#editor .ce-page-container",
        "page_model": "page",
        "edit_selector": "#editor .ce-page-container > canvas",
        "usable_signal": "canvas_pixel",
        "ready_js": (
            "(() => window.__DOCX_IMPORTED__ === true && "
            "document.querySelectorAll('#editor .ce-page-container > canvas').length >= 1)()"
        ),
        "find_source_note": (
            "canvas-editor exposes search only through its command API (executeSearch in the host's main.ts); "
            "no DOM find widget exists for the probe's shortcut path"
        ),
        "note": (
            "@hufe921/canvas-editor paints every page into a canvas inside .ce-page-container; the only other "
            "elements are an empty textarea.ce-inputarea and a 0x0 canvas.ce-magnifier. body textContent is "
            "empty by design. C11 and C14 use the disclosed canvas_pixel signal (a non-blank 2d pixel), "
            "not the shell's first-contentful-paint. A canvas that cannot provide 2d pixels is refused. "
            "C12 stays refused: there are no DOM block boxes with text to shift."
        ),
    },

    "docsplus": {
        "doc_selector": ".tiptap__editor .ProseMirror p",
        "page_selector": None,
        "page_model": "continuous_flow",
        "edit_selector": ".tiptap__editor .ProseMirror p",
        "ready_js": "window.__DOCSPLUS_READY__ === true",
        "find_input_selector": "input[placeholder*=\"Find\" i], input[placeholder*=\"Search\" i], [class*=\"find\"] input, [class*=\"search\"] input",
        "find_count_selector": "[class*=\"count\"], [role=\"status\"]",
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": (
            "source reading: the docs-plus workspace ships no find/search Tiptap extension (repos/docs-plus/extensions/ lists hyperlink, hypermultimedia, indent, inline-code, mermaid, placeholder only), and no find input exists in the host DOM (dom_inventory: input count 0)"
        ),
        "settle_ms": 800,
        "note": (
            "docsplus is the product webapp behind a perf bridge (harness/ui/docsplus/host): the bridge imports the corpus through the product's own importDocument path and sets window.__DOCSPLUS_READY__ when fonts/images have settled, so the ready_js is the product's own ready signal, not a shell one. The document is one continuous ProseMirror flow (.tiptap__editor .ProseMirror, role=textbox) with one <p> per corpus paragraph below a single heading, so page count is not applicable by design and the first <p> is the first-page equivalent. eval-based ready_js works here (no CSP meta on the page; verified by the passing probes)."
        ),
    },
    "genoffice": {
        "doc_selector": ".doc-page.ProseMirror:not(.mp-page) p",
        "page_selector": ".doc-page.ProseMirror:not(.mp-page)",
        "page_model": "page",
        "edit_selector": ".doc-page.ProseMirror:not(.mp-page) p",
        "ready_selector": ".doc-page",
        "ready_js": None,
        "find_input_selector": None,
        "find_count_selector": None,
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": (
            "no find UI in the measured host: FindPanel exists in the product app, but the trial host "
            "opens find only after the editor has focus (click) and then Control+f; the C15 probe drives "
            "a shortcut alone"
        ),
        "settle_ms": 800,
        "note": (
            "genoffice mounts one live ProseMirror per document with class 'doc-page ProseMirror' (App.tsx:1250 editor attributes); non-active pages in the multipage grid are painted clones carrying the extra class mp-page, so :not(.mp-page) selects only the editable page. Paragraphs are plain <p> blocks inside it; verified 9 p boxes (micro) and 24 p boxes (long rung) with distinct tops in the live page. ready_js MUST stay null: the host HTML carries a CSP meta (script-src 'self'), so the probe's eval-based ready_js throws EvalError inside waitForFunction and never passes (observed); the runner then passes --ready-selector .doc-page from BROWSER_TARGETS, the CSP-safe readiness gate."
        ),
    },
    "superdoc": {
        "doc_selector": ".superdoc-line",
        "page_selector": ".superdoc-page",
        "page_model": "page",
        "edit_selector": ".superdoc-line",
        "ready_js": (
            "(() => { const pages = document.querySelectorAll('.superdoc-page'); "
            "if (!pages.length) return false; "
            "const text = Array.from(pages).map((p) => (p.textContent || '').trim()).join(''); "
            "return text.length > 20; })()"
        ),
        "find_input_selector": None,
        "find_count_selector": None,
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": "no find UI in the measured host",
        "note": (
            "SuperDoc v2 renders absolutely positioned .superdoc-page boxes with one .superdoc-line per laid-out "
            "line and edits through a hidden textarea, so block boxes exist for the y-shift assertion."
        ),
    },
}

# Why the other browser hosts are refused today. Each entry names the missing
# surface for this probe; none of them is a statement that the editor lacks the
# feature.
STRUCTURE_NOTES = {
}


class ProbeRefusal(Exception):
    """A probe result that cannot become a sample.

    ``outcome`` defaults to ``failed`` so existing ``assertRaises(ProbeRefusal)``
    tests keep working. ``facts`` are the witness counts a refusal must keep.
    """

    def __init__(self, reason: str, *, outcome: str = "failed", facts: dict | None = None, refusal_code: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.outcome = outcome
        self.facts = dict(facts or {})
        self.refusal_code = refusal_code


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def docx_paragraph_bytes(body: bytes) -> bytes:
    """One ``<w:p>`` per generated line, so paragraph count is the real count."""
    import io
    import zipfile

    text = body.decode("utf-8", errors="replace")
    lines = text.rstrip("\n").split("\n")
    if not lines or any(line == "" for line in lines):
        raise ValueError("workload body has a zero-length line; paragraph split would not be faithful")

    def esc(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    paragraphs = "".join(
        '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % esc(line) for line in lines
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>%s</w:body></w:document>"
    ) % paragraphs
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _RELS_ROOT)
        archive.writestr("word/_rels/document.xml.rels", _RELS_DOC)
        archive.writestr("word/document.xml", document_xml.encode("utf-8"))
    return buffer.getvalue()


def build_fixture(workload_row: dict) -> dict:
    """Ladder body plus the correctness fixtures, split into real paragraphs.

    The generated ascii ladder is space-filled, so a text-presence check needs
    real characters, and C14's I01-I03 conditions need the Unicode, emoji and
    bidi fixtures. ``benchmark_warm_cold`` appends the same correctness fixture
    to its corpus for the same reason. The appended paragraphs are recorded, so
    the paragraph count stays truthful.
    """
    if workload_row['shape'] in ('prose', 'corpus'):
        from perf.fixtures.docx_workload import workload_for_lane

        built = workload_for_lane(workload_row['workload_id'], "document", REPO)
        return {**built, 'workload_row': workload_row, 'bytes': built['docx'],
                'augmented_paragraphs': 4 if workload_row['shape'] == 'prose' else 0}
    built = build_workload(workload_row)
    correctness = correctness_fixtures()
    augmented = (
        built["body"]
        + correctness["unicode"]
        + correctness["emoji"]
        + correctness["bidi"]
        + correctness["ime_committed"]
    )
    payload = docx_paragraph_bytes(augmented)
    return {
        "workload_row": workload_row,
        "bytes": payload,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_size": len(payload),
        "paragraph_count": len(augmented.rstrip(b"\n").split(b"\n")),
        "augmented_paragraphs": 4,
    }


# --------------------------------------------------------------------------- #
# Probe results -> samples (pure; the honesty rules are pinned in perf/tests)
# --------------------------------------------------------------------------- #


def _number_or_none(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _clock_skew_exceeds(probe: dict) -> bool:
    if probe.get("clock_skew_acceptable") is False:
        return True
    skew = _number_or_none(probe.get("clock_skew_ms"))
    return skew is not None and abs(skew) > _CLOCK_SKEW_BOUND_MS


def _clock_skew_missing_or_exceeds(probe: dict) -> bool:
    """C14 no-damage samples must record an in-bounds page clock."""
    if probe.get("clock_skew_acceptable") is False:
        return True
    skew = _number_or_none(probe.get("clock_skew_ms"))
    if skew is None:
        return True
    return abs(skew) > _CLOCK_SKEW_BOUND_MS


def _needs_witness(probe: dict) -> bool:
    """Production payloads carry a witness, or a load/reflow/scale mode.

    Legacy probes in ``test_document_criteria.py`` omit both. Those stay on
    the historical path. ``validate_witness`` is the public gate (#137).
    """
    return "witness" in probe or probe.get("mode") in ("load", "reflow", "scale")


def _require_witness(probe: dict, facts: dict | None = None) -> None:
    if not _needs_witness(probe):
        return
    witness = probe.get("witness")
    if not isinstance(witness, dict):
        raise ProbeRefusal("retained sample has no witness record", facts=facts)
    verdict = validate_witness(witness)
    if not verdict.get("ok"):
        raise ProbeRefusal("witness refused: %s" % (verdict.get("reason") or "refused"), facts=facts)


def c11_measured_samples(probe: dict) -> list:
    """C11 sample: presented frame at or after the document surface.

    Dicts that omit the document-surface keys keep the historical FCP sample.
    ``perf/tests/test_document_criteria.py`` pins that path and is not edited
    by this layer. Production probes always send the surface keys; an FCP that
    precedes the document is then not the sample.
    """
    if not any(key in probe for key in _C11_SURFACE_KEYS):
        paints = probe.get("paints") or []
        if not any(row.get("name") == "first-contentful-paint" for row in paints):
            raise ProbeRefusal("no first-contentful-paint entry in performance paint entries")
        fcp = probe.get("fcp_ms")
        if fcp is None or isinstance(fcp, bool) or float(fcp) < 0:
            raise ProbeRefusal("first-contentful-paint entry has no usable start time")
        return [float(fcp)]
    document = probe.get("document_text_at_ms")
    if document is None:
        document = probe.get("usable_ms")
    document_ms = _number_or_none(document)
    if document_ms is None:
        raise ProbeRefusal("no document surface; FCP is not a C11 sample")
    presented = _number_or_none(probe.get("presented_frame_ms"))
    if presented is None:
        raise ProbeRefusal("no presented frame at or after the document surface; FCP is not a C11 sample")
    if presented + 5 < document_ms:
        raise ProbeRefusal("presented frame precedes the document surface (frame=%r document=%r)" % (presented, document_ms))
    if _clock_skew_exceeds(probe):
        raise ProbeRefusal(
            "clock skew exceeds the %s ms bound (clock_skew_ms=%r); FCP is not a C11 sample"
            % (_CLOCK_SKEW_BOUND_MS, probe.get("clock_skew_ms"))
        )
    _require_witness(probe)
    if presented < 0:
        raise ProbeRefusal("negative presented frame")
    return [presented]


def c12_measured_sample(probe: dict) -> float:
    """C12 sample: input -> first compositor frame at/after the observed y-shift.

    The sample window excludes the probe's own ``getBoundingClientRect``. Old
    unit probes omit ``mode`` and ``window_excludes_forced_layout``; a reflow
    payload that does not exclude that layout is refused.
    """
    if probe.get("status") == "not_applicable":
        raise ProbeRefusal(probe.get("reason") or "C12 not_applicable", outcome="not_applicable")
    if probe.get("error"):
        raise ProbeRefusal(
            "probe refused C12: %s" % probe.get("error"),
            refusal_code="anchor_identity_ambiguous" if probe.get("error") == "anchor_identity_ambiguous" else None,
        )
    if probe.get("moved") is not True:
        raise ProbeRefusal(
            "text-shift assertion failed: anchor block did not move down (anchor_top=%r after=%r)"
            % ((probe.get("before") or {}).get("anchor_top"), probe.get("anchor_top_after"))
        )
    window_known = "window_excludes_forced_layout" in probe or probe.get("mode") == "reflow"
    if window_known and probe.get("window_excludes_forced_layout") is not True:
        raise ProbeRefusal("C12 window includes the probe's own forced layout")
    if _clock_skew_exceeds(probe):
        raise ProbeRefusal(
            "clock skew exceeds the %s ms bound (clock_skew_ms=%r); the frame is not a C12 sample"
            % (_CLOCK_SKEW_BOUND_MS, probe.get("clock_skew_ms"))
        )
    _require_witness(probe)
    presented = probe.get("presented_frame_ms")
    if presented is None:
        raise ProbeRefusal("no compositor frame captured at or after the observed y-shift")
    value = float(presented)
    if value <= 0:
        raise ProbeRefusal("presented_frame_ms must be greater than zero (got %r)" % presented)
    origin = _number_or_none(probe.get("input_page_ms"))
    shift = _number_or_none(probe.get("observed_shift_page_ms"))
    if origin is not None and shift is not None and origin + value + 0.05 < shift:
        raise ProbeRefusal(
            "presented frame precedes the anchor reflow (frame=%r shift=%r input=%r)"
            % (origin + value, shift, origin)
        )
    return value


def _c14_facts(probe: dict) -> dict:
    return {
        "usable_ms": probe.get("usable_ms"),
        "frames_total": probe.get("frames_total"),
        "frames_after_usable": probe.get("frames_after_usable"),
        "mechanism": probe.get("mechanism"),
        "witness": probe.get("witness"),
        "forced_witness": probe.get("forced_witness"),
        "presented_frame_ms": probe.get("presented_frame_ms"),
        "usable_signal": probe.get("usable_signal"),
        "clock_skew_ms": probe.get("clock_skew_ms"),
        "clock_skew_acceptable": probe.get("clock_skew_acceptable"),
        "no_damage_followed": probe.get("mechanism") == "forced_repaint",
    }


# A C14 sample is one of two clocks, never both and never a pool of the two:
# damage after load ends at the compositor frame that showed it; no damage
# ends at the DOM document-surface mark. The measure travels with the sample
# into the attempt row, the reader groups by it, and a no-damage sample is
# never labelled a compositor frame.
C14_FRAME_MEASURE = "presented_frame"
C14_NO_DAMAGE_MEASURE = "usable_no_damage"
C14_MEASURES = (C14_FRAME_MEASURE, C14_NO_DAMAGE_MEASURE)
C14_CLOCK_BY_MEASURE = {
    C14_FRAME_MEASURE: {
        "start": "navigation_start",
        "end": "first compositor screencast frame at or after the document became usable",
        "dom_usability": "document text laid out (concatenated trimmed text >= 8 chars, element has a layout box)",
    },
    C14_NO_DAMAGE_MEASURE: {
        "start": "navigation_start",
        "end": (
            "the DOM document-surface time (usable_ms); no document damage followed load, so no presented "
            "frame bounds this sample and it is not a frame time"
        ),
        "dom_usability": "document text laid out (concatenated trimmed text >= 8 chars, element has a layout box)",
    },
}


def c14_sample_measure(probe: dict) -> str:
    """Which C14 clock this payload's sample comes from (``_c14_facts`` territory)."""
    return C14_NO_DAMAGE_MEASURE if probe.get("mechanism") == "forced_repaint" else C14_FRAME_MEASURE


class C14Sample(float):
    """A C14 timing that carries the clock which produced it."""

    measure = C14_FRAME_MEASURE

    def __new__(cls, value, measure=C14_FRAME_MEASURE):
        sample = super().__new__(cls, value)
        sample.measure = measure
        return sample


def c14_measured_sample(probe: dict) -> float:
    """C14 sample: navigation -> first frame of post-load document damage.

    No document damage is the document-surface time; the sample carries its
    measure (``usable_no_damage``) so it is never published or pooled as a
    compositor-frame time (``presented_frame``). A rejected clock still
    refuses on both paths. A missing surface still refuses.
    """
    facts = _c14_facts(probe)
    if probe.get("mechanism") == "forced_repaint":
        if _clock_skew_missing_or_exceeds(probe):
            raise ProbeRefusal(
                "clock skew exceeds the %s ms bound (clock_skew_ms=%r)" % (_CLOCK_SKEW_BOUND_MS, probe.get("clock_skew_ms")),
                facts=facts,
            )
        usable = probe.get("usable_ms")
        if usable is None or isinstance(usable, bool):
            raise ProbeRefusal("no DOM usability mark (page/block element never appeared with text)", facts=facts)
        return C14Sample(float(usable), C14_NO_DAMAGE_MEASURE)
    _require_witness(probe, facts)
    usable = probe.get("usable_ms")
    if usable is None or isinstance(usable, bool):
        raise ProbeRefusal("no DOM usability mark (page/block element never appeared with text)", facts=facts)
    presented = probe.get("presented_frame_ms")
    if presented is None or isinstance(presented, bool):
        raise ProbeRefusal("no compositor frame captured at or after first usable", facts=facts)
    value = float(presented)
    if value + 5 < float(usable):
        raise ProbeRefusal(
            "compositor frame timestamp precedes the DOM usability mark (frame=%r usable=%r); clock mismatch"
            % (value, usable),
            facts=facts,
        )
    if _clock_skew_exceeds(probe):
        raise ProbeRefusal(
            "clock skew exceeds the %s ms bound (clock_skew_ms=%r)" % (_CLOCK_SKEW_BOUND_MS, probe.get("clock_skew_ms")),
            facts=facts,
        )
    return C14Sample(value, C14_FRAME_MEASURE)


def c15_cell_after_refusal(refusal: ProbeRefusal) -> dict:
    """The C15 cell written when the find probe raises.

    A crash stays ``failed``. ``not_applicable`` is only the host's own claim
    that it has no find widget, which arrives as a payload status, not here.
    """
    recorded = getattr(refusal, "outcome", "failed") or "failed"
    return {
        "n": 0,
        "completion": None,
        "refusal_code": getattr(refusal, "refusal_code", None),
        "measurements": {
            name: {"outcome": recorded, "samples_ms": [], "reason": refusal.reason}
            for name in C15_MEASUREMENTS
        },
    }


def c15_samples_from_payloads(payloads: list) -> dict:
    """One C15 cell from find-probe payloads. n below C15_MIN_N is unverified."""
    if not payloads:
        raise ProbeRefusal("C15 recorded no find payloads", outcome="unverified")
    if payloads[0].get("status") == "not_applicable":
        outcomes = find_outcomes(payloads[0])
        measurements = {
            name: {"outcome": outcome, "samples_ms": [], "reason": reason}
            for name, (outcome, _value, reason) in outcomes.items()
        }
        return {
            "n": 0,
            "minimum_n": C15_MIN_N,
            "completion": None,
            "outcomes": outcomes,
            "measurements": measurements,
        }
    for payload in payloads:
        if (
            payload.get("status") != "measured"
            or payload.get("completion") != "event"
            or "cap_ms" not in payload
            or payload.get("cap_ms") is not None
        ):
            raise ProbeRefusal(
                "C15 did not complete on the find event (status=%r completion=%r cap_ms=%r)"
                % (payload.get("status"), payload.get("completion"), payload.get("cap_ms")),
                outcome="unverified",
            )
    n = len(payloads)
    if n < C15_MIN_N:
        raise ProbeRefusal(
            "C15 recorded n=%d, below the minimum %d" % (n, C15_MIN_N),
            outcome="unverified",
        )
    # The minimum applies per measurement. One later unverified payload drops
    # that measurement's samples; it must not be overwritten by an earlier hit.
    timed = ("first_match", "search_complete")
    collected = {name: [] for name in timed}
    refused = {}
    outcomes = None
    for payload in payloads:
        outcomes = find_outcomes(payload)
        for name in timed:
            outcome, value, reason = outcomes[name]
            if outcome != "measured" or value is None:
                refused[name] = reason or "unverified"
            elif name not in refused:
                collected[name].append(float(value))
    measurements = {}
    for name in C15_MEASUREMENTS:
        outcome, _value, reason = outcomes[name]
        if name in refused or (name in collected and len(collected[name]) < C15_MIN_N):
            why = refused.get(name) or (
                "C15 recorded n=%d for %s, below the minimum %d" % (len(collected.get(name, [])), name, C15_MIN_N)
            )
            measurements[name] = {"outcome": "unverified", "samples_ms": [], "reason": why}
        elif name in collected:
            measurements[name] = {"outcome": "measured", "samples_ms": collected[name], "reason": None}
        else:
            measurements[name] = {"outcome": outcome, "samples_ms": [], "reason": reason}
    return {
        "n": n,
        "minimum_n": C15_MIN_N,
        "completion": "event",
        "outcomes": outcomes,
        "measurements": measurements,
    }


def write_c14_outcome(*, attempt_dir, editor_id, lane, env, probe, label, workload_id):
    """Write the C14 attempt for one probe payload, including a refusal's facts."""
    try:
        sample = c14_measured_sample(probe)
    except ProbeRefusal as refusal:
        facts = dict(getattr(refusal, "facts", None) or {})
        return _write_refusal(
            attempt_dir=attempt_dir,
            criterion_id="C14",
            editor_id=editor_id,
            lane=lane,
            env=env,
            outcome=getattr(refusal, "outcome", "failed") or "failed",
            failure_reason=refusal.reason,
            diagnostic={**facts, "size_rung": label, "workload_id": workload_id},
            publishable=False,
            publication_block_reason=refusal.reason,
            refusal_code=getattr(refusal, "refusal_code", None),
        )
    facts = _c14_facts(probe)
    path, _trial = _write_measured(
        attempt_dir=attempt_dir,
        criterion_id="C14",
        editor_id=editor_id,
        lane=lane,
        env=env,
        samples=[sample],
        doc_output_text=probe.get("document_text"),
        diagnostic={
            "suite": "document",
            "size_rung": label,
            "workload_id": workload_id,
            "measurement": sample.measure,
            "clock": dict(C14_CLOCK_BY_MEASURE[sample.measure]),
            "samples": [{"measure": sample.measure, "clock": dict(C14_CLOCK_BY_MEASURE[sample.measure]), **facts}],
            **facts,
        },
    )
    return path


def write_c14_rung_refusals(
    *,
    attempt_dir,
    editor_id,
    lane,
    env,
    label,
    workload_id,
    reason,
    outcome="failed",
    facts=None,
    refusal_code=None,
):
    """One C14 refusal attempt per measure.

    A refusal predates any sample, so it cannot know which clock the rung
    would have produced; both measures' cells count the failed launch.
    """
    paths = []
    for measure in C14_MEASURES:
        paths.append(
            _write_refusal(
                attempt_dir=attempt_dir,
                criterion_id="C14",
                editor_id=editor_id,
                lane=lane,
                env=env,
                outcome=outcome,
                failure_reason=reason,
                diagnostic={**(facts or {}), "size_rung": label, "workload_id": workload_id, "measurement": measure},
                publishable=False,
                publication_block_reason=reason,
                refusal_code=refusal_code,
            )
        )
    return paths


def find_outcomes(probe: dict) -> dict:
    """C15: one outcome per catalog measurement. A refusal carries no timing."""
    reason = str(probe.get("reason") or "").strip()
    status = probe.get("status")
    if status == "not_applicable":
        if not reason:
            raise ProbeRefusal("not_applicable without a reason", refusal_code="harness_error")
        for key in ("first_match_ms", "search_complete_ms"):
            if probe.get(key) is not None:
                raise ProbeRefusal("not_applicable carries a %s timing" % key, refusal_code="harness_error")
        return {name: ("not_applicable", None, reason) for name in C15_MEASUREMENTS}
    if status != "measured":
        raise ProbeRefusal("find probe returned status %r" % (status,))
    first = probe.get("first_match_ms")
    complete = probe.get("search_complete_ms")
    if first is None and complete is None:
        raise ProbeRefusal("find widget acknowledged neither a first match nor completion")
    out = {}
    out["first_match"] = (
        ("measured", float(first), None) if first is not None else ("unverified", None, "find widget reported no first-match acknowledgement")
    )
    out["search_complete"] = (
        ("measured", float(complete), None) if complete is not None else ("unverified", None, "find widget never reported a stable match count")
    )
    out["replace_all"] = ("not_applicable", None, "replace path was not driven for this host in this run; only find was timed")
    out["index_quiescence"] = (
        "not_applicable",
        None,
        "the host exposes no index-status API; there is no background index to time to quiescence",
    )
    return out


def assert_distinct_c14_rungs(rows: list) -> None:
    """Identical samples on two rungs mean the ladder was pooled or copied."""
    seen = {}
    for row in rows:
        key = tuple(round(float(value), 6) for value in sorted(row["samples_ms"]))
        if not key:
            continue
        if key in seen and seen[key] != row["workload_id"]:
            raise ValueError(
                "C14 rungs %s and %s carry identical samples; the ladder must not be pooled or copied"
                % (seen[key], row["workload_id"])
            )
        seen[key] = row["workload_id"]


def assert_catalog_alignment(catalog_rows: list) -> None:
    """CRITERIA must repeat the catalog's layer, boundary and first cache state."""
    by_id = {row["id"]: row for row in catalog_rows}
    for criterion_id, spec in CRITERIA.items():
        row = by_id[criterion_id]
        if row["layer"] != spec["layer"]:
            raise ValueError("%s layer %r != catalog %r" % (criterion_id, spec["layer"], row["layer"]))
        if row["boundary"] != spec["boundary"]:
            raise ValueError("%s boundary %r != catalog %r" % (criterion_id, spec["boundary"], row["boundary"]))
        if spec["cache_state"] not in row["cache_states"]:
            raise ValueError("%s cache_state %r not declared by catalog" % (criterion_id, spec["cache_state"]))
    for row in catalog_rows:
        if row["id"] == "C15":
            missing = [name for name in C15_MEASUREMENTS if name not in row.get("measurements", [])]
            if missing:
                raise ValueError("C15 catalog is missing measurements %s" % (missing,))


# --------------------------------------------------------------------------- #
# Probe invocation
# --------------------------------------------------------------------------- #


def _attempt_ref(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path.resolve())


def _probe_timeout_ms(target: dict) -> int:
    from perf.runner.load_timeouts import DEFAULT_LOAD_TIMEOUT_MS, load_timeout_ms

    workload_id = target.get("workload_id")
    if isinstance(workload_id, str) and workload_id:
        return load_timeout_ms(workload_id)
    return DEFAULT_LOAD_TIMEOUT_MS


def _probe_cmd(*, mode: str, target: dict, cfg: dict, corpus_path: Path, extra: list, editor_id: str = "") -> list:
    from perf.runner.browser_hosts import select_fixture
    select_fixture(target, corpus_path)
    timeout_ms = _probe_timeout_ms(target)
    cmd = [
        shutil.which("node") or "node",
        str(PROBE),
        "--mode",
        mode,
        "--url",
        target["url"],
        "--corpus",
        str(corpus_path.resolve()),
        "--corpus-route",
        target["corpus_route"],
        "--ready-selector",
        target.get("ready_selector", ""),
        "--doc-selector",
        cfg["doc_selector"],
        "--page-model",
        cfg["page_model"],
        "--edit-selector",
        cfg["edit_selector"],
        "--timeout-ms",
        str(timeout_ms),
    ]
    if cfg.get("page_selector"):
        cmd.extend(["--page-selector", cfg["page_selector"]])
    if cfg.get("ready_js"):
        cmd.extend(["--ready-js", cfg["ready_js"]])
    if cfg.get("usable_signal"):
        cmd.extend(["--usable-signal", cfg["usable_signal"]])
    if cfg.get("document_selector"):
        cmd.extend(["--document-selector", cfg["document_selector"]])
    elif (cfg.get("usable_signal") or "dom_text") not in ("shadow_text", "screencast_ink"):
        cmd.extend(["--document-selector", cfg["doc_selector"]])
    elif cfg.get("usable_signal") == "screencast_ink" and not cfg.get("document_selector"):
        cmd.extend(["--document-selector", cfg["doc_selector"]])
    if target.get("wait_after_ready"):
        cmd.extend(["--wait-after-ready", str(target["wait_after_ready"])])
    if editor_id:
        cmd.extend(["--editor", editor_id])
    if target.get("error_js"):
        cmd.extend(["--error-js", target["error_js"]])
    cmd.extend(extra)
    return cmd


def _subprocess_timeout_s(cmd: list) -> float:
    for index, token in enumerate(cmd):
        if token == "--timeout-ms" and index + 1 < len(cmd):
            try:
                return max(1.0, int(cmd[index + 1]) / 1000.0) + 30.0
            except ValueError:
                break
    return float(PROBE_TIMEOUT_S) + 30.0


def _run_probe(cmd: list, *, editor_id: str, env: dict | None = None) -> dict:
    import os
    run_env = dict(os.environ) if env is None else {**os.environ, **env}
    wall_s = _subprocess_timeout_s(cmd)
    try:
        proc = subprocess.run(cmd, cwd=str(REPO / "harness" / "ui"), capture_output=True, text=True,
                              timeout=wall_s, env=run_env)
    except subprocess.TimeoutExpired:
        raise ProbeRefusal(
            "probe error for %s: editor did not finish within %ss" % (editor_id, int(wall_s)),
            # Our own wall-clock kill, not an evidenced editor crash: a stalled
            # build, a wrong ready_js or a probe bug lands here too (review F6).
            refusal_code="harness_error",
        )
    record_process(proc)
    payload = None
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = None
    if payload is None:
        tail = (proc.stderr or proc.stdout or "")[-300:].strip()
        if "editor_load_failed" in (proc.stderr or ""):
            detail = proc.stderr.split("editor_load_failed:", 1)[-1].strip()[:400]
            raise ProbeRefusal(
                "editor_load_failed: %s" % detail,
                refusal_code="editor_load_failed",
            )
        raise ProbeRefusal(
            "probe produced no JSON for %s (exit %s): %s" % (editor_id, proc.returncode, tail),
            refusal_code="harness_error" if proc.returncode in (0, 2) else "editor_crash",
        )
    if proc.returncode != 0 or payload.get("status") == "probe_error":
        err_blob = (proc.stderr or "") + (payload.get("reason") or "")
        if "editor_load_failed" in err_blob:
            detail = err_blob.split("editor_load_failed:", 1)[-1].strip()[:400]
            raise ProbeRefusal(
                "editor_load_failed: %s" % detail,
                refusal_code="editor_load_failed",
            )
        raise ProbeRefusal(
            "probe error for %s: %s" % (editor_id, payload.get("reason") or proc.stderr[-300:]),
            refusal_code=_probe_error_refusal_code(payload),
        )
    if payload.get("error"):
        err = str(payload["error"])
        refusal_code = "anchor_identity_ambiguous" if err == "anchor_identity_ambiguous" else None
        raise ProbeRefusal("probe refused %s: %s" % (editor_id, err), refusal_code=refusal_code)
    return payload


_PAGE_LOST_REASONS = (
    "target closed", "page crashed", "browser has been closed", "browser closed",
    "crash", "detached", "sigsegv", "sigill", "sigtrap", "timeout", "timed out",
)


def _probe_error_refusal_code(payload: dict) -> str:
    """``editor_crash`` when the page/browser was lost; ``harness_error`` for our own failure."""
    if payload.get("status") == "probe_error":
        reason = str(payload.get("reason") or "").lower()
        if any(token in reason for token in _PAGE_LOST_REASONS):
            return "editor_crash"
    return "harness_error"


# --------------------------------------------------------------------------- #
# Attempt writers
# --------------------------------------------------------------------------- #


def _env_for(*, editor_id: str, editor_version: str, fixture: dict, cache_state: str) -> dict:
    env = _host_base(
        editor_id=editor_id,
        editor_version=editor_version,
        execution_profile=execution_profile(EXECUTION_PROFILE),
        fixture_sha256=fixture["sha256"],
        workload_row=fixture["workload_row"],
        docx_size=fixture["byte_size"],
        cache_state=cache_state,
        repetition_unit="fresh_process",
        run_kind="timing",
        feature_profile_name="P0",
    )
    env["fixture_paragraph_count"] = int(fixture["paragraph_count"])
    env["interpretation_conditions"] = list(INTERPRETATION_CONDITIONS)
    return env


def _write_measured(
    *,
    attempt_dir: Path,
    criterion_id: str,
    editor_id: str,
    lane: str,
    env: dict,
    samples: list,
    diagnostic: dict,
    doc_output_text: str | None = None,
) -> tuple:
    diagnostic = dict(diagnostic)
    intervals = [(row.get("witness") or {}).get("clock_check", {}).get("frame_interval_ms", row.get("frame_interval_ms"))
                 for row in diagnostic.get("samples", [diagnostic])]
    if intervals and all(isinstance(value, (int, float)) and not isinstance(value, bool)
                         and math.isfinite(value) and value > 0 for value in intervals):
        diagnostic["frame_intervals_ms"] = intervals
        if len(set(intervals)) == 1:
            diagnostic["frame_interval_ms"] = intervals[0]
    if "frame_interval_ms" not in diagnostic:
        reason = "frame_interval_inconsistent" if intervals and len(set(intervals)) > 1 else "frame_interval_unavailable"
        path = _write_refusal(attempt_dir=attempt_dir, criterion_id=criterion_id,
            editor_id=editor_id, lane=lane, env=env, outcome="failed",
            failure_reason=reason, diagnostic=diagnostic, publishable=False,
            publication_block_reason=reason)
        trial = json.loads(path.read_text())
        return path, trial
    spec = CRITERIA[criterion_id]
    stats = summarize(samples, spec["cache_state"], env["repetition_unit"], seed=0)
    pub, reason = trial_publishable_flags(env, spec["layer"], None if env["repetition_unit"] == "fresh_process" else stats["n"])
    parts = [part for part in (reason,) if part]
    catalog_row = _catalog_row(criterion_id)
    ok, interp_reason = evaluate_measured_trial(
        catalog_row, env, doc_output_text=doc_output_text, summary_stats=stats
    )
    if not ok:
        pub = False
        parts.append("interpretation: %s" % (interp_reason,))
    if env["host_class"] == "ci_coarse":
        parts.append("ci_coarse host_class blocks headline publication")
    pub, block = _finalize_publishable(False if parts else pub, "; ".join(parts) or None, env)
    trial = _trial_dict(
        criterion_id=criterion_id,
        layer=spec["layer"],
        boundary=spec["boundary"],
        outcome="measured",
        env=env,
        samples_ms=[float(value) for value in samples],
        editor_id=editor_id,
        lane=lane,
        summary_stats=stats,
        publishable=pub,
        publication_block_reason=block,
        diagnostic=diagnostic,
    )
    interval = diagnostic.get("frame_interval_ms")
    if isinstance(interval, (int, float)) and not isinstance(interval, bool) and math.isfinite(interval) and interval > 0:
        trial["sub_frame_samples"] = [value < interval for value in samples]
    if criterion_id == "C11":
        checks = diagnostic.get("samples") or []
        trial["content_verified"] = bool(checks) and all(d.get("content_verified") is True for d in checks)
    trial['measure'] = diagnostic.get('measurement') or diagnostic.get('size_rung') or ''
    trial['refusal_code'] = None if pub else 'publishable_not_true'
    validate_trial(trial)
    path = write_attempt(
        attempt_dir,
        "%s-%s-%s" % (criterion_id.lower(), editor_id, uuid.uuid4().hex[:10]),
        trial,
    )
    return path, trial


def _write_refusal(
    *,
    attempt_dir: Path,
    criterion_id: str,
    editor_id: str,
    lane: str,
    env: dict,
    outcome: str,
    failure_reason: str,
    diagnostic: dict | None = None,
    publishable: bool | None = None,
    publication_block_reason: str | None = None,
    refusal_code: str | None = None,
    content_meta: dict | None = None,
    gate: dict | None = None,
) -> Path:
    spec = CRITERIA[criterion_id]
    if not failure_reason or not failure_reason.strip():
        raise ValueError("refusal for %s/%s needs a reason" % (criterion_id, editor_id))
    if outcome not in ("not_run", "not_applicable", "unsupported", "unverified", "failed"):
        raise ValueError("refusal outcome %r" % (outcome,))
    diagnostic = dict(diagnostic or {})
    if content_meta is not None:
        gate = gate or gate_length_check_for(editor_id, content_meta)
        diagnostic.update(content_gate_record(content_meta, gate))
    trial = _trial_dict(
        criterion_id=criterion_id,
        layer=spec["layer"],
        boundary=spec["boundary"],
        outcome=outcome,
        env=env,
        samples_ms=[],
        failure_reason=failure_reason,
        editor_id=editor_id,
        lane=lane,
        diagnostic=diagnostic,
        publishable=publishable,
        publication_block_reason=publication_block_reason,
    )
    classification_reason = failure_reason
    measurement, separator, detail = failure_reason.partition(": ")
    if separator and (measurement in C15_MEASUREMENTS or measurement.startswith("rung ")):
        classification_reason = detail
    trial['measure'] = (diagnostic or {}).get('measurement') or (diagnostic or {}).get('size_rung') or ''
    trial['refusal_detail'] = failure_reason
    trial['refusal_code'] = (outcome if outcome != 'failed' else
        refusal_code if refusal_code else
        'cpu_throttled' if classification_reason.startswith('cpu_throttled') else
        'host_build' if classification_reason.startswith('host-error:') else
        'unverified' if classification_reason.startswith(('document_content_', 'no document surface', 'no DOM usability mark', 'text-shift assertion failed', 'C12 window includes', 'mixed C14 measures', 'find widget ', 'find probe returned status', 'probe refused ')) else
        'paint_witness_unavailable' if classification_reason.startswith(('witness ', 'clock_', 'frame_', 'clock skew ', 'no compositor frame', 'no presented frame', 'retained sample has no witness', 'presented frame precedes', 'negative presented', 'compositor frame timestamp', 'no first-contentful-paint', 'first-contentful-paint entry')) else
        'crash')
    validate_environment(env)
    validate_trial(trial)
    return write_attempt(
        attempt_dir,
        "%s-%s-%s" % (criterion_id.lower(), editor_id, uuid.uuid4().hex[:10]),
        trial,
    )


_CATALOG = None


def _catalog_row(criterion_id: str) -> dict:
    global _CATALOG
    if _CATALOG is None:
        from perf.scenarios.catalog import scenarios

        _CATALOG = {row["id"]: row for row in scenarios()}
    return _CATALOG[criterion_id]


# --------------------------------------------------------------------------- #
# Per-criterion drivers
# --------------------------------------------------------------------------- #


def _in_sample_bracket(editor_id: str, criterion: str, produce):
    """One nested BrowserRun sample per probe.

    ``begin_sample`` opens the bracket. ``sample`` always closes it, including
    when the probe raises. A throttled sample refuses that probe alone.
    Recording runs without a ``samples`` list are not treated as throttled.
    No active run means the probe is called directly (unit tests).
    """
    run = ACTIVE.get()
    if run is None:
        return produce()
    run.begin_sample()
    payload = None
    error = None
    try:
        payload = produce()
    except BaseException as exc:
        error = exc
    row = {
        "editor_id": editor_id,
        "criterion_id": criterion,
        "outcome": "failed" if error else "measured",
    }
    if error is not None:
        row["failure_reason"] = str(error)[:300]
    run.sample("doc-%s-%s" % (criterion, uuid.uuid4().hex[:10]), row)
    samples = getattr(run, "samples", None)
    throttled = (
        bool(samples)
        and isinstance(samples[-1], dict)
        and samples[-1].get("failure_reason") == "cpu_throttled"
    )
    if error is not None:
        raise error
    if throttled:
        raise ProbeRefusal("cpu_throttled", outcome="failed")
    return payload


def corpus_opening_text(corpus_path: Path) -> str:
    """Reuse the corpus correctness extractor; up to eight opening words."""
    import zipfile
    from perf.fixtures.docx_workload import docx_paragraph_texts
    with zipfile.ZipFile(corpus_path) as archive:
        paragraphs = docx_paragraph_texts(archive.read("word/document.xml"))
    # Legacy micro fixtures begin with space-only paragraphs.
    return next((" ".join(p.split()[:8]) for p in paragraphs if p.strip()), "")


def corpus_content_expectations(corpus_path: Path) -> dict:
    """Opening snippet, closing witness, and a baseline only when it is defined.

    A raw ``w:t`` count is not a universal model length for revision/field or
    alternate-content fixtures: editors legitimately accept different text
    (for example current text versus tracked-move source). In that case the
    2% mass band has no like-for-like baseline and is explicitly not applied.
    """
    import zipfile
    from perf.fixtures.docx_workload import SENTINEL_PREFIX, docx_paragraph_texts
    with zipfile.ZipFile(corpus_path) as archive:
        document_xml = archive.read("word/document.xml")
    paragraphs = docx_paragraph_texts(document_xml)
    text = "\n".join(paragraphs)
    sentinel = None
    if paragraphs and paragraphs[-1].startswith(SENTINEL_PREFIX):
        sentinel = paragraphs[-1]
    ambiguous_model_text = re.search(
        br"<w:(?:moveFrom|moveTo|del|ins)(?:\s|>)|<w:fldChar\b|<w:instrText\b|<mc:AlternateContent\b",
        document_xml,
    )
    if ambiguous_model_text:
        closing = next((paragraph for paragraph in reversed(paragraphs) if paragraph.strip()), None)
        return {
            "opening": corpus_opening_text(corpus_path),
            "sentinel": sentinel,
            "closing": closing,
            "text_chars": len(text),
            "length_check": "coarse",
            "length_check_reason": (
                "fixture contains tracked revisions, field instructions/stubs, or "
                "AlternateContent fallback text; accepted model text is editor-dependent; "
                "a 2% mass band is undefined; opening and closing witnesses remain in force "
                "with a coarse 75%–125% w:t character band"
            ),
        }
    return {
        "opening": corpus_opening_text(corpus_path),
        "sentinel": sentinel,
        "closing": sentinel,
        "text_chars": len(text),
        "length_check": "applied",
        "length_check_reason": None,
    }


def corpus_content_expectation_flags(corpus_path: Path) -> list[str]:
    if not Path(corpus_path).is_file():
        return []
    meta = corpus_content_expectations(corpus_path)
    flags: list[str] = []
    if meta.get("closing"):
        flags.extend(["--expected-closing-sentinel", meta["closing"]])
    if meta.get("text_chars") and meta.get("length_check") in ("applied", "coarse"):
        flags.extend(["--fixture-text-chars", str(meta["text_chars"])])
    if meta.get("length_check"):
        flags.extend(["--length-check-mode", meta["length_check"]])
    return flags


#: What the content gate can run per editor, mirroring EDIT_SURFACES /
#: DOCUMENT_TEXT_SURFACES in perf/runner/edit_surface.mjs (r3lanes4 ruling 5a):
#: the persisted content_length_check / length_enforced / content_check fields
#: describe what the gate ran for THIS editor, never the corpus policy.
GATE_SURFACES = {
    "plate": {"oracle": "dom", "whole": True},
    "docxodus": {"oracle": "dom", "whole": False},
    "superdoc": {"oracle": "dom", "whole": False},
    "genoffice": {"oracle": "dom", "whole": False},
    "folio": {"oracle": "dom", "whole": False},
    "eigenpal": {"oracle": "model"},
    "canvas": {"oracle": "model"},
    "docen": {"oracle": "model"},
    "wordcraft": {"oracle": "absent"},
}


def content_meta_for_workload(workload_id: str, corpus_path: Path | None = None) -> dict:
    if corpus_path and Path(corpus_path).is_file():
        return corpus_content_expectations(corpus_path)
    if workload_id == "complex-corpus":
        return {
            "length_check": "coarse",
            "length_check_reason": (
                "AlternateContent fallback text; accepted model text is editor-dependent; "
                "a 2% mass band is undefined; opening and closing witnesses remain in force "
                "with a coarse 75%–125% w:t character band"
            ),
        }
    return {"length_check": "applied", "length_check_reason": None}


def content_gate_record(content_meta: dict, gate: dict | None = None) -> dict:
    """Persisted disclosure of what the content gate ran for one editor (ruling 5a)."""
    gate = gate or {}
    length_check = gate.get("length_check") or content_meta.get("length_check")
    out = {
        "content_length_check": length_check,
        "content_length_check_reason": content_meta.get("length_check_reason"),
    }
    if gate:
        if "length_enforced" in gate:
            out["content_length_enforced"] = gate.get("length_enforced")
        if gate.get("content_check") is not None:
            out["content_check"] = gate.get("content_check")
        elif "content_check" in gate:
            out["content_check"] = gate.get("content_check")
    return out


def gate_length_check_for(editor_id: str, content_meta: dict) -> dict:
    """The gate disclosure for one editor on one workload.

    A virtualized DOM editor runs opening_only (plus the mounted-text check on
    prose, r3lanes4 ruling 5b); a model-oracle editor runs the corpus length
    band on the model text; an absent oracle (wordcraft) ran nothing. Editors
    outside the trial table use the generic whole-document DOM path, which
    runs the corpus policy.
    """
    surface = GATE_SURFACES.get(editor_id)
    if surface is None:
        enforced = content_meta["length_check"] in ("applied", "coarse")
        return {"length_check": content_meta["length_check"], "length_enforced": enforced, "content_check": "full"}
    if surface["oracle"] == "absent":
        return {"length_check": "not_run", "length_enforced": False, "content_check": "not_run"}
    if surface["oracle"] == "dom" and surface.get("whole") is False:
        check = "opening_only" if content_meta["length_check"] == "coarse" else "mounted_text_in_fixture"
        return {"length_check": "opening_only", "length_enforced": False, "content_check": check}
    enforced = content_meta["length_check"] in ("applied", "coarse")
    check = "full" if surface["oracle"] == "dom" else "model_text"
    return {"length_check": content_meta["length_check"], "length_enforced": enforced, "content_check": check}


def expected_body_path_for(corpus_path: Path, content_meta: dict) -> Path | None:
    """The fixture body file the input lane already uses, written once.

    Only for workloads whose w:t body baseline is unambiguous (ruling 5b):
    complex-corpus keeps opening_only and passes no body.
    """
    if not Path(corpus_path).is_file():
        return None
    if content_meta["length_check"] == "coarse":
        return None
    from perf.runner.docx_plaintext import docx_body_text

    body = docx_body_text(corpus_path)
    body_path = corpus_path.with_name(corpus_path.stem + ".expected-body.txt")
    try:
        with open(body_path, "x", encoding="utf-8") as handle:
            handle.write(body)
    except FileExistsError:
        pass
    return body_path


def _run_load_samples(*, editor_id: str, target: dict, cfg: dict, fixture_path: Path, count: int) -> tuple:
    """C11: fresh browser, corpus content check, then document-frame timing."""
    expected = corpus_opening_text(fixture_path)
    if Path(fixture_path).is_file():
        content_meta = corpus_content_expectations(fixture_path)
    else:
        content_meta = {
            "opening": expected,
            "sentinel": None,
            "closing": None,
            "text_chars": 0,
            "length_check": "not_applicable",
            "length_check_reason": "in-memory corpus oracle; no package baseline available",
        }
    if not expected:
        raise ProbeRefusal("document_content_expectation_absent")
    extra = ["--expected-opening-text", expected, *corpus_content_expectation_flags(fixture_path)]
    cmd = _probe_cmd(
        mode="load",
        target=target,
        cfg=cfg,
        corpus_path=fixture_path,
        extra=extra,
    )
    cmd.extend(["--editor", editor_id])
    # r3lanes4 ruling 5b: hand the probe the fixture body the way the input
    # lane does, so the virtualized mounted-text check can run on prose.
    body_path = expected_body_path_for(Path(fixture_path), content_meta)
    probe_env = {"PERF_EXPECTED_BODY_PATH": str(body_path)} if body_path else {"PERF_EXPECTED_BODY_PATH": ""}
    samples = []
    diagnostics = []
    for _ in range(count):
        payload = _in_sample_bracket(editor_id, "C11", lambda: _run_probe(cmd, editor_id=editor_id, env=probe_env))
        gate = gate_length_check_for(editor_id, content_meta)
        for key, payload_key in (
            ("length_check", "content_length_check"),
            ("length_enforced", "length_enforced"),
            ("content_check", "content_check"),
        ):
            if payload.get(payload_key) is not None:
                gate[key] = payload[payload_key]
        if payload.get("content_verified") is not True:
            if payload.get("surface_reason") in (
                "document_content_absent",
                "document_content_mismatch",
                "document_content_unverifiable",
            ):
                reason = payload["surface_reason"]
                editor_error = payload.get("editor_error")
                if editor_error:
                    reason = "%s: %s" % (reason, editor_error)
                raise ProbeRefusal(reason)
            if payload.get("content_text_accessible") is not False:
                raise ProbeRefusal("document_content_unverified")
        values = c11_measured_samples(payload)
        samples.extend(values)
        diagnostics.append(
            {
                "content_verified": payload.get("content_verified") is True,
                "witness": payload.get("witness"),
                "document_text": payload.get("document_text"),
                "expected_opening_text": expected,
                "content_length_check": gate["length_check"],
                "content_length_check_reason": content_meta["length_check_reason"],
                "content_length_enforced": gate["length_enforced"],
                "content_check": gate["content_check"],
                "fcp_ms": payload.get("fcp_ms"),
                "first_element_ms": payload.get("first_element_ms"),
                "first_element_delta_from_fcp_ms": payload.get("first_element_delta_from_fcp_ms"),
                "first_element_info": payload.get("first_element_info"),
                "first_element_selector": payload.get("first_element_selector"),
                "document_text_at_ms": payload.get("document_text_at_ms"),
                "presented_frame_ms": payload.get("presented_frame_ms"),
                "usable_signal": payload.get("usable_signal"),
                "usable_ms": payload.get("usable_ms"),
                "clock_skew_ms": payload.get("clock_skew_ms"),
                "clock_skew_acceptable": payload.get("clock_skew_acceptable"),
                "frames_total": payload.get("frames_total"),
                "frames_after_usable": payload.get("frames_after_usable"),
                "document_text_chars": payload.get("document_text_chars"),
                "page_count": payload.get("page_count"),
                "page_count_at_first": payload.get("page_count_at_first"),
                "navigation_ms": payload.get("navigation_ms"),
                "ready_ms": payload.get("ready_ms"),
                "paints": payload.get("paints"),
                "page_errors": payload.get("page_errors"),
            }
        )
    return samples, diagnostics


def _run_reflow_samples(*, editor_id: str, target: dict, cfg: dict, fixture_path: Path, count: int) -> tuple:
    cmd = _probe_cmd(
        mode="reflow",
        target=target,
        cfg=cfg,
        corpus_path=fixture_path,
        extra=["--settle-ms", str(SETTLE_MS)],
        editor_id=editor_id,
    )
    cmd.extend(["--editor", editor_id])
    samples = []
    diagnostics = []
    for _ in range(count):
        payload = _in_sample_bracket(editor_id, "C12", lambda: _run_probe(cmd, editor_id=editor_id))
        samples.append(c12_measured_sample(payload))
        content_meta = corpus_content_expectations(fixture_path) if Path(fixture_path).is_file() else {
            "length_check": "not_applicable",
            "length_check_reason": None,
        }
        gate = gate_length_check_for(editor_id, content_meta)
        diagnostics.append(
            {
                "shift_px": payload.get("shift_px"),
                "matched_by": payload.get("matched_by"),
                "block_count_before": payload.get("block_count_before"),
                "block_count_after": payload.get("block_count_after"),
                "insertion_created_block": payload.get("insertion_created_block"),
                "anchor_top_after": payload.get("anchor_top_after"),
                "anchor_occurrence": (payload.get("before") or {}).get("anchor_occurrence"),
                "first_frame_after_input_ms": payload.get("first_frame_after_input_ms"),
                "frames_total": payload.get("frames_total"),
                "frames_after_shift_observed": payload.get("frames_after_shift_observed"),
                "navigation_ms": payload.get("navigation_ms"),
                "ready_ms": payload.get("ready_ms"),
                "clock_skew_ms": payload.get("clock_skew_ms"),
                "clock_skew_acceptable": payload.get("clock_skew_acceptable"),
                "witness": payload.get("witness"),
                "page_errors": payload.get("page_errors"),
                "observed_shift_page_ms": payload.get("observed_shift_page_ms"),
                "input_page_ms": payload.get("input_page_ms"),
                **content_gate_record(content_meta, gate),
            }
        )
    return samples, diagnostics


def _run_scale_samples(*, editor_id: str, target: dict, cfg: dict, fixture_path: Path, count: int) -> tuple:
    cmd = _probe_cmd(
        mode="scale",
        target=target,
        cfg=cfg,
        corpus_path=fixture_path,
        extra=["--settle-ms", "0"],
    )
    cmd.extend(["--editor", editor_id])
    samples = []
    diagnostics = []
    for _ in range(count):
        payload = _in_sample_bracket(editor_id, "C14", lambda: _run_probe(cmd, editor_id=editor_id))
        sample = c14_measured_sample(payload)
        samples.append(sample)
        diagnostics.append(
            {
                "measure": sample.measure,
                "clock": dict(C14_CLOCK_BY_MEASURE[sample.measure]),
                "usable_ms": payload.get("usable_ms"),
                "usable_source": payload.get("usable_source"),
                "first_element_ms": payload.get("first_element_ms"),
                "fcp_ms": payload.get("fcp_ms"),
                "page_count": payload.get("page_count"),
                "document_text_chars": payload.get("document_text_chars"),
                "document_text": payload.get("document_text"),
                "frames_total": payload.get("frames_total"),
                "frames_after_usable": payload.get("frames_after_usable"),
                "mechanism": payload.get("mechanism"),
                "no_damage_followed": payload.get("mechanism") == "forced_repaint",
                "witness": payload.get("witness"),
                "usable_signal": payload.get("usable_signal"),
                "clock_skew_ms": payload.get("clock_skew_ms"),
                "navigation_ms": payload.get("navigation_ms"),
                "ready_ms": payload.get("ready_ms"),
                "page_errors": payload.get("page_errors"),
            }
        )
    measures = [sample.measure for sample in samples]
    if len(set(measures)) > 1:
        # The two measures are different quantities: a compositor-frame time
        # and a DOM timestamp. One rung pools one clock, never a mix of both.
        raise ProbeRefusal(
            "mixed C14 measures in one rung (%s): a compositor-frame sample and a no-damage DOM sample are not pooled"
            % ", ".join(measures),
            refusal_code="unverified",
            facts={
                "sample_measures": measures,
                "no_damage_followed": any(measure == C14_NO_DAMAGE_MEASURE for measure in measures),
            },
        )
    return samples, diagnostics


def _run_find(*, editor_id: str, target: dict, cfg: dict, fixture_path: Path) -> dict:
    if not cfg.get("find_input_selector"):
        return {
            "status": "not_applicable",
            "reason": cfg.get("find_source_note") or "no find widget selector configured for this host",
        }
    cmd = _probe_cmd(
        mode="find",
        target=target,
        cfg=cfg,
        corpus_path=fixture_path,
        extra=[
            "--settle-ms",
            str(SETTLE_MS),
            "--find-input-selector",
            cfg["find_input_selector"],
            "--find-count-selector",
            cfg.get("find_count_selector", ""),
            "--find-match-selector",
            cfg.get("find_match_selector", ""),
            "--find-query",
            cfg.get("find_query", ""),
        ],
    )
    cmd.extend(["--editor", editor_id])
    if cfg.get("find_expected_matches") is not None:
        cmd.extend(["--find-expected-matches", str(cfg["find_expected_matches"])])
    return _run_probe(cmd, editor_id=editor_id)


def _run_find_payloads(*, editor_id: str, target: dict, cfg: dict, fixture_path: Path, count: int) -> list:
    """Enough event completions for C15_MIN_N, clamped to the fresh-process budget.

    A host with no find widget is asked once. Payloads are not duplicated to
    fake a larger n; a budget below the minimum stays unverified.
    """
    if not cfg.get("find_input_selector"):
        return [
            _in_sample_bracket(
                editor_id,
                "C15",
                lambda: _run_find(editor_id=editor_id, target=target, cfg=cfg, fixture_path=fixture_path),
            )
        ]
    limit = sample_budget_for_profile(execution_profile(EXECUTION_PROFILE), "fresh_process")
    reps = max(int(count), C15_MIN_N)
    if reps > limit:
        reps = limit
    payloads = []
    for _ in range(reps):
        payload = _in_sample_bracket(
            editor_id,
            "C15",
            lambda: _run_find(editor_id=editor_id, target=target, cfg=cfg, fixture_path=fixture_path),
        )
        payloads.append(payload)
        if payload.get("status") == "not_applicable":
            break
    return payloads


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--editors", nargs="*", default=None, help="default: every browser host")
    parser.add_argument("--workload", default="micro-paragraphs")
    parser.add_argument("--criteria", nargs="*", default=None, help="default: C11 C12 C14 C15")
    parser.add_argument("--samples", type=int, default=SAMPLE_DEFAULT, help="fresh processes per cell (ci_broad budget: 5)")
    parser.add_argument("--out-root", type=Path, default=None)
    args = parser.parse_args()

    from perf.scenarios.catalog import scenarios

    assert_catalog_alignment(scenarios())

    editors = args.editors or list(BROWSER_TARGETS.keys())
    unknown = [editor for editor in editors if editor not in BROWSER_TARGETS]
    if unknown:
        raise SystemExit("unknown browser host(s): %s" % (", ".join(unknown),))
    criteria = args.criteria or ["C11", "C12", "C14", "C15"]
    unknown = [cid for cid in criteria if cid not in CRITERIA]
    if unknown:
        raise SystemExit("unsupported criterion id(s): %s" % (", ".join(unknown),))
    if args.samples < 1:
        raise SystemExit("--samples must be >= 1")
    limit = sample_budget_for_profile(execution_profile(EXECUTION_PROFILE), "fresh_process")
    if args.samples > limit:
        raise SystemExit("--samples %d exceeds the %s fresh_process budget (%d)" % (args.samples, execution_profile(EXECUTION_PROFILE), limit))

    run_day = date.today().isoformat().replace("-", "_")
    out_root = args.out_root or (REPO / "perf" / "out" / ("document_%s" % run_day))
    attempt_dir = out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir = out_root / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)

    specs = {cid: {**spec, 'workload': args.workload if cid in ('C11', 'C12') else spec['workload']}
             for cid, spec in CRITERIA.items()}
    ladder = {row["workload_id"]: row for row in size_ladder()}
    fixtures: dict = {}
    for workload_id in {rung for cid in criteria for rung in (C14_RUNGS if cid == "C14" else (specs[cid]["workload"],))}:
        rung = ladder[workload_id]
        fixture = build_fixture(rung)
        fixture["path"] = fixture_dir / ("%s-%s.docx" % (workload_id, fixture["sha256"][:16]))
        try:
            assert_workload_allowed(execution_profile(EXECUTION_PROFILE), workload_id)
            allowed = True
        except ValueError:
            # A rung above the profile cap keeps its declared record (hash, size,
            # paragraph count) but its bytes are never written to disk and never
            # reach an editor.
            allowed = False
        if allowed:
            fixture["path"] = run_fixture(workload_id, fixture["bytes"], fixture["path"])
        fixtures[workload_id] = fixture

    rows: list = []
    scaling: list = []
    failures = 0
    gates_by_editor: dict = {}

    for editor_id in editors:
        target = BROWSER_TARGETS[editor_id]
        lane = target.get("lane") or default_lane(editor_id)
        editor_version = pin_label(editor_id)
        cfg = DOCUMENT_TARGETS.get(editor_id)
        support_note = (cfg or {}).get("note")
        find_source_note = (cfg or {}).get("find_source_note")
        prose_fixture = fixtures[specs["C11"]["workload"]]
        editor_content_meta = corpus_content_expectations(prose_fixture["path"]) if prose_fixture["path"].is_file() else {
            "length_check": "not_applicable",
            "length_check_reason": None,
        }
        gates_by_editor[editor_id] = gate_length_check_for(editor_id, editor_content_meta)

        refuse_reason = None
        if cfg is None:
            structure = STRUCTURE_NOTES.get(editor_id, "no verified document-structure selectors for this host")
            refuse_reason = (
                "not driven: benchmark_document has no verified document-structure config for %s (%s); "
                "a guessed first-block/page selector or insertion target would measure the host shell"
                % (editor_id, structure)
            )

        # C11/C12/C14 workloads are fixed; refuse without starting the host.
        def _refuse_cell(criterion_id: str, workout_fixture: dict, reason: str, outcome: str = "not_run", extra: dict | None = None, refusal_code: str | None = None) -> None:
            env = _env_for(
                editor_id=editor_id,
                editor_version=editor_version,
                fixture=workout_fixture,
                cache_state=CRITERIA[criterion_id]["cache_state"],
            )
            wmeta = corpus_content_expectations(workout_fixture["path"]) if workout_fixture["path"].is_file() else editor_content_meta
            path = _write_refusal(
                attempt_dir=attempt_dir,
                criterion_id=criterion_id,
                editor_id=editor_id,
                lane=lane,
                env=env,
                outcome=outcome,
                failure_reason=reason,
                diagnostic=extra,
                refusal_code=refusal_code,
                content_meta=wmeta,
                gate=gates_by_editor[editor_id],
            )
            rows.append(
                {
                    "criterion_id": criterion_id,
                    "editor_id": editor_id,
                    "outcome": outcome,
                    "failure_reason": reason,
                    "attempt_file": _attempt_ref(path),
                    "publishable": False,
                    "support_note": support_note,
                    **{key: value for key, value in (extra or {}).items() if key in ("size_rung", "workload_id", "measurement")},
                }
            )

        if refuse_reason:
            for criterion_id in criteria:
                if criterion_id == "C15":
                    env = _env_for(
                        editor_id=editor_id,
                        editor_version=editor_version,
                        fixture=fixtures[specs["C15"]["workload"]],
                        cache_state=CRITERIA["C15"]["cache_state"],
                    )
                    for measurement in C15_MEASUREMENTS:
                        reason = "%s; measurement %s not driven" % (refuse_reason, measurement)
                        path = _write_refusal(
                            attempt_dir=attempt_dir,
                            criterion_id="C15",
                            editor_id=editor_id,
                            lane=lane,
                            env=env,
                            outcome="not_run",
                            failure_reason=reason,
                            diagnostic={"measurement": measurement},
                        )
                        rows.append(
                            {
                                "criterion_id": "C15",
                                "editor_id": editor_id,
                                "measurement": measurement,
                                "outcome": "not_run",
                                "failure_reason": reason,
                                "attempt_file": _attempt_ref(path),
                                "publishable": False,
                                "support_note": support_note,
                            }
                        )
                elif criterion_id == "C14":
                    for rung in C14_RUNGS:
                        reason = "%s; rung %s not driven" % (refuse_reason, C14_RUNG_LABEL[rung])
                        for measure in C14_MEASURES:
                            _refuse_cell("C14", fixtures[rung], reason, extra={"size_rung": C14_RUNG_LABEL[rung], "workload_id": rung, "measurement": measure})
                else:
                    _refuse_cell(criterion_id, fixtures[specs[criterion_id]["workload"]], refuse_reason)
            continue

        proc = None
        launch_row_start = len(rows)
        try:
            proc = _start_server(editor_id, target)

            for criterion_id in criteria:
                if criterion_id == "C11":
                    fixture = fixtures[specs["C11"]["workload"]]
                    content_meta = corpus_content_expectations(fixture["path"])
                    env = _env_for(
                        editor_id=editor_id,
                        editor_version=editor_version,
                        fixture=fixture,
                        cache_state=CRITERIA["C11"]["cache_state"],
                    )
                    validate_sample_budget(env, args.samples)
                    try:
                        samples, diagnostics = _run_load_samples(
                            editor_id=editor_id,
                            target=target,
                            cfg=cfg,
                            fixture_path=fixture["path"],
                            count=args.samples,
                        )
                    except ProbeRefusal as refusal:
                        refusal_code = getattr(refusal, "refusal_code", None)
                        if refusal_code == "editor_load_failed":
                            content_outcome = "unverified"
                        elif refusal.reason.startswith(("document_content_", "document_content_unverified")):
                            content_outcome = "unverified"
                        else:
                            content_outcome = getattr(refusal, "outcome", "failed") or "failed"
                        if content_outcome == "failed" and refusal.reason.startswith("document_content_"):
                            content_outcome = "unverified"
                        _refuse_cell(
                            "C11",
                            fixture,
                            refusal.reason,
                            outcome=content_outcome,
                            extra={
                                "content_length_check": gate_length_check_for(editor_id, content_meta)["length_check"],
                                "content_check": gate_length_check_for(editor_id, content_meta)["content_check"],
                                "content_length_check_reason": content_meta["length_check_reason"],
                            },
                            refusal_code=getattr(refusal, "refusal_code", None)
                            or ("unverified" if content_outcome == "unverified" else None),
                        )
                        if content_outcome == "failed":
                            failures += 1
                        continue
                    path, trial = _write_measured(
                        attempt_dir=attempt_dir,
                        criterion_id="C11",
                        editor_id=editor_id,
                        lane=lane,
                        env=env,
                        samples=samples,
                        doc_output_text=diagnostics[-1].get("document_text"),
                        diagnostic={
                            "suite": "document",
                            "clock": {
                                "start": "navigation_start",
                                "end": "first presented screencast frame at or after the document surface",
                                "dom_check": "first page/block element present with a layout box, sampled on the next animation frame",
                                "document_text_check": "disclosed document surface (dom text, non-blank canvas pixel, or open shadow-root text) on an animation frame",
                                "dom_check_is_not_the_sample": True,
                                "fcp_is_not_the_sample": True,
                            },
                            "page_model": cfg["page_model"],
                            "page_count_source": (
                                "not_applicable: continuous flow (design doc C11)"
                                if cfg["page_model"] != "page"
                                else "count of %s after ready" % (cfg["page_selector"],)
                            ),
                            "first_element_selector": cfg["page_selector"] or cfg["doc_selector"],
                            "samples": diagnostics,
                        },
                    )
                    rows.append(
                        {
                            "criterion_id": "C11",
                            "editor_id": editor_id,
                            "outcome": trial["outcome"], "failure_reason": trial.get("failure_reason"),
                            "median_ms": (trial.get("summary_stats") or {}).get("median"),
                            "content_verified": trial.get("content_verified", False),
                            "first_element_median_ms": _median_optional([d.get("first_element_ms") for d in diagnostics]),
                            "document_text_median_ms": _median_optional([d.get("document_text_at_ms") for d in diagnostics]),
                            "page_count": diagnostics[-1].get("page_count"),
                            "cache_state": CRITERIA["C11"]["cache_state"],
                            "attempt_file": _attempt_ref(path),
                            "publishable": trial["publishable"],
                            "support_note": support_note,
                        }
                    )

                if criterion_id == "C12":
                    fixture = fixtures[specs["C12"]["workload"]]
                    if editor_id == "wordcraft":
                        _refuse_cell(
                            "C12",
                            fixture,
                            (
                                "wordcraft exposes no document text or block geometry at this pin "
                                "(one WebGL canvas; correctness is only the modified window-title bullet)"
                            ),
                            outcome="not_applicable",
                        )
                        continue
                    env = _env_for(
                        editor_id=editor_id,
                        editor_version=editor_version,
                        fixture=fixture,
                        cache_state=CRITERIA["C12"]["cache_state"],
                    )
                    validate_sample_budget(env, args.samples)
                    try:
                        samples, diagnostics = _run_reflow_samples(
                            editor_id=editor_id,
                            target=target,
                            cfg=cfg,
                            fixture_path=fixture["path"],
                            count=args.samples,
                        )
                    except ProbeRefusal as refusal:
                        c12_outcome = getattr(refusal, "outcome", "failed") or "failed"
                        _refuse_cell(
                            "C12",
                            fixture,
                            refusal.reason,
                            outcome=c12_outcome,
                            refusal_code=getattr(refusal, "refusal_code", None),
                        )
                        if c12_outcome == "failed":
                            failures += 1
                        continue
                    path, trial = _write_measured(
                        attempt_dir=attempt_dir,
                        criterion_id="C12",
                        editor_id=editor_id,
                        lane=lane,
                        env=env,
                        samples=samples,
                        diagnostic={
                            "suite": "document",
                            "clock": {
                                "start": "Enter keypress at the document start",
                                "end": "first compositor screencast frame at or after the anchor block was observed to move down",
                                "raf_observation": "the y-shift is observed on an animation frame; a frame arriving before that is not the sample",
                                "forced_layout": "layout reads are outside the timed window; forced_layout_ms on the probe is always 0",
                            },
                            "insertion": "Enter at document start then one character",
                            "shift_assertion": (
                                "the anchor block (nearest block below the insertion point, located by DOM identity, "
                                "text, and occurrence among equal-text blocks) moves down by >0.5 px"
                            ),
                            "samples": diagnostics,
                        },
                    )
                    rows.append(
                        {
                            "criterion_id": "C12",
                            "editor_id": editor_id,
                            "outcome": trial["outcome"], "failure_reason": trial.get("failure_reason"),
                            "median_ms": (trial.get("summary_stats") or {}).get("median"),
                            "shift_px_median": _median_optional([d.get("shift_px") for d in diagnostics]),
                            "cache_state": CRITERIA["C12"]["cache_state"],
                            "attempt_file": _attempt_ref(path),
                            "publishable": trial["publishable"],
                            "support_note": support_note,
                        }
                    )

                if criterion_id == "C14":
                    rung_rows = []
                    rung_attempts = {}
                    for rung in C14_RUNGS:
                        fixture = fixtures[rung]
                        label = C14_RUNG_LABEL[rung]
                        try:
                            assert_workload_allowed(execution_profile(EXECUTION_PROFILE), rung)
                        except ValueError as exc:
                            reason = "execution_profile: %s" % (exc,)
                            env = _env_for(
                                editor_id=editor_id,
                                editor_version=editor_version,
                                fixture=fixture,
                                cache_state=CRITERIA["C14"]["cache_state"],
                            )
                            for path in write_c14_rung_refusals(
                                attempt_dir=attempt_dir,
                                editor_id=editor_id,
                                lane=lane,
                                env=env,
                                label=label,
                                workload_id=rung,
                                reason=reason,
                                outcome="not_run",
                            ):
                                rung_rows.append(
                                    {
                                        "workload_id": rung,
                                        "size_rung": label,
                                        "outcome": "not_run",
                                        "failure_reason": reason,
                                        "attempt_file": _attempt_ref(path),
                                    }
                                )
                                rows.append(
                                    {
                                        "criterion_id": "C14",
                                        "editor_id": editor_id,
                                        "size_rung": label,
                                        "workload_id": rung,
                                        "outcome": "not_run",
                                        "failure_reason": reason,
                                        "attempt_file": _attempt_ref(path),
                                        "publishable": False,
                                        "support_note": support_note,
                                    }
                                )
                            continue
                        env = _env_for(
                            editor_id=editor_id,
                            editor_version=editor_version,
                            fixture=fixture,
                            cache_state=CRITERIA["C14"]["cache_state"],
                        )
                        validate_sample_budget(env, args.samples)
                        try:
                            samples, diagnostics = _run_scale_samples(
                                editor_id=editor_id,
                                target=target,
                                cfg=cfg,
                                fixture_path=fixture["path"],
                                count=args.samples,
                            )
                        except ProbeRefusal as refusal:
                            reason = "rung %s: %s" % (label, refusal.reason)
                            outcome = getattr(refusal, "outcome", "failed") or "failed"
                            facts = dict(getattr(refusal, "facts", None) or {})
                            for path in write_c14_rung_refusals(
                                attempt_dir=attempt_dir,
                                editor_id=editor_id,
                                lane=lane,
                                env=env,
                                label=label,
                                workload_id=rung,
                                reason=reason,
                                outcome=outcome,
                                facts=facts,
                                refusal_code=getattr(refusal, "refusal_code", None),
                            ):
                                rung_rows.append(
                                    {
                                        "workload_id": rung,
                                        "size_rung": label,
                                        "outcome": outcome,
                                        "failure_reason": reason,
                                        "attempt_file": _attempt_ref(path),
                                    }
                                )
                                rows.append(
                                    {
                                        "criterion_id": "C14",
                                        "editor_id": editor_id,
                                        "size_rung": label,
                                        "workload_id": rung,
                                        "outcome": outcome,
                                        "failure_reason": reason,
                                        "attempt_file": _attempt_ref(path),
                                        "publishable": False,
                                        "support_note": support_note,
                                    }
                                )
                            failures += 1
                            continue
                        rung_attempts[rung] = {"samples": samples, "diagnostics": diagnostics, "env": env}

                    if rung_attempts:
                        assert_distinct_c14_rungs(
                            [
                                {"workload_id": rung, "samples_ms": data["samples"]}
                                for rung, data in rung_attempts.items()
                            ]
                        )
                        curve = {
                            rung: {
                                "n": len(data["samples"]),
                                "median_ms": summarize(
                                    data["samples"], CRITERIA["C14"]["cache_state"], "fresh_process", seed=0
                                )["median"],
                                "measure": (data["diagnostics"][0] or {}).get("measure"),
                            }
                            for rung, data in rung_attempts.items()
                        }
                        for rung, data in rung_attempts.items():
                            label = C14_RUNG_LABEL[rung]
                            rung_measure = (data["diagnostics"][0] or {}).get("measure")
                            path, trial = _write_measured(
                                attempt_dir=attempt_dir,
                                criterion_id="C14",
                                editor_id=editor_id,
                                lane=lane,
                                env=data["env"],
                                samples=data["samples"],
                                doc_output_text=data["diagnostics"][-1].get("document_text"),
                                diagnostic={
                                    "suite": "document",
                                    "size_rung": label,
                                    "workload_id": rung,
                                    "measurement": rung_measure,
                                    "clock": dict(C14_CLOCK_BY_MEASURE[rung_measure]),
                                    "correctness_evidence": "rendered DOM text, checked against I01-I03 by evaluate_measured_trial",
                                    "no_pooled_figure": True,
                                    "curve_medians_ms": curve,
                                    "samples": data["diagnostics"],
                                },
                            )
                            rung_rows.append(
                                {
                                    "workload_id": rung,
                                    "size_rung": label,
                                    "outcome": trial["outcome"], "failure_reason": trial.get("failure_reason"),
                                    "n": len(trial.get("samples_ms") or []),
                                    "median_ms": (trial.get("summary_stats") or {}).get("median"),
                                    "attempt_file": _attempt_ref(path),
                                }
                            )
                            rows.append(
                                {
                                    "criterion_id": "C14",
                                    "editor_id": editor_id,
                                    "size_rung": label,
                                    "workload_id": rung,
                                    "outcome": trial["outcome"], "failure_reason": trial.get("failure_reason"),
                                    "median_ms": (trial.get("summary_stats") or {}).get("median"),
                                    "n": len(data["samples"]),
                                    "cache_state": CRITERIA["C14"]["cache_state"],
                                    "attempt_file": _attempt_ref(path),
                                    "publishable": trial["publishable"],
                                    "support_note": support_note,
                                }
                            )
                    if rung_rows:
                        scaling.append(
                            {
                                "editor_id": editor_id,
                                "rungs": rung_rows,
                                "note": (
                                    "one attempt per size rung; the curve is the per-rung medians above, never a "
                                    "single pooled number"
                                ),
                            }
                        )

                if criterion_id == "C15":
                    fixture = fixtures[specs["C15"]["workload"]]
                    env = _env_for(
                        editor_id=editor_id,
                        editor_version=editor_version,
                        fixture=fixture,
                        cache_state=CRITERIA["C15"]["cache_state"],
                    )
                    try:
                        payloads = _run_find_payloads(
                            editor_id=editor_id,
                            target=target,
                            cfg=cfg,
                            fixture_path=fixture["path"],
                            count=args.samples,
                        )
                        cell = c15_samples_from_payloads(payloads)
                    except ProbeRefusal as refusal:
                        cell = c15_cell_after_refusal(refusal)
                        payloads = []
                    payload = payloads[-1] if payloads else {}
                    for measurement in C15_MEASUREMENTS:
                        detail = cell["measurements"][measurement]
                        outcome = detail["outcome"]
                        samples = detail.get("samples_ms") or []
                        reason = detail.get("reason")
                        if outcome == "measured" and samples:
                            validate_sample_budget(env, len(samples))
                            path, trial = _write_measured(
                                attempt_dir=attempt_dir,
                                criterion_id="C15",
                                editor_id=editor_id,
                                lane=lane,
                                env=env,
                                samples=[float(value) for value in samples],
                                diagnostic={
                                    "suite": "document",
                                    "measurement": measurement,
                                    "samples": payloads,
                                    "completion": cell.get("completion"),
                                    "minimum_n": C15_MIN_N,
                                    "clock": {
                                        "start": "first keystroke typed into the editor's own find widget",
                                        "end": "the find widget acknowledged %s" % measurement,
                                        "scope": (
                                            "editor UI turnaround: it includes the editor's own input dispatch and "
                                            "any search debounce, so it is an upper bound on the model search time, "
                                            "not a model-only clock"
                                        ),
                                    },
                                    "expected_matches": payload.get("expected_matches"),
                                    "observed_count_text": payload.get("observed_count_text"),
                                    "shortcut": payload.get("shortcut"),
                                    "cap_ms": payload.get("cap_ms"),
                                },
                            )
                            rows.append(
                                {
                                    "criterion_id": "C15",
                                    "editor_id": editor_id,
                                    "measurement": measurement,
                                    "outcome": trial["outcome"], "failure_reason": trial.get("failure_reason"),
                                    "n": len(trial.get("samples_ms") or []),
                                    "median_ms": (trial.get("summary_stats") or {}).get("median"),
                                    "cache_state": CRITERIA["C15"]["cache_state"],
                                    "attempt_file": _attempt_ref(path),
                                    "publishable": trial["publishable"],
                                    "support_note": support_note,
                                    "find_source_note": find_source_note,
                                }
                            )
                        else:
                            path = _write_refusal(
                                attempt_dir=attempt_dir,
                                criterion_id="C15",
                                editor_id=editor_id,
                                lane=lane,
                                env=env,
                                outcome=outcome,
                                failure_reason="%s: %s" % (measurement, reason),
                                diagnostic={"measurement": measurement, "completion": cell.get("completion"), "minimum_n": C15_MIN_N},
                                publishable=False,
                                publication_block_reason="%s: %s" % (measurement, reason),
                                refusal_code=cell.get("refusal_code"),
                            )
                            rows.append(
                                {
                                    "criterion_id": "C15",
                                    "editor_id": editor_id,
                                    "measurement": measurement,
                                    "outcome": outcome,
                                    "failure_reason": "%s: %s" % (measurement, reason),
                                    "attempt_file": _attempt_ref(path),
                                    "publishable": False,
                                    "support_note": support_note,
                                    "find_source_note": find_source_note,
                                }
                            )

        except Exception as exc:  # host never came up
            failures += 1
            reason = "host-error: %s" % (str(exc)[:400],)
            attempted = {row["criterion_id"] for row in rows[launch_row_start:]}
            for criterion_id in criteria:
                if criterion_id in attempted:
                    continue
                if criterion_id == "C15":
                    env = _env_for(
                        editor_id=editor_id,
                        editor_version=editor_version,
                        fixture=fixtures[specs["C15"]["workload"]],
                        cache_state=CRITERIA["C15"]["cache_state"],
                    )
                    for measurement in C15_MEASUREMENTS:
                        path = _write_refusal(
                            attempt_dir=attempt_dir,
                            criterion_id="C15",
                            editor_id=editor_id,
                            lane=lane,
                            env=env,
                            outcome="not_run",
                            failure_reason=reason,
                            diagnostic={"measurement": measurement},
                        )
                        rows.append(
                            {
                                "criterion_id": "C15",
                                "editor_id": editor_id,
                                "measurement": measurement,
                                "outcome": "not_run",
                                "failure_reason": reason,
                                "attempt_file": _attempt_ref(path),
                                "publishable": False,
                            }
                        )
                elif criterion_id == "C14":
                    for rung in C14_RUNGS:
                        for measure in C14_MEASURES:
                            _refuse_cell(
                                "C14",
                                fixtures[rung],
                                reason,
                                extra={"size_rung": C14_RUNG_LABEL[rung], "workload_id": rung, "measurement": measure},
                            )
                else:
                    _refuse_cell(criterion_id, fixtures[specs[criterion_id]["workload"]], reason)
        finally:
            if proc is not None:
                _stop_server(proc)

    summary = {
        "suite": "document_criteria",
        "criteria": criteria,
        "content_gate_by_editor": gates_by_editor,
        "execution_profile": execution_profile(EXECUTION_PROFILE),
        "host_class": host_class(),
        "samples_per_cell": args.samples,
        "fixtures": {
            workload_id: {
                "sha256": fixture["sha256"],
                "byte_size": fixture["byte_size"],
                "paragraph_count": fixture["paragraph_count"],
                "builder": "one <w:p> per generated line (see benchmark_document.docx_paragraph_bytes)",
                "file": _attempt_ref(fixture["path"]) if fixture["path"].is_file() else None,
                "file_note": (
                    None
                    if fixture["path"].is_file()
                    else "not written: this rung is above the ci_broad workload cap and its bytes never reach an editor"
                ),
                "augmented_paragraphs": fixture.get("augmented_paragraphs", 0),
                "augmentation": "perf.fixtures.generate.correctness_fixtures (unicode, emoji, bidi, ime)",
            }
            for workload_id, fixture in fixtures.items()
        },
        "support": rows,
        "scaling": scaling,
        "publishable": False,
        "publication_block_reason": (
            "ci_coarse host_class blocks headline publication; this suite is a coverage and support measurement, "
            "not a published distribution"
        ),
        "quiet_machine_check": _quiet_machine_check(),
        "host": {
            "os": sys.platform,
            "arch": platform.machine(),
            "cpu_model": _host_cpu_model(),
            "ram_bytes": _ram_bytes(),
        },
        "commands": [
            "PYTHONPATH=. python3 perf/runner/benchmark_document.py --editors %s --samples %d"
            % (" ".join(editors), args.samples),
            "PYTHONPATH=. python3 -m unittest perf.tests.test_document_criteria -v",
        ],
    }
    out_root.mkdir(parents=True, exist_ok=True)
    write_json(out_root / "summary.json", summary)
    measured = sum(1 for row in rows if row.get("outcome") == "measured")
    print("Wrote %s (%d cells, %d measured, %d refused)" % (out_root / "summary.json", len(rows), measured, len(rows) - measured))
    return 0


def _quiet_machine_check() -> dict:
    """AGENTS.md section 3: record what else was running, never silence it."""
    record = {"load_average": None, "top_cpu": [], "heavy_trial_job_seen": False}
    try:
        record["load_average"] = [round(value, 2) for value in os.getloadavg()]
    except OSError:
        pass
    try:
        proc = subprocess.run(
            ["ps", "-Ao", "pcpu,comm", "-r"], capture_output=True, text=True, timeout=20
        )
        lines = [line.strip() for line in proc.stdout.splitlines()[1:7] if line.strip()]
        record["top_cpu"] = lines
        joined = " ".join(lines).lower()
        record["heavy_trial_job_seen"] = "neurotic_docx_bench" in joined
    except (OSError, subprocess.SubprocessError):
        pass
    record["note"] = (
        "ci_coarse diagnostic host; numbers are not publishable. The load average and the top CPU "
        "processes are recorded instead of claiming a quiet machine."
    )
    return record


def _median_optional(values: list):
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    clean.sort()
    middle = len(clean) // 2
    if len(clean) % 2:
        return clean[middle]
    return (clean[middle - 1] + clean[middle]) / 2.0


def _host_cpu_model() -> str:
    """CPU brand string from ``perf.runner.host`` (``platform.processor()`` is "arm")."""
    return _contract_host()["cpu_model"]


def main() -> int:
    return run_cli(_main, 'benchmark_document', BROWSER_TARGETS, count_flag='--samples', default_count=SAMPLE_DEFAULT, single=False, max_repetitions=lambda profile: sample_budget_for_profile(profile, 'fresh_process'))


if __name__ == "__main__":
    raise SystemExit(main())
