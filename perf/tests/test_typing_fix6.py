"""B9 fix — empty-document typing surfaces (fixc10typ lane 2).

HF evidence (2026-11-11, commit a5b1654): every eigenpal B9 cell crashes 30 s
on ``locator.waitFor`` for ``.docx-page-content [data-paragraph-id][data-start]``
and every folio cell crashes 30 s in ``page.waitForFunction``. The B9 fixture
is a zero-text DOCX by design, so:

- eigenpal paints ``[data-start]`` only on nonzero-range text spans — an empty
  paragraph has no span, so the edit selector can never exist;
- folio's ``ready_js`` demanded a ``[data-page-number]`` with non-empty
  innerText — impossible for a zero-text document — and its editable
  ``.ProseMirror`` mounts off-screen on the first page click, while the
  painted ``.paged-editor__pages`` carries the whole document text.

Each claim has its own measurer:

F1  an eigenpal-shaped surface (a ``data-paragraph-id`` fragment without any
    ``data-start`` span) types and verifies via ``typing_edit_selector`` +
    ``typing_click_selector`` (``typing_empty_span.html``).
F2  a folio-shaped surface (lazy off-screen editable + painted pages) types
    and verifies via ``typing_edit_selector`` + ``typing_present_selector`` +
    ``typing_click_selector`` (``typing_lazy_editable.html``).
F3  the BROWSER_TARGETS entries declare the selectors these surfaces need:
    eigenpal's whole-document editable plus paragraph click target, folio's
    editable/present/click triple and no text-requiring ``ready_js``.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / 'fixtures'


def _session(target, tmp_path):
    from perf.runner.benchmark_typing import session
    args = SimpleNamespace(budget_s=60, cadence_ms=0, sample_s=5,
                           witness_every=100, quiescence_s=0)
    return asyncio.run(session(target, 'abc def', args, tmp_path))


def test_eigenpal_shaped_empty_document_is_measured(tmp_path):
    pytest.importorskip('playwright.async_api')
    pytest.importorskip('psutil')
    from perf.runner.browser_hosts import StaticHost
    host = StaticHost(FIXTURES)
    try:
        result, _rows = _session({
            'url': host.url + '/typing_empty_span.html',
            'edit_selector': '.docx-page-content [data-paragraph-id][data-start]',
            'typing_edit_selector': '.docx-pages',
            'typing_click_selector': '.docx-page-content [data-paragraph-id]',
            'ready_selector': '.status-ok'}, tmp_path)
    finally:
        host.stop()
    assert result['failure_reason'] is None, result
    assert result['characters_typed'] == 7


def test_folio_shaped_lazy_editable_is_measured(tmp_path):
    pytest.importorskip('playwright.async_api')
    pytest.importorskip('psutil')
    from perf.runner.browser_hosts import StaticHost
    host = StaticHost(FIXTURES)
    try:
        result, _rows = _session({
            'url': host.url + '/typing_lazy_editable.html',
            'edit_selector': '[data-page-number]',
            'typing_edit_selector': '.paged-editor__hidden-pm .ProseMirror',
            'typing_present_selector': '.paged-editor__pages',
            'typing_click_selector': '[data-page-number]',
            'typing_load_click_selector': '[data-page-number]',
            'ready_selector': '[data-page-number]'}, tmp_path)
    finally:
        host.stop()
    assert result['failure_reason'] is None, result
    assert result['characters_typed'] == 7


def test_typing_targets_declare_empty_document_selectors():
    from perf.runner.benchmark_warm_cold import BROWSER_TARGETS
    eigenpal = BROWSER_TARGETS['eigenpal']
    assert eigenpal['typing_edit_selector'] == '.docx-pages'
    # `data-paragraph-id` marks text spans; a zero-text document has none, so
    # the caret click lands on the page content box the engine hit-tests.
    assert eigenpal['typing_click_selector'] == '.docx-page-content'
    folio = BROWSER_TARGETS['folio']
    # A zero-text document still paints a page; B9 readiness cannot require text.
    assert folio['typing_ready_js'] is None
    assert folio['typing_edit_selector'] == '.paged-editor__hidden-pm .ProseMirror'
    assert folio['typing_present_selector'] == '.paged-editor__pages'
    assert folio['typing_click_selector'] == '[data-page-number]'
    # The hidden ProseMirror only mounts on a click, inside the load window.
    assert folio['typing_load_click_selector'] == '[data-page-number]'
