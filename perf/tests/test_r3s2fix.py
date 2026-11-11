"""r3s2fix: regression tests for the review of the shakedown-2 fixes.

Each test turns one shape from /Users/arthrod/temp/T/e2-g-rev/.scratch/review-s2/
(probe_py.py, probe_js.mjs, probe_follow.py) from "publishes" to "refused".
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from build import perf_e2_tables as report
from perf.analysis import e2_cells as cells
from perf.runner.witness import validate_witness
from perf.tests.test_e2_reader_r3reader3 import _summary, _write_job
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


# ---------------------------------------------------------------------------
# Item 2 (MAJOR 3): the summary pin must not hide the attempts' pins. A seed
# whose summary says tree-a while its attempts record tree-b measured more
# than one build; the cell is refused, never published under the summary pin.
# Real data (hf-data-shakedown2): 244 job/editor pin pairs, 0 conflicts.
# ---------------------------------------------------------------------------


def _input_job(root, job_id, seed, *, summary_tree, attempt_tree, value=20.0):
    return _write_job(
        root, "benchmark_input", job_id, seed, range(30),
        summary=_summary(job_id, seed, hosts={"plate": {"tree_sha256": summary_tree}}),
        tree=attempt_tree, values={rep: value for rep in range(30)},
    )


def test_summary_pin_conflicting_attempt_pins_refuses_cell(tmp_path):
    first = _input_job(tmp_path / "s0", "j0", 0, summary_tree="tree-a", attempt_tree="tree-b")
    second = _input_job(tmp_path / "s1", "j1", 1, summary_tree="tree-a", attempt_tree="tree-b")
    cell = cells.read_criterion_cell([first, second], "plate", "C07")
    assert not cell["published"], "a seed with two recorded builds must not publish: %r" % (
        cell.get("reason"),
    )
    text = report._cell_text({}, [first, second], "plate", "C07")
    assert "20.0 ms" not in text


def test_summary_pin_matching_attempt_pins_still_publishes(tmp_path):
    first = _input_job(tmp_path / "s0", "j0", 0, summary_tree="tree-a", attempt_tree="tree-a")
    second = _input_job(tmp_path / "s1", "j1", 1, summary_tree="tree-a", attempt_tree="tree-a")
    cell = cells.read_criterion_cell([first, second], "plate", "C07")
    assert cell["published"], "one recorded build per seed must publish: %r" % (
        cell.get("reason"),
    )
    text = report._cell_text({}, [first, second], "plate", "C07")
    assert "20.0 ms" in text


def test_attempt_pins_disagreeing_across_seeds_refuses(tmp_path):
    """The reviewer's disagreeing-samples shape: seed1 tree-b, seed2 tree-c,
    both summaries claiming tree-a."""
    first = _input_job(tmp_path / "s0", "j0", 0, summary_tree="tree-a", attempt_tree="tree-b", value=20.0)
    second = _input_job(tmp_path / "s1", "j1", 1, summary_tree="tree-a", attempt_tree="tree-c", value=99999.0)
    cell = cells.read_criterion_cell([first, second], "plate", "C07")
    assert not cell["published"]
    text = report._cell_text({}, [first, second], "plate", "C07")
    assert "99999" not in text and "20.0 ms" not in text
