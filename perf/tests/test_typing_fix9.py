"""r3typing review regressions — the orchestrator's ruled outcomes.

Ruling 1 (BLOCKER): a session whose oracle cannot read document text is
``unverified`` — ``failure_reason='document_text_not_readable'`` with the
modified flag and trusted-key count kept as evidence — and is never counted
as kept by the publication predicate or by ``perf/analysis/e2_typing.py``.

Ruling 2 (MAJOR): a missing marker-only paragraph is excused only by
absorbed-list evidence *at that paragraph's position* — never by an
unrelated count or item elsewhere in the document.

Ruling 3 (MAJOR): a DOM surface that is not editable and cannot take focus
refuses before any character is typed (browser-side case lives in
``test_typing_browser_integration.py``).

Ruling 4: curly-quote autocorrect stays tolerated, and the session records
how many characters were folded so a report can disclose it.
"""

import asyncio
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from perf.runner.benchmark_typing import (
    type_document,
    normalize_marked,
    marker_only_strings,
)
from perf.runner.docx_plaintext import docx_body_text_and_absorbed
from perf.runner.refusals import RefusalCode

UNVERIFIED = RefusalCode.UNVERIFIED.value
from perf.tests.test_typing_fix2 import good
from perf.tests.test_typing_marathon import FakePage, FakeCDP, ResourceSampler


CAPTION = ("IN THE SUPREME COURT\nLOPEZ\nv.\nUNITED STATES\nTOLEDO-FLORES\n"
           "v.\nUNITED STATES\n1. a. Under the Act, an alien may be removed.\n"
           "End of brief.")
# marker-only lines sit at indexes 2 and 5; dropping them shifts nothing
# else only if the paragraph survives as an empty slot.
CAPTION_BLANKED = ("IN THE SUPREME COURT\nLOPEZ\n\nUNITED STATES\n"
                   "TOLEDO-FLORES\n\nUNITED STATES\n"
                   "1. a. Under the Act, an alien may be removed.\n"
                   "End of brief.")


def _sampler(page):
    resources = SimpleNamespace(clock=lambda: 0, process_snapshot=lambda: [],
                                profile_size=lambda: 100, network={})
    return ResourceSampler(resources, page, FakeCDP(page))


def _type(page, text, **kwargs):
    async def witness(char):
        await page.type(char)
        return good()

    return asyncio.run(type_document(
        page, _sampler(page), witness, text, selector='#editor',
        witness_every=2, clock=lambda: 0, **kwargs))


def _flag_verifier(flag, keys, minimum):
    async def verify():
        return {'flag': flag, 'trusted_keys': keys, 'min_keys': minimum}
    return verify


# --- ruling 1: a flag oracle is unverified evidence, never a kept session ---

def test_flag_oracle_session_is_unverified_not_kept():
    result = _type(FakePage(), 'abc\ndef', flag_verifier=_flag_verifier(
        {'evidence': 'corpus \u2022 - WordCraft', 'modified': True}, 6, 6))
    assert result['failure_reason'] == 'document_text_not_readable'
    assert result['refusal_code'] == UNVERIFIED
    assert result['outcome'] == 'unverified'
    assert result['throughput_chars_s'] is None
    # the flag and key count stay on the row as evidence
    assert result['correctness_oracle'] == 'editor_modified_flag'
    assert result['modified_flag']['modified'] is True
    assert result['trusted_keys'] == 6
    assert result['expected_min_keys'] == 6
    assert result['verified'] == ['modified_flag', 'trusted_keys']
    assert result['text_correctness'] is None
    assert result.get('edit_refusal') is None


def test_flag_oracle_excess_keys_cannot_buy_a_verdict():
    result = _type(FakePage(), 'abc\ndef', flag_verifier=_flag_verifier(
        {'evidence': 'corpus \u2022 - WordCraft', 'modified': True}, 10**6, 6))
    assert result['failure_reason'] == 'document_text_not_readable'
    assert result['refusal_code'] == UNVERIFIED
    assert result['outcome'] == 'unverified'
    assert result['trusted_keys'] == 10**6


