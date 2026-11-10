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
import os
import platform
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
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.benchmark_ci_contract import (  # noqa: E402
    INTERPRETATION_CONDITIONS,
    _finalize_publishable,
    _host_base,
    _ram_bytes,
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

C14_RUNGS = ("micro-paragraphs", "short-paragraphs", "long-paragraphs")
C14_RUNG_LABEL = {"micro-paragraphs": "micro", "short-paragraphs": "short", "long-paragraphs": "long"}
C15_MEASUREMENTS = ("first_match", "search_complete", "replace_all", "index_quiescence")

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
        "find_input_selector": (
            "input[placeholder*=\"Find\" i], input[placeholder*=\"Search\" i], "
            "[class*=\"find\"] input, [class*=\"search\"] input"
        ),
        "find_count_selector": "[class*=\"count\"], [class*=\"result\"], [role=\"status\"]",
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": (
            "source reading: the host's Plate plugin set (harness/ui/plate/src/main.tsx) contains no find plugin"
        ),
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
        "find_input_selector": (
            "input[placeholder*=\"Find\" i], input[placeholder*=\"Search\" i], "
            "[class*=\"find\"] input, [class*=\"search\"] input"
        ),
        "find_count_selector": "[class*=\"count\"], [role=\"status\"]",
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": (
            "probe observation (this change): no find widget appears after Control+f/Meta+f on this host; "
            "the generic selector set stays so a future toolbar changes the verdict without a config edit"
        ),
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
        "ready_js": "window.__DOCEN_READY__ === true",
        "find_input_selector": None,
        "find_count_selector": None,
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": "no find surface verified for this host; C15 refuses by name",
        "note": (
            "docen renders pages as LeaferJS canvases inside docen-document's open shadow root "
            "(.canvas-pages > div), so the probe's in-page document.querySelector sees no block "
            "boxes or text: the light-DOM <docen-document> element is the document surface. "
            "C11 is the browser paint entry only; C12/C14 are refused by the probe. "
            "edit_selector matches the shadow-piercing Playwright locator warm/cold already uses."
        ),
    },
    "wordcraft": {
        "doc_selector": "#wordcraft_canvas",
        "page_selector": None,
        "page_model": "continuous_flow",
        "edit_selector": "#wordcraft_canvas",
        "ready_js": "window.__WORDCRAFT_READY__ === true",
        "find_input_selector": None,
        "find_count_selector": None,
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": "no find surface verified for this host; C15 refuses by name",
        "note": (
            "wasm egui app: the whole document is one canvas, no DOM text. FCP fires on the "
            "blank app's first paint (~24 ms) while the corpus opens ~1 s later (ready_ms 1036), "
            "so the C11 sample is the app-shell paint entry, not a document paint; the readiness "
            "gate still refuses until the app's own title frame names the open document."
        ),
    },
    "apryse": {
        "doc_selector": "#viewer",
        "page_selector": None,
        "page_model": "continuous_flow",
        "edit_selector": "#pageContainer1",
        "ready_js": "window.__aprysePerf && window.__aprysePerf.state === 'rendered'",
        "find_input_selector": None,
        "find_count_selector": None,
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": "no find surface verified for this host; C15 refuses by name",
        "note": (
            "pageContainer1..N live inside the apryse-webviewer open shadow root, invisible to "
            "the probe's in-page queries; #viewer is the light-DOM WebViewer mount. "
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
        "find_source_note": (
            "no find UI on this host: probe --mode find (2026-11-08, /tmp/perf-run-logs/doc-config-docxodus-find.json) "
            "returned not_applicable 'no find widget appears after Control+f/Meta+f'"
        ),
        "note": (
            "Default surface is convertDocxToPaginatedHtml output: materialized .page-box page divs "
            "(816x1056 at 1280px) with one p per source paragraph, static (no caret). The Block-editor mount "
            "(#modeEditor) renders [data-anchor] p blocks but at docxodus 15.0.0 wires 0 contenteditable blocks, "
            "so no keyboard-driven y-shift surface exists on either mode; C12 is not_applicable."
        ),
    },
    "canvas": {
        "doc_selector": "#editor .ce-page-container > canvas",
        "page_selector": "#editor .ce-page-container",
        "page_model": "page",
        "edit_selector": "#editor .ce-page-container > canvas",
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
            "empty by design, so C12 (no DOM block boxes with text) and C14 (DOM-text usable mark) are "
            "not_applicable on this surface; C11 is measurable because FCP counts the painted canvas."
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
        "find_input_selector": ".find-input",
        "find_count_selector": ".find-count",
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": (
            "source reading: genoffice FindPanel.tsx renders .find-input and an aria-live .find-count (repos/genoffice/apps/docs/src/renderer/components/FindPanel.tsx:517,532); the count selector was not exercised end-to-end in this change"
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
        "find_input_selector": (
            "input[placeholder*=\"Find\" i], input[placeholder*=\"Search\" i], "
            "[class*=\"find\"] input, [class*=\"search\"] input"
        ),
        "find_count_selector": "[class*=\"count\"], [role=\"status\"]",
        "find_query": "NEEDLE",
        "find_expected_matches": 5,
        "find_source_note": (
            "source reading: SuperDoc ships a .sd-find-replace surface and superdoc.ui.search, but this host "
            "constructs SuperDoc without a UI handle"
        ),
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
    """A probe result that cannot become a sample. Carries the recorded reason."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


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


def c11_measured_samples(probe: dict) -> list:
    """C11 samples are the browser's own first-contentful-paint entries."""
    paints = probe.get("paints") or []
    if not any(row.get("name") == "first-contentful-paint" for row in paints):
        raise ProbeRefusal("no first-contentful-paint entry in performance paint entries")
    fcp = probe.get("fcp_ms")
    if fcp is None or isinstance(fcp, bool) or float(fcp) < 0:
        raise ProbeRefusal("first-contentful-paint entry has no usable start time")
    # probe['first_element_ms'] is the DOM check. It is recorded beside the
    # paint entry and is never substituted for it.
    return [float(fcp)]


def c12_measured_sample(probe: dict) -> float:
    """C12 sample: input -> first compositor frame at/after the observed y-shift."""
    if not probe.get("moved"):
        raise ProbeRefusal(
            "text-shift assertion failed: anchor block did not move down (anchor_top=%r after=%r)"
            % ((probe.get("before") or {}).get("anchor_top"), probe.get("anchor_top_after"))
        )
    presented = probe.get("presented_frame_ms")
    if presented is None:
        raise ProbeRefusal("no compositor frame captured at or after the observed y-shift")
    value = float(presented)
    if value < 0:
        raise ProbeRefusal("negative presented_frame_ms")
    return value


def c14_measured_sample(probe: dict) -> float:
    """C14 sample: navigation -> first compositor frame at/after usable."""
    usable = probe.get("usable_ms")
    if usable is None:
        raise ProbeRefusal("no DOM usability mark (page/block element never appeared with text)")
    presented = probe.get("presented_frame_ms")
    if presented is None:
        raise ProbeRefusal("no compositor frame captured at or after first usable")
    value = float(presented)
    if value + 5 < float(usable):
        raise ProbeRefusal(
            "compositor frame timestamp precedes the DOM usability mark (frame=%r usable=%r); clock mismatch"
            % (value, usable)
        )
    return value


def find_outcomes(probe: dict) -> dict:
    """C15: one outcome per catalog measurement. A refusal carries no timing."""
    reason = str(probe.get("reason") or "").strip()
    status = probe.get("status")
    if status == "not_applicable":
        if not reason:
            raise ProbeRefusal("not_applicable without a reason")
        for key in ("first_match_ms", "search_complete_ms"):
            if probe.get(key) is not None:
                raise ProbeRefusal("not_applicable carries a %s timing" % key)
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
        return path.name


def _probe_cmd(*, mode: str, target: dict, cfg: dict, corpus_path: Path, extra: list) -> list:
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
        str(PROBE_TIMEOUT_S * 1000),
    ]
    if cfg.get("page_selector"):
        cmd.extend(["--page-selector", cfg["page_selector"]])
    if cfg.get("ready_js"):
        cmd.extend(["--ready-js", cfg["ready_js"]])
    if target.get("wait_after_ready"):
        cmd.extend(["--wait-after-ready", str(target["wait_after_ready"])])
    cmd.extend(extra)
    return cmd


def _run_probe(cmd: list, *, editor_id: str) -> dict:
    proc = subprocess.run(cmd, cwd=str(REPO / "harness" / "ui"), capture_output=True, text=True, timeout=PROBE_TIMEOUT_S)
    payload = None
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = None
    if payload is None:
        raise ProbeRefusal(
            "probe produced no JSON for %s (exit %s): %s"
            % (editor_id, proc.returncode, (proc.stderr or proc.stdout or "")[-300:].strip())
        )
    if proc.returncode != 0 or payload.get("status") == "probe_error":
        raise ProbeRefusal("probe error for %s: %s" % (editor_id, payload.get("reason") or proc.stderr[-300:]))
    if payload.get("error"):
        raise ProbeRefusal("probe refused %s: %s" % (editor_id, payload["error"]))
    return payload


# --------------------------------------------------------------------------- #
# Attempt writers
# --------------------------------------------------------------------------- #


def _env_for(*, editor_id: str, editor_version: str, fixture: dict, cache_state: str) -> dict:
    env = _host_base(
        editor_id=editor_id,
        editor_version=editor_version,
        execution_profile=EXECUTION_PROFILE,
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
    spec = CRITERIA[criterion_id]
    stats = summarize(samples, spec["cache_state"], env["repetition_unit"], seed=0)
    pub, reason = trial_publishable_flags(env, spec["layer"], stats["n"])
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
) -> Path:
    spec = CRITERIA[criterion_id]
    if not failure_reason or not failure_reason.strip():
        raise ValueError("refusal for %s/%s needs a reason" % (criterion_id, editor_id))
    if outcome not in ("not_run", "not_applicable", "unsupported", "unverified", "failed"):
        raise ValueError("refusal outcome %r" % (outcome,))
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
    )
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


