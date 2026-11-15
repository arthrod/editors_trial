"""A refused clock check names the check that failed, not a skew that is in bound (#195).

At the 500k rung, canvas-editor and Docen were refused with "clock skew
exceeds the 5.0 ms bound (clock_skew_ms=-0.2)": the witness's clock check
failed on another sub-check, and the message blamed the skew.
"""
import pytest

from perf.runner import benchmark_document as bd
from perf.runner.benchmark_document import ProbeRefusal


def _probe(skew, reason):
    return {"clock_skew_ms": skew, "clock_skew_acceptable": False,
            "witness": {"clock_check": {"kind": "clock_skew", "acceptable": False, "reason": reason}}}


def test_an_in_bound_skew_names_the_failed_check():
    text = bd._clock_refusal_text(_probe(-0.2, "anchor_lag_above_bound"))
    assert "anchor_lag_above_bound" in text
    assert "exceeds" not in text


def test_an_out_of_bound_skew_still_says_so():
    assert "exceeds the 5.0 ms bound" in bd._clock_refusal_text(_probe(12.5, "page_offset_above_bound"))


def test_a_missing_check_says_it_is_missing():
    assert "not recorded" in bd._clock_refusal_text({"clock_skew_ms": None, "clock_skew_acceptable": None})


@pytest.mark.parametrize("fn", ["c11_measured_samples", "c12_measured_sample", "c14_measured_sample"])
def test_every_sample_reader_uses_it(fn):
    import inspect
    source = inspect.getsource(getattr(bd, fn))
    assert "clock skew exceeds the %s ms bound" not in source
    assert "_clock_refusal_text(" in source
