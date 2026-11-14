"""#203: the reader applies C14's damage window to records made before the fix.

C14's natural witness asks whether document damage followed load inside a
500 ms window after a settled frame. Before #203 the window's deadline started
after setup calls into a busy page returned, so a frame recorded minutes later
was accepted: GenOffice at 500,000 words (job 162, e2-apryse) read 268 s from a
frame 144 s past its window opening. Those records carry the evidence: the
frame's page time, the window's opening and length, and the clock conversion's
upper error bound. A frame past ``after_page_ms + window_ms + error`` is not
damage inside the window, so the sample is the document-surface time,
``usable_no_damage``, exactly as the fixed harness reports it. The cached row
is never mutated; a record from the fixed harness (``strict_window`` present)
is left alone.
"""
from copy import deepcopy

from perf.analysis import e2_cells

_PRESENTED_CLOCK = {
    "dom_usability": "document text laid out (concatenated trimmed text >= 8 chars, element has a layout box)",
    "end": "first compositor screencast frame at or after the document became usable",
    "start": "navigation_start",
}


def _row(frame=268147.934, after=124173.7, window=500, error_upper=700.2, usable=3334.2, **witness_extra):
    witness = {
        "kind": "frame_witness",
        "outcome": "witnessed",
        "frame_page_ms": frame,
        "after_page_ms": after,
        "window_ms": window,
        "clock_check": {"conversion": {"error_upper_ms": error_upper}, "lag_bound_ms": error_upper},
        **witness_extra,
    }
    sample = {
        "clock": dict(_PRESENTED_CLOCK),
        "measure": "presented_frame",
        "mechanism": "document_damage",
        "no_damage_followed": False,
        "usable_ms": usable,
        "witness": witness,
    }
    return {
        "criterion_id": "C14",
        "editor_id": "genoffice",
        "measure": "presented_frame",
        "outcome": "measured",
        "samples_ms": [frame],
        "summary_stats": {"median": frame, "n": 1},
        "diagnostic": {
            "clock": dict(_PRESENTED_CLOCK),
            "curve_medians_ms": {"prose-500kw": {"measure": "presented_frame", "median_ms": frame, "n": 1}},
            "measurement": "presented_frame",
            "samples": [sample],
            "size_rung": "prose-500kw",
            "workload_id": "prose-500kw",
        },
    }


def test_damage_past_the_window_reads_as_the_document_surface_time():
    row = _row()
    fixed = e2_cells.c14_window_corrected(row)
    assert fixed["measure"] == "usable_no_damage"
    assert fixed["samples_ms"] == [3334.2]
    assert e2_cells.trial_measure(fixed) == "usable_no_damage"
    sample = fixed["diagnostic"]["samples"][0]
    assert sample["measure"] == "usable_no_damage"
    assert sample["no_damage_followed"] is True
    assert fixed["diagnostic"]["measurement"] == "usable_no_damage"
    assert fixed["diagnostic"]["curve_medians_ms"]["prose-500kw"] == {
        "measure": "usable_no_damage", "median_ms": 3334.2, "n": 1}
    assert "not a frame time" in fixed["diagnostic"]["clock"]["end"]
    note = fixed["window_reclassified"]
    assert note["issue"] == 203
    assert note["frame_after_window_open_ms"] == 143974.2
    assert note["window_end_after_open_ms"] == 1200.2
    assert note["was_ms"] == 268147.934


def test_the_cached_row_is_not_mutated():
    row = _row()
    before = deepcopy(row)
    e2_cells.c14_window_corrected(row)
    assert row == before


def test_damage_inside_the_window_stays():
    row = _row(frame=124173.7 + 400)
    assert e2_cells.c14_window_corrected(row) is row


def test_damage_past_500_ms_inside_the_clock_error_stays():
    """eigenpal's small documents: damage 526 to 612 ms after the window opened,
    inside the conversion's upper error bound, is not provably outside it."""
    row = _row(frame=124173.7 + 612, error_upper=250)
    assert e2_cells.c14_window_corrected(row) is row


def test_a_record_from_the_fixed_harness_is_left_alone():
    row = _row(strict_window=True, window_end_page_ms=124173.7 + 750)
    assert e2_cells.c14_window_corrected(row) is row


def test_other_criteria_and_no_damage_rows_are_left_alone():
    row = _row()
    other = dict(row, criterion_id="C11")
    assert e2_cells.c14_window_corrected(other) is other
    no_damage = dict(row, measure="usable_no_damage")
    assert e2_cells.c14_window_corrected(no_damage) is no_damage