@pytest.mark.parametrize('flag,edit_refusal', [
    (None, 'modified_flag_unreadable'),
    ({'evidence': 'corpus - WordCraft', 'modified': False}, 'modified_flag_unchanged'),
])
def test_flag_oracle_negative_flag_is_still_unverified(flag, edit_refusal):
    result = _type(FakePage(), 'abc\ndef', flag_verifier=_flag_verifier(flag, 6, 6))
    assert result['failure_reason'] == 'document_text_not_readable'
    assert result['outcome'] == 'unverified'
    assert result['edit_refusal'] == edit_refusal
    assert result['modified_flag'] == flag


def test_flag_oracle_keys_below_min_is_still_unverified():
    result = _type(FakePage(), 'abc\ndef', flag_verifier=_flag_verifier(
        {'evidence': 'corpus \u2022 - WordCraft', 'modified': True}, 5, 6))
    assert result['failure_reason'] == 'document_text_not_readable'
    assert result['outcome'] == 'unverified'
    assert result['edit_refusal'] == 'trusted_keys_below_min'


def test_publication_predicate_never_keeps_a_flag_oracle_row():
    from perf.runner.browser_run import typing_session_kept
    flag_row = {'criterion_id': 'TYPING', 'session_kind': 'throughput',
                'outcome': 'measured', 'failure_reason': None,
                'correctness_oracle': 'editor_modified_flag',
                'throughput_chars_s': 100}
    assert typing_session_kept(flag_row, 'throughput') is False
    kept_row = {**flag_row, 'correctness_oracle': 'dom_document_text', 'refusal_code': None}
    assert typing_session_kept(kept_row, 'throughput') is True
    unverified_row = {**flag_row, 'correctness_oracle': 'editor_modified_flag',
                      'outcome': 'unverified',
                      'failure_reason': 'document_text_not_readable',
                      'throughput_chars_s': None}
    assert typing_session_kept(unverified_row, 'throughput') is False


def test_analysis_session_refusal_rejects_a_flag_oracle_row():
    from perf.analysis.e2_typing import session_refusal, DEFERRED
    row = {'outcome': 'measured', 'failure_reason': None, 'refusal_code': None,
           'publication_block_reason': DEFERRED,
           'correctness_oracle': 'editor_modified_flag',
           'throughput_chars_s': 100}
    assert session_refusal(row, 'throughput') == 'document_text_not_readable'


# --- ruling 2: absorbed evidence is positional, never a count ---

def _read_document(text, absorbed):
    async def read():
        return {'text': text, 'absorbed_markers': absorbed}
    return read


def test_absorbed_item_at_the_marker_position_excuses_a_renumbered_label():
    # Both v. lines became numbered items: the text carries empty slots and
    # the DOM census reports an item at exactly those two line indexes.
    absorbed = [{'index': 2, 'marker': 'i.'}, {'index': 5, 'marker': 'ii.'}]
    result = _type(FakePage(), CAPTION,
                   read_document=_read_document(CAPTION_BLANKED, absorbed))
    assert result['failure_reason'] is None, result
    assert result['marker_only'] == {
        'expected': ['v.', 'v.'], 'in_text': [],
        'absorbed': [{'index': 2, 'marker': 'i.'}, {'index': 5, 'marker': 'ii.'}],
        'missing': [], 'surplus': []}


def test_absorbed_item_elsewhere_does_not_excuse_a_missing_marker():
    # One v. line lost; the only absorbed item sits at index 5 — an
    # unrelated item must not answer for the paragraph at index 2.
    text = ("IN THE SUPREME COURT\nLOPEZ\n\nUNITED STATES\nTOLEDO-FLORES\n"
            "v.\nUNITED STATES\n1. a. Under the Act, an alien may be removed.\n"
            "End of brief.")
    absorbed = [{'index': 5, 'marker': 'v.'}]
    result = _type(FakePage(), CAPTION, read_document=_read_document(text, absorbed))
    assert result['failure_reason'] == 'text_mismatch'
    assert result['marker_only']['missing'] == [{'index': 2, 'marker': 'v.'}]


