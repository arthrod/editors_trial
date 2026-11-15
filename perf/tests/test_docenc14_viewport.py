"""#174 — screencast_ink certifies the first viewport, never the whole element.

Docen's first page is a canvas inside ``docen-document``'s shadow root,
816x1056 at (232, 294) — 450 px below the 1280x900 viewport's bottom edge.
``Page.captureScreenshot`` returns the full clip while every screencast frame
is clamped to the viewport, so the settled reference and the frame crops
never shared dimensions and usable was refused ``settled_frame_not_observed``
on every rung. The resolved region is now intersected with the viewport, the
payload records that clamp, and a Python-side refusal publishes the probe's
own ``surface_reason`` instead of "retained sample has no witness record".
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

import perf.runner.benchmark_document as bd
from perf.tests import test_b3_fix3 as helpers

FIXTURES = Path(__file__).resolve().parent / "fixtures"

DOCEN_SCALE_ARGS = [
    "--usable-signal", "screencast_ink",
    "--doc-selector", "docen-document",
    "--document-selector", ".canvas-pages > div:first-child",
    "--page-model", "continuous_flow",
    "--ready-selector", '#host[data-ready="1"]',
    "--ready-js", "window.__DOCEN_READY__ === true",
    "--timeout-ms", "12000",
]


class ViewportCrossingHost(helpers.Fix3Hosts):
    """A docen-shaped host whose painted element crosses the viewport edge."""

    def test_a_document_element_taller_than_the_viewport_is_usable(self):
        payload = self.probe("scale", "docenc14_tall.html", DOCEN_SCALE_ARGS)
        self.assertIsNotNone(
            payload.get("usable_ms"),
            "usable must be stamped for the first viewport: %r" % (payload.get("surface_reason"),),
        )
        self.assertIsNone(payload.get("surface_reason"), payload)

    def test_the_viewport_clamp_is_disclosed_on_the_payload(self):
        payload = self.probe("scale", "docenc14_tall.html", DOCEN_SCALE_ARGS)
        self.assertIs(payload.get("region_clamped_to_viewport"), True, payload)
        unclamped = payload.get("region_unclamped_css") or {}
        for key, expected in (("x", 232.0), ("y", 294.0), ("width", 816.0), ("height", 1056.0)):
            self.assertAlmostEqual(
                unclamped.get(key), expected, places=1,
                msg="region_unclamped_css[%s]: %r" % (key, unclamped),
            )
        region = payload.get("region_css") or {}
        self.assertLessEqual(
            (region.get("y") or 0) + (region.get("height") or 0), 900.0,
            "the certified region must end inside the 900 px viewport: %r" % (region,),
        )


class CropInkRegionEdge(unittest.TestCase):
    def test_edge_crossing_crops_have_identical_dimensions(self):
        node = helpers._node()
        if node is None:
            self.skipTest("node is not on PATH")
        script = FIXTURES / "docenc14_crop.mjs"
        result = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class C14SurfaceReason(unittest.TestCase):
    """A probe refusal is published under its own name, not the witness gate's."""

    def test_a_probe_refusal_publishes_its_own_reason(self):
        probe = {
            "mode": "scale",
            "usable_ms": None,
            "witness": None,
            "surface_reason": "settled_frame_not_observed",
            "frames_total": 15,
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c14_measured_sample(probe)
        self.assertIn("settled_frame_not_observed", caught.exception.reason)
        self.assertNotIn("no witness record", caught.exception.reason)
        facts = getattr(caught.exception, "facts", {}) or {}
        self.assertEqual(facts.get("surface_reason"), "settled_frame_not_observed")

    def test_usable_ms_is_refused_before_the_witness_is_checked(self):
        probe = {
            "mode": "scale",
            "usable_ms": None,
            "surface_reason": "document_surface_absent",
            "witness": {"outcome": "no_frame"},
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c14_measured_sample(probe)
        self.assertIn("document_surface_absent", caught.exception.reason)

    def test_a_usable_sample_still_requires_its_witness(self):
        probe = {
            "mode": "scale",
            "usable_ms": 800.0,
            "presented_frame_ms": 812.5,
            "clock_skew_ms": 0.1,
            "witness": None,
        }
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c14_measured_sample(probe)
        self.assertIn("no witness record", caught.exception.reason)

    def test_a_missing_surface_reason_keeps_the_generic_usability_refusal(self):
        probe = {"mode": "scale", "usable_ms": None, "witness": {"outcome": "no_frame"}}
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c14_measured_sample(probe)
        self.assertIn("usability", caught.exception.reason)


if __name__ == "__main__":
    unittest.main()
