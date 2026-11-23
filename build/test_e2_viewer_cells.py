"""Report E2, later campaign: a viewer's cells say "does not apply", not "not measured" or "scheduled count not recorded".

Nutrient is a viewer (owner's decision: kept, disclosed). Its input lane
records every launch ``not_applicable`` with the runner's viewer sentence,
and the warm/cold lane schedules no typing launch for it at all. The summary
printed "not measured" for click, paste and undo, and "no figure" with
"scheduled count not recorded" for typing (2026-11-23 render). Both are
untrue: there was nothing to measure, and the count was recorded (zero).

Run: python3 -m pytest build/test_e2_viewer_cells.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT))

import perf_e2_summary as summary  # noqa: E402
import perf_e2_tables as E2  # noqa: E402
from perf.runner import benchmark_document, benchmark_warm_cold  # noqa: E402

VIEWER = benchmark_warm_cold.BROWSER_TARGETS["nutrient"]["viewer_not_applicable"]
NO_REFLOW = benchmark_document.DOCUMENT_TARGETS["nutrient"]["c12_not_applicable"]


def _rounds(reason_code="not_applicable"):
    return ('first: not enough samples (n = 0 of 10; reasons %s: 10); '
            'second: not enough samples (n = 0 of 10; reasons %s: 10)' % (reason_code, reason_code))


def _cells(why):
    return ({"refusal_reasons": {"not_applicable": [why]}}, {"refusal_reasons": {"not_applicable": [why]}})


def test_the_summary_knows_every_reason_the_runner_gives_a_viewer():
    assert VIEWER in summary.NOTHING_TO_MEASURE
    assert NO_REFLOW in summary.NOTHING_TO_MEASURE


def test_a_viewer_refused_click_says_does_not_apply():
    assert summary._why(_rounds(), _cells(VIEWER)) == 'does not apply'


def test_a_harness_refusal_still_says_not_measured():
    assert summary._why(_rounds(), _cells("paint_witness_unavailable")) == 'not measured'


def _cell_text_with(groups, editor="nutrient"):
    pooled = {"groups": groups, "published": False, "reason": "first seed: 0 of 0 launches kept"}
    facts = {}
    with mock.patch.object(E2.e2_cells, "read_criterion_cell", return_value=pooled):
        text = E2._cell_text(facts, [], editor, "C05", "warm_steady", "prose-500w")
    return text, facts


def test_a_viewer_cell_with_no_launch_scheduled_says_does_not_apply_and_why():
    text, facts = _cell_text_with([{"scheduled": 0}, {"scheduled": 0}])
    assert text == "does not apply: %s (no launch was scheduled for it)" % VIEWER
    assert summary._why(text) == 'does not apply'
    assert "scheduled count not recorded" not in text


def test_an_editor_cell_with_no_launch_scheduled_is_not_called_a_viewer():
    text, _ = _cell_text_with([{"scheduled": 0}, {"scheduled": 0}], editor="opendoc")
    assert text == "first: scheduled count not recorded"


def test_a_viewer_criterion_the_runner_schedules_keeps_its_own_wording():
    """Codex: a zero count can be a summary without its order; opening applies to a viewer."""
    pooled = {"groups": [{"scheduled": 0}, {"scheduled": 0}], "published": False, "reason": "x"}
    with mock.patch.object(E2.e2_cells, "read_criterion_cell", return_value=pooled):
        text = E2._cell_text({}, [], "nutrient", "C11", "", "prose-500w")
    assert text == "first: scheduled count not recorded"


def test_a_blocked_viewer_round_is_not_called_not_applicable():
    text, _ = _cell_text_with([{"scheduled": 0, "blocked": True, "block_reason": "run blocked"}, {"scheduled": 0}])
    assert not text.startswith("does not apply")


def test_the_runner_leaves_exactly_these_criteria_out_of_the_viewer():
    targets = benchmark_warm_cold.BROWSER_TARGETS
    declared = set(targets["nutrient"]["criteria"])
    every_editor = set.intersection(*(set(t.get("criteria") or {}) for name, t in targets.items() if name != "nutrient"))
    assert summary.VIEWER_UNSCHEDULED["nutrient"] <= every_editor - declared
    assert summary.VIEWER_NOT_APPLICABLE["nutrient"] == VIEWER


def test_a_missing_scheduled_count_still_says_so():
    text, _ = _cell_text_with([{"scheduled": None}, {"scheduled": 10}])
    assert text == "first: scheduled count not recorded"
