"""Issue #167 — list-marker absorption for SuperDoc, Folio, and GenOffice."""

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


def test_superdoc_renumbered_marker_on_prior_line_tolerates_typed_prefix():
    """Real capture: innerText carries CSS list labels on their own line
    (241.) before body text, replacing typed 1. a. on the STATEMENT lead-in."""
    text = BRIEF.read_text()
    lines = text.split("\n")
    _, body = prefix_marker_rest(lines[74])
    expected = lines[74]
    actual = f"241.\n{body}"
    result = _type(expected, actual, absorbed=[{"index": 0, "marker": "241."}])
    assert result["failure_reason"] is None, result
    assert {"index": 0, "marker": "1."} in result["tolerated_list_markers"]


def test_superdoc_inline_renumbered_marker_tolerates_multi_prefix():
    text = BRIEF.read_text()
    lines = text.split("\n")
    _, body = prefix_marker_rest(lines[74])
    expected = "\n".join(lines[:380])
    actual = "\n".join(lines[:74] + [f"241. {body}"] + lines[75:380])
    result = _type(expected, actual)
    assert result["failure_reason"] is None, result


def test_vanished_prefix_without_evidence_still_refuses():
    result = _type("STATEMENT\n1. a. Under the Act\n", "STATEMENT\nUnder the Act\n")
    assert result["failure_reason"] == "text_mismatch"


def test_text_mismatch_records_bounded_divergence_context():
    result = _type("alpha beta", "alpha gamma")
    assert result["failure_reason"] == "text_mismatch"
    assert "divergence_expected_excerpt" in result
    assert "divergence_actual_excerpt" in result
    assert len(result["divergence_expected_excerpt"]) <= 81
    assert len(result["divergence_actual_excerpt"]) <= 81
