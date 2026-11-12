"""#169 F3: a line-leading (c)/(r) rendered as a glyph is symbol autocorrect.

The list-marker parser used to claim (c), (C), (r), and (R) before the
symbol rewrite, so the approved tolerance never fired. A list label the
editor kept is still a list-marker excuse, not a glyph.
"""

from __future__ import annotations

import pytest

from perf.tests.test_typing_fix167 import _type

_GLYPHS = [
    ("(c) test", "\u00a9 test"),
    ("(C) test", "\u00a9 test"),
    ("(r) test", "\u00ae test"),
    ("(R) test", "\u00ae test"),
]


@pytest.mark.parametrize("expected,actual", _GLYPHS)
def test_line_leading_symbol_is_autocorrect_not_a_list_marker(expected, actual):
    result = _type(expected, actual)
    assert result["failure_reason"] is None, result
    assert result["tolerated_symbol_autocorrect_chars"] == 1, result
    assert result["tolerated_list_markers"] == [], result
    assert result["tolerated_marker_strings"] == [], result
    assert result["marker_only"]["missing"] == [], result


def test_line_leading_parenthetical_kept_as_a_list_label_still_excuses():
    """The editor absorbed (c) as a list label and did not paint a glyph."""
    result = _type(
        "(c) test",
        "test",
        absorbed=[{"index": 0, "marker": "(c)", "empty": False}],
    )
    assert result["failure_reason"] is None, result
    assert {"index": 0, "marker": "(c)"} in result["tolerated_list_markers"]
    assert result["tolerated_symbol_autocorrect_chars"] == 0, result
    assert result["marker_only"]["missing"] == [], result


def test_painted_parenthetical_is_not_counted_as_a_symbol():
    result = _type("(c) test", "(c) test")
    assert result["failure_reason"] is None, result
    assert result["tolerated_symbol_autocorrect_chars"] == 0, result
    assert result["tolerated_list_markers"] == [], result
