"""B5 — the C10 scroll lane (#106).

The defect: the C10 probe published a *measured* scroll latency for hosts
where nothing scrolled (the old probe skipped the scroll and timed two
``requestAnimationFrame`` callbacks anyway), it never looked inside an open
shadow root, and it ran on the 5-paragraph micro fixture.

The claims this file checks, each with its own measurer:

A1  a host whose document fits the viewport is **not** ``measured``: the
    probe says ``not_applicable`` and says why (the fake host ``fits.html``).
A2  a host with prose-50kw is measured, and **every** measured sample names
    the container it scrolled and a ``scrollTop`` delta above 0 (the fake host
    ``prose.html``).
A3  a host whose scroller lives inside an **open shadow root** is found and
    measured, and the shadow host is named (the fake host ``shadow.html``).
A4  every measured sample carries B1c's frame witness, its clock-skew bound
    and the run's clock check (the pixel anchor's evidence).
A5  the container is the scroller that **holds the document's text**: a
    hidden decoy with a huge scroll range and a blinking box outside the
    document must not be measured as the document's scroll (the fake host
    ``decoy.html``).
A6  a document that fits beside a small overflow widget is **not** measured
    (the fake host ``widget.html``).
A7  the caret mask reaches inside the open shadow roots, so a caret blinking
    in a shadow tree is not the witness's frame.
B1  the run records the execution profile that admits prose-50kw and the seed.
B2  the runner writes a ``not_applicable`` trial (never ``measured``) for the
    host whose document fits.
B3  every measured sample of the runner's trial names its container, its
    ``scrollTop`` delta and the movement of the document's content.
B4  a profile that refuses prose-50kw is refused **with a reason**; nothing
    is measured and nothing crashes.
B5  ``--fake-host`` and ``--editor`` are mutually exclusive: a fake host's
    measurement is never filed under an editor's id.
B6  the trial's publishability follows the policy (the profile and the host
    class), never a hardcoded sentence.
C   the pure parts: the profile gate, the environment, the sample verdict and
    the publication flags.

The browser tests drive headless Chromium through node and the Playwright the
harness pins. They skip when node or that browser is missing; they never skip
because the lane is missing, so a missing implementation is a failure and not
a silent pass.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.fixtures.docx_workload import workload_docx  # noqa: E402
from perf.fixtures.profiles import allowed_workloads  # noqa: E402
from perf.runner import adversarial_c10_scroll as scroll  # noqa: E402
from perf.runner.browser_hosts import StaticHost  # noqa: E402

PROBE = REPO / "perf" / "runner" / "adversarial_c10_scroll.mjs"
RUNNER = REPO / "perf" / "runner" / "adversarial_c10_scroll.py"
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts" / "b5_scroll"
TIMEOUT_S = 300

#: The rectangle a fake host's document box occupies.
CONTAINER_RECT = {"x": 0.0, "y": 0.0, "width": 1280.0, "height": 900.0}


def _node() -> str | None:
    return shutil.which("node")


def _playwright_dir() -> Path | None:
    for candidate in (
        REPO / "harness" / "ui" / "plate" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright",
    ):
        if candidate.is_dir():
            return candidate
    return None


def _corpus(tmp: Path) -> Path:
    """The prose-50kw document, written where the probe can read it."""
    built = workload_docx("prose-50kw")
    path = tmp / "prose-50kw.docx"
    path.write_bytes(built["docx"])
    return path


def _witness(**overrides) -> dict:
    """A witness record that B1c's validator accepts (#130's shape)."""
    record = {
        "outcome": "witnessed",
        "frame_page_ms": 100.0,
        "frames_total": 3,
        "frames_after": 1,
        "diff_ratio": 0.1,
        "threshold": 0.00001,
        "min_pixels": 4,
        "changed_pixels": 4000,
        "caret_masked": True,
        "document_scoped": True,
        "document_region": {
            "source": "rect",
            "selector": None,
            "rect_css_px": dict(CONTAINER_RECT),
        },
        "clock_check": {
            "kind": "clock_skew",
            "acceptable": True,
            "reason": None,
            "page_offset_ms": 0.1,
            "bound_ms": 2.0,
        },
    }
    record.update(overrides)
    return record


def _sample(**overrides) -> dict:
    """A probe sample that the lane's verdict must judge on its own."""
    sample = {
        "outcome": "measured",
        "container": {"selector": "#doc", "rect_css_px": dict(CONTAINER_RECT)},
        "scroll_top_delta": 600,
        "content_moved_px": 600,
        "scroll_frame_ms": 12.5,
        "witness": _witness(),
    }
    sample.update(overrides)
    return sample


