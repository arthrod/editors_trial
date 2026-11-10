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

The fix for #130 adds:

W6  the clock gate fails closed on an injected screencast-timestamp error
    (the reviewer's fault-injection probe, `fixtures/witness/clock_shift_probe.mjs`:
    shifts 0/+1000/-1000 ms; only 0 is acceptable, with the reason named), and
    the record states the published conversion bound ([-2 ms, +lag bound]).
W7  only document damage counts as the document's paint: a shell-only change
    with `region: #doc` is not witnessed, a document change is, a record
    without a region carries `document_scoped: false` and the validator
    refuses it (`not_document_scoped`).
W8  the validator refuses every reviewer counterexample (missing/failed
    clock check, null outcome, no post-marker frame or pixels, failed caret
    mask, non-finite time) with a named reason; the CLI exits 1 on them.

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


def _load_validator():
    """Import perf/runner/witness.py; a missing file is a failure, not a skip."""
    if not WITNESS_PY.is_file():
        raise AssertionError(
            "perf/runner/witness.py (the witness reader/validator) is missing"
        )
    spec = importlib.util.spec_from_file_location("perf_witness", WITNESS_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _WitnessBrowserCase(unittest.TestCase):
    """Shared plumbing for the browser-side tests: the fixture server."""

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


class WitnessBrowserTests(_WitnessBrowserCase):
    """The browser side of B1c, driven through witness.mjs."""

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
        # The gate (#130): `acceptable` is the AND of the recorded checks, and
        # every refusal names the check that failed.
        checks = record.get("checks")
        self.assertIsInstance(
            checks, dict, "the clock check must record what was checked: %r" % (record,)
        )
        for key in (
            "timestamp_kind_known",
            "page_offset_within_bound",
            "page_offset_spread_within_bound",
            "anchor_found",
            "anchor_pixel_checked",
            "anchor_causality",
            "anchor_lag_within_bound",
        ):
            self.assertIn(key, checks, "the clock check must name %s: %r" % (key, record))
        if record.get("acceptable"):
            self.assertIsNone(
                record.get("reason"), "an acceptable check has no reason: %r" % (record,)
            )
            self.assertTrue(
                all(checks.values()),
                "acceptable requires every check to pass: %r" % (record,),
            )
            self.assertLessEqual(
                abs(float(skew)),
                float(record.get("bound_ms")),
                "an acceptable check keeps the page offset within the bound: %r"
                % (record,),
            )
        else:
            self.assertTrue(
                record.get("reason"),
                "a refused clock check names the failed check: %r" % (record,),
            )
        # The published conversion bound is stated, asymmetric, and never
        # claims a precision the anchor did not prove (no "±2 ms").
        conversion = record.get("conversion")
        self.assertIsInstance(
            conversion, dict, "the clock check states its published bound: %r" % (record,)
        )
        self.assertEqual(
            conversion.get("error_lower_ms"),
            -2,
            "the lower bound is -2 ms by causality: %r" % (record,),
        )
        upper = conversion.get("error_upper_ms")
        self.assertIsInstance(
            upper, (int, float), "the upper bound is the lag bound: %r" % (record,)
        )
        interval = record.get("frame_interval_ms")
        if isinstance(interval, (int, float)):
            self.assertGreaterEqual(
                upper,
                interval,
                "the lag bound must be at least one frame interval: %r" % (record,),
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
        return _load_validator()

    @staticmethod
    def good_record() -> dict:
        """A record that carries every kind of evidence the validator demands:
        a witnessed, document-scoped, caret-masked frame with pixels above the
        threshold and an acceptable clock check from its run."""
        return {
            "outcome": "witnessed",
            "frame_page_ms": 1234.5,
            "frames_total": 7,
            "frames_after": 3,
            "diff_ratio": 0.01,
            "threshold": 0.00005,
            "min_pixels": 4,
            "changed_pixels": 900,
            "caret_masked": True,
            "document_scoped": True,
            "clock_skew_ms": 0.2,
            "clock_skew_acceptable": True,
            "clock_check": {
                "kind": "clock_skew",
                "acceptable": True,
                "reason": None,
                "page_offset_ms": 0.2,
            },
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


class WitnessClockGateTests(unittest.TestCase):
    """W6 (#130 defect 1): the clock gate fails on an injected clock error.

    The reviewer's fault-injection probe (review finding 1) is now a fixture:
    `fixtures/witness/clock_shift_probe.mjs` shifts only each screencast
    frame's `metadata.timestamp` and runs `clockSkew()`. Pixels and page
    clocks are untouched, so a gate that accepts `+1000` or `-1000` ms is a
    gate that cannot fail.
    """

    _records = None

    @classmethod
    def setUpClass(cls):
        if _node() is None:
            raise unittest.SkipTest("node is not on PATH")
        if _playwright_dir() is None:
            raise unittest.SkipTest("harness/ui has no playwright package")

    def records(self) -> dict:
        if WitnessClockGateTests._records is None:
            cmd = [
                _node(),
                str(FIXTURES / "clock_shift_probe.mjs"),
                str(WITNESS_MJS),
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
                "the clock-shift probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
                % (proc.returncode, proc.stdout, proc.stderr),
            )
            records = {}
            for line in proc.stdout.splitlines():
                entry = json.loads(line)
                self.assertEqual(
                    entry.get("case"), "shift", "unexpected probe output: %r" % (entry,)
                )
                records[int(entry["shift"])] = entry
            self.assertEqual(
                set(records),
                {0, 1000, -1000},
                "the probe must cover shifts 0/+1000/-1000 ms: %r" % (sorted(records),),
            )
            WitnessClockGateTests._records = records
        return WitnessClockGateTests._records

    def test_the_untouched_clock_is_acceptable(self):
        record = self.records()[0]
        self.assertTrue(
            record.get("acceptable"),
            "a shift of 0 ms (no injected error) must be acceptable: %r" % (record,),
        )
        self.assertIsNone(record.get("reason"))

    def test_a_positive_timestamp_shift_is_refused(self):
        record = self.records()[1000]
        self.assertFalse(
            record.get("acceptable"),
            "a +1000 ms screencast timestamp error must not be acceptable: %r"
            % (record,),
        )
        self.assertEqual(
            record.get("reason"),
            "anchor_lag_above_bound",
            "the refusal must name the failed check: %r" % (record,),
        )
        checks = record.get("checks")
        self.assertIsInstance(checks, dict)
        self.assertIs(checks.get("anchor_lag_within_bound"), False)

    def test_a_negative_timestamp_shift_is_refused(self):
        record = self.records()[-1000]
        self.assertFalse(
            record.get("acceptable"),
            "a -1000 ms screencast timestamp error must not be acceptable: %r"
            % (record,),
        )
        self.assertEqual(
            record.get("reason"),
            "anchor_before_change",
            "the refusal must name the failed check: %r" % (record,),
        )
        checks = record.get("checks")
        self.assertIsInstance(checks, dict)
        self.assertIs(checks.get("anchor_causality"), False)

    def test_the_anchor_is_chosen_by_pixels(self):
        for shift in (0, 1000, -1000):
            record = self.records()[shift]
            self.assertTrue(
                record.get("anchor_pixel_checked"),
                "the anchor must be proven by pixels at shift %s: %r" % (shift, record),
            )


class WitnessDocumentRegionTests(_WitnessBrowserCase):
    """W7 (#130 defect 2): only document damage is the document's paint."""

    def test_header_only_change_is_not_witnessed_with_a_region(self):
        record = self.run_witness(
            "--op",
            "witness-frame",
            "--url",
            self.url("shell_noise.html"),
            "--after-js",
            "window.__witnessArm()",
            "--window-ms",
            "900",
            "--region",
            "#doc",
        )
        self.assertIs(
            record.get("document_scoped"),
            True,
            "a witness with a region must say it is document-scoped: %r" % (record,),
        )
        self.assertEqual(
            record.get("outcome"),
            "no_frame",
            "a 100x100 shell recolor with an unchanged #doc must not be "
            "witnessed as the document's paint: %r" % (record,),
        )
        self.assertIsNone(record.get("frame_page_ms"))
        self.assertLessEqual(
            float(record.get("diff_ratio") or 0.0),
            float(record.get("threshold") or 0.0),
            "no pixel of the document region changed: %r" % (record,),
        )
        region = record.get("document_region")
        self.assertIsInstance(region, dict, "the region must be recorded: %r" % (record,))
        self.assertEqual(region.get("source"), "selector")
        self.assertEqual(region.get("selector"), "#doc")

    def test_document_change_is_witnessed_with_a_region(self):
        record = self.run_witness(
            "--op",
            "witness-frame",
            "--url",
            self.url("change_after_marker.html"),
            "--after-js",
            "window.__witnessArm()",
            "--window-ms",
            "900",
            "--region",
            "#doc",
        )
        self.assertIs(
            record.get("document_scoped"), True, "the region was given: %r" % (record,)
        )
        self.assertEqual(
            record.get("outcome"),
            "witnessed",
            "a change inside #doc must be witnessed with region #doc: %r" % (record,),
        )
        marker = float(record["marker_page_ms"])
        self.assertGreaterEqual(
            float(record["frame_page_ms"]),
            marker + 50 - 2,
            "the witness frame must not precede the change at marker+50 ms by "
            "more than the published lower bound (-2 ms): %r" % (record,),
        )
        self.assertGreater(
            float(record.get("diff_ratio") or 0.0),
            float(record.get("threshold") or 1.0),
        )
        self.assertGreaterEqual(int(record.get("frames_after") or 0), 1)

    def test_a_record_without_a_region_is_refused_by_the_validator(self):
        record = self.run_witness(
            "--op",
            "witness-frame",
            "--url",
            self.url("shell_noise.html"),
            "--after-js",
            "window.__witnessArm()",
            "--window-ms",
            "900",
        )
        # Without a region the whole-frame witness still fires on the shell's
        # damage -- that is exactly why the record must be refused.
        self.assertEqual(
            record.get("outcome"),
            "witnessed",
            "the unscoped witness sees the shell's damage: %r" % (record,),
        )
        self.assertNotEqual(
            record.get("document_scoped"),
            True,
            "a record without a region is not document-scoped: %r" % (record,),
        )
        validator = _load_validator()
        verdict = validator.validate_witness(record)
        self.assertTrue(
            verdict.get("refused"),
            "a record that is not document-scoped must be refused: %r" % (verdict,),
        )
        self.assertEqual(verdict.get("reason"), "not_document_scoped")

    def test_an_unknown_selector_is_recorded_not_thrown(self):
        record = self.run_witness(
            "--op",
            "witness-frame",
            "--url",
            self.url("plain.html"),
            "--after-js",
            "window.__witnessArm()",
            "--window-ms",
            "600",
            "--region",
            "#does-not-exist",
        )
        self.assertIs(
            record.get("document_scoped"),
            False,
            "an unresolvable region leaves the record unscoped: %r" % (record,),
        )
        self.assertTrue(
            record.get("document_region_error"),
            "the region failure must be recorded, not thrown: %r" % (record,),
        )
        validator = _load_validator()
        verdict = validator.validate_witness(record)
        self.assertTrue(verdict.get("refused"))
        self.assertEqual(verdict.get("reason"), "not_document_scoped")


class WitnessValidatorCounterexampleTests(unittest.TestCase):
    """W8 (#130 defects 3-4): the reviewer's counterexamples, permanent.

    Every record in `CASES` was accepted by the pre-fix validator and must be
    refused with a named reason; the good record still passes.
    """

    #: (name, updates on the good record, the reason the refusal must name)
    CASES = [
        (
            "missing-skew",
            {
                "clock_check": None,
                "clock_skew_ms": None,
                "clock_skew_acceptable": False,
                "timestamp_kind": "monotonic_seconds",
            },
            "clock_check_not_acceptable",
        ),
        ("null-outcome", {"outcome": None, "frame_page_ms": None}, "no_outcome"),
        (
            "zero-pixels",
            {"frames_after": 0, "diff_ratio": 0.0, "changed_pixels": 0},
            "no_frame_after_marker",
        ),
        (
            "mask-failed",
            {"caret_masked": False, "caret_mask_error": "injection failed"},
            "caret_mask_failed",
        ),
        ("nonfinite-time", {"frame_page_ms": float("nan")}, "nonfinite_time"),
        ("not-document-scoped", {"document_scoped": False}, "not_document_scoped"),
    ]

    def load_validator(self):
        return _load_validator()

    def test_each_counterexample_is_refused_with_a_named_reason(self):
        validator = self.load_validator()
        for name, updates, reason in self.CASES:
            with self.subTest(case=name):
                record = WitnessValidatorTests.good_record() | updates
                verdict = validator.validate_witness(record)
                self.assertTrue(
                    verdict.get("refused"),
                    "%s must be refused (pre-fix it was accepted): %r" % (name, verdict),
                )
                self.assertFalse(verdict.get("ok"))
                self.assertEqual(
                    verdict.get("reason"),
                    reason,
                    "%s must name its reason: %r" % (name, verdict),
                )

    def test_the_good_record_still_passes(self):
        validator = self.load_validator()
        verdict = validator.validate_witness(WitnessValidatorTests.good_record())
        self.assertFalse(
            verdict.get("refused"), "the good record must still pass: %r" % (verdict,)
        )
        self.assertTrue(verdict.get("ok"))

    def test_the_cli_refuses_the_counterexample_files(self):
        validator = self.load_validator()
        with tempfile.TemporaryDirectory() as tmp:
            for name, updates, _reason in self.CASES:
                if name == "nonfinite-time":
                    continue  # NaN is not valid JSON; covered below
                path = Path(tmp) / f"{name}.json"
                path.write_text(
                    json.dumps(WitnessValidatorTests.good_record() | updates),
                    encoding="utf-8",
                )
                proc = subprocess.run(
                    ["python3", "-I", str(WITNESS_PY), "--file", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(REPO),
                )
                self.assertEqual(
                    proc.returncode,
                    1,
                    "%s: the CLI must exit 1 on a refused record (rc=%s)\n"
                    "stdout: %s\nstderr: %s"
                    % (name, proc.returncode, proc.stdout, proc.stderr),
                )
                verdict = json.loads(proc.stdout)
                self.assertFalse(verdict.get("ok"))

            good = Path(tmp) / "good.json"
            good.write_text(
                json.dumps(WitnessValidatorTests.good_record()), encoding="utf-8"
            )
            proc = subprocess.run(
                ["python3", "-I", str(WITNESS_PY), "--file", str(good)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(REPO),
            )
            self.assertEqual(
                proc.returncode, 0, "the good record must exit 0: %s" % (proc.stdout,)
            )

    def test_the_reader_rejects_nan_in_a_file(self):
        """`NaN` is not JSON; the reader refuses it instead of parsing it."""
        validator = self.load_validator()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nan.json"
            path.write_text(
                json.dumps(WitnessValidatorTests.good_record() | {"frame_page_ms": float("nan")}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                validator.load_witness(path)
            proc = subprocess.run(
                ["python3", "-I", str(WITNESS_PY), "--file", str(path)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(REPO),
            )
            self.assertNotEqual(
                proc.returncode,
                0,
                "a NaN record must not be published (rc=0): %s" % (proc.stdout,),
            )


if __name__ == "__main__":
    unittest.main()