def test_absorbed_item_on_a_text_line_does_not_excuse():
    # Evidence claiming index 2 while line 2 still carries real text is
    # inconsistent with the document and cannot excuse the missing v.
    text = CAPTION.replace('LOPEZ\nv.\n', 'LOPEZ\n')
    absorbed = [{'index': 2, 'marker': 'v.'}]
    result = _type(FakePage(), CAPTION, read_document=_read_document(text, absorbed))
    assert result['failure_reason'] == 'text_mismatch'


def test_dropping_every_marker_line_refuses():
    result = _type(FakePage(), CAPTION,
                   read_document=_read_document(CAPTION_BLANKED, []))
    assert result['failure_reason'] == 'text_mismatch'
    assert result['marker_only']['missing'] == [
        {'index': 2, 'marker': 'v.'}, {'index': 5, 'marker': 'v.'}]


def test_docx_absorbed_evidence_is_the_paragraph_positions():
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('word/document.xml', (
            b'<?xml version="1.0"?><w:document xmlns:w="w"><w:body>'
            b'<w:p><w:r><w:t>before</w:t></w:r></w:p>'
            b'<w:p><w:pPr><w:numPr/></w:pPr></w:p>'
            b'<w:p><w:r><w:t>after</w:t></w:r></w:p></w:body></w:document>'))
    buf.seek(0)
    text, absorbed = docx_body_text_and_absorbed(buf)
    assert text == 'before\n\nafter'
    assert absorbed == [{'index': 1, 'marker': None}]


# --- ruling 4: tolerated quote autocorrect is disclosed ---

def test_curly_quote_fold_is_disclosed_on_the_session():
    text = 'say "hi" and \'bye\''
    folded = 'say \u201chi\u201d and \u2018bye\u2019'
    result = _type(FakePage(), text, read_document=_read_document(folded, []))
    assert result['failure_reason'] is None, result
    assert result['tolerated_quote_autocorrect_chars'] == 4


def test_case_changes_are_still_refused():
    result = _type(FakePage(), 'abc', read_document=_read_document('ABC', []))
    assert result['failure_reason'] == 'text_mismatch'


# --- resource-phase NITs: the correctness read is not typing ---

def test_typed_100_is_marked_before_the_correctness_read():
    async def check():
        page = FakePage()
        events = []

        class Samples:
            selector = None
            typed_text = ''
            characters_typed = 0

            async def mark(self, name):
                events.append('mark:' + name)

            async def sample(self):
                pass

        async def witness(char):
            await page.type(char)
            return good()

        async def read():
            events.append('read')
            return {'text': 'abc', 'absorbed_markers': []}

        result = await type_document(
            page, Samples(), witness, 'abc', selector='#editor',
            witness_every=2, clock=lambda: 0, read_document=read)
        assert result['failure_reason'] is None
        assert (events.index('mark:typed_100') < events.index('read')
                < events.index('mark:correctness_read'))

    asyncio.run(check())


def test_model_surfaces_skip_the_present_dom_sample():
    from perf.tests.test_typing_r3typing3 import _probe_type
    import asyncio
    result = asyncio.run(_probe_type('x' * 80, 'x' * 80, present_text=False, pay_dom_s=0.25))
    assert result['_inner_reads'] == 0


def test_enter_edit_mode_does_not_wait_for_a_text_line_in_empty_documents():
    from perf.runner import benchmark_typing
    source = __import__('inspect').getsource(benchmark_typing)
    assert 'text_line_timeout_ms=0' in source


def test_fixture_docx_hash_is_recorded():
    from perf.runner import benchmark_typing
    source = __import__('inspect').getsource(benchmark_typing)
    assert 'fixture_docx_sha256' in source


def test_folio_env_port_follows_perf_port_offset():
    from perf.runner.benchmark_warm_cold import offset_targets
    targets = {
        'folio': {'url': 'http://127.0.0.1:5217/',
                  'env': {'FOLIO_PLAYGROUND_PORT': '5217', 'FOLIO_REPO': '/x'}},
        'plate': {'url': 'http://127.0.0.1:5173/'},
    }
    out = offset_targets(targets, 2000)
    assert out['folio']['env']['FOLIO_PLAYGROUND_PORT'] == '7217'
    assert out['folio']['env']['FOLIO_REPO'] == '/x'
    assert out['folio']['env']['PORT'] == '7217'
