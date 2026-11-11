"""r3s2fix: regression tests for the review of the shakedown-2 fixes.

Each test turns one shape from /Users/arthrod/temp/T/e2-g-rev/.scratch/review-s2/
(probe_py.py, probe_js.mjs, probe_follow.py) from "publishes" to "refused".
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from perf.runner.witness import validate_witness
from perf.tests.test_witness import WitnessValidatorTests

REPO = Path(__file__).resolve().parents[2]


def _node() -> str | None:
    return shutil.which("node")


# ---------------------------------------------------------------------------
# Item 1 (MAJOR 2): a lag bound above the 250 ms floor needs at least ten
# frame-interval samples. Two stalled frames used to widen the bound to
# 3 * 1350 = 4050 ms, so a 4 s key-to-paint "measured".
# ---------------------------------------------------------------------------


def _loose_frame_record() -> dict:
    """The reviewer's frame_validator shape: interval 1350 ms on two samples,
    bound 4050, lag 4000 — internally consistent, resting on too little data."""
    record = WitnessValidatorTests.good_record()
    clock = record["clock_check"]
    interval = 1350.0
    lag_bound = max(3 * interval, 250.0)
    lag = 4000.0
    clock["frame_interval_ms"] = interval
    clock["frame_interval_samples"] = 2
    clock["lag_bound_ms"] = lag_bound
    clock["frame_lag_ms"] = lag
    clock["frame_page_ms"] = clock["change_page_ms"] + lag
    clock["checks"]["anchor_lag_within_bound"] = True
    clock["conversion"]["error_upper_ms"] = lag_bound
    clock["conversion"]["published"] = '[-2 ms, +%s ms] (never "±2 ms")' % lag_bound
    if isinstance(record.get("after_page_ms"), (int, float)) and not isinstance(
        record.get("after_page_ms"), bool
    ):
        record["frame_page_ms"] = record["after_page_ms"] + lag
    return record


def test_lag_bound_above_floor_with_two_interval_samples_refused():
    verdict = validate_witness(_loose_frame_record())
    assert verdict.get("refused"), "a 4050 ms bound on two samples must be refused: %r" % (verdict,)
    assert verdict.get("reason") == "clock_check_evidence_contradicted"


def test_healthy_interval_record_still_validates():
    verdict = validate_witness(WitnessValidatorTests.good_record())
    assert not verdict.get("refused"), "the healthy 60-sample record must pass: %r" % (verdict,)
    assert verdict.get("ok")


def test_erased_sample_count_cannot_widen_the_bound():
    """Deleting frame_interval_samples must not rescue a bound above the floor."""
    record = _loose_frame_record()
    del record["clock_check"]["frame_interval_samples"]
    verdict = validate_witness(record)
    assert verdict.get("refused"), "a bound above the floor with no sample count must refuse: %r" % (verdict,)


def test_frame_interval_bound_rule_in_node():
    """The producer's own rule (r3s2fix_frame_interval.mjs)."""
    node = _node()
    if node is None:
        raise pytest.skip("node is not on PATH")
    script = Path(__file__).with_name("r3s2fix_frame_interval.mjs")
    proc = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
