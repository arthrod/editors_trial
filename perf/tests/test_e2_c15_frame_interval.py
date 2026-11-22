"""E2: C15's find probe reads the frame interval the way the witness clock check does.

runFind asked frameInterval for 6 frames; the median of two middle rAF deltas
differs between fresh processes at one refresh rate (16.65, 16.673 ms on
OpenDoc), and _write_measured, which needs one interval across samples,
refused every measured C15 cell as frame_interval_inconsistent. The witness
clock check takes the 60-frame default, whose median reads 16.7 every time.
runFind now makes that same call. _write_measured is unchanged: samples
taken at different refresh rates are still refused.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _body(source: str, name: str) -> str:
    start = source.index("async function %s(" % name)
    end = source.find("\nasync function ", start + 1)
    return source[start:end if end >= 0 else None]


class FindIntervalIsTheWitnessRead(unittest.TestCase):
    def test_run_find_uses_the_witness_frame_count(self):
        probe = _body((REPO / "perf/runner/document_probe.mjs").read_text(encoding="utf-8"), "runFind")
        calls = re.findall(r"frameInterval\(([^)]*)\)", probe)
        self.assertEqual(calls, ["ctx.page"], calls)

    def test_the_witness_clock_check_reads_sixty_frames_the_default(self):
        witness = (REPO / "perf/runner/witness.mjs").read_text(encoding="utf-8")
        self.assertIn("export async function frameInterval(page, { frames = 60,", witness)
        self.assertIn("await frameInterval(page, { frames: 60 })", witness)

    def test_samples_at_different_refresh_rates_are_still_refused(self):
        from perf.runner import benchmark_document as bd
        from perf.tests.test_document_criteria import _env, _fixture

        env = _env(_fixture("micro-search"), cache_state="warm_steady")
        for intervals, refused in (((16.7, 8.3), True), ((16.7, 16.7), False)):
            diagnostic = {"samples": [{"frame_interval_ms": value} for value in intervals]}
            with tempfile.TemporaryDirectory() as tmp:
                _path, trial = bd._write_measured(attempt_dir=Path(tmp), criterion_id="C15", editor_id="plate",
                                                  lane="browser_slate", env=env, samples=[150.0, 151.0],
                                                  diagnostic=diagnostic)
            reason = trial.get("failure_reason")
            if refused:
                self.assertEqual(reason, "frame_interval_inconsistent", intervals)
            else:
                self.assertNotEqual(reason, "frame_interval_inconsistent", intervals)


if __name__ == "__main__":
    unittest.main()
