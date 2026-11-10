"""Browser-visible cells must not be recorded under a headless-only lane.

perf/README.md: a lane may claim only what it can see. Before this test the
warm/cold runner labelled every browser attempt with ``default_lane()`` — the
*first* lane in the registry — so plate's pixels were recorded as
``headless_docx`` and wordcraft's as ``docx_crate``. The lane is now declared
per browser target; this test keeps the declaration honest.
"""

import unittest

from perf.adapters.capabilities import LANES, default_lane
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS

# Lanes that can observe pixels; everything else in LANES cannot.
VISIBLE_LANES = {"browser", "browser_slate", "wasm_editor", "wasm_ui", "editor", "webviewer", "app"}


class BrowserLaneLabelTest(unittest.TestCase):
    def test_every_browser_target_declares_a_lane(self):
        for editor_id, target in BROWSER_TARGETS.items():
            self.assertIn("lane", target, editor_id)

    def test_declared_lane_belongs_to_the_editor(self):
        for editor_id, target in BROWSER_TARGETS.items():
            self.assertIn(target["lane"], LANES[editor_id], editor_id)

    def test_visible_criteria_are_not_filed_under_a_headless_lane(self):
        for editor_id, target in BROWSER_TARGETS.items():
            claims_pixels = any(
                layer == "browser_visible" for _, layer in target["criteria"].values()
            )
            if claims_pixels:
                self.assertIn(
                    target["lane"],
                    VISIBLE_LANES,
                    "%s claims browser_visible in lane %r" % (editor_id, target["lane"]),
                )

    def test_known_mislabels_cannot_return(self):
        # These were the two real mislabels: default_lane() is the wrong answer
        # for both editors because their first lane is headless.
        self.assertEqual(BROWSER_TARGETS["plate"]["lane"], "browser_slate")
        self.assertNotEqual(BROWSER_TARGETS["plate"]["lane"], default_lane("plate"))
        self.assertEqual(BROWSER_TARGETS["wordcraft"]["lane"], "wasm_ui")
        self.assertNotEqual(BROWSER_TARGETS["wordcraft"]["lane"], default_lane("wordcraft"))


if __name__ == "__main__":
    unittest.main()
