"""B1c: the shared witness module (frame witness, clock skew, renderer).

The module under test is `perf/runner/witness.mjs` (the browser side, driven
here through its own command line) and `perf/runner/witness.py` (the stdlib
reader/validator of the records the browser side writes).

What the tests claim:

W1  a fake host that changes the page 50 ms after a marker is witnessed: the
    frame the module reports is at or after the change, in the page's clock.
W2  a fake host whose only change is a blinking caret is *not* witnessed: the
    caret is masked, so the pixels do not change.
W3  the clock-skew probe returns a number and says which kind of timestamp
    the screencast carries.
W4  the renderer probe returns a renderer string, or says why it has none.
W5  the Python validator refuses a record whose skew is above the bound and a
    record whose outcome is `no_frame`.

The browser tests drive headless Chromium through node and the Playwright that
the harness pins (`harness/ui/node_modules/playwright`). They skip when node or
that browser is missing; they never skip because the module is missing, so a
missing implementation is a failure and not a silent pass.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WITNESS_MJS = REPO / "perf" / "runner" / "witness.mjs"
WITNESS_PY = REPO / "perf" / "runner" / "witness.py"
FIXTURES = REPO / "perf" / "tests" / "fixtures" / "witness"

TIMEOUT_S = 180


def _node() -> str | None:
    return shutil.which("node")


def _load_fixture_server():
    spec = importlib.util.spec_from_file_location(
        "witness_fixture_server", FIXTURES / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _playwright_dir() -> Path | None:
    """The Playwright the harness pins, if this checkout has it."""
    for candidate in (
        REPO / "harness" / "ui" / "plate" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright",
    ):
        if candidate.is_dir():
            return candidate
    return None


class WitnessBrowserTests(unittest.TestCase):
    """The browser side of B1c, driven through witness.mjs."""

    server = None
    base_url = ""

    @classmethod
    def setUpClass(cls):
        node = _node()
        if node is None:
            raise unittest.SkipTest("node is not on PATH")
        if _playwright_dir() is None:
            raise unittest.SkipTest("harness/ui has no playwright package")
        server_module = _load_fixture_server()
        cls.server, _thread, cls.base_url = server_module.serve(FIXTURES)

    @classmethod
    def tearDownClass(cls):
        if cls.server is not None:
            cls.server.shutdown()
            cls.server.server_close()

    # -- helpers ---------------------------------------------------------

    def run_witness(self, *args: str) -> dict:
        """Run witness.mjs and return the JSON record it prints."""
        cmd = [
            _node(),
            str(WITNESS_MJS),
            "--out",
            "-",
            *[str(a) for a in args],
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            cwd=str(REPO),
        )
        self.assertEqual(
            proc.returncode,
            0,
            "witness.mjs failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr),
        )
        try:
            record = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - failure path
            self.fail(
                "witness.mjs did not print one JSON record (%s)\nstdout: %r\nstderr: %r"
                % (exc, proc.stdout, proc.stderr)
            )
        self.assertIsInstance(record, dict, "the witness record must be a plain object")
        return record

    def url(self, name: str) -> str:
        return f"{self.base_url}/{name}"

    # -- W1 --------------------------------------------------------------

    def test_w1_the_change_after_the_marker_is_witnessed(self):
        """The witness frame is at or after marker + 50 ms (minus the skew)."""
        record = self.run_witness(
            "--op",
            "witness-frame",
            "--url",
            self.url("change_after_marker.html"),
            "--after-js",
            "window.__witnessArm()",
            "--window-ms",
            "900",
        )
        self.assertEqual(
            record.get("outcome"),
            "witnessed",
            "the change 50 ms after the marker must be witnessed: %r" % (record,),
        )
        self.assertIsInstance(record.get("frame_page_ms"), (int, float))
        skew = abs(float(record.get("clock_skew_ms") or 0.0))
        marker = float(record["marker_page_ms"])
        self.assertGreaterEqual(
            record["frame_page_ms"],
            marker + 50 - skew,
            "the witness frame (%r) must not precede the change at marker+50ms "
            "(marker=%r, skew=%r)" % (record.get("frame_page_ms"), marker, skew),
        )
        self.assertGreater(record.get("diff_ratio", 0), record.get("threshold", 1))
        self.assertGreater(record.get("frames_after", 0), 0)

    # -- W2 --------------------------------------------------------------

    def test_w2_a_blinking_caret_is_not_a_witness(self):
        """The caret is masked, so the blinking caret is not a frame."""
        record = self.run_witness(
            "--op",
            "witness-frame",
            "--url",
            self.url("caret_blink.html"),
            "--after-js",
            "window.__witnessArm()",
            "--window-ms",
            "1200",
        )
        self.assertTrue(
            record.get("caret_masked"),
            "the witness must record that it masked the caret: %r" % (record,),
        )
        self.assertEqual(
            record.get("outcome"),
            "no_frame",
            "a blinking caret must not stop the witness clock: %r" % (record,),
        )
        self.assertIsNone(record.get("frame_page_ms"))
        self.assertLessEqual(
            float(record.get("diff_ratio") or 0.0),
            float(record.get("threshold") or 0.0),
            "the masked caret must not change the pixels: %r" % (record,),
        )

    def test_w2_control_the_caret_is_a_frame_when_it_is_not_masked(self):
        """Without the mask the same caret blink is a visible change."""
        record = self.run_witness(
            "--op",
            "witness-frame",
            "--url",
            self.url("caret_blink.html"),
            "--after-js",
            "window.__witnessArm()",
            "--window-ms",
            "1200",
            "--caret-mask",
            "off",
        )
        self.assertFalse(record.get("caret_masked"))
        self.assertEqual(
            record.get("outcome"),
            "witnessed",
            "an unmasked blinking caret damages the compositor and must be seen "
            "as a change, otherwise the masked result proves nothing: %r" % (record,),
        )

    # -- W3 --------------------------------------------------------------

    def test_w3_the_clock_skew_is_a_number_with_a_timestamp_kind(self):
        record = self.run_witness(
            "--op", "clock-skew", "--url", self.url("plain.html")
        )
        skew = record.get("skew_ms")
        self.assertIsInstance(
            skew, (int, float), "clockSkew must return a number: %r" % (record,)
        )
        self.assertFalse(
            isinstance(skew, bool), "clockSkew must return a number: %r" % (record,)
        )
        self.assertIn(
            record.get("timestamp_kind"),
            ("epoch_seconds", "monotonic_seconds", "unknown"),
            "clockSkew must say which kind of timestamp it converted: %r" % (record,),
        )
        self.assertTrue(record.get("method"), "clockSkew must name its method")
        self.assertIsInstance(record.get("bound_ms"), (int, float))
        self.assertEqual(
            bool(record.get("acceptable")),
            abs(float(skew)) <= float(record.get("bound_ms")),
            "acceptable must follow the bound: %r" % (record,),
        )

    # -- W4 --------------------------------------------------------------

    def test_w4_the_renderer_is_reported_or_why_is(self):
        record = self.run_witness("--op", "renderer", "--url", self.url("plain.html"))
        renderer = record.get("renderer")
        why = record.get("why")
        self.assertTrue(
            isinstance(renderer, str) and renderer.strip(),
            "the renderer string must not be empty without a reason: %r" % (record,),
        )
        self.assertTrue(record.get("source"), "the renderer source must be recorded")
        self.assertIn("headless", record)
        self.assertTrue(record.get("chromium_version"), "the version must be recorded")
        if renderer.strip() in ("", "unknown"):
            self.assertTrue(why, "an unknown renderer needs a why: %r" % (record,))

    # -- the frame interval ---------------------------------------------

    def test_the_frame_interval_is_the_median_of_many_frames(self):
        record = self.run_witness(
            "--op", "frame-interval", "--url", self.url("plain.html"), "--frames", "60"
        )
        self.assertGreaterEqual(
            int(record.get("count") or 0),
            60,
            "the frame interval needs at least 60 frames: %r" % (record,),
        )
        median = record.get("median_ms")
        self.assertIsInstance(median, (int, float), "the median must be a number")
        self.assertGreater(median, 0.0)
        self.assertNotIn("mean_ms", record, "the mean is not a robust statistic here")
        self.assertNotIn("min_ms", record, "the minimum is not the frame interval")


class WitnessValidatorTests(unittest.TestCase):
    """The Python reader/validator of witness records."""

    def load_validator(self):
        self.assertTrue(
            WITNESS_PY.is_file(),
            "perf/runner/witness.py (the witness reader/validator) is missing",
        )
        spec = importlib.util.spec_from_file_location("perf_witness", WITNESS_PY)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def good_record() -> dict:
        return {
            "outcome": "witnessed",
            "frame_page_ms": 1234.5,
            "frames_total": 7,
            "frames_after": 3,
            "diff_ratio": 0.01,
            "threshold": 0.00005,
            "caret_masked": True,
            "clock_skew_ms": 0.2,
        }

    # -- W5 --------------------------------------------------------------

    def test_w5_the_validator_refuses_a_skew_above_the_bound(self):
        validator = self.load_validator()
        record = self.good_record()
        record["clock_skew_ms"] = 5.0
        verdict = validator.validate_witness(record)
        self.assertTrue(
            verdict.get("refused"), "a skew above the bound must be refused: %r" % (verdict,)
        )
        self.assertIn("skew", str(verdict.get("reason")))

    def test_w5_the_validator_refuses_a_no_frame_record(self):
        validator = self.load_validator()
        record = self.good_record()
        record["outcome"] = "no_frame"
        record["frame_page_ms"] = None
        verdict = validator.validate_witness(record)
        self.assertTrue(
            verdict.get("refused"),
            "a no_frame witness must be refused: %r" % (verdict,),
        )
        self.assertIn("no_frame", str(verdict.get("reason")))

    def test_w5_the_validator_accepts_a_good_record(self):
        validator = self.load_validator()
        verdict = validator.validate_witness(self.good_record())
        self.assertFalse(verdict.get("refused"), "a good record must pass: %r" % (verdict,))
        self.assertTrue(verdict.get("ok"))

    def test_w5_the_validator_refuses_a_broken_record(self):
        validator = self.load_validator()
        broken = self.good_record()
        broken["outcome"] = "measured"
        verdict = validator.validate_witness(broken)
        self.assertTrue(verdict.get("refused"), "an unknown outcome must be refused")

    def test_the_validator_reads_a_record_from_disk(self):
        validator = self.load_validator()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "witness.json"
            path.write_text(json.dumps(self.good_record()), encoding="utf-8")
            record = validator.load_witness(path)
            self.assertEqual(record["outcome"], "witnessed")
            verdict = validator.validate_witness(record)
            self.assertFalse(verdict.get("refused"))


if __name__ == "__main__":
    unittest.main()
