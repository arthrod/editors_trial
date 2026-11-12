"""Issue #167 — list-item evidence for prefix markers and marker-only lines."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from perf.runner.benchmark_typing import prefix_marker_rest, type_document
from perf.tests.test_typing_fix2 import good
from perf.tests.test_typing_fix9 import _read_document, _sampler
from perf.tests.test_typing_marathon import FakePage

BRIEF = Path(__file__).resolve().parents[1] / "fixtures/briefs/sg-brief-13000w.txt"


def _type(text, actual, *, absorbed=None):
    async def witness(_ch):
        return good()

    return asyncio.run(
        type_document(
            FakePage(),
            _sampler(FakePage()),
            witness,
            text,
            selector="#e",
            witness_every=10**9,
            read_document=_read_document(actual, absorbed or []),
        )
    )


def test_superdoc_renumbered_241_from_real_line_74_shape():
    """Captured shape: CSS list label 241. on the statement line, typed 1. a."""
    lines = BRIEF.read_text().split("\n")
    exp_line = lines[74]
    markers, body = prefix_marker_rest(exp_line)
    assert markers[:2] == ["1.", "a."]
    actual_line = f"{body}"
    absorbed = [
        {"index": 0, "marker": "241.", "empty": False},
        {"index": 0, "marker": "a.", "empty": False},
    ]
    result = _type(exp_line + "\n", actual_line + "\n", absorbed=absorbed)
    assert result["failure_reason"] is None, result
    assert {"index": 0, "marker": "1."} in result["tolerated_list_markers"]
    assert {"index": 0, "marker": "a."} in result["tolerated_list_markers"]


def test_folio_data_list_marker_with_text():
    """Folio reports %1. on the same innerText line as the paragraph body."""
    exp = "STATEMENT\n1. a. Under the Act\nEnd\n"
    act = "STATEMENT\nUnder the Act\nEnd\n"
    absorbed = [
        {"index": 1, "marker": "%1.", "empty": False},
        {"index": 1, "marker": "a.", "empty": False},
    ]
    result = _type(exp, act, absorbed=absorbed)
    assert result["failure_reason"] is None, result


def test_genoffice_list_item_same_line():
    """GenOffice list marker node on the body line (numeric label)."""
    exp = "1. a. Body text here.\n"
    act = "Body text here.\n"
    absorbed = [{"index": 0, "marker": "1.", "empty": False}, {"index": 0, "marker": "a.", "empty": False}]
    result = _type(exp, act, absorbed=absorbed)
    assert result["failure_reason"] is None, result


def test_v_marker_survives_blank_line_shift():
    """Extra blank lines in the read must not misalign standalone v. markers."""
    exp = "A\n\nv.\nB\n"
    act = "A\n\n\n\nv.\n\nB\n"
    result = _type(exp, act)
    assert result["failure_reason"] is None, result


def test_dropped_body_word_refuses():
    result = _type("alpha beta gamma", "alpha gamma")
    assert result["failure_reason"] == "text_mismatch"


def test_extra_body_word_refuses():
    result = _type("alpha beta", "alpha extra beta")
    assert result["failure_reason"] == "text_mismatch"


def test_vanished_prefix_without_list_item_refuses():
    result = _type("1. a. Under the Act\n", "Under the Act\n")
    assert result["failure_reason"] == "text_mismatch"


def test_wrong_marker_class_iv_for_decimal_refuses():
    exp = "1. a. Body\n"
    act = "Body\n"
    absorbed = [{"index": 0, "marker": "iv.", "empty": False}]
    result = _type(exp, act, absorbed=absorbed)
    assert result["failure_reason"] == "text_mismatch"


def test_one_list_item_cannot_answer_two_lines():
    exp = "1. First line\n1. Second line\n"
    act = "First line\nSecond line\n"
    absorbed = [{"index": 0, "marker": "1.", "empty": False}]
    result = _type(exp, act, absorbed=absorbed)
    assert result["failure_reason"] == "text_mismatch"


def test_text_mismatch_records_bounded_divergence_context():
    result = _type("alpha beta", "alpha gamma")
    assert result["failure_reason"] == "text_mismatch"
    assert "divergence_expected_excerpt" in result
    assert "divergence_actual_excerpt" in result
    assert len(result["divergence_expected_excerpt"]) <= 81
    assert len(result["divergence_actual_excerpt"]) <= 81
