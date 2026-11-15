"""r3c12g: C12 edit-confirmation poll must stay inside the probe budget."""
from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LANE = REPO / "perf" / "runner" / "lane_edit_burst.mjs"
PROBE = REPO / "perf" / "runner" / "document_probe.mjs"


class C12EditConfirmBound(unittest.TestCase):
    def test_lane_edit_confirm_is_not_lane_poll_bound(self):
        # C12_LANE_SOURCE points this assertion at a scratch copy of a revert
        # file. The default is the worktree module. A bound of 60000 ms or more
        # fails, including a numeric separator (60_000).
        lane_path = Path(os.environ.get("C12_LANE_SOURCE", str(LANE)))
        lane = lane_path.read_text(encoding="utf-8")
        self.assertIn("LANE_EDIT_CONFIRM_MS", lane)
        self.assertIn("LANE_POLL_BOUND_MS", lane)
        assigned = re.search(
            r"export const LANE_EDIT_CONFIRM_MS = ([0-9_]+|LANE_POLL_BOUND_MS)\s*;",
            lane,
        )
        self.assertIsNotNone(assigned, "C12 confirm bound must be a numeric literal")
        token = assigned.group(1)
        self.assertNotEqual(
            token,
            "LANE_POLL_BOUND_MS",
            "C12 edit confirmation must not inherit the 600s lane poll bound",
        )
        self.assertLess(
            int(token.replace("_", "")),
            60000,
            "C12 edit confirmation must stay under 60000 ms, got %s" % token,
        )

    def test_reflow_probe_passes_a_bounded_confirm_timeout(self):
        probe = PROBE.read_text(encoding="utf-8")
        call = probe.split("await waitForC12CaretEdit", 1)[-1].split(");", 1)[0]
        self.assertIn("timeoutMs", call)
        self.assertIn("editConfirmMs", probe)


if __name__ == "__main__":
    unittest.main()
