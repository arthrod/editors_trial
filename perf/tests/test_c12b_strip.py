"""#169 F4: an extra painted marker on an excused line is divergence.

``strip_surrogate`` used to drop every leading marker once one was excused,
so "x. y. body" measured against "a. body" (tolerated ['a.']) and "y." vanished.
"""

from __future__ import annotations

from perf.tests.test_typing_fix167 import _type


def test_extra_painted_marker_on_an_excused_line_refuses():
    """'x.' answers 'a.' (same alpha class). 'y.' must stay in the compare."""
    result = _type("a. body", "x. y. body")
    assert result["failure_reason"] == "text_mismatch", result
    assert "y." in (result.get("divergence_actual_excerpt") or ""), result


def test_one_painted_surrogate_of_the_same_class_still_measures():
    result = _type("a. body", "x. body")
    assert result["failure_reason"] is None, result
    assert result["tolerated_marker_strings"] == ["a."], result