def _run_load_samples(*, editor_id: str, target: dict, cfg: dict, fixture_path: Path, count: int) -> tuple:
    """C11: one fresh browser per sample; sample = navigation -> FCP entry."""
    cmd = _probe_cmd(mode="load", target=target, cfg=cfg, corpus_path=fixture_path, extra=[])
    samples = []
    diagnostics = []
    for _ in range(count):
        payload = _run_probe(cmd, editor_id=editor_id)
        values = c11_measured_samples(payload)
        samples.extend(values)
        diagnostics.append(
            {
                "fcp_ms": payload.get("fcp_ms"),
                "first_element_ms": payload.get("first_element_ms"),
                "first_element_delta_from_fcp_ms": payload.get("first_element_delta_from_fcp_ms"),
                "first_element_info": payload.get("first_element_info"),
                "first_element_selector": payload.get("first_element_selector"),
                "document_text_at_ms": payload.get("document_text_at_ms"),
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
    )
    samples = []
    diagnostics = []
    for _ in range(count):
        payload = _run_probe(cmd, editor_id=editor_id)
        samples.append(c12_measured_sample(payload))
        diagnostics.append(
            {
                "shift_px": payload.get("shift_px"),
                "matched_by": payload.get("matched_by"),
                "block_count_before": payload.get("block_count_before"),
                "block_count_after": payload.get("block_count_after"),
                "insertion_created_block": payload.get("insertion_created_block"),
                "anchor_top_after": payload.get("anchor_top_after"),
                "first_frame_after_input_ms": payload.get("first_frame_after_input_ms"),
                "frames_total": payload.get("frames_total"),
                "frames_after_shift_observed": payload.get("frames_after_shift_observed"),
                "navigation_ms": payload.get("navigation_ms"),
                "ready_ms": payload.get("ready_ms"),
                "page_errors": payload.get("page_errors"),
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
    samples = []
    diagnostics = []
    for _ in range(count):
        payload = _run_probe(cmd, editor_id=editor_id)
        samples.append(c14_measured_sample(payload))
        diagnostics.append(
            {
                "usable_ms": payload.get("usable_ms"),
                "usable_source": payload.get("usable_source"),
                "first_element_ms": payload.get("first_element_ms"),
                "fcp_ms": payload.get("fcp_ms"),
                "page_count": payload.get("page_count"),
                "document_text_chars": payload.get("document_text_chars"),
                "document_text": payload.get("document_text"),
                "frames_total": payload.get("frames_total"),
                "frames_after_usable": payload.get("frames_after_usable"),
                "navigation_ms": payload.get("navigation_ms"),
                "ready_ms": payload.get("ready_ms"),
                "page_errors": payload.get("page_errors"),
            }
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
    if cfg.get("find_expected_matches") is not None:
        cmd.extend(["--find-expected-matches", str(cfg["find_expected_matches"])])
    return _run_probe(cmd, editor_id=editor_id)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--editors", nargs="*", default=None, help="default: every browser host")
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
    limit = sample_budget_for_profile(EXECUTION_PROFILE, "fresh_process")
    if args.samples > limit:
        raise SystemExit("--samples %d exceeds the %s fresh_process budget (%d)" % (args.samples, EXECUTION_PROFILE, limit))

    run_day = date.today().isoformat().replace("-", "_")
    out_root = args.out_root or (REPO / "perf" / "out" / ("document_%s" % run_day))
    attempt_dir = out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir = out_root / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)

    ladder = {row["workload_id"]: row for row in size_ladder()}
    fixtures: dict = {}
    for workload_id in set(list(C14_RUNGS) + [spec["workload"] for spec in CRITERIA.values() if spec["workload"]]):
        rung = ladder[workload_id]
        fixture = build_fixture(rung)
        fixture["path"] = fixture_dir / ("%s-split.docx" % workload_id)
        try:
            assert_workload_allowed(EXECUTION_PROFILE, workload_id)
            allowed = True
        except ValueError:
            # A rung above the profile cap keeps its declared record (hash, size,
            # paragraph count) but its bytes are never written to disk and never
            # reach an editor.
            allowed = False
        if allowed and not fixture["path"].is_file():
            fixture["path"].write_bytes(fixture["bytes"])
        fixtures[workload_id] = fixture

    rows: list = []
    scaling: list = []
    failures = 0

    for editor_id in editors:
        target = BROWSER_TARGETS[editor_id]
        lane = target.get("lane") or default_lane(editor_id)
        editor_version = pin_label(editor_id)
        cfg = DOCUMENT_TARGETS.get(editor_id)
        support_note = (cfg or {}).get("note")
        find_source_note = (cfg or {}).get("find_source_note")
        refuse_reason = None
        if cfg is None:
            structure = STRUCTURE_NOTES.get(editor_id, "no verified document-structure selectors for this host")
            refuse_reason = (
                "not driven: benchmark_document has no verified document-structure config for %s (%s); "
                "a guessed first-block/page selector or insertion target would measure the host shell"
                % (editor_id, structure)
            )

        # C11/C12/C14 workloads are fixed; refuse without starting the host.
        def _refuse_cell(criterion_id: str, workout_fixture: dict, reason: str, outcome: str = "not_run", extra: dict | None = None) -> None:
            env = _env_for(
                editor_id=editor_id,
                editor_version=editor_version,
                fixture=workout_fixture,
                cache_state=CRITERIA[criterion_id]["cache_state"],
            )
            path = _write_refusal(
                attempt_dir=attempt_dir,
                criterion_id=criterion_id,
                editor_id=editor_id,
                lane=lane,
                env=env,
                outcome=outcome,
                failure_reason=reason,
                diagnostic=extra,
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
                        fixture=fixtures[CRITERIA["C15"]["workload"]],
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
                        _refuse_cell("C14", fixtures[rung], reason, extra={"size_rung": C14_RUNG_LABEL[rung], "workload_id": rung})
                else:
                    _refuse_cell(criterion_id, fixtures[CRITERIA[criterion_id]["workload"]], refuse_reason)
            continue

        proc = None
        try:
            proc = _start_server(editor_id, target)

            for criterion_id in criteria:
                if criterion_id == "C11":
                    fixture = fixtures[CRITERIA["C11"]["workload"]]
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
                        _refuse_cell("C11", fixture, refusal.reason, outcome="failed")
                        failures += 1
                        continue
                    path, trial = _write_measured(
                        attempt_dir=attempt_dir,
                        criterion_id="C11",
                        editor_id=editor_id,
                        lane=lane,
                        env=env,
                        samples=samples,
                        diagnostic={
                            "suite": "document",
                            "clock": {
                                "start": "navigation_start",
                                "end": "performance first-contentful-paint entry",
                                "dom_check": "first page/block element present with a layout box, sampled on the next animation frame",
                                "document_text_check": "document text laid out (concatenated trimmed text >= 8 chars)",
                                "dom_check_is_not_the_sample": True,
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
                            "outcome": "measured",
                            "median_ms": trial["summary_stats"]["median"],
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
                    fixture = fixtures[CRITERIA["C12"]["workload"]]
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
                        _refuse_cell("C12", fixture, refusal.reason, outcome="failed")
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
                            },
                            "insertion": "Enter at document start then one character",
                            "shift_assertion": (
                                "the anchor block (unique text below the insertion point, located by DOM identity "
                                "or text) moves down by >0.5 px"
                            ),
                            "samples": diagnostics,
                        },
                    )
                    rows.append(
                        {
                            "criterion_id": "C12",
                            "editor_id": editor_id,
                            "outcome": "measured",
                            "median_ms": trial["summary_stats"]["median"],
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
                            assert_workload_allowed(EXECUTION_PROFILE, rung)
                        except ValueError as exc:
                            reason = "execution_profile: %s" % (exc,)
                            env = _env_for(
                                editor_id=editor_id,
                                editor_version=editor_version,
                                fixture=fixture,
                                cache_state=CRITERIA["C14"]["cache_state"],
                            )
                            path = _write_refusal(
                                attempt_dir=attempt_dir,
                                criterion_id="C14",
                                editor_id=editor_id,
                                lane=lane,
                                env=env,
                                outcome="not_run",
                                failure_reason=reason,
                                diagnostic={"size_rung": label, "workload_id": rung},
                            )
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
                            path = _write_refusal(
                                attempt_dir=attempt_dir,
                                criterion_id="C14",
                                editor_id=editor_id,
                                lane=lane,
                                env=env,
                                outcome="failed",
                                failure_reason=reason,
                                diagnostic={"size_rung": label, "workload_id": rung},
                            )
                            rung_rows.append(
                                {
                                    "workload_id": rung,
                                    "size_rung": label,
                                    "outcome": "failed",
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
                                    "outcome": "failed",
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
                            }
                            for rung, data in rung_attempts.items()
                        }
                        for rung, data in rung_attempts.items():
                            label = C14_RUNG_LABEL[rung]
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
                                    "clock": {
                                        "start": "navigation_start",
                                        "end": "first compositor screencast frame at or after the document became usable",
                                        "dom_usability": "document text laid out (concatenated trimmed text >= 8 chars, element has a layout box)",
                                    "correctness_evidence": "rendered DOM text, checked against I01-I03 by evaluate_measured_trial",
                                    },
                                    "no_pooled_figure": True,
                                    "curve_medians_ms": curve,
                                    "samples": data["diagnostics"],
                                },
                            )
                            rung_rows.append(
                                {
                                    "workload_id": rung,
                                    "size_rung": label,
                                    "outcome": "measured",
                                    "n": len(data["samples"]),
                                    "median_ms": trial["summary_stats"]["median"],
                                    "attempt_file": _attempt_ref(path),
                                }
                            )
                            rows.append(
                                {
                                    "criterion_id": "C14",
                                    "editor_id": editor_id,
                                    "size_rung": label,
                                    "workload_id": rung,
                                    "outcome": "measured",
                                    "median_ms": trial["summary_stats"]["median"],
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
                    fixture = fixtures[CRITERIA["C15"]["workload"]]
                    env = _env_for(
                        editor_id=editor_id,
                        editor_version=editor_version,
                        fixture=fixture,
                        cache_state=CRITERIA["C15"]["cache_state"],
                    )
                    try:
                        payload = _run_find(
                            editor_id=editor_id,
                            target=target,
                            cfg=cfg,
                            fixture_path=fixture["path"],
                        )
                        outcomes = find_outcomes(payload)
                    except ProbeRefusal as refusal:
                        outcomes = {
                            name: ("not_applicable", None, refusal.reason) for name in C15_MEASUREMENTS
                        }
                    for measurement, (outcome, value, reason) in outcomes.items():
                        if outcome == "measured" and value is not None:
                            path, trial = _write_measured(
                                attempt_dir=attempt_dir,
                                criterion_id="C15",
                                editor_id=editor_id,
                                lane=lane,
                                env=env,
                                samples=[float(value)],
                                diagnostic={
                                    "suite": "document",
                                    "measurement": measurement,
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
                                },
                            )
                            rows.append(
                                {
                                    "criterion_id": "C15",
                                    "editor_id": editor_id,
                                    "measurement": measurement,
                                    "outcome": "measured",
                                    "median_ms": trial["summary_stats"]["median"],
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
                                diagnostic={"measurement": measurement},
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
            for criterion_id in criteria:
                if criterion_id == "C15":
                    env = _env_for(
                        editor_id=editor_id,
                        editor_version=editor_version,
                        fixture=fixtures[CRITERIA["C15"]["workload"]],
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
                        _refuse_cell(
                            "C14",
                            fixtures[rung],
                            reason,
                            extra={"size_rung": C14_RUNG_LABEL[rung], "workload_id": rung},
                        )
                else:
                    _refuse_cell(criterion_id, fixtures[CRITERIA[criterion_id]["workload"]], reason)
        finally:
            if proc is not None:
                _stop_server(proc)

    summary = {
        "suite": "document_criteria",
        "criteria": criteria,
        "execution_profile": EXECUTION_PROFILE,
        "host_class": "ci_coarse",
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
                "file": _attempt_ref(fixture["path"]),
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
            "cpu_model": platform.processor() or "unknown",
            "ram_bytes": _ram_bytes(),
        },
        "commands": [
            "PYTHONPATH=. python3 perf/runner/benchmark_document.py --editors %s --samples %d"
            % (" ".join(editors), args.samples),
            "PYTHONPATH=. python3 -m unittest perf.tests.test_document_criteria -v",
        ],
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    measured = sum(1 for row in rows if row.get("outcome") == "measured")
    print("Wrote %s (%d cells, %d measured, %d refused)" % (out_root / "summary.json", len(rows), measured, len(rows) - measured))
    return 1 if failures else 0


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


if __name__ == "__main__":
    raise SystemExit(main())
