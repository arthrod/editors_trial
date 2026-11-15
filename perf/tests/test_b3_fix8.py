"""Chromium integration: fair Unicode matching and scoped visible text (#135)."""
import pytest
from perf.tests import test_b3_fix7 as content
from perf.tests import test_b3_fix5 as quiet

BASE = 'Alpha bravo charlie delta echo foxtrot golf hotel'

@pytest.fixture(scope='module')
def host():
    # Reuse the existing real-browser integration server and probe transport.
    quiet.DocumentQuietHosts.setUpClass()
    client = quiet.DocumentQuietHosts()
    try:
        yield client
    finally:
        quiet.DocumentQuietHosts.tearDownClass()

@pytest.mark.parametrize('case,expected', [
    ('baseline', BASE), ('smart_quotes', BASE), ('soft_hyphen', BASE),
    ('guillemets', BASE), ('nbsp', BASE),
    ('ligature', BASE.replace('bravo', 'final')),
    ('en_dash', BASE.replace('Alpha bravo', 'Alpha-bravo')),
    ('em_dash', BASE.replace('Alpha bravo', 'Alpha-bravo')),
    ('zero_width', BASE), ('casefold', BASE.replace('bravo', 'Straße')),
    ('baseline', '«ALPHA» bravo char\u00adlie delta echo foxtrot golf “hotel”'),
])
def test_honest_render(host, case, expected):
    result = content.ContentHosts.check(host, 'b3_fix8_text.html?case='+case, expected)
    print(case, expected, result['content_verified'], result['surface_reason'])
    assert result['content_verified'] is True, result
    assert result['usable_ms'] is not None, result

# 8ac764ae (2026-11-10, "count painted aria-hidden text"): folio and
# superdoc paint the document inside aria-hidden, so painted aria-hidden text
# IS the document surface now -- test_fixdoc_surface.py::PaintedAriaHidden
# carries the replacement assertion -- and 'aria_hidden' left this list.
@pytest.mark.parametrize('case', [
    'offscreen', 'below_region', 'textarea', 'input', 'opacity_ancestor',
    'display_none', 'visibility_hidden',
])
def test_hidden_correct_text_cannot_verify(host, case):
    result = content.ContentHosts.check(host, 'b3_fix8_text.html?case='+case, BASE)
    print(case, result['content_verified'], result['surface_reason'])
    assert result['content_verified'] is False, result
    assert result['surface_reason'] == 'document_content_mismatch', result
    assert result['usable_ms'] is None, result
    assert 'Alpha' not in result['document_text'], result