class _FakeHost:
    """The fake hosts, served by B1's static server."""

    server = None
    corpus = None
    tmp = None

    @classmethod
    def start(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.corpus = _corpus(Path(cls.tmp.name))
        cls.server = StaticHost(
            HOSTS, corpus_route="/corpus.docx", fixture=cls.corpus
        )
        return cls.server.url

    @classmethod
    def stop(cls):
        if cls.server is not None:
            cls.server.stop()
            cls.server = None
        if cls.tmp is not None:
            cls.tmp.cleanup()
            cls.tmp = None


class ScrollProbeTests(unittest.TestCase):
    """The browser side of the lane, driven through the probe's own CLI."""

    base = ""

    @classmethod
    def setUpClass(cls):
        node = _node()
        if node is None:
            raise unittest.SkipTest("node is not on PATH")
        if _playwright_dir() is None:
            raise unittest.SkipTest("harness/ui has no playwright package")
        cls.base = _FakeHost.start()

    @classmethod
    def tearDownClass(cls):
        _FakeHost.stop()

    def probe(self, page: str, *, pairs: int = 1, extra=()) -> dict:
        """Run the probe; retry when the measurement *failed*.

        A failed measurement is either a fact about the machine (the clock
        check of #130 refused the sample, the compositor could not present a
        frame inside the window on a loaded box) or a bug in the lane. The
        test may not assert on the first kind, and it may not hide the second
        either: the measurement is retried (three times at most) and the
        assertions below are unchanged - a lane that always fails still fails
        the test. A *refusal* (not_applicable) is not retried: it is the
        lane's answer.
        """
        payload = {}
        for _ in range(3):
            payload = self._probe_once(page, pairs=pairs, extra=extra)
            if payload.get("outcome") != "failed":
                break
        return payload

    def _probe_once(self, page: str, *, pairs: int = 1, extra=()) -> dict:
        cmd = [
            _node(),
            str(PROBE),
            "--url",
            "%s/%s" % (self.base, page),
            "--corpus",
            str(_FakeHost.corpus),
            "--corpus-route",
            "/corpus.docx",
            "--ready-js",
            "window.__docxReady === true",
            "--pairs",
            str(pairs),
            *[str(value) for value in extra],
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_S, cwd=str(REPO)
        )
        self.assertEqual(
            proc.returncode,
            0,
            "the scroll probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr),
        )
        payload = json.loads(proc.stdout)
        self.assertIsInstance(payload, dict, "the probe must print one JSON object")
        return payload

    # -- A1 --------------------------------------------------------------

    def test_a1_a_document_that_fits_the_viewport_is_not_measured(self):
        payload = self.probe("fits.html")
        self.assertNotEqual(
            payload.get("outcome"),
            "measured",
            "a host whose document fits the viewport must not be measured: %r" % (payload,),
        )
        self.assertEqual(
            payload.get("outcome"),
            "not_applicable",
            "the refusal must be not_applicable: %r" % (payload,),
        )
        self.assertIn(
            "no scroll container",
            str(payload.get("reason")),
            "the refusal must say what it did not find: %r" % (payload,),
        )
        samples = payload.get("samples") or []
        self.assertTrue(samples, "the probe must report the sample it refused")
        for sample in samples:
            self.assertNotEqual(sample.get("outcome"), "measured")
            self.assertIsNone(sample.get("scroll_frame_ms"))

    # -- A2 --------------------------------------------------------------

    def test_a2_every_measured_sample_names_its_container_and_its_delta(self):
        payload = self.probe("prose.html")
        self.assertEqual(
            payload.get("outcome"),
            "measured",
            "the prose-50kw host must be measured: %r" % (payload,),
        )
        samples = payload.get("samples") or []
        self.assertTrue(samples, "the probe must report a sample")
        for sample in samples:
            self.assertEqual(sample.get("outcome"), "measured", "%r" % (sample,))
            container = sample.get("container") or {}
            self.assertTrue(
                str(container.get("selector") or "").strip(),
                "a measured sample must name the container it scrolled: %r" % (sample,),
            )
            delta = sample.get("scroll_top_delta")
            self.assertIsInstance(delta, (int, float), "%r" % (sample,))
            self.assertGreater(
                delta,
                0,
                "a measured sample must have moved the scrollTop: %r" % (sample,),
            )

    def test_a2b_the_document_itself_moved_and_the_witness_saw_the_container(self):
        """A frame that changed is not evidence that the document scrolled."""
        payload = self.probe("prose.html")
        sample = (payload.get("samples") or [{}])[0]
        self.assertEqual(sample.get("outcome"), "measured", "%r" % (payload,))
        self.assertGreater(
            sample.get("content_moved_px") or 0,
            0,
            "the document's own content must have moved: %r" % (sample,),
        )
        witness = sample.get("witness") or {}
        self.assertTrue(
            witness.get("document_scoped"),
            "the witness must be scoped to the document: %r" % (witness,),
        )
        region = (witness.get("document_region") or {}).get("rect_css_px")
        container_rect = (sample.get("container") or {}).get("rect_css_px")
        self.assertIsInstance(region, dict, "the witness must record its region: %r" % (witness,))
        self.assertIsInstance(container_rect, dict, "%r" % (sample,))
        for key in ("x", "y", "width", "height"):
            self.assertAlmostEqual(
                float(region[key]),
                float(container_rect[key]),
                delta=2.0,
                msg="the witness's region must be the container's own box: %r" % (witness,),
            )

    # -- A3 --------------------------------------------------------------

    def test_a3_the_scroller_inside_an_open_shadow_root_is_found(self):
        payload = self.probe("shadow.html")
        samples = payload.get("samples") or []
        self.assertTrue(samples, "the probe must report a sample")
        sample = samples[0]
        self.assertEqual(
            sample.get("outcome"),
            "measured",
            "the scroller inside the open shadow root must be measured: %r" % (sample,),
        )
        container = sample.get("container") or {}
        self.assertTrue(
            container.get("in_shadow_root"),
            "the container must be recorded as living in a shadow root: %r" % (container,),
        )
        self.assertTrue(
            container.get("shadow_hosts"),
            "the shadow host chain must be recorded: %r" % (container,),
        )
        self.assertGreater(sample.get("scroll_top_delta") or 0, 0)
        self.assertGreater(sample.get("content_moved_px") or 0, 0)

    def test_a3b_a_refusal_names_the_shadow_root_it_searched(self):
        """A shadow root with nothing scrollable in it is named, not hidden."""
        payload = self.probe("shadow-fits.html")
        self.assertNotEqual(
            payload.get("outcome"),
            "measured",
            "a document that fits the viewport must not be measured: %r" % (payload,),
        )
        reason = str(payload.get("reason"))
        self.assertIn(
            "shadow",
            reason.lower(),
            "the refusal must name the shadow root it searched: %r" % (reason,),
        )
        self.assertIn(
            "div#host",
            reason,
            "the refusal must name the shadow host: %r" % (reason,),
        )

    # -- A4 --------------------------------------------------------------

    def test_a4_the_measured_sample_carries_the_witness_and_its_skew_bound(self):
        payload = self.probe("prose.html")
        sample = (payload.get("samples") or [{}])[0]
        self.assertEqual(sample.get("outcome"), "measured", "%r" % (payload,))
        witness = sample.get("witness")
        self.assertIsInstance(witness, dict, "the sample must carry the witness record")
        self.assertEqual(witness.get("outcome"), "witnessed", "%r" % (witness,))
        self.assertIsInstance(witness.get("frame_page_ms"), (int, float))
        skew = sample.get("clock_skew") or {}
        self.assertIn("skew_ms", skew, "the clock skew must be recorded: %r" % (skew,))
        self.assertIsInstance(skew.get("bound_ms"), (int, float))
        self.assertTrue(
            witness.get("clock_skew_bound_ms") is not None,
            "the witness must record the skew bound it was held to: %r" % (witness,),
        )
        check = witness.get("clock_check") or {}
        self.assertTrue(
            check.get("acceptable") is True,
            "the witness must carry the run's clock check (the pixel anchor's "
            "evidence), not a bare page offset: %r" % (witness,),
        )

    # -- A5 --------------------------------------------------------------

    def test_a5_the_container_is_the_scroller_that_holds_the_document(self):
        """A hidden decoy with a huge scroll range is not the document."""
        payload = self.probe("decoy.html")
        sample = (payload.get("samples") or [{}])[0]
        self.assertEqual(
            sample.get("outcome"),
            "measured",
            "the document's own scroller must be measured: %r" % (sample,),
        )
        container = sample.get("container") or {}
        self.assertEqual(
            container.get("selector"),
            "#doc",
            "the container must be the scroller that holds the document, not the "
            "decoy with the largest scroll range: %r" % (container,),
        )
        self.assertNotEqual(container.get("selector"), "#decoy")
        self.assertGreater(sample.get("content_moved_px") or 0, 0)

    # -- A6 --------------------------------------------------------------

    def test_a6_a_document_that_fits_beside_a_widget_is_not_measured(self):
        """The widget scrolls; the document does not. The document is C10."""
        payload = self.probe("widget.html")
        self.assertNotEqual(
            payload.get("outcome"),
            "measured",
            "a fitting document must not be measured through a small widget: %r"
            % (payload,),
        )
        self.assertEqual(
            payload.get("outcome"),
            "not_applicable",
            "the refusal must be not_applicable: %r" % (payload,),
        )
        reason = str(payload.get("reason"))
        self.assertIn(
            "widget",
            reason,
            "the refusal must name the scroller it rejected: %r" % (reason,),
        )

    # -- A7 --------------------------------------------------------------

    def test_a7_the_caret_mask_reaches_inside_the_open_shadow_roots(self):
        """A document stylesheet does not match the elements in a shadow tree."""
        payload = self.probe("shadow.html")
        sample = (payload.get("samples") or [{}])[0]
        self.assertEqual(sample.get("outcome"), "measured", "%r" % (payload,))
        self.assertGreaterEqual(
            sample.get("caret_mask_shadow_roots") or 0,
            1,
            "the caret mask must be injected into the open shadow roots: %r" % (sample,),
        )


class ScrollRunnerTests(unittest.TestCase):
    """The runner, end to end, against the fake hosts."""

    def run_runner(self, *, page: str, extra=(), profile="dedicated_publish") -> dict:
        """Run the runner; retry when the measurement *failed*.

        Same reason as the probe helper: a failed measurement on a loaded
        machine is usually the clock check or a frame that did not arrive in
        the window. The assertions are unchanged.
        """
        result = {}
        for _ in range(3):
            result = self._run_runner_once(page=page, extra=extra, profile=profile)
            if (result.get("trial") or {}).get("outcome") != "failed":
                break
        return result

    def _run_runner_once(self, *, page: str, extra=(), profile="dedicated_publish") -> dict:
        out = Path(tempfile.mkdtemp(prefix="b5-c10-"))
        self.addCleanup(shutil.rmtree, str(out), True)
        cmd = [
            sys.executable,
            str(RUNNER),
            "--fake-host",
            str(HOSTS),
            "--fake-page",
            page,
            "--out-root",
            str(out),
            "--pairs",
            "1",
            "--seed",
            "7",
            "--execution-profile",
            profile,
            *[str(value) for value in extra],
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_S, cwd=str(REPO)
        )
        self.assertEqual(
            proc.returncode,
            0,
            "the runner failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr),
        )
        attempts = sorted(out.glob("**/attempts/*.json"))
        self.assertTrue(attempts, "the runner wrote no attempt: %s" % (proc.stdout,))
        trial = json.loads(attempts[0].read_text(encoding="utf-8"))
        summaries = sorted(out.glob("**/summary.json"))
        self.assertTrue(summaries, "the runner wrote no run summary")
        run_summary = json.loads(summaries[-1].read_text(encoding="utf-8"))
        return {"trial": trial, "run_summary": run_summary, "stdout": proc.stdout}

    # -- B1 --------------------------------------------------------------

    def test_b1_the_run_records_the_profile_that_admits_prose50k_and_the_seed(self):
        result = self.run_runner(page="prose.html")
        trial = result["trial"]
        env = trial.get("environment") or {}
        profile = env.get("execution_profile")
        self.assertIn(
            profile,
            ("ci_contract", "ci_broad", "dedicated_publish"),
            "the trial must record an execution profile: %r" % (env,),
        )
        self.assertIn(
            "prose-50kw",
            allowed_workloads(profile),
            "the recorded profile must admit prose-50kw: %r" % (profile,),
        )
        self.assertEqual(env.get("workload_id"), "prose-50kw")
        self.assertEqual(
            trial.get("seed"),
            7,
            "the trial must record the seed of the run: %r" % (trial,),
        )
        self.assertEqual(
            result["run_summary"].get("seed"),
            7,
            "the run summary must record the seed: %r" % (result["run_summary"],),
        )
        self.assertEqual(
            result["run_summary"].get("execution_profile"),
            profile,
            "the run and the trial must record the same profile: %r"
            % (result["run_summary"],),
        )

    # -- B2 --------------------------------------------------------------

    def test_b2_a_document_that_fits_the_viewport_is_never_measured(self):
        result = self.run_runner(page="fits.html")
        trial = result["trial"]
        self.assertNotEqual(
            trial.get("outcome"),
            "measured",
            "a host whose document fits the viewport must not be measured: %r" % (trial,),
        )
        self.assertEqual(trial.get("outcome"), "not_applicable", "%r" % (trial,))
        self.assertIn("no scroll container", str(trial.get("failure_reason")))
        self.assertEqual(trial.get("samples_ms"), [])

    # -- B3 --------------------------------------------------------------

    def test_b3_every_measured_sample_names_its_container_and_its_delta(self):
        result = self.run_runner(page="prose.html")
        trial = result["trial"]
        self.assertEqual(trial.get("outcome"), "measured", "%r" % (trial,))
        samples = (trial.get("diagnostic") or {}).get("samples") or []
        self.assertTrue(samples, "the trial must record its samples: %r" % (trial,))
        self.assertEqual(len(samples), len(trial.get("samples_ms") or []))
        for sample in samples:
            container = sample.get("container") or {}
            self.assertTrue(
                str(container.get("selector") or "").strip(),
                "a measured sample must name its container: %r" % (sample,),
            )
            self.assertGreater(
                sample.get("scroll_top_delta") or 0,
                0,
                "a measured sample must have moved the scrollTop: %r" % (sample,),
            )
            self.assertGreater(
                sample.get("content_moved_px") or 0,
                0,
                "a measured sample must have moved the document's content: %r"
                % (sample,),
            )

    # -- B4 --------------------------------------------------------------

    def test_b4_a_profile_that_refuses_the_workload_is_refused_with_a_reason(self):
        result = self.run_runner(page="prose.html", profile="ci_broad")
        trial = result["trial"]
        self.assertNotEqual(trial.get("outcome"), "measured")
        self.assertEqual(trial.get("outcome"), "not_run", "%r" % (trial,))
        reason = str(trial.get("failure_reason"))
        self.assertIn("prose-50kw", reason, "the refusal must name the workload: %r" % (reason,))
        self.assertEqual(trial.get("samples_ms"), [])

    # -- B5 --------------------------------------------------------------

    def test_b5_a_fake_host_is_never_measured_under_an_editor_id(self):
        out = Path(tempfile.mkdtemp(prefix="b5-c10-fake-"))
        self.addCleanup(shutil.rmtree, str(out), True)
        cmd = [
            sys.executable,
            str(RUNNER),
            "--fake-host",
            str(HOSTS),
            "--fake-page",
            "prose.html",
            "--editor",
            "plate",
            "--out-root",
            str(out),
            "--pairs",
            "1",
            "--seed",
            "7",
            "--execution-profile",
            "dedicated_publish",
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_S, cwd=str(REPO)
        )
        self.assertNotEqual(
            proc.returncode,
            0,
            "--fake-host and --editor must be mutually exclusive: %s" % (proc.stdout,),
        )
        self.assertIn(
            "mutually exclusive",
            proc.stderr,
            "the refusal must say why: %s" % (proc.stderr,),
        )
        for path in out.glob("**/*.json"):
            self.assertNotIn(
                "plate",
                path.read_text(encoding="utf-8"),
                "a fake host's measurement must never be filed under an editor: %s"
                % (path,),
            )

    # -- B6 --------------------------------------------------------------

    def test_b6_the_publishability_follows_the_profile_and_the_host_class(self):
        coarse = self.run_runner(page="prose.html")
        self.assertNotEqual(coarse["trial"].get("publishable"), True)
        decision = (coarse["trial"].get("diagnostic") or {}).get("publication") or {}
        self.assertFalse(decision.get("publishable"), "%r" % (coarse["trial"],))
        self.assertIn(
            "ci_coarse",
            str(decision.get("block_reason")),
            "a ci_coarse host cannot publish visible latency, and the trial must "
            "say so: %r" % (decision,),
        )
        dedicated = self.run_runner(page="prose.html", extra=["--host-class", "dedicated"])
        decision = (dedicated["trial"].get("diagnostic") or {}).get("publication") or {}
        self.assertTrue(
            decision.get("publishable"),
            "a dedicated host with a publish profile may publish: %r" % (decision,),
        )
        self.assertIsNone(decision.get("block_reason"), "%r" % (decision,))
        self.assertIsNone(
            (dedicated["trial"].get("diagnostic") or {}).get("environment_schema_error"),
            "a dedicated host with a publish profile is a schema-valid environment: %r"
            % (dedicated["trial"],),
        )


class ScrollUnitTests(unittest.TestCase):
    """The pure parts of the lane: the profile gate, the environment, the verdict."""

    def verdict(self, sample, **kwargs):
        self.assertTrue(
            hasattr(scroll, "scroll_sample_verdict"),
            "the lane has no sample verdict: a sample that cannot be judged is not measured",
        )
        return scroll.scroll_sample_verdict(sample, **kwargs)

    def test_a_sample_without_a_container_is_refused(self):
        outcome, reason, value = self.verdict(
            _sample(container={"selector": "", "rect_css_px": dict(CONTAINER_RECT)})
        )
        self.assertEqual(outcome, "failed")
        self.assertIn("container", reason)
        self.assertIsNone(value)

    def test_a_sample_whose_scrolltop_did_not_move_is_refused(self):
        outcome, reason, value = self.verdict(_sample(scroll_top_delta=0))
        self.assertEqual(outcome, "failed")
        self.assertIn("scrollTop", reason)
        self.assertIsNone(value)

    def test_a_sample_whose_document_did_not_move_is_refused(self):
        """A frame that changed is not a scroll: the content must have moved."""
        outcome, reason, value = self.verdict(_sample(content_moved_px=0))
        self.assertEqual(outcome, "failed")
        self.assertIn("did not scroll", reason)
        self.assertIsNone(value)

    def test_a_witness_that_is_not_document_scoped_is_refused(self):
        """A whole-frame diff lets shell damage pose as document paint."""
        witness = _witness(document_scoped=False, document_region=None)
        outcome, reason, value = self.verdict(_sample(witness=witness))
        self.assertEqual(outcome, "failed")
        self.assertIn("document-scoped", reason)
        self.assertIsNone(value)

    def test_a_witness_whose_region_is_not_the_container_is_refused(self):
        witness = _witness(
            document_region={
                "source": "rect",
                "selector": None,
                "rect_css_px": {"x": 0.0, "y": 0.0, "width": 40.0, "height": 40.0},
            }
        )
        outcome, reason, value = self.verdict(_sample(witness=witness))
        self.assertEqual(outcome, "failed")
        self.assertIn("region", reason)
        self.assertIsNone(value)

    def test_a_witness_without_an_acceptable_clock_check_is_refused(self):
        witness = _witness(
            clock_check={
                "kind": "clock_skew",
                "acceptable": False,
                "reason": "no_anchor_evidence",
                "page_offset_ms": 0.1,
                "bound_ms": 2.0,
            }
        )
        outcome, reason, value = self.verdict(_sample(witness=witness))
        self.assertEqual(outcome, "failed")
        self.assertIn("clock", reason.lower())
        self.assertIsNone(value)

    def test_a_witness_above_the_skew_bound_is_refused(self):
        outcome, reason, value = self.verdict(_sample(witness=_witness(clock_skew_ms=9.0)))
        self.assertEqual(outcome, "failed")
        self.assertIn("skew", reason.lower())
        self.assertIsNone(value)

    def test_a_good_sample_is_measured(self):
        outcome, reason, value = self.verdict(_sample())
        self.assertEqual(outcome, "measured")
        self.assertIsNone(reason)
        self.assertEqual(value, 12.5)

    def test_only_dedicated_publish_admits_prose_50kw(self):
        self.assertTrue(
            hasattr(scroll, "profile_admits_workload"),
            "the lane has no profile gate: the profile must be able to refuse the workload",
        )
        self.assertTrue(scroll.profile_admits_workload("dedicated_publish"))
        self.assertFalse(scroll.profile_admits_workload("ci_broad"))
        self.assertFalse(scroll.profile_admits_workload("ci_contract"))

    def test_the_environment_records_the_profile_and_the_workload(self):
        self.assertTrue(
            hasattr(scroll, "scroll_env"),
            "the lane has no environment builder",
        )
        fixture = scroll.scroll_fixture()
        env = scroll.scroll_env(
            editor_id="plate",
            editor_version="test",
            execution_profile="dedicated_publish",
            host_class="ci_coarse",
            fixture=fixture,
        )
        self.assertEqual(env["execution_profile"], "dedicated_publish")
        self.assertEqual(env["workload_id"], "prose-50kw")
        self.assertEqual(env["host_class"], "ci_coarse")
        self.assertGreater(env["fixture_byte_size"], 0)

    def test_the_environment_matches_b1s_builder(self):
        """B5 builds the environment itself; it must not drift from B1a's."""
        from perf.runner.benchmark_ci_contract import _host_base

        fixture = scroll.scroll_fixture()
        mine = scroll.scroll_env(
            editor_id="plate",
            editor_version="test",
            execution_profile="ci_broad",
            host_class="ci_coarse",
            fixture=fixture,
        )
        theirs = _host_base(
            editor_id="plate",
            editor_version="test",
            execution_profile="ci_broad",
            fixture_sha256=fixture["sha256"],
            workload_row=fixture["workload_row"],
            docx_size=fixture["byte_size"],
            cache_state="warm_steady",
            repetition_unit="fresh_process",
            run_kind="timing",
            feature_profile_name="P0",
        )
        # B1a counts the ladder's paragraphs; the lane counts the document it
        # built. Everything else must be the same environment.
        theirs["fixture_paragraph_count"] = int(fixture["paragraph_count"])
        self.assertEqual(mine, theirs)

    def test_the_publication_flags_follow_the_policy(self):
        self.assertTrue(
            hasattr(scroll, "scroll_publication_flags"),
            "the lane has no publication decision: the publishability must follow "
            "the profile and the host class",
        )
        fixture = scroll.scroll_fixture()
        coarse = scroll.scroll_env(
            editor_id="plate",
            editor_version="test",
            execution_profile="ci_broad",
            host_class="ci_coarse",
            fixture=fixture,
        )
        publishable, reason = scroll.scroll_publication_flags(coarse, 3)
        self.assertFalse(publishable)
        self.assertIn("ci_coarse", reason)
        dedicated = scroll.scroll_env(
            editor_id="plate",
            editor_version="test",
            execution_profile="dedicated_publish",
            host_class="dedicated",
            fixture=fixture,
        )
        publishable, reason = scroll.scroll_publication_flags(dedicated, 3)
        self.assertTrue(publishable)
        self.assertIsNone(reason)
        # The n>=2 rule (I10) belongs to the published distribution, not to a
        # single repetition's trial: the caller may still ask for it.
        publishable, reason = scroll.scroll_publication_flags(dedicated, 1)
        self.assertFalse(publishable)
        self.assertIn("n>=2", reason)


if __name__ == "__main__":
    unittest.main()
