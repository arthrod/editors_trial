"""r3s2fix: regression tests for the review of the shakedown-2 fixes.

Each test turns one shape from /Users/arthrod/temp/T/e2-g-rev/.scratch/review-s2/
(probe_py.py, probe_js.mjs, probe_follow.py) from "publishes" to "refused".
"""
import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from build import perf_e2_tables as report
from perf.analysis import e2_cells as cells
from perf.runner import benchmark_document as bd
from perf.runner.witness import validate_witness
from perf.tests.test_e2_reader_r3reader3 import _summary, _write_job
from perf.tests.test_e2_reader_r3reader4 import _blocks_camp
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


# ---------------------------------------------------------------------------
# Item 3 (MAJOR 4): launch files a job's order never named are not aggregated;
# the cell is refused. A byte-identical re-pull of the same run keeps
# deduplicating and publishing. Real data (hf-data-shakedown2): 66 ordered
# jobs, 0 unscheduled launch cells.
# ---------------------------------------------------------------------------


def _add_outlier_files(camp: Path, job_name: str, start: int, count: int, value: float):
    """The reviewer's add_outlier_files: copies of one attempt at `value`
    under launch names the order never declared."""
    job = camp / "benchmark_input" / job_name
    for index in range(start, start + count):
        directory = job / "cells" / ("%04d-plate" % index) / "attempts"
        directory.mkdir(parents=True, exist_ok=True)
        row = json.loads((job / "cells" / "0000-plate" / "attempts" / "c07.json").read_text())
        row["samples_ms"] = [value]
        row["sub_frame_samples"] = [False]
        (directory / "c07.json").write_text(json.dumps(row))


def test_unscheduled_launch_files_in_a_block_refuse_cell(tmp_path):
    a = _blocks_camp(tmp_path, "extra-a", 1)
    b = _blocks_camp(tmp_path, "extra-b", 2)
    _add_outlier_files(a, "b01", 1000, 31, 99999.0)
    _add_outlier_files(b, "b01", 1000, 31, 99999.0)
    cell = cells.read_criterion_cell([a, b], "plate", "C07")
    assert not cell["published"], "31 unscheduled launch files must refuse the cell: %r" % (
        cell.get("reason"),
    )
    text = report._cell_text({}, [a, b], "plate", "C07")
    assert "99999" not in text
    assert "61 of 30" not in text


def test_legitimate_identical_repull_still_publishes(tmp_path):
    a = _blocks_camp(tmp_path, "leg-a", 1)
    b = _blocks_camp(tmp_path, "leg-b", 2)
    shutil.copytree(a / "benchmark_input" / "b01", a / "benchmark_input" / "b01-repull")
    cell = cells.read_criterion_cell([a, b], "plate", "C07")
    assert cell["published"], "a byte-identical re-pull must deduplicate and publish: %r" % (
        cell.get("reason"),
    )
    text = report._cell_text({}, [a, b], "plate", "C07")
    assert "20.0 ms" in text


# ---------------------------------------------------------------------------
# Item 4 (MAJOR 7): the presented-frame C14 path must use the same
# missing-or-exceeds clock check as forced_repaint — an unverifiable page
# clock refuses the sample. Real data (hf-data-shakedown2): 20 presented-
# frame rows, all carry diagnostic.samples[i].clock_skew_ms.
# ---------------------------------------------------------------------------


def _c14_presented_frame_probe(**overrides):
    probe = {
        "usable_ms": 140.0,
        "presented_frame_ms": 160.0,
        "frames_total": 11,
        "frames_after_usable": 4,
        "clock_skew_ms": 0.4,
    }
    probe.update(overrides)
    return probe


def test_presented_frame_without_a_recorded_clock_refuses():
    probe = _c14_presented_frame_probe()
    del probe["clock_skew_ms"]
    with pytest.raises(bd.ProbeRefusal) as caught:
        bd.c14_measured_sample(probe)
    assert "clock" in caught.value.reason.lower()


def test_presented_frame_with_an_excessive_clock_refuses():
    probe = _c14_presented_frame_probe(clock_skew_ms=bd._CLOCK_SKEW_BOUND_MS + 1.0)
    with pytest.raises(bd.ProbeRefusal) as caught:
        bd.c14_measured_sample(probe)
    assert "clock" in caught.value.reason.lower()


def test_presented_frame_with_a_clock_within_bound_measures():
    sample = bd.c14_measured_sample(_c14_presented_frame_probe())
    assert float(sample) == 160.0
    assert sample.measure == bd.C14_FRAME_MEASURE


# ---------------------------------------------------------------------------
# Item 6 (MAJOR 9): the GenOffice find note must not claim anything about the
# product's focus behaviour — the product source (App.tsx:5875..6098) opens
# find from a window keydown listener whenever a document is set, with no
# focus gate. C15 (find) is not measured for any editor in this report.
# ---------------------------------------------------------------------------


def test_genoffice_find_note_makes_no_product_claim():
    note = bd.DOCUMENT_TARGETS["genoffice"]["find_source_note"]
    lowered = note.lower()
    assert "focus" not in lowered
    assert "control+f" not in lowered and "ctrl" not in lowered
    assert "findpanel" not in lowered
    assert "not measured" in lowered


# ---------------------------------------------------------------------------
# Item 7 (MAJOR 10): a usable stamp that comes from a selector must require
# the element to be contentEditable — the same gate usable_js already uses
# (edit_surface.mjs usableExpression). A visible non-editable element is not
# a usable editor surface. Same rule for every editor that uses a selector.
# ---------------------------------------------------------------------------


def _typing_options():
    from types import SimpleNamespace

    return SimpleNamespace(
        budget_s=30,
        cadence_ms=0,
        sample_s=5,
        witness_every=100,
        quiescence_s=0,
    )


def _typing_session(tmp_path, fixture, usable_selector):
    pytest.importorskip("playwright.async_api")
    pytest.importorskip("psutil")
    from perf.runner.benchmark_typing import session
    from perf.runner.browser_hosts import StaticHost

    host = StaticHost(Path(__file__).parent / "fixtures")
    try:
        result, _rows = asyncio.run(
            session(
                {
                    "url": host.url + "/" + fixture,
                    "edit_selector": "#editor",
                    "ready_selector": ".status-ok",
                    "typing_usable_selector": usable_selector,
                },
                "abc",
                _typing_options(),
                tmp_path,
            )
        )
    finally:
        host.stop()
    return result


def test_usable_selector_on_a_non_editable_element_never_stamps(tmp_path):
    """focused_readonly's .status-ok is a visible div, not editable: the
    usable stamp must stay null, so the session refuses at the load gate."""
    result = _typing_session(tmp_path, "focused_readonly.html", ".status-ok")
    assert result["failure_reason"] == "no_correctness_adapter", result
    assert result["characters_typed"] == 0


def test_usable_selector_on_an_editable_element_stamps(tmp_path):
    """typing_fair's #editor is contenteditable: the selector path must still
    produce a usable stamp, so the session gets past the load gate."""
    result = _typing_session(tmp_path, "typing_fair.html", "#editor")
    assert result.get("failure_reason") != "no_correctness_adapter", result
