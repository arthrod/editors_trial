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

import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
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
        """A real witnessed record, captured once from headless Chromium
        through `witness.mjs`'s own CLI (`captured_frame_witness.json`),
        deep-copied so each test corrupts its own copy.

        Until #137 round 4 this was a hand-made 13-key "legacy" record. No
        producer writes that shape (`witnessFrame()` always emits
        `kind: 'frame_witness'`), and a record without the producer's
        markers is refused `not_a_witness_record` now, so every fixture in
        this file is the production shape, built from the capture."""
        return json.loads(json.dumps(_load_captured_record()))

    # -- W5 --------------------------------------------------------------

    def test_w5_the_validator_refuses_a_skew_above_the_bound(self):
        validator = self.load_validator()
        record = self.good_record()
        # lax layer (owner 2026-11-11): the bound moved 2 -> 5 ms, so 5.0 is
        # at the bound and passes; the probe sits above it.
        record["clock_skew_ms"] = 6.0
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

    #: (name, updates on the good record, the reason the refusal must name).
    #: Round 4: the fixture is the real capture, so the malformations the
    #: lenient branch used to catch late (a missing clock check, a NaN
    #: frame time, a scope flag over a region) are named by the strict
    #: schema first -- `witness_schema_invalid` -- which is the honest
    #: reason for a production record that stopped being the producer's.
    CASES = [
        (
            "missing-skew",
            {
                "clock_check": None,
                "clock_skew_ms": None,
                "clock_skew_acceptable": False,
                "timestamp_kind": "monotonic_seconds",
            },
            "witness_schema_invalid",
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
        ("nonfinite-time", {"frame_page_ms": float("nan")}, "witness_schema_invalid"),
        ("not-document-scoped", {"document_scoped": False}, "witness_schema_invalid"),
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


class WitnessIssue137Tests(unittest.TestCase):
    """Issue #137 (the #130 follow-up): evidence the validator asserted, not checked.

    Each record in `CASES` is one case of the issue (the re-review's findings
    3-4); every one was accepted with ``ok: true`` by the validator as it
    stood after #130 (reproduction: `e2-logs/b1c-fix2/repro-before.log`, the
    reviewer's `/tmp/rerev-b1c-b4/validator.py` against this tree). Each must
    be refused with its own named reason, and the armed good record — the
    same fields a real `witnessFrame()` run records — must still pass.
    """

    @staticmethod
    def armed_good_record() -> dict:
        """The good record plus the fields a real run adds: the arm instant
        (`after_page_ms`, the page-clock value passed to `witnessFrame`) and
        the diff's pixel totals. Since round 4 the fixture IS the real
        capture -- already armed, already carrying its totals -- so this is
        the production record itself."""
        return WitnessValidatorTests.good_record()

    #: (name, updates on the armed good record, the reason the refusal must
    #: name). Round 4: the fixture is a production record, so the cases a
    #: hand-made record could only show as a bare type error (a NaN or
    #: string arm, a wrong-typed pixel floor, a scope flag over a region)
    #: are named by the strict schema first (`witness_schema_invalid`); the
    #: evidence contradictions (pre-arm frame, flags over their own checks)
    #: keep their own reasons. The frame-before-arm case uses a frame
    #: between the capture's baseline and its arm, so the baseline rule
    #: does not fire first.
    CASES = [
        # 1. a frame before its arm: ordinary valid JSON, impossible evidence.
        ("frame-before-arm", {"frame_page_ms": 1500.0}, "frame_before_arm"),
        # 2. a non-finite arm through the direct API (the JSON reader refuses
        #    a bare NaN; the validator must not depend on the reader for it).
        ("arm-nan", {"after_page_ms": float("nan")}, "witness_schema_invalid"),
        # 3. more frames after the marker than were ever recorded.
        #    (Round 6: the case used to set frames_total to 0, but a record
        #    with zero frames now contradicts the anchor's own evidence
        #    first -- the check counted three -- so the case raises
        #    frames_after past any window's frame count instead, which is
        #    what its name tests.)
        (
            "frames-after-above-total",
            {"frames_after": 10**6},
            "frame_counts_inconsistent",
        ),
        # 4. a pixel floor of the wrong type skips the floor: 0 pixels pass.
        (
            "min-pixels-not-a-number",
            {"changed_pixels": 0, "min_pixels": "4"},
            "witness_schema_invalid",
        ),
        # 5. `acceptable: true` asserted over recorded anchor evidence that
        #    says no (the boolean was trusted over its own checks). (Round
        #    6: the schema runs before the recomputation, so this minimal
        #    hand-made check is named as malformed first; the flag-over-
        #    evidence contradiction is still in errors.)
        (
            "acceptable-over-anchor-evidence",
            {
                "clock_check": {
                    "kind": "clock_skew",
                    "acceptable": True,
                    "reason": None,
                    "page_offset_ms": 0.2,
                    "anchor_pixel_checked": False,
                    "checks": {"anchor_found": False},
                }
            },
            "clock_check_schema_invalid",
        ),
        # 6. `document_scoped: true` with the region's failure recorded next to it.
        (
            "scoped-with-region-error",
            {"document_region_error": "selector missing"},
            "witness_schema_invalid",
        ),
    ]

    #: the same fail-open family, one step further: a wrong-typed arm, an
    #: acceptable flag with its recorded checks erased, and an anchor that
    #: says unchecked while the checks dict claims otherwise. (Round 6:
    #: both nested-evidence cases are named by the schema's token now --
    #: the schema runs before the recomputation, and a check that is
    #: missing or lying about its evidence is malformed before it is
    #: contradictory; the refusal and the evidence tokens in errors are
    #: unchanged.)
    EXTRA_CASES = [
        ("arm-not-a-number", {"after_page_ms": "1200"}, "witness_schema_invalid"),
        (
            "acceptable-without-recorded-checks",
            {
                "clock_check": {
                    "kind": "clock_skew",
                    "acceptable": True,
                    "reason": None,
                    "page_offset_ms": 0.2,
                    "checks": None,
                }
            },
            "clock_check_schema_invalid",
        ),
        (
            "acceptable-over-unchecked-anchor",
            {
                "clock_check": {
                    "kind": "clock_skew",
                    "acceptable": True,
                    "reason": None,
                    "page_offset_ms": 0.2,
                    "anchor_pixel_checked": False,
                    "checks": {"anchor_found": True, "anchor_pixel_checked": True},
                }
            },
            "clock_check_schema_invalid",
        ),
    ]

    def load_validator(self):
        return _load_validator()

    def assert_refused_for(self, validator, record, name, reason):
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
        self.assertTrue(
            verdict.get("errors"), "%s must carry its evidence tokens" % (name,)
        )

    def test_each_case_is_refused_with_its_own_reason(self):
        validator = self.load_validator()
        for name, updates, reason in self.CASES:
            with self.subTest(case=name):
                self.assert_refused_for(
                    validator, self.armed_good_record() | updates, name, reason
                )

    def test_each_hardening_case_is_refused_with_its_own_reason(self):
        validator = self.load_validator()
        for name, updates, reason in self.EXTRA_CASES:
            with self.subTest(case=name):
                self.assert_refused_for(
                    validator, self.armed_good_record() | updates, name, reason
                )

    def test_the_armed_good_record_still_passes(self):
        validator = self.load_validator()
        verdict = validator.validate_witness(self.armed_good_record())
        self.assertFalse(
            verdict.get("refused"),
            "the armed good record must pass exactly like the plain one: %r"
            % (verdict,),
        )
        self.assertTrue(verdict.get("ok"))
        self.assertIsNone(verdict.get("reason"))

    def test_a_frame_at_the_arm_is_not_refused(self):
        """The producer accepts a frame at `pageMs >= after_page_ms`; equality
        is the boundary and must not become a refusal."""
        validator = self.load_validator()
        record = self.armed_good_record()
        record["frame_page_ms"] = record["after_page_ms"]
        verdict = validator.validate_witness(record)
        self.assertFalse(
            verdict.get("refused"), "a frame at the arm is causal: %r" % (verdict,)
        )

    def test_the_cli_refuses_a_pre_arm_frame(self):
        """The CLI is the publication gate; the pre-arm frame must exit 1."""
        validator = self.load_validator()
        record = self.armed_good_record() | {"frame_page_ms": 1500.0}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pre-arm.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            rc = validator.main(["--file", str(path)])
            self.assertEqual(
                rc, 1, "the CLI must refuse a frame before its arm (rc=%s)" % (rc,)
            )


class WitnessIssue137Round3Tests(unittest.TestCase):
    """Issue #137, round 3 (codex re-review `e2-logs/rereview-b1c-2.md`): the
    five findings, as the re-review's own probe states them.

    Round 2 closed the six exact counterexamples but still trusted flags over
    evidence: erased checks, all-true flags over impossible measurements, and
    pixel counts that cannot describe the recorded ratio were all accepted
    (`ok: true`) at f21115b. Round 3 replaces flag-checking with a strict
    schema plus recomputation of every derived verdict; these five findings
    are the RED tests that generation was written against.
    """

    def load_validator(self):
        return _load_validator()

    # -- finding 1: erased or non-Boolean anchor checks still pass ---------

    def test_finding1_erased_checks_are_refused(self):
        validator = self.load_validator()
        record = WitnessIssue137Tests.armed_good_record() | {
            "clock_check": WitnessValidatorTests.good_record()["clock_check"]
            | {"checks": {}}
        }
        verdict = validator.validate_witness(record)
        self.assertTrue(
            verdict.get("refused"),
            "an acceptable clock check whose recorded checks were erased "
            "proves nothing: %r" % (verdict,),
        )

    def test_finding1_null_check_values_are_refused(self):
        validator = self.load_validator()
        record = WitnessIssue137Tests.armed_good_record() | {
            "clock_check": WitnessValidatorTests.good_record()["clock_check"]
            | {"checks": {"anchor_found": None}, "anchor_pixel_checked": None}
        }
        verdict = validator.validate_witness(record)
        self.assertTrue(
            verdict.get("refused"),
            "a null check is not evidence: %r" % (verdict,),
        )
        # round 6: the schema runs before the recomputation, so the missing
        # recorded checks are the schema's token; the erased-evidence token
        # is still in errors.
        self.assertEqual(
            verdict.get("reason"),
            "clock_check_schema_invalid",
        )
        self.assertTrue(
            any("erased or non-boolean" in str(e) for e in verdict.get("errors", [])),
            "the erased checks are still named: %r" % (verdict.get("errors"),),
        )

    def test_finding2_a_nested_offset_above_the_bound_is_refused(self):
        """The re-review's `offset_disagrees`: the nested page offset says
        1000 ms while the deprecated top-level alias stays small; the alias
        must not hide the contradictory evidence."""
        validator = self.load_validator()
        record = WitnessIssue137Tests.armed_good_record() | {
            "clock_check": WitnessValidatorTests.good_record()["clock_check"]
            | {"page_offset_ms": 1000}
        }
        verdict = validator.validate_witness(record)
        self.assertTrue(
            verdict.get("refused"),
            "a page offset of 1000 ms contradicts the acceptable flag even "
            "when the deprecated alias is small: %r" % (verdict,),
        )
        self.assertEqual(verdict.get("reason"), "clock_check_evidence_contradicted")

    # -- finding 3: pixel evidence reports impossible counts ---------------

    def test_finding3_changed_pixels_above_total_are_refused(self):
        validator = self.load_validator()
        record = WitnessIssue137Tests.armed_good_record() | {
            "changed_pixels": 900,
            "total_pixels": 1,
        }
        verdict = validator.validate_witness(record)
        self.assertTrue(
            verdict.get("refused"),
            "a subset of changed pixels cannot exceed the total: %r" % (verdict,),
        )
        self.assertEqual(verdict.get("reason"), "pixel_evidence_contradicted")

    def test_finding3_zero_changed_pixels_with_a_zero_floor_are_refused(self):
        validator = self.load_validator()
        record = WitnessIssue137Tests.armed_good_record() | {
            "changed_pixels": 0,
            "min_pixels": 0,
        }
        verdict = validator.validate_witness(record)
        self.assertTrue(
            verdict.get("refused"),
            "a zero pixel floor gates nothing, and zero changed pixels cannot "
            "carry a positive ratio: %r" % (verdict,),
        )
        self.assertEqual(
            verdict.get("reason"),
            "witness_schema_invalid",
            "round 4: a production record's pixel floor is the schema's to "
            "check; a floor below 1 gates nothing: %r" % (verdict,),
        )

    # -- finding 4: a null total-frame count bypasses the subset check -----

    def test_finding4_a_null_total_frame_count_is_refused(self):
        validator = self.load_validator()
        record = WitnessIssue137Tests.armed_good_record() | {"frames_total": None}
        verdict = validator.validate_witness(record)
        self.assertTrue(
            verdict.get("refused"),
            "a null frames_total skips the subset check; a required count is "
            "an integer, never null: %r" % (verdict,),
        )
        self.assertEqual(
            verdict.get("reason"),
            "witness_schema_invalid",
            "round 4: a required count is the schema's to check; a null count "
            "is an integer, never null: %r" % (verdict,),
        )

    # -- finding 5: the mask flag contradicts its own error ----------------

    def test_finding5_a_mask_error_contradicts_the_accepted_flag(self):
        validator = self.load_validator()
        record = WitnessIssue137Tests.armed_good_record() | {
            "caret_mask_error": "injection failed"
        }
        verdict = validator.validate_witness(record)
        self.assertTrue(
            verdict.get("refused"),
            "caret_masked=true with a recorded mask error is a flag asserted "
            "over its own failure: %r" % (verdict,),
        )
        self.assertEqual(verdict.get("reason"), "caret_mask_contradicted")


class WitnessValidatorShapeTests(unittest.TestCase):
    """The validator's shape contract, pinned so the branches stay exercised.

    These are not counterexamples: every refusal here was already refused
    before #137. They pin the reason each malformed shape names and the
    CLI's exit codes, so the witness module keeps its measured coverage
    above the 80 % lines / 70 % branches baseline (#137).

    Round 4: the fixture is the real capture (a production record), so the
    malformations the lenient branch used to catch field-by-field
    (``invalid_record``, ``no_frame_time``, ``invalid_arm_time``,
    ``min_pixels_invalid``) are named by the strict schema first —
    ``witness_schema_invalid`` — and the legacy clock shapes that this
    class used to pin as ACCEPTED are refused ``not_a_witness_record``
    (they carry none of the producer's markers; no producer writes them).
    """

    #: (name, updates on the good record, the reason the refusal must name)
    REFUSED = [
        (
            "nested-check-not-acceptable-with-reason",
            {"clock_check": {"acceptable": False, "reason": "anchor_lag_above_bound"}},
            "clock_check_not_acceptable",
        ),
        (
            "nested-check-not-acceptable-silent",
            {"clock_check": {"acceptable": False, "reason": None}},
            "clock_check_not_acceptable",
        ),
        (
            "no-clock-check-anywhere",
            {
                "clock_check": None,
                "clock_skew_ms": None,
                "clock_skew_acceptable": None,
            },
            "witness_schema_invalid",
        ),
        (
            "acceptable-flag-without-a-skew",
            {
                "clock_check": None,
                "clock_skew_ms": None,
                "clock_skew_acceptable": True,
            },
            "witness_schema_invalid",
        ),
        ("frame-time-missing", {"frame_page_ms": None}, "witness_schema_invalid"),
        (
            "ratio-below-threshold",
            {"diff_ratio": 0.00001},
            "no_pixel_evidence",
        ),
        ("below-pixel-floor", {"changed_pixels": 1}, "no_pixel_evidence"),
        ("caret-not-masked", {"caret_masked": False}, "caret_not_masked"),
        (
            "counts-not-integers",
            {"frames_total": "7", "frames_after": "3"},
            "witness_schema_invalid",
        ),
        ("count-negative", {"frames_total": -1}, "witness_schema_invalid"),
        ("count-after-null", {"frames_after": None}, "witness_schema_invalid"),
        ("diff-ratio-not-a-number", {"diff_ratio": "high"}, "witness_schema_invalid"),
        ("diff-ratio-above-one", {"diff_ratio": 1.5}, "witness_schema_invalid"),
        ("threshold-not-a-number", {"threshold": "tiny"}, "witness_schema_invalid"),
        ("threshold-not-positive", {"threshold": 0.0}, "witness_schema_invalid"),
        (
            "caret-masked-not-a-boolean",
            {"caret_masked": "yes"},
            "witness_schema_invalid",
        ),
        (
            "document-scoped-not-a-boolean",
            {"document_scoped": 1},
            "witness_schema_invalid",
        ),
        (
            "no-frame-with-a-frame-time",
            {"outcome": "no_frame"},
            "witness_schema_invalid",
        ),
        ("arm-infinite", {"after_page_ms": float("inf")}, "witness_schema_invalid"),
    ]

    #: the legacy clock shapes this class pinned as ACCEPTED before round 4.
    #: No producer writes them (`witnessFrame()` always emits
    #: `kind: 'frame_witness'`), so they are not witness records; the
    #: discriminator refuses them, and the verdict stays parseable.
    LEGACY_SHAPES = [
        {"clock_skew_ms": None, "skew_ms": 0.2, "clock_check": None},
        {"clock_skew_ms": None},
        {
            "clock_skew_ms": None,
            "clock_check": None,
            "clock_skew": {"skew_ms": 0.2},
        },
    ]

    def load_validator(self):
        return _load_validator()

    def test_each_malformed_shape_names_its_reason(self):
        validator = self.load_validator()
        for name, updates, reason in self.REFUSED:
            with self.subTest(case=name):
                record = WitnessValidatorTests.good_record() | updates
                verdict = validator.validate_witness(record)
                self.assertTrue(
                    verdict.get("refused"), "%s must be refused: %r" % (name, verdict)
                )
                self.assertEqual(
                    verdict.get("reason"),
                    reason,
                    "%s must name its reason: %r" % (name, verdict),
                )

    @staticmethod
    def _strip_producer_markers(record: dict) -> dict:
        """The capture with every producer marker removed: the "legacy
        simple" shape the round-3 validator accepted on the strength of an
        alias. Whatever else the record still carries, it no longer says
        what the producer says."""
        record = json.loads(json.dumps(record))
        record.pop("kind", None)
        record.pop("clock_check_source", None)
        cc = record.get("clock_check")
        if isinstance(cc, dict):
            for key in (
                "method",
                "page_offset_samples",
                "lag_bound_ms",
                "conversion",
                "change_page_ms",
                "frame_page_ms",
                "frame_lag_ms",
            ):
                cc.pop(key, None)
        return record

    def test_legacy_clock_shapes_are_refused_not_a_witness_record(self):
        """Round 4 inverted this pin: the legacy shapes carry none of the
        producer's markers, so they are not witness records. They stay
        parseable — a verdict comes back, not a crash — but it can never be
        ok for publication, whatever alias carries the skew."""
        validator = self.load_validator()
        for i, updates in enumerate(self.LEGACY_SHAPES):
            with self.subTest(case=i):
                record = self._strip_producer_markers(
                    WitnessValidatorTests.good_record()
                ) | updates
                verdict = validator.validate_witness(record)
                self.assertTrue(
                    verdict.get("refused"),
                    "the legacy shape %r must be refused: %r" % (updates, verdict),
                )
                self.assertFalse(verdict.get("ok"))
                self.assertEqual(verdict.get("reason"), "not_a_witness_record")

    def test_an_explicit_skew_argument_is_used(self):
        """`skew=` overrides the record's own offset (the caller measured it)."""
        validator = self.load_validator()
        record = WitnessValidatorTests.good_record()
        verdict = validator.validate_witness(record, skew=0.3)
        self.assertFalse(verdict.get("refused"))
        self.assertEqual(verdict.get("skew_ms"), 0.3)
        # lax layer (owner 2026-11-11): 5.0 ms now sits inside the bound.
        verdict = validator.validate_witness(record, skew=5.0)
        self.assertFalse(verdict.get("refused"))
        verdict = validator.validate_witness(record, skew=5.5)
        self.assertTrue(verdict.get("refused"))
        self.assertEqual(verdict.get("reason"), "clock_skew_above_bound")

    def test_a_record_that_is_not_a_mapping_is_refused(self):
        validator = self.load_validator()
        verdict = validator.validate_witness(None)
        self.assertTrue(verdict.get("refused"))
        self.assertEqual(verdict.get("reason"), "record_not_a_mapping")
        self.assertIsNone(verdict.get("record"))

    def test_missing_threshold_is_refused(self):
        validator = self.load_validator()
        record = WitnessValidatorTests.good_record()
        del record["threshold"]
        verdict = validator.validate_witness(record)
        self.assertTrue(verdict.get("refused"))
        self.assertEqual(verdict.get("reason"), "witness_schema_invalid")
        self.assertTrue(
            any("missing field" in str(e) for e in verdict.get("errors", [])),
            "the missing field must be named: %r" % (verdict.get("errors"),)
        )

    def test_missing_changed_pixels_is_refused(self):
        validator = self.load_validator()
        record = WitnessValidatorTests.good_record()
        del record["changed_pixels"]
        verdict = validator.validate_witness(record)
        self.assertTrue(verdict.get("refused"))
        self.assertEqual(verdict.get("reason"), "witness_schema_invalid")

    def test_the_cli_exit_codes(self):
        validator = self.load_validator()
        good = WitnessValidatorTests.good_record()
        bad = good | {"outcome": "no_frame"}
        with tempfile.TemporaryDirectory() as tmp:
            good_path = Path(tmp) / "good.json"
            good_path.write_text(json.dumps(good), encoding="utf-8")
            bad_path = Path(tmp) / "bad.json"
            bad_path.write_text(json.dumps(bad), encoding="utf-8")
            missing_path = Path(tmp) / "missing.json"
            junk_path = Path(tmp) / "junk.json"
            junk_path.write_text("{", encoding="utf-8")
            bundle_path = Path(tmp) / "bundle.json"
            bundle_path.write_text(json.dumps([good, bad]), encoding="utf-8")
            all_good_path = Path(tmp) / "all-good.json"
            all_good_path.write_text(json.dumps([good, good]), encoding="utf-8")
            scalar_path = Path(tmp) / "scalar.json"
            scalar_path.write_text("5", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(validator.main(["--file", str(good_path)]), 0)
                self.assertEqual(validator.main(["--file", str(bad_path)]), 1)
                self.assertEqual(validator.main(["--file", str(missing_path)]), 2)
                self.assertEqual(validator.main(["--file", str(junk_path)]), 2)
                self.assertEqual(validator.main(["--file", str(scalar_path)]), 1)
                self.assertEqual(
                    validator.main(["--file", str(bundle_path)]),
                    1,
                    "a bundle with one refused record exits 1",
                )
                bundle = json.loads(out.getvalue().splitlines()[-1])
                self.assertEqual(bundle["records"], 2)
                self.assertTrue(bundle["refused"])
                self.assertEqual(
                    validator.main(["--file", str(all_good_path)]),
                    0,
                    "a bundle of good records exits 0",
                )
            verdict = json.loads(out.getvalue().splitlines()[-1])
            self.assertFalse(verdict["refused"])
            self.assertEqual(verdict["records"], 2)


def _load_captured_record() -> dict:
    """A real witnessed record captured once from headless Chromium through
    `witness.mjs`'s own CLI (the fixture `captured_frame_witness.json`, kept in
    the tree so the mutation matrix runs without a browser)."""
    path = FIXTURES / "captured_frame_witness.json"
    if not path.is_file():
        raise AssertionError(
            "perf/tests/fixtures/witness/captured_frame_witness.json is missing; "
            "recapture it with the real-Chromium witness test"
        )
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise AssertionError("the captured fixture must be a JSON object")
    return record


class WitnessProductionEvidenceTests(unittest.TestCase):
    """Round 3, part 1 and 2: the strict schema and the recomputation.

    A record that identifies itself as a production `witnessFrame()` record
    (`kind: frame_witness`, a `clock_check_source`, or a nested clock check of
    the `page_clock_offset+pixel_anchor` method) must carry every field the
    producer emits, with the producer's type and range, and every verdict the
    record derives from its measurements -- the anchor's causality and lag,
    the page offset and its spread, the diff ratio, the pixel counts, the
    region's pixel arithmetic -- is recomputed from those measurements. A
    null where a number is required is refused. The fixture is a real
    captured record, so these tests pin the contract against what the
    producer actually emits, not a hand-drawn copy of it.
    """

    def load_validator(self):
        return _load_validator()

    def setUp(self):
        self.validator = self.load_validator()
        self.record = _load_captured_record()

    def refused(self, updates: dict, note: str) -> None:
        mutated = json.loads(json.dumps(self.record))  # deep copy
        for key, value in updates.items():
            if key.startswith("clock_check."):
                self.record_set(mutated, key, value)
            else:
                mutated[key] = value
        verdict = self.validator.validate_witness(mutated)
        self.assertTrue(
            verdict.get("refused"), "%s must be refused: %r" % (note, verdict)
        )

    @staticmethod
    def record_set(record, dotted_key, value):
        parts = dotted_key.split(".")
        target = record
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value

    # -- the control: a real record validates -----------------------------

    def test_the_captured_record_validates(self):
        verdict = self.validator.validate_witness(self.record)
        self.assertFalse(
            verdict.get("refused"),
            "the real captured record must validate: %r" % (verdict,),
        )
        self.assertIsNone(verdict.get("reason"))

    # -- part 1: the strict schema ----------------------------------------

    def test_a_missing_producer_field_is_refused(self):
        for field in (
            "kind",
            "frames_ack_skipped",
            "window_ms",
            "window_requested_ms",
            "baseline_source",
            "region_pixels",
            "total_pixels",
            "max_diff_ratio",
            "timestamp_kind",
            "time_origin_ms",
            "clock_check_source",
            "clock_skew_method",
            "clock_skew_bound_ms",
            "clock_skew_acceptable",
            "elapsed_ms",
            "caret_mask_css",
        ):
            with self.subTest(field=field):
                mutated = json.loads(json.dumps(self.record))
                del mutated[field]
                verdict = self.validator.validate_witness(mutated)
                self.assertTrue(
                    verdict.get("refused"),
                    "a production record without %s must be refused: %r"
                    % (field, verdict),
                )

    def test_a_null_where_a_number_is_required_is_refused(self):
        for field in (
            "frames_total",
            "frames_after",
            "diff_ratio",
            "threshold",
            "min_pixels",
            "changed_pixels",
            "total_pixels",
            "region_pixels",
            "time_origin_ms",
            "clock_skew_bound_ms",
        ):
            with self.subTest(field=field):
                self.refused({field: None}, "null %s" % (field,))

    def test_out_of_range_producer_fields_are_refused(self):
        self.refused({"window_ms": 499}, "window_ms below the producer's clamp")
        self.refused({"min_pixels": 0}, "a zero pixel floor")
        self.refused({"diff_ratio": 1.5}, "a ratio above 1")
        self.refused({"frames_total": 4.5}, "a fractional frame count")
        self.refused({"frames_ack_skipped": -1}, "a negative count")
        self.refused({"kind": "clock_skew"}, "a kind the producer never emits")
        self.refused(
            {"clock_check_source": "bogus"}, "an unknown clock_check_source"
        )
        self.refused(
            {"timestamp_kind": "unknown"},
            "a witnessed frame needed a convertible timestamp",
        )

    def test_wrongly_typed_nested_evidence_is_refused(self):
        self.refused({"clock_check.checks": "x"}, "checks as a string")
        self.refused({"clock_check.page_offset_samples": "x"}, "samples as a string")
        self.refused({"clock_check.notes": "x"}, "notes as a string")
        self.refused({"clock_check.conversion": []}, "conversion as a list")

    # -- part 2: recomputed verdicts ---------------------------------------

    def test_the_anchor_causality_and_lag_are_recomputed(self):
        # frame_page_ms 1000 ms before its own change, all flags true.
        self.refused(
            {
                "clock_check.frame_page_ms": 0,
                "clock_check.change_page_ms": 1000,
                "clock_check.frame_lag_ms": -1000,
            },
            "an anchor frame that precedes its change",
        )
        cc = self.record["clock_check"]
        # the recorded lag must equal frame_page_ms - change_page_ms
        self.refused(
            {"clock_check.frame_lag_ms": cc["frame_lag_ms"] + 1000},
            "a lag that is not the anchor's own difference",
        )
        # a lag above the recorded bound
        self.refused(
            {"clock_check.frame_lag_ms": cc["lag_bound_ms"] + 1},
            "an anchor lag above its bound",
        )
        # the bound itself is derived from the frame interval
        self.refused(
            {"clock_check.lag_bound_ms": cc["lag_bound_ms"] + 100},
            "a lag bound the frame interval does not give",
        )
        self.refused(
            # lax layer (owner 2026-11-11): the floor is 250 ms now, so the
            # corrupted interval must triple past it to contradict the bound.
            {"clock_check.frame_interval_ms": cc["frame_interval_ms"] + 100},
            "a frame interval the lag bound contradicts",
        )

    def test_the_page_offset_is_recomputed_from_its_samples(self):
        cc = self.record["clock_check"]
        self.refused(
            {"clock_check.page_offset_ms": cc["page_offset_ms"] + 1},
            "a page offset that is not the median of its samples",
        )
        self.refused(
            {"clock_check.page_offset_samples": [5.0] * len(cc["page_offset_samples"])},
            "samples whose median is not the recorded offset",
        )
        self.refused(
            {"clock_check.page_offset_spread_ms": cc["page_offset_spread_ms"] + 1},
            "a spread that is not max-min of the samples",
        )
        self.refused(
            {"clock_check.page_offset_ms": 1000},
            "a page offset above the bound (the alias must not hide it)",
        )

    def test_every_alias_must_agree_with_its_evidence(self):
        cc = self.record["clock_check"]
        self.refused(
            {"clock_skew_ms": cc["page_offset_ms"] + 1},
            "the deprecated clock_skew_ms alias"
        )
        self.refused(
            {"clock_check.skew_ms": cc["page_offset_ms"] + 1},
            "the nested deprecated skew_ms alias"
        )
        self.refused(
            {"time_origin_ms": self.record["time_origin_ms"] + 1},
            "the top-level time_origin_ms"
        )
        self.refused(
            {"marker_page_ms": self.record["after_page_ms"] + 1},
            "the marker_page_ms alias of the arm"
        )
        self.refused(
            {"clock_skew_method": "bogus"}, "the clock_skew_method alias"
        )
        self.refused(
            {"clock_skew_bound_ms": cc["bound_ms"] + 1},
            "the clock_skew_bound_ms alias"
        )
        self.refused(
            {"clock_skew_acceptable": False},
            "the clock_skew_acceptable alias"
        )
        self.refused(
            {"clock_check.reason": "anchor_missing"},
            "an acceptable check with a refusal reason"
        )

    def test_the_pixel_evidence_is_recomputed(self):
        self.refused(
            {"diff_ratio": 1.0}, "a ratio that is not changed/total"
        )
        self.refused(
            {"changed_pixels": self.record["changed_pixels"] + 1},
            "changed pixels the ratio does not describe"
        )
        self.refused(
            {"total_pixels": self.record["changed_pixels"] - 1},
            "a total below the changed pixels"
        )
        self.refused(
            {"max_diff_ratio": 0.5}, "a max ratio that is not changed/total"
        )

    def test_the_region_arithmetic_is_recomputed(self):
        region = self.record["document_region"]
        self.refused(
            {"region_pixels": self.record["region_pixels"] + 1},
            "region_pixels must be the device rect's area"
        )
        self.refused(
            {
                "document_region": region
                | {
                    "rect_device_px": region["rect_device_px"]
                    | {"y": region["rect_device_px"]["y"] + 1}
                }
            },
            "a device rect that is not the CSS rect at the recorded dpr",
        )
        self.refused(
            {"document_region": region | {"device_pixel_ratio": 2}},
            "a dpr the device rect contradicts",
        )

    def test_the_conversion_bound_is_recomputed(self):
        cc = self.record["clock_check"]
        self.refused(
            {"clock_check.conversion": cc["conversion"] | {"error_lower_ms": -3}},
            "the conversion's lower bound is -2 ms by causality",
        )
        self.refused(
            {
                "clock_check.conversion": cc["conversion"]
                | {"error_upper_ms": cc["lag_bound_ms"] + 1}
            },
            "the conversion's upper bound is the lag bound",
        )

    def test_the_witness_frame_stays_causal_against_its_arm(self):
        self.refused(
            {"frame_page_ms": self.record["after_page_ms"] - 100},
            "a witness frame before its arm",
        )
        self.refused(
            {"baseline_page_ms": self.record["frame_page_ms"] + 100},
            "a baseline taken after the witness frame",
        )


class WitnessMutationTests(unittest.TestCase):
    """Round 3, part 3: the generated mutation test.

    The fixture is a real captured record. For every field of that record
    (top level, the nested clock check, the document region, the conversion)
    each corruption -- delete, null, wrong type, out-of-range, contradictory
    value -- must produce a refusal, or the (field, corruption) pair must be
    listed in HARMLESS with the reason it cannot affect the verdict. The
    corruptions are generated from the field's own type, so adding a producer
    field without a schema rule shows up here as an unlisted acceptance, and
    a justification for a corruption that is in fact refused fails the test.
    """

    DELETE = object()  # sentinel: the key is removed

    #: (where, field, corruption) -> why the corruption cannot change the
    #: verdict. Every entry is an in-range value change of a field that is an
    #: input or an informational observation: only its type, range and its
    #: checkable relations gate anything, and those are enforced by this same
    #: matrix through the other corruptions and the recomputation tests.
    HARMLESS = {
        ("", "timestamp_kind", "contradictory"):
            "which known kind the timestamps had is an observation the record "
            "cannot prove; only a known kind gates (enforced by out-of-range)",
        ("", "window_ms", "contradictory"):
            "the wait budget actually used; informational for publication",
        ("", "window_requested_ms", "contradictory"):
            "the raw request before the producer's clamp; informational",
        ("", "frames_total", "contradictory"):
            "a raw frame count; only frames_after <= frames_total, the check's "
            "own count <= it (round 6: the same run's recorder only "
            "accumulates) and the integer range are checkable (enforced by "
            "out-of-range and by frames_after's corruption)",
        ("", "frames_ack_skipped", "contradictory"):
            "a count of frames whose ack never settled; its integer range and "
            "its subset relation to frames_total gate (round 5: it may not "
            "exceed the total), and the corruption shifts it within the total",
        ("", "elapsed_ms", "contradictory"):
            "the wall-clock duration of the wait; informational",
        ("", "frame_page_ms", "contradictory"):
            "the measurement itself; only its causal relations (arm, baseline) "
            "are checkable, and an in-range shift that keeps them cannot be "
            "detected from the record alone",
        ("", "baseline_page_ms", "null"):
            "the producer emits null when the baseline came from the caller",
        ("", "baseline_page_ms", "contradictory"):
            "which frame was the baseline; only baseline <= witness frame is "
            "checkable, and a shift below it cannot be detected from the record",
        ("", "baseline_source", "contradictory"):
            "which baseline was used; informational",
        ("", "caret_mask_css", "contradictory"):
            "the injected style text; the mask's effect is proven by pixels",
        ("", "caret_mask_error", "contradictory"):
            "an empty string is the producer's null-equivalent (no error)",
        ("", "marker_page_ms", "delete"):
            "marker_page_ms is the CLI's alias of after_page_ms; a record made "
            "through the module API does not carry it, and when present it "
            "must agree (enforced by the null and contradictory corruptions)",
        ("", "clock_check_source", "contradictory"):
            "whether the check ran inline or was handed over names the same "
            "measured evidence; only page_offset_only would matter, and it is "
            "refused (acceptable is then false)",
        ("document_region", "selector", "contradictory"):
            "which selector resolved the region; informational",
        ("document_region", "rect_css_px", "contradictory"):
            "the DOM rect; only the device rect it clamps to is checkable, so "
            "a sub-pixel shift that clamps identically cannot be detected",
        ("clock_check", "timestamp_kind", "contradictory"):
            "same as the top-level kind: known vs unknown is what gates",
        ("clock_check", "timestamp_field", "contradictory"):
            "which metadata field carried the timestamp; informational",
        ("clock_check", "frame_monotonic_ms", "null"):
            "the producer emits null when the metadata carried no monotonic "
            "reading",
        ("clock_check", "frame_monotonic_ms", "contradictory"):
            "a raw monotonic reading; not derivable from the record",
        ("clock_check", "frames_total", "contradictory"):
            "the check's own frame count at its own instant; an anchor needs "
            "the producer's minimum of two of them -- a baseline plus the "
            "anchor frame (round 5 refused zero, round 6 one) -- and the "
            "count may not exceed the record's own (round 6), but which "
            "count in between the recorder had is not derivable from the "
            "record",
        ("clock_check", "anchor_diff_ratio", "contradictory"):
            "the anchor's own diff ratio; its producer threshold and its pixel "
            "floor over the producer's probe region gate (round 5; round 6 "
            "pins the probe's geometry to the record's own dpr), but the "
            "exact value above them is not derivable from the record",
        # ("clock_check", "anchor_probe_region_px", "contradictory") was
        # here until round 5, justifying a one-pixel origin shift with the
        # unchanged area. Round 6 (R5-4) removed it: the producer emits a
        # constant origin (x=y=0), so a shifted probe is a record the
        # producer never wrote and is refused.
        ("clock_check", "frame_interval_source", "contradictory"):
            "where the interval came from; informational",
        ("clock_check", "frame_interval_samples", "contradictory"):
            "how many rAF deltas were seen; informational",
        ("clock_check", "frame_interval_ms", "null"):
            "the producer emits null when no rAF delta arrived; the lag bound "
            "must then be the rule's 250 ms minimum, which is recomputed",
        ("clock_check", "frame_interval_samples", "null"):
            "the producer's defensive null for an absent count; informational",
        ("clock_check", "lag_bound_rule", "contradictory"):
            "prose restating lag_bound_ms, which is recomputed",
        ("clock_check", "caret_mask_error", "contradictory"):
            "an empty string is the producer's null-equivalent (no error)",
        ("clock_check", "notes", "contradictory"):
            "prose; the numeric evidence is recomputed elsewhere",
        ("clock_check.conversion", "formula", "contradictory"):
            "prose restating the conversion, whose bounds are recomputed",
        ("clock_check.conversion", "error_lower_why", "contradictory"): "prose",
        ("clock_check.conversion", "error_upper_why", "contradictory"): "prose",
        ("clock_check.conversion", "published", "contradictory"):
            "prose restating the numeric bounds, which are recomputed",
    }

    def load_validator(self):
        return _load_validator()

    @staticmethod
    def _set(record, where, field, value):
        target = record
        for part in [p for p in where.split(".") if p]:
            target = target[part]
        if value is WitnessMutationTests.DELETE:
            del target[field]
        else:
            target[field] = value

    def contradictory(self, record, where, field):
        """The contradictory corruption for one field: a value of the right
        type that contradicts what the record's other evidence says (for
        derived fields), or None when the field's value is not derived -- an
        in-range shift of such a field is then generated from its type and
        must be justified in HARMLESS."""
        cc = record["clock_check"]
        region = record.get("document_region") or {}
        other_kind = (
            "monotonic_seconds"
            if record.get("timestamp_kind") != "monotonic_seconds"
            else "epoch_seconds"
        )
        other_nested_kind = (
            "monotonic_seconds"
            if cc.get("timestamp_kind") != "monotonic_seconds"
            else "epoch_seconds"
        )
        rect = dict(region.get("rect_css_px") or {})
        if rect:
            rect = dict(rect, y=rect["y"] + 0.01)  # clamps to the same device y
        table = {
            ("", "kind"): lambda r: "clock_skew",
            ("", "outcome"): lambda r: "no_frame",
            ("", "frame_page_ms"): lambda r: r["frame_page_ms"] + 100.0,
            ("", "frames_after"): lambda r: r["frames_total"] + 1,
            ("", "diff_ratio"): lambda r: 1.0,
            ("", "threshold"): lambda r: r["diff_ratio"] + 1.0,
            ("", "min_pixels"): lambda r: float(r["changed_pixels"]) + 1.0,
            ("", "caret_masked"): lambda r: False,
            ("", "caret_mask_error"): lambda r: "",
            ("", "after_page_ms"): lambda r: r["frame_page_ms"] + 100.0,
            ("", "baseline_page_ms"): lambda r: r["frame_page_ms"] - 100.0,
            ("", "baseline_source"): lambda r: "caller",
            ("", "document_scoped"): lambda r: False,
            ("", "document_region"): lambda r: dict(
                region,
                rect_device_px=dict(
                    region["rect_device_px"], y=region["rect_device_px"]["y"] + 1
                ),
            ),
            ("", "document_region_error"): lambda r: "selector missing",
            ("", "region_pixels"): lambda r: float(r["region_pixels"]) + 1.0,
            ("", "changed_pixels"): lambda r: r["changed_pixels"] + 1,
            ("", "total_pixels"): lambda r: max(0, r["changed_pixels"] - 1),
            ("", "max_diff_ratio"): lambda r: 0.5,
            ("", "timestamp_kind"): lambda r: other_kind,
            ("", "time_origin_ms"): lambda r: r["time_origin_ms"] + 1,
            ("", "clock_check"): lambda r: {},
            ("", "clock_check_source"): lambda r: "inline",
            ("", "clock_skew_ms"): lambda r: cc["page_offset_ms"] + 1.0,
            ("", "clock_skew_method"): lambda r: "bogus",
            ("", "clock_skew_bound_ms"): lambda r: cc["bound_ms"] + 1.0,
            ("", "clock_skew_acceptable"): lambda r: False,
            ("", "marker_page_ms"): lambda r: r["after_page_ms"] + 1.0,
            ("clock_check", "kind"): lambda r: "frame_witness",
            ("clock_check", "acceptable"): lambda r: False,
            ("clock_check", "reason"): lambda r: "anchor_missing",
            ("clock_check", "checks"): lambda r: {k: False for k in cc["checks"]},
            ("clock_check", "method"): lambda r: "page_clock_offset",
            ("clock_check", "timestamp_kind"): lambda r: other_nested_kind,
            ("clock_check", "bound_ms"): lambda r: cc["bound_ms"] + 1.0,
            ("clock_check", "page_offset_ms"): lambda r: cc["page_offset_ms"] + 1.0,
            (
                "clock_check",
                "page_offset_samples",
            ): lambda r: [5.0] * len(cc["page_offset_samples"]),
            (
                "clock_check",
                "page_offset_spread_ms",
            ): lambda r: cc["page_offset_spread_ms"] + 1.0,
            ("clock_check", "skew_ms"): lambda r: cc["page_offset_ms"] + 1.0,
            ("clock_check", "time_origin_ms"): lambda r: cc["time_origin_ms"] + 1,
            ("clock_check", "change_page_ms"): lambda r: cc["frame_page_ms"] + 100.0,
            ("clock_check", "frame_page_ms"): lambda r: cc["frame_page_ms"] + 1000.0,
            ("clock_check", "frame_lag_ms"): lambda r: cc["frame_lag_ms"] + 1000.0,
            ("clock_check", "anchor_pixel_checked"): lambda r: False,
            ("clock_check", "anchor_diff_ratio"): lambda r: 0.5,
            (
                "clock_check",
                "anchor_probe_region_px",
            ): lambda r: dict(cc["anchor_probe_region_px"], x=1),
            ("clock_check", "frame_interval_ms"): lambda r: cc["frame_interval_ms"] + 100.0,
            ("clock_check", "lag_bound_ms"): lambda r: cc["lag_bound_ms"] + 100.0,
            ("clock_check", "conversion"): lambda r: {},
            ("clock_check", "caret_masked"): lambda r: False,
            ("clock_check", "caret_mask_error"): lambda r: "",
            ("document_region", "source"): lambda r: "rect",
            ("document_region", "rect_css_px"): lambda r: rect,
            (
                "document_region",
                "rect_device_px",
            ): lambda r: dict(region["rect_device_px"], y=region["rect_device_px"]["y"] + 1),
            (
                "document_region",
                "device_pixel_ratio",
            ): lambda r: 2.0,
            ("clock_check.conversion", "error_lower_ms"): lambda r: -3.0,
            (
                "clock_check.conversion",
                "error_upper_ms",
            ): lambda r: cc["lag_bound_ms"] + 1.0,
        }
        maker = table.get((where, field))
        return maker(record) if maker else None

    def corruptions(self, record, where, field):
        """The five corruptions for one field, generated from its value. A
        corruption whose value equals the field's present value (null on a
        field that is already null) is meaningless and skipped."""
        target = record
        for part in [p for p in where.split(".") if p]:
            target = target[part]
        value = target[field]
        out = [("delete", self.DELETE), ("null", None)]
        if isinstance(value, bool):
            out.append(("wrong-type", "yes"))
            # a bool has no range; its flip is the contradiction
        elif isinstance(value, (int, float)):
            out.append(("wrong-type", "4"))
            out.append(("out-of-range", -1))
        elif isinstance(value, str):
            out.append(("wrong-type", 5))
            out.append(("out-of-range", ""))
        elif isinstance(value, list):
            out.append(("wrong-type", "x"))
            out.append(("out-of-range", []))
        elif isinstance(value, dict):
            out.append(("wrong-type", []))
            out.append(("out-of-range", {}))
        contradictory = self.contradictory(record, where, field)
        if contradictory is None:
            # not derived: an in-range shift of the same type; for these to
            # be accepted the (field, "contradictory") pair must sit in
            # HARMLESS with the reason, which is the point of the matrix.
            if isinstance(value, bool):
                contradictory = not value
            elif isinstance(value, (int, float)):
                contradictory = value + 1
            elif isinstance(value, str):
                contradictory = value + "-mutated"
            elif isinstance(value, list):
                contradictory = ["mutated"]
        if contradictory is not None:
            out.append(("contradictory", contradictory))
        return [
            (name, value_)
            for name, value_ in out
            if not (value_ is not self.DELETE and value_ == value)
        ]

    def fields(self, record):
        """Every field of the record, one dotted where per level the schema
        covers: top level, clock_check, document_region, conversion."""
        out = [("", field) for field in sorted(record)]
        out += [("clock_check", field) for field in sorted(record["clock_check"])]
        if isinstance(record.get("document_region"), dict):
            out += [
                ("document_region", field)
                for field in sorted(record["document_region"])
            ]
        if isinstance(record["clock_check"].get("conversion"), dict):
            out += [
                ("clock_check.conversion", field)
                for field in sorted(record["clock_check"]["conversion"])
            ]
        return out

    def test_every_single_field_corruption_is_refused_or_justified(self):
        validator = self.load_validator()
        record = _load_captured_record()
        verdict = validator.validate_witness(record)
        self.assertFalse(
            verdict.get("refused"),
            "the uncorrupted fixture must validate: %r" % (verdict,),
        )
        checked = 0
        accepted = set()
        for where, field in self.fields(record):
            for name, value in self.corruptions(record, where, field):
                with self.subTest(
                    field="%s%s" % (where + "." if where else "", field),
                    corruption=name,
                ):
                    mutated = json.loads(json.dumps(record))
                    self._set(mutated, where, field, value)
                    verdict = validator.validate_witness(mutated)
                    checked += 1
                    if not verdict.get("refused"):
                        accepted.add((where, field, name))
                        self.assertIn(
                            (where, field, name),
                            self.HARMLESS,
                            "%s%s corrupted with %r was accepted without a "
                            "justification"
                            % (where + "." if where else "", field, value),
                        )
        # The matrix must actually cover the record, every justification must
        # name a corruption that was really applied, and (the sharp edge) a
        # justification may only exist for a corruption that is genuinely
        # accepted -- otherwise the list quietly rots into lies.
        self.assertGreaterEqual(
            checked, 200, "the matrix must be generated, not hand-picked"
        )
        applied = set()
        for where, field in self.fields(record):
            for name, _value in self.corruptions(record, where, field):
                applied.add((where, field, name))
        for entry in self.HARMLESS:
            self.assertIn(
                entry,
                applied,
                "the justification %r names a corruption the matrix never "
                "applied" % (entry,),
            )
            self.assertIn(
                entry,
                accepted,
                "the justification %r names a corruption that is in fact "
                "refused; remove it" % (entry,),
            )

    def test_the_harmless_list_stays_short(self):
        """A justification is an exception; fifty of them would be a schema
        with holes. The count is pinned so a new one is a visible decision
        (the matrix is ~500 cells; the refusals are the overwhelming
        majority)."""
        self.assertLessEqual(
            len(self.HARMLESS),
            40,
            "the harmless list grew: %r" % (sorted(self.HARMLESS),),
        )

class WitnessRealRecordTests(_WitnessBrowserCase):
    """Round 3 against the real producer: a fresh capture validates, and the
    re-review's browser-record mutations (its `browser.py` probe) on that
    fresh capture are refused."""

    def capture(self) -> dict:
        return self.run_witness(
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

    def test_a_fresh_real_capture_validates(self):
        record = self.capture()
        validator = _load_validator()
        verdict = validator.validate_witness(record)
        self.assertFalse(
            verdict.get("refused"),
            "a fresh real capture must validate: %r" % (verdict,),
        )
        self.assertIsNone(verdict.get("reason"))

    def test_the_rereview_mutations_on_a_fresh_capture_are_refused(self):
        record = self.capture()
        validator = _load_validator()
        cc = record["clock_check"]
        mutations = {
            "erased_checks": {"checks": {}, "anchor_pixel_checked": None},
            "lying_checks": {
                "frame_page_ms": 0,
                "change_page_ms": 1000,
                "frame_lag_ms": -1000,
            },
            "offset_disagrees": {"page_offset_ms": 1000},
        }
        for name, change in mutations.items():
            with self.subTest(case=name):
                mutated = record | {"clock_check": cc | change}
                verdict = validator.validate_witness(mutated)
                self.assertTrue(
                    verdict.get("refused"),
                    "%s on a real record must be refused: %r" % (name, verdict),
                )
                self.assertIn(
                    verdict.get("reason"),
                    (
                        "clock_check_evidence_missing",
                        "clock_check_evidence_contradicted",
                        # round 6: the schema runs before the recomputation,
                        # so the erased checks are the schema's token first
                        "clock_check_schema_invalid",
                    ),
                    "%s must name the clock check's own refusal: %r"
                    % (name, verdict),
                )

    def test_the_round6_mutations_on_a_fresh_capture_are_refused(self):
        """Round 6 (R5-3/R5-4) against the producer's own fresh output: the
        invariants this round pins -- a baseline frame plus the anchor
        frame, the check's frames within the run's own count, the probe a
        square at the corner sized by the run's own dpr -- hold on the real
        capture, and breaking each one is refused."""
        record = self.capture()
        validator = _load_validator()
        cc = record["clock_check"]
        # the invariants themselves, on the producer's own output
        self.assertGreaterEqual(
            cc["frames_total"],
            validator.ANCHOR_MIN_FRAMES,
            "a run that found an anchor has a baseline frame and an anchor "
            "frame: %r" % (cc["frames_total"],),
        )
        self.assertLessEqual(
            cc["frames_total"],
            record["frames_total"],
            "the recorder only accumulates between the check and the record",
        )
        side = validator._probe_side_px(record["document_region"]["device_pixel_ratio"])
        self.assertEqual(
            cc["anchor_probe_region_px"],
            {"x": validator.PROBE_ORIGIN_X, "y": validator.PROBE_ORIGIN_Y, "width": side, "height": side},
            "the fresh capture's probe is the producer's own geometry",
        )
        mutations = {
            "one_anchor_frame": lambda r: r["clock_check"].__setitem__("frames_total", 1),
            "check_beyond_the_run": lambda r: r["clock_check"].__setitem__(
                "frames_total", r["frames_total"] + 1
            ),
            "probe_off_the_corner": lambda r: r["clock_check"][
                "anchor_probe_region_px"
            ].__setitem__("x", 1),
            "probe_not_square": lambda r: r["clock_check"][
                "anchor_probe_region_px"
            ].__setitem__("width", 800),
            "probe_not_this_dprs_size": lambda r: r["clock_check"][
                "anchor_probe_region_px"
            ].__setitem__("width", side * 2)
            or r["clock_check"]["anchor_probe_region_px"].__setitem__("height", side * 2),
        }
        for name, mutate in mutations.items():
            with self.subTest(case=name):
                mutated = json.loads(json.dumps(record))
                mutate(mutated)
                verdict = validator.validate_witness(mutated)
                self.assertTrue(
                    verdict.get("refused"),
                    "%s on a real record must be refused: %r" % (name, verdict),
                )
                self.assertEqual(
                    verdict.get("reason"),
                    "clock_check_evidence_contradicted",
                    "%s: %r" % (name, verdict),
                )


class WitnessIssue137Round4Tests(unittest.TestCase):
    """Issue #137, round 4 (pi MiniMax-M3's re-review `rereview-b1c-3.md`).

    N1/N2 -- the discriminator is positive. A record IS a frame witness only
    when it carries the producer's markers (``kind: 'frame_witness'``, a
    ``clock_check_source``, or the production nested clock check with its raw
    measurements). A record without them is refused ``not_a_witness_record``
    -- there is no lenient "legacy" branch that can return ok -- and erasing
    the markers of a real record (nine fields, or one at a time) must not
    downgrade it into one. If the old hand-made "legacy simple" shape stays
    parseable at all, its verdict is that same distinct, never-publishable
    refusal.

    N4 -- the schema is closed: an unknown top-level or nested field is
    refused ``witness_schema_invalid``; the allowed key sets are exactly the
    keys the producer emits (asserted against the real capture), and the
    ``clock_skew`` alias slot is not read unless the producer writes it (it
    never does).

    N5 -- a caller-supplied ``bound_ms`` must be a finite positive number and
    a caller-supplied ``skew`` a finite number; anything else is refused
    ``nonfinite_time`` instead of silently disabling the skew gate.
    """

    def load_validator(self):
        return _load_validator()

    def captured(self) -> dict:
        return json.loads(json.dumps(_load_captured_record()))

    @staticmethod
    def hand_made_legacy_record() -> dict:
        """The 13-key shape no producer writes: `witnessFrame()` always emits
        ``kind: 'frame_witness'`` (perf/runner/witness.mjs), so this record
        carries no clock-check evidence, no document region, no arm and no
        pixel totals. The round-3 validator accepted it with ``ok: true`` and
        B3's own decision code published its figures (re-review,
        `publication_repro.py`)."""
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

    #: the producer's markers: the two top-level ones and the seven nested
    #: ones (N2: erasing exactly this set is what used to reach the fallback;
    #: nine fields, not the six the round-3 report claimed).
    TOP_MARKERS = ("kind", "clock_check_source")
    NESTED_MARKERS = (
        "method",
        "page_offset_samples",
        "lag_bound_ms",
        "conversion",
        "change_page_ms",
        "frame_page_ms",
        "frame_lag_ms",
    )

    # -- N1: a record with no markers is not a witness record -------------

    def test_a_hand_made_legacy_record_is_refused_not_a_witness_record(self):
        validator = self.load_validator()
        for name, record in (
            ("the 13-key legacy shape", self.hand_made_legacy_record()),
            (
                "the same, without any clock_check",
                self.hand_made_legacy_record() | {"clock_check": None},
            ),
        ):
            with self.subTest(case=name):
                verdict = validator.validate_witness(record)
                self.assertTrue(
                    verdict.get("refused"),
                    "%s must be refused: %r" % (name, verdict),
                )
                self.assertFalse(verdict.get("ok"))
                self.assertEqual(verdict.get("reason"), "not_a_witness_record")

    def test_the_legacy_clock_shapes_are_refused_not_a_witness_record(self):
        """The shapes the round-3 file pinned as ACCEPTED (the deprecated
        `skew_ms` alias, the `clock_skew` dict): still parseable -- the
        validator returns a verdict, never crashes -- but never `ok`."""
        validator = self.load_validator()
        legacy = self.hand_made_legacy_record()
        shapes = {
            "skew_ms alias": legacy | {"clock_skew_ms": None, "skew_ms": 0.2},
            "clock_skew dict": legacy
            | {"clock_skew_ms": None, "clock_skew": {"skew_ms": 0.2}},
            "empty record": {},
        }
        for name, record in shapes.items():
            with self.subTest(case=name):
                verdict = validator.validate_witness(record)  # parses, no crash
                self.assertTrue(verdict.get("refused"), "%s: %r" % (name, verdict))
                self.assertFalse(verdict.get("ok"))
                self.assertEqual(verdict.get("reason"), "not_a_witness_record")

    # -- N2: erasing markers must not downgrade a real record -------------

    def test_the_nine_field_erasure_is_refused(self):
        """N2's sharp case: the record keeps all eight `checks: true` and
        loses every measurement that would prove them. The round-3 validator
        accepted it because the recomputation returned early once the nested
        method was gone."""
        validator = self.load_validator()
        for name, keep_checks in (("checks erased too", False), ("checks kept", True)):
            with self.subTest(case=name):
                record = self.captured()
                checks = record["clock_check"].get("checks")
                for key in self.TOP_MARKERS:
                    record.pop(key, None)
                for key in self.NESTED_MARKERS:
                    record["clock_check"].pop(key, None)
                if not keep_checks:
                    record["clock_check"].pop("checks", None)
                else:
                    record["clock_check"]["checks"] = checks
                self.assertFalse(
                    validator._is_production_record(record),
                    "the nine-field erasure is the fallback the re-review named",
                )
                verdict = validator.validate_witness(record)
                self.assertTrue(
                    verdict.get("refused"),
                    "a real record whose markers were erased must still be "
                    "refused (%s): %r" % (name, verdict),
                )
                self.assertEqual(verdict.get("reason"), "not_a_witness_record")

    def test_erasing_one_marker_at_a_time_keeps_the_strict_schema(self):
        """Each marker alone leaves the others (probe2 §E): the record stays a
        production record and faces the strict schema, so no partial erasure
        can reach a lenient branch."""
        validator = self.load_validator()
        for key in self.TOP_MARKERS:
            record = self.captured()
            record.pop(key)
            self.assertTrue(
                validator._is_production_record(record),
                "without %s the record still carries the other markers" % (key,),
            )
            verdict = validator.validate_witness(record)
            self.assertTrue(
                verdict.get("refused"),
                "a production record without %s must be refused: %r" % (key, verdict),
            )
            self.assertEqual(verdict.get("reason"), "witness_schema_invalid")
        for key in self.NESTED_MARKERS:
            record = self.captured()
            record["clock_check"].pop(key)
            self.assertTrue(
                validator._is_production_record(record),
                "without clock_check.%s the record still carries the other "
                "markers" % (key,),
            )
            verdict = validator.validate_witness(record)
            self.assertTrue(
                verdict.get("refused"),
                "a production record without clock_check.%s must be refused: %r"
                % (key, verdict),
            )

    def test_a_witnessed_record_must_carry_its_evidence(self):
        """No region (a whole-frame diff, the exact thing #130/W7 forbids),
        no arm (the frame's causality check cannot run), no pixel totals
        (changed=1e9 with ratio 0.01 was accepted): all refused."""
        validator = self.load_validator()
        cases = {}
        no_region = self.captured()
        del no_region["document_region"]
        cases["no document_region"] = no_region
        no_arm = self.captured()
        del no_arm["after_page_ms"]
        cases["no after_page_ms"] = no_arm
        no_total = self.captured()
        del no_total["total_pixels"]
        no_total["changed_pixels"] = 10**9
        cases["no total_pixels, changed=1e9"] = no_total
        for name, record in cases.items():
            with self.subTest(case=name):
                verdict = validator.validate_witness(record)
                self.assertTrue(
                    verdict.get("refused"), "%s must be refused: %r" % (name, verdict)
                )

    def test_the_recorded_checks_must_exist(self):
        """An acceptable check with its `checks` deleted (or replaced by the
        minimal legacy shape) proves nothing."""
        validator = self.load_validator()
        deleted = self.captured()
        del deleted["clock_check"]["checks"]
        minimal = self.captured()
        minimal["clock_check"] = {
            "kind": "clock_skew",
            "acceptable": True,
            "reason": None,
            "page_offset_ms": 0.2,
        }
        for name, record in (
            ("checks deleted", deleted),
            ("the minimal legacy nested check", minimal),
        ):
            with self.subTest(case=name):
                verdict = validator.validate_witness(record)
                self.assertTrue(
                    verdict.get("refused"), "%s must be refused: %r" % (name, verdict)
                )

    def test_the_recomputation_is_not_gated_on_the_method(self):
        """N2: with `clock_check.method` erased and the anchor times lying
        (frame 1000 ms before its own change), the recomputation must still
        run and name the contradiction -- the round-3 code returned early on
        the missing method and let the eight `true` flags through.
        (Round 6: the reason token is the schema's now, because the schema
        runs before the recomputation and the erased method is a
        malformation; what the test protects -- the recomputation runs
        anyway and the lying times are named in errors -- is asserted
        below.)"""
        validator = self.load_validator()
        record = self.captured()
        del record["clock_check"]["method"]
        record["clock_check"]["frame_page_ms"] = 0
        record["clock_check"]["change_page_ms"] = 1000
        record["clock_check"]["frame_lag_ms"] = -1000
        verdict = validator.validate_witness(record)
        self.assertTrue(
            verdict.get("refused"),
            "lying anchor times must be refused with or without the method: %r"
            % (verdict,),
        )
        self.assertEqual(
            verdict.get("reason"),
            "clock_check_schema_invalid",
            "the erased method is a schema malformation the schema names first "
            "(round 6): %r" % (verdict,),
        )
        self.assertTrue(
            any("precedes its own change" in str(e) for e in verdict.get("errors", [])),
            "the recomputation still ran and named the lying anchor times: %r"
            % (verdict.get("errors"),),
        )

    def test_markers_on_a_hand_made_record_do_not_rescue_it(self):
        """The re-review's asymmetry, the other way round: putting the two
        top-level markers on the hand-made record makes it a production
        record, and the strict schema then refuses it for the evidence it
        lacks -- it can never pass as a legacy one instead."""
        validator = self.load_validator()
        record = self.hand_made_legacy_record() | {
            "kind": "frame_witness",
            "clock_check_source": "caller",
        }
        verdict = validator.validate_witness(record)
        self.assertTrue(verdict.get("refused"), "%r" % (verdict,))
        self.assertEqual(verdict.get("reason"), "witness_schema_invalid")

    # -- N4: the closed schema --------------------------------------------

    def test_an_unknown_field_is_refused(self):
        validator = self.load_validator()
        top = self.captured()
        top["a_field_the_producer_never_writes"] = 1
        nested = self.captured()
        nested["clock_check"]["also_unknown"] = [1, 2, 3]
        alias = self.captured()
        alias["clock_skew"] = {"skew_ms": 1000.0}
        for name, record in (
            ("unknown top-level field", top),
            ("unknown nested field", nested),
            ("the clock_skew alias slot", alias),
        ):
            with self.subTest(case=name):
                verdict = validator.validate_witness(record)
                self.assertTrue(
                    verdict.get("refused"), "%s must be refused: %r" % (name, verdict)
                )
                self.assertEqual(verdict.get("reason"), "witness_schema_invalid")

    def test_the_clock_skew_alias_slot_is_not_read(self):
        """The producer never writes a top-level `clock_skew` on a frame
        witness record; the reader must not use it as evidence either."""
        validator = self.load_validator()
        record = self.captured() | {"clock_skew": {"skew_ms": 1000.0}}
        self.assertNotEqual(
            validator._skew_of(record),
            1000.0,
            "the alias slot the producer never writes must not be read",
        )

    def test_the_allowed_key_sets_equal_the_producers_emitted_keys(self):
        """The closed schema's allowed sets are exactly the keys the producer
        emits on a real capture -- not a hand-drawn copy of them."""
        validator = self.load_validator()
        record = _load_captured_record()
        self.assertEqual(
            set(record) | {"quiet_window"},
            set(validator._PRODUCTION_ALLOWED_KEYS),
            "the top-level allowed set must equal the capture's keys plus "
            "the optional quiet_window block the r3c07b C07 path emits",
        )
        self.assertEqual(
            set(record["clock_check"]),
            set(validator._CLOCK_CHECK_ALLOWED_KEYS),
            "the nested allowed set must equal the capture's clock_check keys",
        )

    # -- N5: the caller's own arguments -----------------------------------

    def test_a_nonfinite_or_nonpositive_bound_argument_is_refused(self):
        """A NaN or infinite bound makes every comparison false (a dead
        gate); a non-positive one gates nothing. Both are refused instead of
        silently disabling the skew check."""
        validator = self.load_validator()
        record = self.captured()
        for name, bound in (
            ("nan", float("nan")),
            ("inf", float("inf")),
            ("zero", 0.0),
            ("negative", -2.0),
            ("not a number", "2"),
            ("garbage", "garbage"),
            ("a boolean", True),
        ):
            with self.subTest(bound=name):
                verdict = validator.validate_witness(record, bound_ms=bound)
                self.assertTrue(
                    verdict.get("refused"),
                    "bound_ms=%s must be refused, not silently used" % (name,),
                )
                self.assertFalse(verdict.get("ok"))
                self.assertEqual(verdict.get("reason"), "nonfinite_time")
        # the honest bound still works
        self.assertFalse(validator.validate_witness(record, bound_ms=2.0)["refused"])

    def test_a_nonfinite_skew_argument_is_refused(self):
        """A caller that measured NaN must not get a pass: the round-3 code
        silently dropped the argument and used the record's own offset."""
        validator = self.load_validator()
        record = self.captured()
        for name, skew in (("nan", float("nan")), ("inf", float("inf"))):
            with self.subTest(skew=name):
                verdict = validator.validate_witness(record, skew=skew)
                self.assertTrue(
                    verdict.get("refused"),
                    "skew=%s must be refused, never fallen back from" % (name,),
                )
                self.assertEqual(verdict.get("reason"), "nonfinite_time")
        # a finite explicit skew still overrides the record's own
        verdict = validator.validate_witness(record, skew=0.3)
        self.assertFalse(verdict.get("refused"))
        self.assertEqual(verdict.get("skew_ms"), 0.3)


class WitnessIssue137Round5Tests(unittest.TestCase):
    """Issue #137, round 5 (codex's re-review `rereview-b1c-4.md`).

    N4 -- the schema is closed RECURSIVELY: every object the producer emits
    (the document region and its two rects, the nested check's recorded
    checks, its anchor probe region, its conversion statement) carries an
    allowed-key set derived from the real capture; an unknown key at any
    object path is refused ``witness_schema_invalid``. Round 4 closed only
    the first two levels.

    R4-1 -- no input can make validation raise: numbers outside the float
    domain the producer writes (``10**400``), and arithmetic that overflows
    it (a CSS rect at a ``1e308`` dpr), are refused with a named reason
    instead of aborting; the CLI always prints a JSON verdict, never a
    traceback.

    R4-2 -- the anchor evidence must be consistent with how ``witness.mjs``
    finds an anchor: a claimed anchor needs the recorder's frames (the
    check's ``frames_total >= 1``), the record's ``frames_ack_skipped`` is a
    subset of its ``frames_total``, and the anchor's own diff ratio is at
    the producer's threshold (1e-5) and its pixel floor (4 changed pixels
    in the probe region), both tolerant of the six-decimal rounding. The
    re-review's zero-anchor record reached B3's accepted sample output; it
    must be refused before that.
    """

    def load_validator(self):
        return _load_validator()

    def captured(self) -> dict:
        return json.loads(json.dumps(_load_captured_record()))

    @staticmethod
    def _object_paths(value, path=()):
        """Every ``(path, object)`` of a record's object tree, recursively --
        the same walk the re-review's `adversarial.py` used to place an
        unknown key at every object path of the capture."""
        if isinstance(value, dict):
            yield path, value
            for key, item in value.items():
                yield from WitnessIssue137Round5Tests._object_paths(item, path + (key,))

    def _at(self, record, path):
        for key in path:
            record = record[key]
        return record

    # -- N4: the schema is closed recursively ------------------------------

    def test_an_unknown_key_is_refused_at_every_object_path(self):
        """The generated closure test: the capture's object tree is walked,
        an unknown key is added at every object path, and every one of those
        records is refused `witness_schema_invalid`. Round 4 left six of
        these paths open (document_region and its rects, checks, the probe
        region, conversion)."""
        validator = self.load_validator()
        fixture = self.captured()
        paths = list(self._object_paths(fixture))
        self.assertGreaterEqual(
            len(paths), 8, "the walk must cover the nested objects: %r" % ([".".join(p) for p, _ in paths],)
        )
        for path, _obj in paths:
            with self.subTest(object_path=".".join(path) or "<root>"):
                mutated = self.captured()
                self._at(mutated, path)["unknown_field"] = 1
                verdict = validator.validate_witness(mutated)
                self.assertTrue(
                    verdict.get("refused"),
                    "an unknown key at %r must be refused: %r"
                    % (".".join(path) or "<root>", verdict),
                )
                self.assertEqual(
                    verdict.get("reason"),
                    "witness_schema_invalid",
                    "the closed schema names the unknown key at %r: %r"
                    % (".".join(path) or "<root>", verdict),
                )

    def test_the_nested_allowed_key_sets_equal_the_capture(self):
        """Every nested allowed set is derived from the real capture, not
        hand-drawn: each equals the keys the producer emits at that path."""
        validator = self.load_validator()
        record = _load_captured_record()
        for path, allowed in (
            ("document_region", validator._DOCUMENT_REGION_ALLOWED_KEYS),
            ("document_region.rect_css_px", validator._RECT_ALLOWED_KEYS),
            ("document_region.rect_device_px", validator._RECT_ALLOWED_KEYS),
            ("clock_check.checks", validator._CHECKS_ALLOWED_KEYS),
            ("clock_check.anchor_probe_region_px", validator._PROBE_REGION_ALLOWED_KEYS),
            ("clock_check.conversion", validator._CONVERSION_ALLOWED_KEYS),
        ):
            with self.subTest(object_path=path):
                self.assertEqual(
                    set(self._at(record, tuple(path.split(".")))),
                    set(allowed),
                    "the allowed set at %s must equal the capture's keys" % (path,),
                )

    # -- R4-1: no input can raise -----------------------------------------

    def test_numbers_outside_the_float_domain_are_refused_not_raises(self):
        """The re-review's overflow counterexamples: `10**400` is valid JSON
        and `1e308` a finite float, and both aborted validation with
        OverflowError. Each must get a named refusal instead."""
        validator = self.load_validator()
        for name, mutate, reason in (
            (
                "the css rect times a 1e308 dpr overflows the recomputation",
                lambda r: r["document_region"].__setitem__("device_pixel_ratio", 1e308),
                "witness_schema_invalid",
            ),
            (
                "a frame time outside the float domain",
                lambda r: r.__setitem__("frame_page_ms", 10**400),
                "witness_schema_invalid",
            ),
        ):
            with self.subTest(case=name):
                record = self.captured()
                mutate(record)
                verdict = validator.validate_witness(record)  # must not raise
                self.assertTrue(verdict.get("refused"), "%s must be refused: %r" % (name, verdict))
                self.assertEqual(verdict.get("reason"), reason, "%s: %r" % (name, verdict))

    def test_huge_caller_arguments_are_refused_nonfinite_time(self):
        """A bound or skew too large for the float domain is outside every
        bound the producer ever wrote; the N5 refusal must name it, not
        crash on the conversion."""
        validator = self.load_validator()
        record = self.captured()
        for name, kwargs in (
            ("bound 10**400", {"bound_ms": 10**400}),
            ("skew 10**400", {"skew": 10**400}),
        ):
            with self.subTest(argument=name):
                verdict = validator.validate_witness(record, **kwargs)  # must not raise
                self.assertTrue(verdict.get("refused"), "%s must be refused" % (name,))
                self.assertEqual(verdict.get("reason"), "nonfinite_time")

    def test_no_numeric_leaf_anywhere_can_crash_validation(self):
        """The generated numeric sweep: every numeric leaf of the capture
        (and of its sample lists) is replaced with `1e308` and `10**400`;
        validation must always return a verdict object, never raise. The
        re-review's exhaustive probe crashed on several of these."""
        validator = self.load_validator()
        fixture = self.captured()
        seen = 0
        for path, obj in self._object_paths(fixture):
            for key, value in list(obj.items()):
                slots = []
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    slots.append(None)  # the leaf itself
                elif isinstance(value, list):
                    slots.extend(
                        index
                        for index, item in enumerate(value)
                        if isinstance(item, (int, float)) and not isinstance(item, bool)
                    )
                for slot in slots:
                    for name, bad_value in (("1e308", 1e308), ("10**400", 10**400)):
                        with self.subTest(
                            field=".".join(path + (key,))
                            + ("[]" if slot is not None else ""),
                            value=name,
                        ):
                            seen += 1
                            mutated = self.captured()
                            target = self._at(mutated, path)
                            if slot is None:
                                target[key] = bad_value
                            else:
                                target[key][slot] = bad_value
                            verdict = validator.validate_witness(mutated)
                            self.assertIsInstance(verdict, dict)
                            self.assertIn("ok", verdict)
                            self.assertIn("refused", verdict)
        self.assertGreaterEqual(seen, 100, "the sweep must be generated over the record")

    def test_the_cli_prints_a_json_verdict_for_an_overflowing_record(self):
        """The CLI is the publication gate: for the huge-int record that
        crashed it (a traceback, no verdict on stdout), it must print one
        JSON refusal and exit 1, and a subprocess run must show no
        traceback on stderr."""
        validator = self.load_validator()
        record = self.captured()
        record["frame_page_ms"] = 10**400
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "huge.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = validator.main(["--file", str(path)])
            self.assertEqual(code, 1)
            verdict = json.loads(out.getvalue().strip())
            self.assertTrue(verdict["refused"])
            self.assertFalse(verdict["ok"])
            self.assertTrue(verdict["reason"], "the refusal must be named")
            proc = subprocess.run(
                [sys.executable, "-I", str(WITNESS_PY), "--file", str(path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertNotIn("Traceback", proc.stderr)
            parsed = json.loads(proc.stdout)
            self.assertTrue(parsed["refused"])

    # -- R4-2: anchor evidence consistency --------------------------------

    def test_impossible_anchor_evidence_is_refused(self):
        """The re-review's three mutations, each independently accepted by
        the round-4 validator and each impossible for the producer: an
        anchor with no recorder frames, more skipped ACKs than frames, and
        an anchor ratio below the producer's own threshold."""
        validator = self.load_validator()

        def case(name, mutate, reason):
            record = self.captured()
            mutate(record)
            verdict = validator.validate_witness(record)
            self.assertTrue(
                verdict.get("refused"), "%s must be refused: %r" % (name, verdict)
            )
            self.assertEqual(verdict.get("reason"), reason, "%s: %r" % (name, verdict))

        case(
            "zero anchor frames",
            lambda r: r["clock_check"].__setitem__("frames_total", 0),
            "clock_check_evidence_contradicted",
        )
        case(
            "impossible ack count",
            lambda r: r.__setitem__("frames_ack_skipped", r["frames_total"] + 1),
            "witness_schema_invalid",
        )
        case(
            "anchor ratio below the producer threshold",
            lambda r: r["clock_check"].__setitem__("anchor_diff_ratio", 1e-12),
            "clock_check_evidence_contradicted",
        )

    def test_the_anchor_pixel_floor_is_rounding_tolerant(self):
        """The floor is the producer's, not a tighter one: an anchor that
        changed exactly the floor's pixels (4 in the 8x8 probe at dpr 1,
        4 in a 16x16 probe at dpr 2) validates; one changed-pixel-equivalent
        below it is refused. The six-decimal rounding of the recorded ratio
        must not refuse the floor-edge anchor.

        (Round 6 corrected this test's premise: a 16x16 probe is the
        producer's only at dpr 2 -- its side is max(1, round(8*dpr)) at the
        record's own device_pixel_ratio -- so the dpr-2 case now also sets
        the record's dpr and the device rect the producer would derive
        from it, instead of asking for a probe no dpr of the record
        produces.)"""
        validator = self.load_validator()
        for dpr, edge in ((1, 4 / 64), (2, 4 / 256)):
            with self.subTest(dpr=dpr):
                at_floor = self.captured()
                if at_floor["document_region"]["device_pixel_ratio"] != dpr:
                    region = at_floor["document_region"]
                    css = region["rect_css_px"]
                    device = {
                        key: int(float(css[key]) * dpr + 0.5)
                        for key in ("x", "y", "width", "height")
                    }
                    at_floor["document_region"] = (
                        region
                        | {"device_pixel_ratio": dpr, "rect_device_px": device}
                    )
                    at_floor["region_pixels"] = device["width"] * device["height"]
                at_floor["clock_check"]["anchor_diff_ratio"] = edge
                at_floor["clock_check"]["anchor_probe_region_px"] = {
                    "x": 0,
                    "y": 0,
                    "width": 8 * dpr,
                    "height": 8 * dpr,
                }
                verdict = validator.validate_witness(at_floor)
                self.assertFalse(
                    verdict.get("refused"),
                    "an anchor at exactly the floor must validate (dpr %s): %r"
                    % (dpr, verdict),
                )
                below = json.loads(json.dumps(at_floor))
                below["clock_check"]["anchor_diff_ratio"] = edge - 1e-3
                verdict = validator.validate_witness(below)
                self.assertTrue(
                    verdict.get("refused"),
                    "an anchor below the floor must be refused (dpr %s): %r"
                    % (dpr, verdict),
                )
                self.assertEqual(verdict.get("reason"), "clock_check_evidence_contradicted")

    def test_the_zero_anchor_record_cannot_be_a_published_sample(self):
        """The publication gate is `validate_witness`'s ok: B3's
        `_require_witness` refuses exactly on `not verdict['ok']` (the
        re-review drove the zero-anchor record through B3's C11/C12 and got
        accepted samples). The zero-anchor record's verdict must never be
        ok, whatever else it claims."""
        validator = self.load_validator()
        record = self.captured()
        record["clock_check"]["frames_total"] = 0
        verdict = validator.validate_witness(record)
        self.assertIsNotNone(verdict.get("ok"))
        self.assertFalse(verdict["ok"], "the zero-anchor record must not be ok: %r" % (verdict,))
        self.assertTrue(verdict["refused"])


class WitnessIssue137Round6Tests(unittest.TestCase):
    """Issue #137, round 6 (codex's re-review `rereview-b1c-5.md`).

    R5-1 -- no input can raise, take two: the nested schema runs BEFORE any
    helper reads the check's values, and the sample statistics are total
    over every JSON value. A malformed ``page_offset_samples`` element
    (``[null]`` crashed ``_median`` with a TypeError before the schema ran)
    is a named ``clock_check_schema_invalid`` refusal, and a property sweep
    feeds every leaf of a real capture with null, a string, a list, a dict,
    a bool, NaN and ``10**400`` -- every cell must return a verdict, and
    the CLI must print exactly one JSON verdict for every one of them.

    R5-2 -- the CLI's read failures keep the same JSON-verdict contract: a
    garbage, empty, truncated, non-UTF-8 or ``NaN`` file (or a directory)
    gets a named ``record_unreadable`` verdict on stdout; the exit stays 2,
    but stdout is never empty again.

    R5-3 -- an anchor needs the recorder evidence the producer needs to
    find one: `anchorFrame()` keeps a pre-change baseline frame (index
    ``before - 1``) and searches only later frames (from ``before``), so a
    claimed anchor on fewer than two recorder frames -- one frame is as
    impossible as zero was -- is a contradiction, and so is a check whose
    ``frames_total`` exceeds the record's own (the anchor is one of this
    run's frames; the recorder only accumulates).

    R5-4 -- the anchor probe is the producer's own geometry: a square at
    the frame's top-left corner, ``max(1, round(8 * dpr))`` to a side at
    the record's own device pixel ratio, and its area is recomputed from
    that geometry -- never taken from the record -- before the producer's
    four-changed-pixel floor is applied to it. An 800x8 "probe" cannot
    weaken the floor, and a probe away from the corner or off the
    producer's size rule is not one the producer emits.
    """

    #: every JSON value a leaf can be corrupted with (NaN is not JSON, but
    #: the direct API receives Python objects, and the CLI's reader refuses
    #: the ``NaN`` token the stdlib serializer would write for it).
    BAD_VALUES = (
        ("null", None),
        ("string", "bad"),
        ("list", []),
        ("dict", {}),
        ("list-of-string", ["bad"]),
        ("bool-true", True),
        ("bool-false", False),
        ("nan", float("nan")),
        ("huge-int", 10**400),
    )

    def load_validator(self):
        return _load_validator()

    def captured(self) -> dict:
        return json.loads(json.dumps(_load_captured_record()))

    def validated(self, validator, record):
        """The verdict, or a failure naming the exception no input may raise."""
        try:
            return validator.validate_witness(record)
        except Exception as error:  # noqa: BLE001 -- the point of R5-1
            self.fail(
                "validate_witness raised %s: %s (no input may make it raise)"
                % (type(error).__name__, error)
            )

    @staticmethod
    def _leaf_slots(value, path=()):
        """Every assignment slot of a record's tree, recursively: one
        ``(path, container, key)`` per object field and per list element.
        The re-review's type sweep corrupts exactly these."""
        if isinstance(value, dict):
            for key, item in value.items():
                yield path + (key,), value, key
                yield from WitnessIssue137Round6Tests._leaf_slots(item, path + (key,))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield path + (index,), value, index
                yield from WitnessIssue137Round6Tests._leaf_slots(item, path + (index,))

    def _set(self, record, path, value):
        container = record
        for key in path[:-1]:
            container = container[key]
        container[path[-1]] = value

    # -- R5-1: no input can raise -----------------------------------------

    def test_malformed_page_offset_samples_are_a_named_schema_refusal(self):
        """The re-review's own counterexample -- ``page_offset_samples`` =
        ``[null]`` on an otherwise fresh capture crashed ``_median`` with a
        TypeError (the recomputation read the samples before the nested
        schema checked them), and its sweep found ValueError/TypeError for
        strings, objects, lists and bools at every sample index. Each must
        be the schema's own refusal."""
        validator = self.load_validator()
        fixture = self.captured()
        samples = fixture["clock_check"]["page_offset_samples"]
        self.assertGreaterEqual(
            len(samples), 3, "the fixture carries the producer's own samples"
        )
        bad_lists = [
            [None],
            ["bad"],
            [{}],
            [[]],
            [["bad"]],
            [True],
            [10**400],
            [float("nan")],
            "bad",
            {},
            None,
            3,
        ]
        bad_lists += [
            [None if index == slot else sample for index, sample in enumerate(samples)]
            for slot in range(len(samples))
        ]
        for bad in bad_lists:
            with self.subTest(samples=repr(bad)[:70]):
                record = self.captured()
                record["clock_check"]["page_offset_samples"] = bad
                verdict = self.validated(validator, record)
                self.assertTrue(
                    verdict.get("refused"),
                    "malformed samples must be refused: %r" % (verdict,),
                )
                self.assertFalse(verdict.get("ok"))
                self.assertEqual(
                    verdict.get("reason"),
                    "clock_check_schema_invalid",
                    "a sample the producer would not write is the schema's "
                    "refusal, named before any recomputation: %r" % (verdict,),
                )

    def test_no_json_value_at_any_leaf_can_make_validation_raise(self):
        """The property the round-5 report overclaimed: EVERY leaf of a real
        capture (object fields and list elements, at every nesting level)
        fed with null, a string, a list, a dict, a bool, NaN and 10**400
        returns a verdict object -- never an exception."""
        validator = self.load_validator()
        fixture = self.captured()
        slots = list(self._leaf_slots(fixture))
        self.assertGreaterEqual(
            len(slots), 60, "the sweep must be generated over the record's leaves"
        )
        seen = 0
        for path, _container, _key in slots:
            for name, value in self.BAD_VALUES:
                with self.subTest(leaf=".".join(map(str, path)), value=name):
                    seen += 1
                    mutated = self.captured()
                    self._set(mutated, path, value)
                    verdict = self.validated(validator, mutated)
                    self.assertIsInstance(verdict, dict)
                    self.assertIn("ok", verdict)
                    self.assertIn("refused", verdict)
        self.assertGreaterEqual(seen, 500, "the sweep must cover every leaf")

    def test_the_cli_prints_one_json_verdict_for_every_mutated_record(self):
        """The same sweep through the CLI: each mutated capture goes to a
        file (NaN serializes as the bare token the reader refuses), and
        stdout must be exactly one JSON verdict -- a refusal for the
        malformed file, a verdict for the record, never silence."""
        validator = self.load_validator()
        fixture = self.captured()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "record.json"
            for path_slots, _container, _key in self._leaf_slots(fixture):
                for name, value in self.BAD_VALUES:
                    with self.subTest(
                        leaf=".".join(map(str, path_slots)), value=name
                    ):
                        mutated = self.captured()
                        self._set(mutated, path_slots, value)
                        path.write_text(json.dumps(mutated), encoding="utf-8")
                        out = io.StringIO()
                        with contextlib.redirect_stdout(out):
                            code = validator.main(["--file", str(path)])
                        self.assertIn(code, (0, 1, 2))
                        printed = out.getvalue().strip()
                        self.assertTrue(printed, "the CLI never prints nothing")
                        verdict = json.loads(printed)
                        self.assertIsInstance(verdict["ok"], bool)
                        self.assertIsInstance(verdict["refused"], bool)

    # -- R5-2: the CLI's read failures print their verdict ----------------

    def test_the_cli_prints_a_json_verdict_for_files_it_cannot_read(self):
        """Garbage, an empty file, a truncated object, non-UTF-8 bytes, a
        bare NaN and a directory: exit stays 2, and stdout carries a named
        ``record_unreadable`` refusal (round 5 left it empty, losing the
        verdict consumers were promised)."""
        validator = self.load_validator()
        files = {
            "garbage": b"not json",
            "empty": b"",
            "truncated": b"{",
            "invalid utf-8": b"\xff\xfe\x00",
            "a bare NaN": b"NaN",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, data in files.items():
                with self.subTest(file=name):
                    path = root / (name.replace(" ", "_") + ".json")
                    path.write_bytes(data)
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        code = validator.main(["--file", str(path)])
                    self.assertEqual(code, 2, "%s is not a readable record" % (name,))
                    verdict = json.loads(out.getvalue().strip())
                    self.assertFalse(verdict["ok"])
                    self.assertTrue(verdict["refused"])
                    self.assertEqual(
                        verdict.get("reason"),
                        "record_unreadable",
                        "the read refusal is named: %r" % (verdict,),
                    )
            with self.subTest(file="a directory"):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = validator.main(["--file", str(root)])
                self.assertEqual(code, 2)
                self.assertEqual(
                    json.loads(out.getvalue().strip()).get("reason"),
                    "record_unreadable",
                )
            # a real subprocess run: no traceback, one JSON verdict
            garbage = root / "garbage.json"
            proc = subprocess.run(
                [sys.executable, "-I", str(WITNESS_PY), "--file", str(garbage)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertTrue(json.loads(proc.stdout)["refused"])

    # -- R5-3: the recorder evidence an anchor needs ----------------------

    def test_an_anchor_needs_its_baseline_frame_and_its_own(self):
        """`anchorFrame()` keeps a baseline from before the change and
        searches only later frames, so a found anchor means at least two
        recorder frames; and both frame counts the record carries count the
        same run's recorder, which only accumulates. The re-review's
        one-frame record (and a check claiming more frames than the run
        recorded) sailed through to B3's published samples."""
        validator = self.load_validator()

        def refused(name, mutate):
            record = self.captured()
            mutate(record)
            verdict = self.validated(validator, record)
            self.assertFalse(
                verdict.get("ok"), "%s must not be publishable: %r" % (name, verdict)
            )
            self.assertTrue(verdict.get("refused"), "%s: %r" % (name, verdict))
            self.assertEqual(
                verdict.get("reason"),
                "clock_check_evidence_contradicted",
                "%s: %r" % (name, verdict),
            )

        refused(
            "one frame cannot hold a baseline and an anchor",
            lambda r: r["clock_check"].__setitem__("frames_total", 1),
        )
        refused(
            "zero frames (round 5's case, kept)",
            lambda r: r["clock_check"].__setitem__("frames_total", 0),
        )
        refused(
            "the check counts more frames than the run recorded",
            lambda r: r["clock_check"].__setitem__("frames_total", r["frames_total"] + 1),
        )

    # -- R5-4: the probe geometry is the producer's -----------------------

    def test_the_anchor_probe_is_the_producers_geometry(self):
        """The producer emits exactly one probe: a square at the frame's
        top-left corner whose side is max(1, round(8*dpr)) at the same dpr
        the document region records. Nothing else may carry the pixel
        floor: not a shifted origin, not a rectangle, not a square of a
        size no dpr of this record produces."""
        validator = self.load_validator()
        for name, probe in (
            ("a negative x", {"x": -1, "y": 0, "width": 8, "height": 8}),
            ("a negative y", {"x": 0, "y": -1, "width": 8, "height": 8}),
            ("off the corner", {"x": 5, "y": 7, "width": 8, "height": 8}),
            ("not square", {"x": 0, "y": 0, "width": 800, "height": 8}),
            ("not square the other way", {"x": 0, "y": 0, "width": 8, "height": 800}),
            ("square but not this dpr's size", {"x": 0, "y": 0, "width": 16, "height": 16}),
        ):
            with self.subTest(probe=name):
                record = self.captured()
                record["clock_check"]["anchor_probe_region_px"] = probe
                verdict = self.validated(validator, record)
                self.assertTrue(
                    verdict.get("refused"), "%s: %r" % (name, verdict)
                )
                self.assertEqual(
                    verdict.get("reason"),
                    "clock_check_evidence_contradicted",
                    "%s: %r" % (name, verdict),
                )

    def test_an_impossible_probe_cannot_weaken_the_pixel_floor(self):
        """The re-review's floor bypass, exactly: ``anchor_diff_ratio``
        0.001 is refused over the producer's 8x8 probe, and merely widening
        the probe to 800 px made the round-5 validator accept it (the
        inflated area turned 0.064 changed pixels into 6.4). The floor is
        applied to the area the producer's geometry gives, recomputed."""
        validator = self.load_validator()
        honest = self.captured()
        honest["clock_check"]["anchor_diff_ratio"] = 0.001
        verdict = self.validated(validator, honest)
        self.assertTrue(
            verdict.get("refused"),
            "0.001 over the producer's 8x8 probe is under the floor: %r"
            % (verdict,),
        )
        inflated = self.captured()
        inflated["clock_check"]["anchor_diff_ratio"] = 0.001
        inflated["clock_check"]["anchor_probe_region_px"]["width"] = 800
        verdict = self.validated(validator, inflated)
        self.assertFalse(
            verdict.get("ok"),
            "an 800x8 probe is not one the producer emits; it cannot weaken "
            "the floor: %r" % (verdict,),
        )
        self.assertTrue(verdict.get("refused"))
        self.assertEqual(verdict.get("reason"), "clock_check_evidence_contradicted")
        # the producer's own probe still carries the floor's edge (round 5)
        at_floor = self.captured()
        at_floor["clock_check"]["anchor_diff_ratio"] = 4 / 64
        self.assertFalse(self.validated(validator, at_floor).get("refused"))

    # -- the drift guard: the constants come from the producer ------------

    def test_the_validator_constants_are_derived_from_witness_mjs(self):
        """Every constant the validator recomputes with is parsed out of
        `witness.mjs` itself -- the bounds and floors, the anchor probe's
        geometry, and the baseline-plus-anchor minimum -- so the validator
        cannot drift from the producer it checks."""
        validator = self.load_validator()
        source = WITNESS_MJS.read_text(encoding="utf-8")

        def producer_constant(name):
            match = re.search(r"export const %s = (-?[0-9.]+);" % (name,), source)
            self.assertIsNotNone(
                match, "witness.mjs must still export %s" % (name,)
            )
            return float(match.group(1))

        for validator_name, producer_name in (
            ("CAUSALITY_SLOP_MS", "CAUSALITY_SLOP_MS"),
            ("PAGE_OFFSET_SPREAD_BOUND_MS", "PAGE_OFFSET_SPREAD_BOUND_MS"),
            ("LAG_BOUND_INTERVALS", "ANCHOR_LAG_BOUND_INTERVALS"),
            ("LAG_BOUND_MIN_MS", "ANCHOR_LAG_BOUND_MIN_MS"),
            ("PRODUCER_MIN_WINDOW_MS", "DEFAULT_WINDOW_MS"),
            ("ANCHOR_DIFF_THRESHOLD", "DEFAULT_THRESHOLD"),
            ("ANCHOR_MIN_PIXELS", "DEFAULT_MIN_PIXELS"),
        ):
            with self.subTest(constant=validator_name):
                self.assertEqual(
                    getattr(validator, validator_name),
                    producer_constant(producer_name),
                    "the validator's %s must be the producer's %s"
                    % (validator_name, producer_name),
                )

        # the anchor probe: a square at the frame's top-left corner, its
        # side max(1, round(PROBE_CSS_PX * dpr)) -- the same expression for
        # width and height (the backreference), the same dpr reading the
        # document region records.
        probe = re.search(
            r"const probeRegion = \{\s*x: (\d+),\s*y: (\d+),\s*"
            r"width: Math\.max\(1, Math\.round\((\d+(?:\.\d+)?) \* dpr\)\),\s*"
            r"height: Math\.max\(1, Math\.round\(\3 \* dpr\)\),\s*\};",
            source,
        )
        self.assertIsNotNone(
            probe, "witness.mjs must keep emitting the anchor's probe region"
        )
        self.assertEqual(
            int(probe.group(1)),
            validator.PROBE_ORIGIN_X,
            "the producer's probe sits at x=0",
        )
        self.assertEqual(int(probe.group(2)), validator.PROBE_ORIGIN_Y)
        self.assertEqual(
            float(probe.group(3)),
            validator.PROBE_CSS_PX,
            "the producer's probe is 8 CSS px to a side",
        )

        # the anchor's own acceptance, in the producer's own code: strictly
        # above the threshold, at least the floor's changed pixels.
        self.assertIsNotNone(
            re.search(
                r"diff\.ratio > DEFAULT_THRESHOLD && diff\.changed >= DEFAULT_MIN_PIXELS",
                source,
            ),
            "the producer's anchor acceptance keeps its threshold and floor",
        )

        # an anchor needs a baseline frame before the change plus a frame
        # after it: the producer keeps the baseline at `before - 1`, gives
        # up without one, and searches only frames from `before` -- so no
        # recorder with fewer than two frames can yield an anchor.
        for pattern in (
            r"const baselineFrame = recorder\.frames\[before - 1\] \|\| null;",
            r"if \(!baselineDecoded \|\| !baselineFrame\) break;",
            r"for \(let i = before; i < recorder\.frames\.length; i\+\+\)",
        ):
            self.assertIsNotNone(
                re.search(pattern, source),
                "the producer's anchor search must keep %r" % (pattern,),
            )
        self.assertEqual(
            validator.ANCHOR_MIN_FRAMES,
            2,
            "a baseline plus the anchor frame is the producer's minimum",
        )

        # the three frame counts the validator relates count the same
        # recorder: the check's at its instant, the quiet refusal's record,
        # and the measured record's at the end.
        self.assertEqual(
            len(re.findall(r"frames_total: recorder\.frames\.length", source)),
            3,
            "the check and the records count the same recorder's frames",
        )
        self.assertGreaterEqual(
            source.count("window.devicePixelRatio || 1"),
            2,
            "the probe and the document region read the same dpr",
        )


class WitnessIssue137Round7Tests(unittest.TestCase):
    """Issue #137, round 7 (codex's re-review `rereview-b1c-6.md`: R6-1).

    The direct API's totality claim, finished. Round 6 closed the values
    the recomputation reads; the *diagnostics* still formatted them:
    ``%r``/``%d``/``%s`` of a 5,001-digit integer raises ``ValueError`` at
    the interpreter's 4,300-digit conversion limit, so the refusal itself
    crashed -- on 105 of the re-review's 110 substitution paths, in the
    schema's own messages, and in the caller-argument refusals (a
    ``bound_ms`` of ``10**5000``). The CLI was safe only because its JSON
    reader refuses such an integer first; the direct API expressly claims
    totality over parsed Python values.

    R7-1 -- a finite supported numeric domain: every numeric field of the
    record (top level, the nested check, its samples, the probe region,
    the conversion statement, the document region and its rects) accepts
    only finite values with ``|x| <= 1e15`` -- ints and floats; booleans
    are not numbers. Anything outside is the schema's own named refusal
    (``witness_schema_invalid`` / ``clock_check_schema_invalid``) whose
    message carries the token ``value_out_of_range``, checked BEFORE any
    arithmetic or formatting reads the value. This replaces round 6's
    boundary: a huge-but-valid informational number (a 1,000-digit
    ``frames_total`` was accepted with ``ok: true``) now refuses.

    R7-2 -- one bounded, exception-safe describer (``_describe``) builds
    every diagnostic that names a value: the value's type plus at most 64
    characters, never ``str()``/``repr()``/``%d`` of an unbounded value,
    and an integer outside the domain is shown only as ``<int, N bits>``.
    The interpreter's protective conversion limit is never touched, and
    the describer is total over any Python object (the direct API accepts
    any mapping, so keys and values need not be JSON at all).
    """

    #: values outside the supported numeric domain, at numeric leaves
    OUT_OF_DOMAIN = (
        ("1e16", 1e16),
        ("-1e16", -1e16),
        ("10**400", 10**400),
        ("float('1e308')", float("1e308")),
    )

    #: every diagnostic is built from fixed text plus descriptions; none
    #: may run past this many characters.
    MESSAGE_LIMIT = 512

    def load_validator(self):
        return _load_validator()

    def captured(self) -> dict:
        return json.loads(json.dumps(_load_captured_record()))

    def validated(self, validator, record, **kwargs):
        """The verdict, or a failure naming the exception no input may raise."""
        try:
            return validator.validate_witness(record, **kwargs)
        except Exception as error:  # noqa: BLE001 -- the point of R6-1
            self.fail(
                "validate_witness raised %s: %s (no input may make it raise)"
                % (type(error).__name__, error)
            )

    @staticmethod
    def _summary(verdict):
        """A bounded description of a verdict for a failure message. Never
        ``repr()`` the verdict itself: it echoes the record, whose values
        are exactly the unbounded ones under test (the R6-1 lesson applies
        to test diagnostics too)."""
        errors = verdict.get("errors") or ["<no error>"]
        return "reason=%r, first error: %s" % (
            verdict.get("reason"),
            str(errors[0])[:160],
        )

    @staticmethod
    def _paths(value, path=()):
        """Every path of a record's tree -- the re-review's walk: the root,
        every object field (recursively) and every array element."""
        yield path
        if isinstance(value, dict):
            for key, item in value.items():
                yield from WitnessIssue137Round7Tests._paths(item, path + (key,))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from WitnessIssue137Round7Tests._paths(item, path + (index,))

    @staticmethod
    def _numeric_slots(value, path=()):
        """Every path a numeric leaf sits at (object fields and array
        elements alike), recursively."""
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, (int, float)) and not isinstance(item, bool):
                    yield path + (key,)
                else:
                    yield from WitnessIssue137Round7Tests._numeric_slots(
                        item, path + (key,)
                    )
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, (int, float)) and not isinstance(item, bool):
                    yield path + (index,)
                else:
                    yield from WitnessIssue137Round7Tests._numeric_slots(
                        item, path + (index,)
                    )

    def _set(self, record, path, value):
        """A copy of the record with ``value`` substituted at ``path``."""
        mutated = self.captured() if record is None else record
        if not path:
            return value
        container = mutated
        for key in path[:-1]:
            container = container[key]
        container[path[-1]] = value
        return mutated

    @staticmethod
    def _area_reason(path):
        """The schema token that owns a path: the nested check has its own."""
        return (
            "clock_check_schema_invalid"
            if path and path[0] == "clock_check"
            else "witness_schema_invalid"
        )

    # -- R6-1: the re-review's 110-path sweep, permanent ------------------

    def test_a_five_thousand_digit_integer_at_every_path_is_refused(self):
        """``10**5000`` substituted at every path of the real capture (the
        root, every object field, every array element, every leaf) raised
        ``ValueError`` on 105 of the re-review's 110 paths -- the refusal
        itself crashed. Every path must return a refused verdict, never an
        exception, with bounded messages."""
        validator = self.load_validator()
        fixture = self.captured()
        paths = list(self._paths(fixture))
        self.assertGreaterEqual(
            len(paths), 100, "the sweep must cover the capture's every path"
        )
        for path in paths:
            with self.subTest(path=".".join(map(str, path)) or "<root>"):
                mutated = self._set(None, path, 10**5000)
                verdict = self.validated(validator, mutated)
                self.assertIsInstance(verdict, dict)
                self.assertIn("ok", verdict)
                self.assertTrue(
                    verdict.get("refused"),
                    "a 5,001-digit integer at %s must be refused (%s)"
                    % (".".join(map(str, path)) or "<root>", self._summary(verdict)),
                )
                self.assertFalse(verdict["ok"])
                for message in verdict.get("errors", []):
                    self.assertLess(
                        len(message),
                        self.MESSAGE_LIMIT,
                        "diagnostics are bounded: %r" % (message[:80],),
                    )

    # -- R7-1: the supported numeric domain --------------------------------

    def test_numeric_leaves_outside_the_domain_refuse_value_out_of_range(self):
        """``1e16``, ``-1e16``, ``10**400`` and ``float('1e308')`` at every
        numeric leaf of the capture: the owning schema's refusal, with the
        ``value_out_of_range`` token in the message, named before any
        formatting shows the value's digits (the passes after the sweep
        stay total; round 8 corrected the stronger wording here)."""
        validator = self.load_validator()
        fixture = self.captured()
        slots = list(self._numeric_slots(fixture))
        self.assertGreaterEqual(
            len(slots), 50, "the sweep must cover every numeric leaf"
        )
        for path in slots:
            for name, value in self.OUT_OF_DOMAIN:
                with self.subTest(leaf=".".join(map(str, path)), value=name):
                    mutated = self._set(None, path, value)
                    verdict = self.validated(validator, mutated)
                    self.assertTrue(
                        verdict.get("refused"),
                        "%s at %s must be refused (%s)"
                        % (name, ".".join(map(str, path)), self._summary(verdict)),
                    )
                    self.assertFalse(verdict["ok"])
                    self.assertEqual(
                        verdict.get("reason"),
                        self._area_reason(path),
                        "the domain is the owning schema's refusal: %s"
                        % (self._summary(verdict),),
                    )
                    self.assertTrue(
                        any(
                            "value_out_of_range" in str(message)
                            for message in verdict.get("errors", [])
                        ),
                        "the refusal names value_out_of_range: %r"
                        % (verdict.get("errors", [])[:3],),
                    )

    def test_the_domain_boundary_is_drawn_at_1e15_and_not_tighter(self):
        """``|x| <= 1e15`` is the domain, inclusive: a count of exactly
        ``10**15`` frames (and an informational ``elapsed_ms`` of ``1e15``)
        is inside it and the record still validates; one frame more is
        ``value_out_of_range``."""
        validator = self.load_validator()
        at_limit = self.captured()
        at_limit["frames_total"] = 10**15
        at_limit["elapsed_ms"] = 1e15
        verdict = self.validated(validator, at_limit)
        self.assertFalse(
            verdict.get("refused"),
            "the boundary itself is in the domain: %r" % (verdict,),
        )
        over = self.captured()
        over["frames_total"] = 10**15 + 1
        verdict = self.validated(validator, over)
        self.assertTrue(verdict.get("refused"))
        self.assertEqual(verdict.get("reason"), "witness_schema_invalid")
        self.assertTrue(
            any(
                "value_out_of_range" in str(message)
                for message in verdict.get("errors", [])
            )
        )

    def test_the_cli_refuses_a_parseable_thousand_digit_count(self):
        """A 4,200-digit ``frames_total`` is legal JSON the reader accepts,
        and the round-6 CLI published it (``ok: true``, exit 0): outside
        the domain it must be a named refusal, and the CLI must still
        print exactly one JSON verdict with no traceback."""
        validator = self.load_validator()
        record = self.captured()
        record["frames_total"] = 10**4200
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "huge-count.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = validator.main(["--file", str(path)])
            self.assertEqual(code, 1)
            verdict = json.loads(out.getvalue().strip())
            self.assertTrue(verdict["refused"])
            self.assertFalse(verdict["ok"])
            self.assertEqual(verdict.get("reason"), "witness_schema_invalid")
            proc = subprocess.run(
                [sys.executable, "-I", str(WITNESS_PY), "--file", str(path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertNotIn("Traceback", proc.stderr)
            parsed = json.loads(proc.stdout)
            self.assertTrue(parsed["refused"])

    # -- R7-2: bounded, exception-safe diagnostics -------------------------

    def test_huge_caller_arguments_are_described_not_formatted(self):
        """The N5 refusals themselves must not crash on the value they
        refuse: a bound or skew of ``10**5000`` is outside every domain,
        and its refusal message describes it (by its bits), never its
        digits."""
        validator = self.load_validator()
        record = self.captured()
        for name, kwargs in (
            ("bound 10**5000", {"bound_ms": 10**5000}),
            ("skew 10**5000", {"skew": 10**5000}),
        ):
            with self.subTest(argument=name):
                verdict = self.validated(validator, record, **kwargs)
                self.assertTrue(verdict.get("refused"))
                self.assertEqual(verdict.get("reason"), "nonfinite_time")
                for message in verdict.get("errors", []):
                    self.assertLess(
                        len(message),
                        self.MESSAGE_LIMIT,
                        "the refusal itself is bounded: %r" % (message[:80],),
                    )

    def test_the_describer_is_bounded_and_exception_safe(self):
        """``_describe``: at most 64 characters, the type named, no digits of
        an out-of-domain integer, total over every Python value -- the
        direct API accepts objects whose repr raises."""
        validator = self.load_validator()
        describe = validator._describe

        class Evil:
            def __repr__(self):
                raise RuntimeError("no diagnostics through me")

        for value in (
            None,
            True,
            False,
            0,
            5,
            -5,
            10**15,
            10**15 + 1,
            -(10**15 + 1),
            10**400,
            10**5000,
            -(10**5000),
            0.0,
            -0.5,
            1e15,
            1e308,
            float("inf"),
            float("-inf"),
            float("nan"),
            "",
            "ok",
            "x" * 10000,
            [],
            {},
            [None] * 100,
            Evil(),
        ):
            with self.subTest(value=type(value).__name__):
                text = describe(value)
                self.assertIsInstance(text, str)
                self.assertLessEqual(
                    len(text), 64, "the description is bounded: %r" % (text,)
                )
        self.assertEqual(
            describe(10**5000),
            "<int, %d bits>" % ((10**5000).bit_length(),),
            "an out-of-domain integer is described by its bits",
        )
        self.assertIn("int", describe(5))
        self.assertIn("str", describe("x" * 10000))

    def test_direct_api_keys_the_producer_never_writes_are_total(self):
        """The direct API accepts any Python mapping: non-string keys (and
        two keys no order shares) are unknown-key evidence to describe, not
        a ``TypeError`` out of ``sorted()`` or ``", ".join()``."""
        validator = self.load_validator()
        # two unknown keys of unorderable types: sorted() used to raise
        mixed = self.captured()
        mixed["zzz"] = 1
        mixed[42] = 2
        verdict = self.validated(validator, mixed)
        self.assertTrue(verdict.get("refused"))
        self.assertEqual(verdict.get("reason"), "witness_schema_invalid")
        # a non-string key among the recorded checks: join() used to raise
        int_key = self.captured()
        int_key["clock_check"]["checks"] = dict(int_key["clock_check"]["checks"])
        int_key["clock_check"]["checks"][42] = False
        verdict = self.validated(validator, int_key)
        self.assertTrue(verdict.get("refused"))
        self.assertIn(
            verdict.get("reason"),
            ("witness_schema_invalid", "clock_check_schema_invalid"),
            "the recursive closure names the unknown key wherever it sits "
            "(the top-level schema runs first): %s" % (self._summary(verdict),),
        )

    # -- the controls round 7 must not move --------------------------------

    def test_the_honest_capture_and_the_floor_edges_still_validate(self):
        """The honest saved capture validates untouched, and so do the
        floor-edge anchors (exactly the producer's 4 changed pixels over
        its 8x8 probe at dpr 1, 4 over 16x16 at dpr 2): the domain and the
        describer refuse nothing the producer writes."""
        validator = self.load_validator()
        verdict = self.validated(validator, self.captured())
        self.assertFalse(
            verdict.get("refused"),
            "the honest capture still validates: %r" % (verdict,),
        )
        self.assertIsNone(verdict.get("reason"))
        for dpr, edge in ((1, 4 / 64), (2, 4 / 256)):
            with self.subTest(dpr=dpr):
                at_floor = self.captured()
                region = at_floor["document_region"]
                if region["device_pixel_ratio"] != dpr:
                    css = region["rect_css_px"]
                    device = {
                        key: int(float(css[key]) * dpr + 0.5)
                        for key in ("x", "y", "width", "height")
                    }
                    at_floor["document_region"] = region | {
                        "device_pixel_ratio": dpr,
                        "rect_device_px": device,
                    }
                    at_floor["region_pixels"] = device["width"] * device["height"]
                at_floor["clock_check"]["anchor_diff_ratio"] = edge
                at_floor["clock_check"]["anchor_probe_region_px"] = {
                    "x": 0,
                    "y": 0,
                    "width": 8 * dpr,
                    "height": 8 * dpr,
                }
                verdict = self.validated(validator, at_floor)
                self.assertFalse(
                    verdict.get("refused"),
                    "a floor-edge anchor still validates (dpr %s): %r"
                    % (dpr, verdict),
                )


class _BadReprInt(int):
    """An int subclass whose every string conversion raises (#137 round 8,
    R7-2): the diagnostics must never run one."""

    def __repr__(self):
        raise RuntimeError("repr must not run")

    def __str__(self):
        raise RuntimeError("str must not run")

    def __format__(self, format_spec):
        raise RuntimeError("format must not run")


class _BadReprFloat(float):
    """A float subclass whose every string conversion raises (R7-2)."""

    def __repr__(self):
        raise RuntimeError("repr must not run")

    def __str__(self):
        raise RuntimeError("str must not run")

    def __format__(self, format_spec):
        raise RuntimeError("format must not run")


class WitnessIssue137Round8Tests(unittest.TestCase):
    """Issue #137, round 8 (codex's re-review `rereview-b1c-7.md`: R7-1
    major, R7-2 minor).

    R7-1 -- an explicitly supplied skew outside the supported numeric
    domain is the caller-argument boundary's own refusal, BEFORE any
    fallback to the record's offset. Round 7's domain filter made
    `_skew_of` discard a finite out-of-domain caller offset and fall
    back to the record's own, so `validate_witness(record, skew=1e16)`
    returned ``ok: true`` on the honest capture (the re-review's probe:
    every value from ``1e15+1`` up was silently replaced; ``1cbaf2a`` had
    refused each of them). The N5 contract is absolute: the caller's
    explicit offset wins, and an unusable one is a refusal that must not
    disappear. ``1e15`` itself stays in the domain, handled by the bound
    as before (``clock_skew_above_bound``).

    R7-2 -- every diagnostic that names an input-derived value goes
    through ``_describe``: round 7 left the lag-bound contradiction
    formatting its ``lag_bound`` raw (``%s``), which raises for an int
    subclass whose repr raises and printed all 309 digits of ``10**308``;
    and the CLI's read/abort helpers formatted their paths and exceptions
    raw too. The whole validator is exercised with repr-raising numbers
    at every numeric path, not only ``_describe(Evil())``.
    """

    #: every diagnostic is built from fixed text plus descriptions; none
    #: may run past this many characters.
    MESSAGE_LIMIT = 512

    def load_validator(self):
        return _load_validator()

    def captured(self) -> dict:
        return json.loads(json.dumps(_load_captured_record()))

    def validated(self, validator, record, **kwargs):
        """The verdict, or a failure naming the exception no input may raise."""
        try:
            return validator.validate_witness(record, **kwargs)
        except Exception as error:  # noqa: BLE001 -- the point of R7-2
            self.fail(
                "validate_witness raised %s: %s (no input may make it raise)"
                % (type(error).__name__, error)
            )

    @staticmethod
    def _summary(verdict):
        """A bounded description of a verdict for a failure message."""
        errors = verdict.get("errors") or ["<no error>"]
        return "reason=%r, first error: %s" % (
            verdict.get("reason"),
            str(errors[0])[:160],
        )

    @staticmethod
    def _numeric_slots(value, path=()):
        """Every path a numeric leaf sits at, recursively."""
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, (int, float)) and not isinstance(item, bool):
                    yield path + (key,)
                else:
                    yield from WitnessIssue137Round8Tests._numeric_slots(
                        item, path + (key,)
                    )
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, (int, float)) and not isinstance(item, bool):
                    yield path + (index,)
                else:
                    yield from WitnessIssue137Round8Tests._numeric_slots(
                        item, path + (index,)
                    )

    def _substitute(self, path, value):
        """A copy of the capture with ``value`` substituted at ``path``."""
        mutated = self.captured()
        container = mutated
        for key in path[:-1]:
            container = container[key]
        container[path[-1]] = value
        return mutated

    # -- R7-1: an explicit out-of-domain skew never falls back ----------

    def test_an_explicit_out_of_domain_skew_is_refused_never_replaced(self):
        """The re-review's values: ``1e15+1`` (float and int), ``1e16``,
        ``-1e16``, ``1e308``, ``inf``, ``nan`` and ``10**5000`` supplied as
        the caller's skew are each a refusal at the caller-argument
        boundary -- never a silent replacement by the record's own offset
        (the honest capture's ``-0.2``), whatever bound the caller also
        supplies."""
        validator = self.load_validator()
        record = self.captured()
        cases = (
            ("1e15+1 (float)", 1e15 + 1),
            ("10**15+1 (int)", 10**15 + 1),
            ("1e16", 1e16),
            ("-1e16", -1e16),
            ("1e308", 1e308),
            ("-1e308", -1e308),
            ("inf", float("inf")),
            ("nan", float("nan")),
            ("10**5000", 10**5000),
        )
        for name, skew in cases:
            with self.subTest(skew=name):
                verdict = self.validated(validator, record, skew=skew)
                self.assertTrue(
                    verdict.get("refused"),
                    "an explicit skew of %s must be refused (%s)"
                    % (name, self._summary(verdict)),
                )
                self.assertFalse(verdict.get("ok"))
                self.assertEqual(
                    verdict.get("reason"),
                    "nonfinite_time",
                    "the caller-argument boundary owns the refusal: %s"
                    % (self._summary(verdict),),
                )
                self.assertIsNone(
                    verdict.get("skew_ms"),
                    "the record's own offset must not stand in for %s" % (name,),
                )
                self.assertFalse(verdict.get("skew_checked"))
                for message in verdict.get("errors", []):
                    self.assertLess(
                        len(message),
                        self.MESSAGE_LIMIT,
                        "the refusal itself is bounded: %r" % (message[:80],),
                    )
        # the refusal is the domain's, not the bound's: a bound wide enough
        # to hold the skew still refuses it
        verdict = self.validated(validator, record, skew=1.5e15, bound_ms=1e16)
        self.assertTrue(
            verdict.get("refused"),
            "an out-of-domain skew refuses even under a wider bound (%s)"
            % (self._summary(verdict),),
        )
        self.assertEqual(verdict.get("reason"), "nonfinite_time")

    def test_an_in_domain_explicit_skew_keeps_the_bound_s_verdict(self):
        """``1e15`` is inside the domain (the boundary is inclusive), so it
        keeps round 7's behaviour: the skew gate refuses it as
        ``clock_skew_above_bound`` with the caller's own value recorded,
        and a usable explicit skew still wins over the record's offset."""
        validator = self.load_validator()
        record = self.captured()
        verdict = self.validated(validator, record, skew=1e15)
        self.assertTrue(verdict.get("refused"))
        self.assertEqual(verdict.get("reason"), "clock_skew_above_bound")
        self.assertEqual(verdict.get("skew_ms"), 1e15)
        self.assertTrue(verdict.get("skew_checked"))
        verdict = self.validated(validator, record, skew=0.3)
        self.assertFalse(verdict.get("refused"))
        self.assertEqual(verdict.get("skew_ms"), 0.3)
        # the helper's own contract: an explicit unusable offset is never
        # silently swapped for the record's (validate_witness refuses it)
        self.assertIsNone(validator._skew_of(record, 1e16))
        self.assertEqual(validator._skew_of(record, 0.3), 0.3)

    # -- R7-2: no diagnostic formats an input-derived value raw ----------

    def test_repr_raising_numbers_at_every_numeric_path_are_total(self):
        """The whole validator, not only ``_describe``: an int/float
        subclass whose ``__repr__``/``__str__``/``__format__`` raise,
        substituted at every numeric leaf of the real capture -- same
        value (the verdict must not move) and the re-review's wrong value
        (101; every message bounded). No path may raise."""
        validator = self.load_validator()
        fixture = self.captured()
        slots = list(self._numeric_slots(fixture))
        self.assertGreaterEqual(
            len(slots), 50, "the sweep must cover every numeric leaf"
        )
        for path in slots:
            where = ".".join(map(str, path))
            original = fixture
            for key in path:
                original = original[key]
            if isinstance(original, int) and not isinstance(original, bool):
                same, wrong = _BadReprInt(original), _BadReprInt(101)
            else:
                same, wrong = _BadReprFloat(float(original)), _BadReprFloat(101.0)
            for name, value in (("same value", same), ("101", wrong)):
                with self.subTest(leaf=where, value=name):
                    verdict = self.validated(
                        validator, self._substitute(path, value)
                    )
                    self.assertIsInstance(verdict, dict)
                    for message in verdict.get("errors", []):
                        self.assertLess(
                            len(message),
                            self.MESSAGE_LIMIT,
                            "diagnostics are bounded at %s (%s): %r"
                            % (where, name, message[:80]),
                        )
                    if name == "same value":
                        self.assertFalse(
                            verdict.get("refused"),
                            "a same-value substitution changes no verdict at "
                            "%s (%s)" % (where, self._summary(verdict)),
                        )

    def test_the_lag_bound_contradiction_describes_its_value(self):
        """R7-2's own repro: ``lag_bound_ms`` set to a repr-raising int
        (in domain, but contradicting the rule's bound) and to ``10**308``
        (out of domain): the contradiction is named, never formatted --
        the re-review measured a ``RuntimeError`` and a 389-character
        diagnostic here."""
        validator = self.load_validator()
        record = self.captured()
        correct = record["clock_check"]["lag_bound_ms"]
        wrong = _BadReprInt(int(correct) + 1000)
        verdict = self.validated(
            validator, self._substitute(("clock_check", "lag_bound_ms"), wrong)
        )
        self.assertTrue(verdict.get("refused"))
        self.assertEqual(
            verdict.get("reason"),
            "clock_check_evidence_contradicted",
            "the wrong (in-domain) bound is the evidence's contradiction: %s"
            % (self._summary(verdict),),
        )
        huge = self._substitute(("clock_check", "lag_bound_ms"), 10**308)
        verdict = self.validated(validator, huge)
        self.assertTrue(verdict.get("refused"))
        for message in verdict.get("errors", []):
            self.assertLess(
                len(message),
                self.MESSAGE_LIMIT,
                "no diagnostic carries 309 digits: %r" % (message[:80],),
            )

    def test_the_cli_abort_and_read_refusals_are_bounded(self):
        """The CLI's own diagnostics (the abort and read helpers, and the
        stderr line) describe their paths and exceptions boundedly: an
        exception whose ``__str__`` raises and a 100,000-character path
        must not make the last-resort printers raise or print unbounded
        text."""
        validator = self.load_validator()

        class EvilError(Exception):
            def __repr__(self):
                raise RuntimeError("repr must not run")

            def __str__(self):
                raise RuntimeError("str must not run")

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            validator._print_validation_aborted(EvilError("boom"))
        verdict = json.loads(out.getvalue().strip())
        self.assertEqual(verdict.get("reason"), "validation_aborted")
        self.assertTrue(verdict.get("refused"))
        for message in verdict.get("errors", []):
            self.assertLess(
                len(message), self.MESSAGE_LIMIT, "bounded: %r" % (message,)
            )

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            validator._print_record_unreadable("z" * 100000, EvilError("boom"))
        verdict = json.loads(out.getvalue().strip())
        self.assertEqual(verdict.get("reason"), "record_unreadable")
        self.assertLess(
            len(out.getvalue()),
            self.MESSAGE_LIMIT,
            "the path is described, never echoed: %d chars"
            % (len(out.getvalue()),),
        )

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = validator.main(["--file", "z" * 100000])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue().strip()).get("reason"), "record_unreadable")
        self.assertLess(len(out.getvalue()), self.MESSAGE_LIMIT)
        self.assertLess(
            len(err.getvalue()),
            self.MESSAGE_LIMIT,
            "the stderr line is bounded too: %d chars" % (len(err.getvalue()),),
        )


if __name__ == "__main__":
    unittest.main()
