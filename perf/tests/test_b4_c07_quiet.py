"""r3c07b: the quiet-box C07 contract — io checks, witness schema, contracts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CONTRACT = REPO / "perf" / "tests" / "b4_c07_quiet_contract.mjs"
HOSTS = REPO / "perf" / "tests" / "b4_c07_quiet_hosts.mjs"


def _quiet_window(**over):
    window = {
        "required_ms": 1000,
        "budget_ms": 8000,
        "proven": True,
        "observed_ms": 1240.5,
        "start_page_ms": 2100.0,
        "end_page_ms": 3340.5,
        "changes_seen": 0,
        "events": [],
        "exhausted": False,
        "violated": False,
    }
    window.update(over)
    return window


def _quiet_rect_record(**over):
    """A production-shaped witness carrying a quiet-window proof."""
    from perf.tests.test_b4_fixinput4 import _caret_rect_record

    record = _caret_rect_record(48, 30, 400)
    record["quiet_window"] = _quiet_window(**over)
    return record


def test_a_witness_with_a_proven_quiet_window_is_publishable():
    from perf.runner.witness import validate_witness

    verdict = validate_witness(_quiet_rect_record())
    assert verdict["ok"] is True, verdict


def test_a_witnessed_record_cannot_claim_a_violated_quiet_window():
    from perf.runner.witness import validate_witness

    verdict = validate_witness(_quiet_rect_record(violated=True))
    assert verdict["ok"] is False

    verdict = validate_witness(_quiet_rect_record(exhausted=True))
    assert verdict["ok"] is False

    verdict = validate_witness(_quiet_rect_record(observed_ms=600.0))
    assert verdict["ok"] is False


def _quiet_observation(identity, point, y, arm, frame):
    from perf.tests.witness_records import publishable_witness_record

    witness = publishable_witness_record(frame, arm, quiet_window=_quiet_window())
    return {
        "observation_id": identity,
        "sample_ms": frame - arm,
        "frame_ms": frame,
        "input_ms": arm,
        "point": point,
        "x": 640,
        "y": y,
        "line": {"top": y - 10, "bottom": y + 10},
        "scope": "quiet_box_first_paint",
        "anchor_inside": True,
        "caret_on_clicked_line": True,
        "quiet_window": _quiet_window(),
        "fresh_state": {"state": "untouched_verified"},
        "witness": witness,
    }


def test_c07_measures_with_two_distinct_line_observations():
    """Ruling: at least two painted points measure C07; three are no longer required."""
    from perf.runner.criteria_input_io import assert_payload_shape
    from perf.tests.test_input_criteria import _entry, _payload

    observations = [
        _quiet_observation("click-0", "first_text_line", 200, 100.0, 140.0),
        _quiet_observation("click-1", "last_text_line", 700, 300.0, 341.0),
    ]
    entry = _entry(
        "C07",
        outcome="measured",
        samples_ms=[40.0, 41.0],
        observations=observations,
        sample_observation_ids=["click-0", "click-1"],
    )
    assert_payload_shape(_payload({"C07": entry}))


def test_c07_observation_without_quiet_evidence_is_not_a_sample():
    from perf.runner.criteria_input_io import assert_payload_shape
    from perf.tests.test_input_criteria import _entry, _payload

    kept = _quiet_observation("click-0", "first_text_line", 200, 100.0, 140.0)
    missing = _quiet_observation("click-1", "last_text_line", 700, 300.0, 341.0)
    del missing["quiet_window"]
    entry = _entry(
        "C07",
        outcome="measured",
        samples_ms=[40.0, 41.0],
        observations=[kept, missing],
        sample_observation_ids=["click-0", "click-1"],
    )
    with pytest.raises(ValueError, match="quiet"):
        assert_payload_shape(_payload({"C07": entry}))


def test_c07_observations_sharing_coordinates_are_not_two_points():
    from perf.runner.criteria_input_io import assert_payload_shape
    from perf.tests.test_input_criteria import _entry, _payload

    first = _quiet_observation("click-0", "first_text_line", 200, 100.0, 140.0)
    dup = _quiet_observation("click-1", "page_centre", 200, 300.0, 341.0)
    entry = _entry(
        "C07",
        outcome="measured",
        samples_ms=[40.0, 41.0],
        observations=[first, dup],
        sample_observation_ids=["click-0", "click-1"],
    )
    with pytest.raises(ValueError, match="distinct"):
        assert_payload_shape(_payload({"C07": entry}))


def test_c07_quiet_refusal_codes_map():
    from perf.fixtures.profiles import size_ladder
    from perf.runner.criteria_input_io import trials_from_payload
    from perf.tests.test_input_criteria import _entry, _payload
    from perf.tests.test_schema import _env

    env = _env()
    workload = next(row for row in size_ladder() if row["workload_id"] == "prose-500w")
    for reason, code in (
        ("click_box_not_quiet_before_click", "unverified"),
        ("editor_state_not_untouched", "unverified"),
        ("fewer_than_two_distinct_painted_lines", "unverified"),
        ("editor_load_failed: computeRowColInfo of null", "editor_load_failed"),
    ):
        payload = _payload(
            {"C07": _entry("C07", outcome="failed", samples_ms=[], failure_reason=reason, observations=[])}
        )
        trial = trials_from_payload(
            payload,
            editor_version="plate",
            fixture_sha256=env["fixture_sha256"],
            workload_row=workload,
            docx_size=100,
        )["C07"]
        assert trial["refusal_code"] == code, (reason, trial["refusal_code"])


def test_b4_c07_quiet_contract():
    proc = subprocess.run(
        ["node", str(CONTRACT)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    assert "checks ok" in proc.stdout


@pytest.mark.timeout(420)
def test_b4_c07_quiet_hosts():
    proc = subprocess.run(
        ["node", str(HOSTS)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=400,
    )
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    assert "checks ok" in proc.stdout
