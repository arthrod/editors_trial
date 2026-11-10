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
A4  every measured sample carries B1c's frame witness and its clock-skew
    bound.
B1  the run records the execution profile that admits prose-50kw and the seed.

Two premises of this file changed under #130 and #132, and they are changed
here, in their own commit, before any of the new counterexamples:

* a witness record must satisfy B1c's validator (#130): it needs
  ``document_scoped``, ``changed_pixels`` and the run's clock check (the
  pixel anchor's evidence), not a bare ``clock_skew_ms``. The unit tests
  below therefore use a record of the shape the validator accepts.
* the execution profile belongs to the *run* (#132: ``run_cli`` owns
  ``--execution-profile``), so the lane no longer has a profile of its own:
  the runner is invoked with the profile that admits prose-50kw, and the
  trial has to record *that* profile.

B2  the runner writes a ``not_applicable`` trial (never ``measured``) for the
    host whose document fits.
B3  every measured sample of the runner's trial names its container and its
    ``scrollTop`` delta.
B4  a profile that refuses prose-50kw is refused **with a reason**; nothing
    is measured and nothing crashes.
C   the pure parts: the profile gate, the environment and the sample verdict.

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


#: The rectangle a fake host's document box occupies.
CONTAINER_RECT = {"x": 0.0, "y": 0.0, "width": 1280.0, "height": 900.0}


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


def _corpus(tmp: Path) -> Path:
    """The prose-50kw document, written where the probe can read it."""
    built = workload_docx("prose-50kw")
    path = tmp / "prose-50kw.docx"
    path.write_bytes(built["docx"])
    return path


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

    # -- A3 --------------------------------------------------------------

    def test_a3_the_scroller_inside_an_open_shadow_root_is_found(self):
        payload = self.probe("shadow.html")
        samples = payload.get("samples") or []
        self.assertTrue(samples, "the probe must report a sample")
        sample = samples[0]
        if sample.get("outcome") != "measured":
            # A refusal is allowed, but it must name the shadow root.
            self.assertIn(
                "shadow",
                str(sample.get("reason")).lower(),
                "a refusal must name the shadow root: %r" % (sample,),
            )
            return
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


class ScrollRunnerTests(unittest.TestCase):
    """The runner, end to end, against the fake hosts."""

    def run_runner(self, *, page: str, extra=(), profile="dedicated_publish") -> dict:
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

    # -- B4 --------------------------------------------------------------

    def test_b4_a_profile_that_refuses_the_workload_is_refused_with_a_reason(self):
        result = self.run_runner(page="prose.html", profile="ci_broad")
        trial = result["trial"]
        self.assertNotEqual(trial.get("outcome"), "measured")
        self.assertEqual(trial.get("outcome"), "not_run", "%r" % (trial,))
        reason = str(trial.get("failure_reason"))
        self.assertIn("prose-50kw", reason, "the refusal must name the workload: %r" % (reason,))
        self.assertEqual(trial.get("samples_ms"), [])


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


if __name__ == "__main__":
    unittest.main()
