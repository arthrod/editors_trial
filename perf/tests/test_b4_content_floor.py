"""C08 and WordCraft's C09 do not take a caret-only frame for the response (#207).

In the publication runs the frame C08 timed changed 16-58 pixels in most
samples of five editors (WordCraft at 4-8 ms, before any paste was painted);
a painted paste changed 677 pixels or more. The content criteria now pass the
witness a floor of 100 changed pixels.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REPRO = REPO / "perf" / "tests" / "b4_content_floor_repro.mjs"
_CACHE: dict = {}


def _run() -> dict:
    if "out" not in _CACHE:
        proc = subprocess.run(["node", str(REPRO)], cwd=str(REPO), capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, proc.stderr
        _CACHE["out"] = json.loads(proc.stdout)
    return _CACHE["out"]


def test_the_floor_sits_between_the_largest_caret_frame_and_the_smallest_paste():
    # 58 px: the largest caret-only frame measured. 677 px: the smallest painted paste.
    assert 58 < _run()["floor"] == 100 < 677


def test_at_the_default_the_witness_takes_the_caret_frame():
    """The behaviour the criteria had: the 46-pixel frame 5 ms after the key."""
    record = _run()["default_floor"]
    assert record["outcome"] == "witnessed"
    assert record["changed_pixels"] == 46
    assert record["frame_after_ms"] == 5


def test_with_the_floor_the_witness_takes_the_text_frame():
    record = _run()["content_floor"]
    assert record["outcome"] == "witnessed"
    assert record["changed_pixels"] == 1600
    assert record["frame_after_ms"] == 150
    assert record["min_pixels"] == 100


def test_paste_asks_the_witness_for_the_floor():
    calls = _run()["paste_calls"]
    assert calls and all(value == 100 for value in calls), calls


def test_undo_of_one_character_keeps_the_default():
    """One glyph changes fewer pixels than the floor: 17-251 in the publication runs."""
    calls = _run()["undo_calls"]
    assert calls and all(value is None for value in calls), calls


def test_every_content_sample_carries_the_floor():
    source = _run()["source"]
    for name in ("measureBulkInsert", "measureBulkInsertCopyOracle", "measureUndoCopyOracle"):
        floors, samples = source[name]
        assert samples >= 1 and floors == samples, (name, floors, samples)
    assert source["measureUndo"][0] == 0
    assert source["wrapper_forwards"] is True
