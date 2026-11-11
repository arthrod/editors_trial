"""B4 input lane fixinput4: caret paint, model text, and the protection variant."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CONTRACT = REPO / "perf" / "tests" / "b4_fixinput4_contract.mjs"


def _zip_parts(blob: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(blob)) as package:
        return {name: package.read(name) for name in package.namelist()}


def test_strip_removes_only_the_protection_element_and_is_stable():
    from perf.fixtures.docx_workload import strip_document_protection, workload_docx

    original = workload_docx("complex-corpus")
    once = strip_document_protection(original["docx"])
    twice = strip_document_protection(original["docx"])
    assert once == twice
    assert hashlib.sha256(once).hexdigest() != original["sha256"]
    before = _zip_parts(original["docx"])
    after = _zip_parts(once)
    assert set(before) == set(after)
    for name, data in before.items():
        if name == "word/settings.xml":
            continue
        assert data == after[name], name
    assert before["word/settings.xml"].count(b"documentProtection") == 1
    assert b"w:documentProtection" not in after["word/settings.xml"]
    assert after["word/settings.xml"] != before["word/settings.xml"]
    kept = before["word/settings.xml"].replace(
        before["word/settings.xml"][before["word/settings.xml"].index(b"<w:documentProtection") :
                                     before["word/settings.xml"].index(b"/>", before["word/settings.xml"].index(b"<w:documentProtection")) + 2],
        b"",
        1,
    )
    assert after["word/settings.xml"] == kept


def test_edit_lanes_load_the_variant_and_load_lanes_keep_the_original():
    from perf.fixtures.docx_workload import workload_docx, workload_for_lane

    original = workload_docx("complex-corpus")
    # Every lane that edits loads the variant; a lane that only reads keeps the original.
    for lane in ("input", "resources", "memory", "document", "warm_cold"):
        variant = workload_for_lane("complex-corpus", lane)
        assert variant["fixture_variant"] == "complex-corpus-without-document-protection"
        assert variant["fixture_source_sha256"] == original["sha256"]
        assert variant["sha256"] != original["sha256"]
        assert b"w:documentProtection" not in variant["docx"]
    assert workload_for_lane("complex-corpus", "scroll")["sha256"] == original["sha256"]
    prose = workload_docx("prose-500w")
    assert workload_for_lane("prose-500w", "input")["sha256"] == prose["sha256"]
    assert "fixture_variant" not in workload_for_lane("prose-500w", "input")


def test_input_fixture_serves_the_variant_bytes():
    from perf.runner.benchmark_input import _fixture

    path, sha, size, row = _fixture("plate", "complex-corpus")
    assert row["fixture_variant"] == "complex-corpus-without-document-protection"
    assert row["fixture_source_sha256"]
    blob = path.read_bytes()
    assert hashlib.sha256(blob).hexdigest() == sha
    assert len(blob) == size
    assert b"w:documentProtection" not in _zip_parts(blob)["word/settings.xml"]
    from perf.fixtures.docx_workload import workload_for_lane

    assert sha == workload_for_lane("complex-corpus", "input")["sha256"]


def test_variant_sha_is_copied_onto_the_trial():
    from perf.fixtures.profiles import size_ladder
    from perf.runner.criteria_input_io import trials_from_payload
    from perf.tests.test_input_criteria import _entry, _payload
    from perf.tests.test_schema import _env

    env = _env()
    workload = next(row for row in size_ladder() if row["workload_id"] == "complex-corpus")
    entry = _entry(
        "C08",
        outcome="failed",
        samples_ms=[],
        failure_reason="document_protected_read_only",
        observations=[],
    )
    payload = _payload({"C08": entry})
    payload["fixture_variant"] = "complex-corpus-without-document-protection"
    payload["fixture_source_sha256"] = "ab" * 32
    trial = trials_from_payload(
        payload,
        editor_version="plate",
        fixture_sha256=env["fixture_sha256"],
        workload_row=workload,
        docx_size=100,
    )["C08"]
    assert trial["refusal_code"] == "document_protected_read_only"
    assert trial["diagnostic"]["fixture_variant"] == "complex-corpus-without-document-protection"
    assert trial["diagnostic"]["fixture_source_sha256"] == "ab" * 32


def test_caret_dom_response_without_a_frame_is_rejected():
    from perf.runner.criteria_input_io import assert_payload_shape
    from perf.tests.test_input_criteria import _entry, _payload

    # A timeout clock plus caret_dom_response is not a painted sample.
    observation = {
        "observation_id": "click-0",
        "sample_ms": 12.5,
        "frame_ms": 12.5,
        "input_ms": 0,
        "caret_dom_response": True,
        "point": "page_centre",
        "scope": "dom_caret_on_clicked_line",
        "line": None,
        "anchor_inside": True,
    }
    entry = _entry(
        "C07",
        samples_ms=[12.5],
        observations=[observation],
        sample_observation_ids=["click-0"],
    )
    with pytest.raises(ValueError, match="witness"):
        assert_payload_shape(_payload({"C07": entry}))


def _caret_rect_record(width, height, changed, outcome="witnessed"):
    """A captured production witness, shrunk to a caret box and unmasked."""
    from perf.runner.witness import _js_round

    path = REPO / "perf" / "tests" / "fixtures" / "witness" / "captured_frame_witness.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    dpr = 1
    css = {"x": 40, "y": 80, "width": width, "height": height}
    device = {
        key: _js_round(css[key] * dpr) for key in ("x", "y", "width", "height")
    }
    area = device["width"] * device["height"]
    record = copy.deepcopy(record)
    record["caret_masked"] = False
    record["caret_mask_css"] = None
    record["caret_mask_error"] = None
    record["document_scoped"] = True
    record["document_region"] = {
        "source": "rect",
        "selector": None,
        "rect_css_px": css,
        "rect_device_px": device,
        "device_pixel_ratio": dpr,
    }
    record["region_pixels"] = area
    record["total_pixels"] = area
    record["outcome"] = outcome
    if outcome == "witnessed":
        ratio = changed / area
        record["changed_pixels"] = changed
        record["diff_ratio"] = ratio
        record["max_diff_ratio"] = ratio
    else:
        record["frame_page_ms"] = None
        record["changed_pixels"] = 0
        record["diff_ratio"] = 0.0
        record["max_diff_ratio"] = 0.0
    # The run's calibration stays masked. Only the frame record drops it.
    assert record["clock_check"]["caret_masked"] is True
    return record


def test_unmasked_caret_rect_is_a_publishable_witness():
    from perf.runner.witness import validate_witness

    verdict = validate_witness(_caret_rect_record(16, 22, 98))
    assert verdict["ok"] is True
    assert verdict["refused"] is False
    assert verdict["reason"] is None


def test_unmasked_document_diff_is_still_refused():
    from perf.runner.witness import validate_witness

    path = REPO / "perf" / "tests" / "fixtures" / "witness" / "captured_frame_witness.json"
    whole = json.loads(path.read_text(encoding="utf-8"))
    whole["caret_masked"] = False
    whole["caret_mask_css"] = None
    verdict = validate_witness(whole)
    assert verdict["ok"] is False
    assert verdict["reason"] == "witness_schema_invalid"

    oversized = _caret_rect_record(800, 70, 100)
    refused = validate_witness(oversized)
    assert refused["ok"] is False
    assert refused["reason"] == "witness_schema_invalid"


def test_click_region_box_bounds_are_publishable_witnesses():
    """r3lanes4 #2: the documented C07 click box is 48 CSS px wide, line tall."""
    from perf.runner.witness import validate_witness

    # The documented box: 48 wide, a line box (~22-40 px) tall, at most 96.
    verdict = validate_witness(_caret_rect_record(48, 30, 400))
    assert verdict["ok"] is True
    tall = validate_witness(_caret_rect_record(48, 96, 400))
    assert tall["ok"] is True
    wider = validate_witness(_caret_rect_record(49, 30, 400))
    assert wider["ok"] is False
    assert wider["reason"] == "witness_schema_invalid"


def test_unmasked_caret_with_no_pixels_is_no_frame():
    from perf.runner.witness import validate_witness

    verdict = validate_witness(_caret_rect_record(16, 42, 0, outcome="no_frame"))
    assert verdict["ok"] is False
    assert verdict["reason"] == "no_frame"


def test_fixinput4_contract():
    proc = subprocess.run(
        ["node", str(CONTRACT)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    assert "checks ok" in proc.stdout
