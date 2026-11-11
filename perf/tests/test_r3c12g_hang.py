"""r3c12g: C12 edit-confirmation poll must stay inside the probe budget."""
from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LANE = REPO / "perf" / "runner" / "lane_edit_burst.mjs"
PROBE = REPO / "perf" / "runner" / "document_probe.mjs"


class C12EditConfirmBound(unittest.TestCase):
    def test_lane_edit_confirm_is_not_lane_poll_bound(self):
        lane = LANE.read_text(encoding="utf-8")
        self.assertIn("LANE_EDIT_CONFIRM_MS", lane)
        self.assertIn("LANE_POLL_BOUND_MS", lane)
        self.assertRegex(
            lane,
            r"export const LANE_EDIT_CONFIRM_MS = (?!LANE_POLL_BOUND_MS)\d+",
            "C12 edit confirmation must not inherit the 600s lane poll bound",
        )

    def test_reflow_probe_passes_a_bounded_confirm_timeout(self):
        probe = PROBE.read_text(encoding="utf-8")
        call = probe.split("await waitForC12CaretEdit", 1)[-1].split(");", 1)[0]
        self.assertIn("timeoutMs", call)
        self.assertIn("editConfirmMs", probe)


if __name__ == "__main__":
    unittest.main()
