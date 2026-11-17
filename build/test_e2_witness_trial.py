"""The trial comparison of the two typing witnesses (#245) is read from the trial's samples, never typed (#255)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e2_witness_trial as trial  # noqa: E402
import perf_e2_tables as E2  # noqa: E402


def sample(root, n, editor, criterion, iteration, glyph, shadow, outcome="measured", refused=None):
    job = root / "space-a" / "runs" / "RID" / "benchmark_warm_cold" / "RID-000" / "samples"
    job.mkdir(parents=True, exist_ok=True)
    row = {"editor_id": editor, "criterion_id": criterion, "iteration": iteration, "outcome": outcome,
           "edit_confirmation": {"witness_page_ms": glyph,
                                 "pixel_settle_shadow": {"match_page_ms": shadow, "failure_reason": refused}}}
    (job / f"input-{n:04d}.json").write_text(json.dumps(row))


def build(tmp_path):
    n = 0
    for editor in ("folio", "plate"):
        for iteration in (0, 1, 2):
            for late in (0.0, 0.0):
                n += 1
                sample(tmp_path, n, editor, "C06", iteration, 1000.0 + late, 1000.0)
    sample(tmp_path, 90, "folio", "C06", 0, 1066.7, 1000.0)
    sample(tmp_path, 91, "folio", "C06", 0, 1033.3, 1000.0)
    sample(tmp_path, 92, "plate", "C05", 0, 1000.0, None, refused="not_settled")   # no shadow time: not compared
    sample(tmp_path, 93, "plate", "C05", 0, 1000.0, 1000.0, outcome="failed")        # not measured: not compared
    sample(tmp_path, 94, "canvas", "C05", 0, None, None)                               # no shadow record at all
    (tmp_path / "space-a" / "runs" / "RID" / "benchmark_warm_cold" / "RID-000" / "samples" / "input-0094.json"
     ).write_text(json.dumps({"editor_id": "canvas", "criterion_id": "C05", "iteration": 0, "outcome": "measured",
                              "edit_confirmation": {"pixel_settle": {}}}))
    return tmp_path


def test_the_record_counts_only_key_presses_both_witnesses_timed(tmp_path):
    record = trial.compare(build(tmp_path))
    assert record["compared"] == 14 and record["same_frame"] == 12
    assert record["editors"] == ["folio", "plate"]
    assert record["differed"] == [{"editor": "folio", "criterion": "C06", "key": 0, "count": 2,
                                   "glyph_later_ms": [33.3, 66.7]}]
    assert record["not_compared"] == {"shadow_refused": 1}
    assert record["runs"] == ["space-a/RID"]


def test_the_sentence_is_written_from_the_record():
    record = {"compared": 384, "same_frame": 368, "editors": ["docxodus", "eigenpal", "folio", "genoffice", "plate",
                                                                "superdoc"],
              "differed": [{"editor": "folio", "criterion": "C06", "key": 0, "count": 16,
                            "glyph_later_ms": [33.3, 100.0]}]}
    text = E2.witness_trial_text(record)
    assert "on the 6 editors that have glyph geometry" in text
    assert "on 368 of 384 key presses the two ended on the same frame" in text
    assert "The 16 that differed were all Folio's first key of a burst, where the glyph witness ended 33 to 100 ms later" in text


def test_a_trial_with_no_difference_and_no_record_say_so():
    text = E2.witness_trial_text({"compared": 10, "same_frame": 10, "editors": ["plate"], "differed": []})
    assert "on 10 of 10 key presses the two ended on the same frame." in text and "differed" not in text
    assert E2.witness_trial_text(None) == "The trial comparison of the two witnesses is not recorded."


def test_differences_that_are_not_one_key_of_one_editor_are_listed_not_summarised():
    record = {"compared": 20, "same_frame": 17, "editors": ["folio", "plate"],
              "differed": [{"editor": "folio", "criterion": "C06", "key": 0, "count": 2, "glyph_later_ms": [33.3, 50.0]},
                           {"editor": "plate", "criterion": "C05", "key": 0, "count": 1, "glyph_later_ms": [-16.7, -16.7]}]}
    text = E2.witness_trial_text(record)
    assert "The 3 that differed: Folio, C06, key 1 of its launch, 2 (glyph witness 33 to 50 ms later)" in text
    assert "Plate.js, C05, key 1 of its launch, 1 (glyph witness 17 ms earlier)" in text
