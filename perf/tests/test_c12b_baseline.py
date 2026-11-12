"""#169 F1: C12 movement is judged against the arm baseline, once.

``scroll-back-after-move.html`` records a post-Enter move and then scrolls
the anchor back. That sample stays measured. ``drift-before-arm.html``
moves the anchor between the census and the arm re-read; Enter itself
moves nothing, and the refusal names the arm baseline.
"""

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path

import pytest

import perf.runner.benchmark_document as bd
from perf.tests.test_r3c12h import reflow_host_payload
from perf.tests.test_schema import _env

REPO = Path(__file__).resolve().parents[2]


def _playwright_ready() -> bool:
    if os.environ.get("WITNESS_PLAYWRIGHT"):
        return True
    for candidate in (
        REPO / "harness" / "ui" / "plate" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright-core",
    ):
        if candidate.is_dir():
            return True
    return False


_needs_browser = pytest.mark.skipif(
    not (shutil.which("node") and _playwright_ready()),
    reason="node+playwright required",
)


@_needs_browser
def test_scroll_back_after_a_recorded_move_is_measured():
    payload = reflow_host_payload("scroll-back-after-move.html", timeout_ms=15000)
    assert payload.get("error") is None, payload
    assert payload.get("moved") is True, payload
    assert payload.get("anchor_frames", 0) >= 1, payload
    assert payload.get("observed_shift_page_ms") is not None, payload
    before = payload.get("before") or {}
    assert isinstance(before.get("census_anchor_top"), (int, float)), payload
    assert isinstance(before.get("anchor_top"), (int, float)), payload
    assert payload.get("anchor_before_top") == before["anchor_top"], payload
    sample = bd.c12_measured_sample(payload)
    assert sample == payload["presented_frame_ms"]
    assert sample > 0


@_needs_browser
def test_drift_before_arm_names_the_arm_baseline():
    payload = reflow_host_payload("drift-before-arm.html", timeout_ms=15000)
    before = payload.get("before") or {}
    census = before.get("census_anchor_top")
    arm = before.get("anchor_top")
    after = payload.get("anchor_top_after")
    assert isinstance(census, (int, float)), payload
    assert isinstance(arm, (int, float)), payload
    # The drift lands before the arm re-read. The printed baseline is that
    # re-read, not the earlier census top.
    assert arm > census + 5, payload
    assert payload.get("anchor_before_top") == arm, payload
    assert payload.get("moved") is not True, payload
    with pytest.raises(bd.ProbeRefusal) as caught:
        bd.c12_measured_sample(payload)
    reason = caught.value.reason
    assert "no post-Enter frame moved the anchor below the arm baseline" in reason, reason
    assert "did not move down" not in reason, reason
    assert repr(arm) in reason, reason
    assert repr(census) not in reason, reason
    # The pair must not describe a downward move that the check then denies.
    if isinstance(after, (int, float)):
        assert not (after > arm + 0.5 and "did not move" in reason), reason


class ArmBaselineRefusal(unittest.TestCase):
    def test_unmoved_probe_names_the_check_and_the_arm_number(self):
        probe = {
            "moved": False,
            "before": {"anchor_top": 66.0, "census_anchor_top": 36.0},
            "anchor_top_after": 58.0,
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(probe)
        reason = caught.exception.reason
        self.assertIn("no post-Enter frame moved the anchor below the arm baseline", reason)
        self.assertIn(repr(66.0), reason)
        self.assertNotIn("did not move down", reason)
        self.assertNotIn(repr(36.0), reason)

def test_arm_baseline_refusal_stays_unverified(tmp_path):
    reason = (
        "no post-Enter frame moved the anchor below the arm baseline "
        "(arm_baseline=66.0 after=58.0)"
    )
    path = bd._write_refusal(
        attempt_dir=tmp_path,
        criterion_id="C12",
        editor_id="superdoc",
        lane="browser",
        env=_env(),
        outcome="failed",
        failure_reason=reason,
    )
    import json

    trial = json.loads(path.read_text())
    assert trial["refusal_code"] == "unverified", trial
    assert trial["samples_ms"] == []
