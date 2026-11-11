"""B5 — the C10 scroll lane (#106, #134).

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
B2  the runner writes a ``not_applicable`` trial (never ``measured``) for the
    host whose document fits.
B3  every measured sample of the runner's trial names its container and its
    ``scrollTop`` delta.
B4  a profile that refuses prose-50kw is refused **with a reason**; nothing
    is measured and nothing crashes.
C   the pure parts: the profile gate, the environment and the sample verdict.

The review of #134 added the counterexamples of the adversarial review
(``e2-logs/review-b5.md``), each with its own measurer:

F1  the witness is **scoped to the scrolled container**: damage outside the
    document cannot pose as the document's paint (``decoy.html``).
F2  the container is the scroller that **holds the document text**, not the
    scroller with the largest range (``decoy.html``, ``widget.html``).
F3  ``--fake-host`` and ``--editor`` are **mutually exclusive**: a fake
    measurement is never filed under a real editor's id.
F4  the trial's **publishability follows the profile and the host class**,
    with the publication gate's own reason.
F5  the sample proves the **content moved** (the scrolled content, not only a
    changed frame).
F6  the throttle refusal is **evidence**, not one string match on one sample.
F7  the nits: the latency is rounded, and the refusal does not claim a
    closed shadow root the page may not have.

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

#: The profile that admits prose-50kw. B1 owns the flag (``run_cli`` parses
#: ``--execution-profile``); the lane reads the run.
PUBLISH_PROFILE = "dedicated_publish"


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
    from perf.tests.witness_records import publishable_witness_record
    fields = {'document_region': {
        'source': 'rect', 'selector': None,
        'rect_css_px': {'x': 0, 'y': 0, 'width': 800, 'height': 900},
    }}
    fields.update(overrides)
    return publishable_witness_record(100, 87.5, **fields)


def _sample(**overrides) -> dict:
    """A probe sample the lane must judge: a scrolled container that moved."""
    sample = {
        "outcome": "measured",
        "container": {
            "selector": "#doc",
            # The container the probe scrolled. The authority compares this
            # box to the witness's document_region (within 1 px).
            "region_rect": {"x": 0, "y": 0, "width": 800, "height": 900},
        },
        "content": {"moved_px": 600, "top_before": 12.0, "top_after": -588.0},
        "scroll_top_delta": 600,
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
    def test_missing_named_container_does_not_fall_back_to_auto_selection(self):
        payload = self.probe("prose.html", extra=["--container-selector", "#absent"])
        self.assertNotEqual(payload.get("outcome"), "measured", payload)
        self.assertIn("container_selector_not_found", str(payload), payload)


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
        # #130: the record must carry the run's clock check, with its anchor.
        check = witness.get("clock_check") or {}
        self.assertIs(
            check.get("acceptable"),
            True,
            "the witness must carry the run's clock check: %r" % (witness,),
        )

    # -- F1: the witness is scoped to the scrolled container ------------

    def test_f1_the_witness_is_scoped_to_the_scrolled_container(self):
        """Damage outside the document cannot witness the document's scroll.

        The fake host blinks a 40x40 square at x=1000, outside the document
        box, and scrolls a decoy scroller that holds no text. The witness
        must be scoped to the container the lane scrolled, and that scope
        must exclude the blinking square.
        """
        payload = self.probe("decoy.html")
        samples = payload.get("samples") or []
        self.assertTrue(samples, "the probe must report a sample")
        sample = samples[0]
        self.assertEqual(
            sample.get("outcome"),
            "measured",
            "the prose host must be measured: %r" % (sample,),
        )
        witness = sample.get("witness") or {}
        self.assertIs(
            witness.get("document_scoped"),
            True,
            "the witness must be scoped to the document: %r" % (witness,),
        )
        region = witness.get("document_region") or {}
        self.assertTrue(region, "the witness must record its document region: %r" % (witness,))
        rect = region.get("rect_css_px") or {}
        self.assertLessEqual(
            rect.get("x", 0) + rect.get("width", 0),
            900,
            "the document region must exclude the blinking square at x=1000: %r" % (rect,),
        )
        self.assertGreater(
            witness.get("region_pixels") or 0,
            0,
            "the scoped region must have pixels: %r" % (witness,),
        )
        self.assertLessEqual(
            witness.get("changed_pixels") or 0,
            witness.get("region_pixels") or 0,
            "the changed pixels must be inside the document region: %r" % (witness,),
        )

    # -- F2: the container holds the document text -----------------------

    def test_f2_the_container_is_the_scroller_that_holds_the_document_text(self):
        """The decoy scroller has the largest range and no text at all."""
        payload = self.probe("decoy.html")
        sample = (payload.get("samples") or [{}])[0]
        container = sample.get("container") or {}
        self.assertNotEqual(
            container.get("selector"),
            "#decoy",
            "the decoy holds no text: it is not the document's scroller: %r" % (sample,),
        )
        self.assertEqual(
            container.get("selector"),
            "#doc",
            "the container must be the scroller that holds the document text: %r" % (sample,),
        )

    def test_f2b_a_fitting_document_with_a_small_widget_is_not_measured(self):
        """A widget with a small overflow is not the document's scroller."""
        payload = self.probe("widget.html")
        self.assertNotEqual(
            payload.get("outcome"),
            "measured",
            "a document that fits the viewport must not be measured: %r" % (payload,),
        )
        self.assertEqual(
            payload.get("outcome"),
            "not_applicable",
            "the refusal must be not_applicable: %r" % (payload,),
        )
        self.assertIn(
            "document text",
            str(payload.get("reason")),
            "the refusal must say that no scroller holds the document text: %r" % (payload,),
        )

    # -- F5: the content moved -------------------------------------------

    def test_f5_the_sample_proves_that_the_content_moved(self):
        """A changed frame is not a scroll: the content must have moved."""
        payload = self.probe("prose.html")
        sample = (payload.get("samples") or [{}])[0]
        self.assertEqual(sample.get("outcome"), "measured", "%r" % (payload,))
        content = sample.get("content") or {}
        delta = sample.get("scroll_top_delta") or 0
        moved = content.get("moved_px")
        self.assertIsInstance(moved, (int, float), "%r" % (sample,))
        self.assertGreater(
            moved,
            0,
            "the scrolled content must have moved: %r" % (sample,),
        )
        self.assertAlmostEqual(
            moved,
            delta,
            delta=2,
            msg="the content must move with the scroll: %r" % (sample,),
        )
        self.assertNotEqual(
            content.get("visible_text_before"),
            content.get("visible_text_after"),
            "the text visible at the top of the scroller must change: %r" % (content,),
        )

    # -- F7: the nits ----------------------------------------------------

    def test_f7_the_latency_is_rounded_to_the_millisecond(self):
        payload = self.probe("prose.html")
        sample = (payload.get("samples") or [{}])[0]
        value = sample.get("scroll_frame_ms")
        self.assertIsInstance(value, (int, float), "%r" % (sample,))
        self.assertEqual(
            value,
            round(float(value), 3),
            "the latency must be rounded to the millisecond: %r" % (value,),
        )

    def test_f7b_the_refusal_does_not_claim_a_closed_shadow_root(self):
        payload = self.probe("fits.html")
        reason = str(payload.get("reason"))
        self.assertNotIn(
            "a closed shadow root is not reachable",
            reason,
            "the refusal must not claim the page has a closed shadow root: %r" % (reason,),
        )
        self.assertIn(
            "if the page has one",
            reason,
            "the refusal must be conditional about a closed shadow root: %r" % (reason,),
        )


    # -- F8: the damage outside the document ----------------------------

    def test_f8_damage_outside_the_document_does_not_witness_the_scroll(self):
        """A frame that changed for another reason is not the scroll.

        The fake host scrolls a document whose text is transparent: the scroll
        moves the content, but the container paints the same pixels before and
        after. Next to it a 40x40 square repaints on every animation frame. A
        witness that diffs the whole frame sees that square and publishes it
        as the scroll; a witness scoped to the scrolled container does not.
        """
        payload = self.probe("blink.html")
        self.assertNotEqual(
            payload.get("outcome"),
            "measured",
            "a scroll that paints no document pixel must not be published: the "
            "frame that changed was somebody else's damage: %r" % (payload,),
        )
        samples = payload.get("samples") or []
        self.assertTrue(samples, "the probe must report the sample it refused")
        self.assertNotEqual(samples[0].get("outcome"), "measured")

    # -- F9: the content probe follows the scrolled content --------------

    def test_f9_the_content_probe_follows_the_scrolled_content(self):
        """The evidence that the document scrolled must itself move.

        The fake host puts a *fixed* panel (which holds text) inside the
        scroller. A content probe that takes the first element carrying text
        stops at the panel, the panel does not move when the document scrolls,
        and the lane reports that the document did not scroll — while it did.
        """
        payload = self.probe("fixed-panel.html")
        self.assertEqual(
            payload.get("outcome"),
            "measured",
            "the document scrolls under a fixed panel: %r" % (payload,),
        )
        sample = (payload.get("samples") or [{}])[0]
        content = sample.get("content") or {}
        self.assertGreater(
            content.get("moved_px") or 0,
            0,
            "the content that moved with the scroll must be recorded: %r" % (sample,),
        )
        self.assertNotEqual(
            content.get("probe_selector"),
            "#panel",
            "the content probe must not be the panel that cannot move: %r" % (content,),
        )

    # -- F10: the per-host override --------------------------------------

    def test_f10_the_per_host_override_names_the_container_and_is_recorded(self):
        """A host may name its own container; the override is recorded."""
        payload = self.probe("override.html", extra=["--scroll-container", "#small"])
        sample = (payload.get("samples") or [{}])[0]
        self.assertEqual(sample.get("outcome"), "measured", "%r" % (payload,))
        container = sample.get("container") or {}
        self.assertEqual(
            container.get("selector"),
            "#small",
            "the override must name the container: %r" % (sample,),
        )
        self.assertEqual(
            payload.get("scroll_container_override"),
            "#small",
            "the payload must record the override: %r" % (payload,),
        )
        selection = (sample.get("search") or {})
        self.assertIn(
            "named",
            str(selection.get("chosen_reason") or ""),
            "the sample must record that the operator named the container: %r"
            % (selection,),
        )

    # -- F2, round 2: the document's scroller, not the innermost one -----

    def test_f2c_a_nested_note_does_not_steal_the_document(self):
        """The document's scroller is the deepest-text owner, not the innermost survivor.

        ``nested-note.html`` puts a short note inside ``#doc``. The note is
        the innermost scroller. ``#doc`` holds the document text.
        """
        payload = self.probe("nested-note.html")
        self.assertEqual(payload.get("outcome"), "measured", "%r" % (payload,))
        sample = (payload.get("samples") or [{}])[0]
        container = sample.get("container") or {}
        self.assertEqual(
            container.get("selector"),
            "#doc",
            "the nested note is not the document: %r" % (sample,),
        )
        self.assertNotEqual(container.get("selector"), "#note")
        self.assertEqual(
            container.get("container_rule") or sample.get("container_rule"),
            "text",
            "the document's own text chooses the container: %r" % (sample,),
        )

    def test_f2d_a_text_widget_beside_a_fitting_document_is_not_measured(self):
        """A widget that contains the word Notes is not the document's scroller.

        The document fits. It has no scroller. C10 is not applicable.
        """
        payload = self.probe("text-widget.html")
        self.assertEqual(
            payload.get("outcome"),
            "not_applicable",
            "the document has no scroller: %r" % (payload,),
        )
        self.assertNotEqual(payload.get("outcome"), "measured")
        reason = str(payload.get("reason"))
        self.assertIn("document", reason.lower(), "%r" % (payload,))
        for sample in payload.get("samples") or []:
            container = sample.get("container") or {}
            self.assertNotEqual(
                container.get("selector"),
                "#widget",
                "the widget must not be published as the document: %r" % (sample,),
            )

    def test_f2e_a_textless_canvas_scroller_is_the_surface(self):
        """A canvas editor has no DOM text. The scroller that covers the viewport is the document.

        The same shape as ``harness/ui/canvas`` ``#editor``: overflow-y auto
        around a canvas, covering at least half the viewport. The label is
        ``container_rule: surface``.
        """
        payload = self.probe("canvas.html")
        self.assertEqual(payload.get("outcome"), "measured", "%r" % (payload,))
        sample = (payload.get("samples") or [{}])[0]
        container = sample.get("container") or {}
        self.assertEqual(container.get("selector"), "#editor", "%r" % (sample,))
        self.assertEqual(
            container.get("container_rule") or sample.get("container_rule"),
            "surface",
            "a textless page uses the surface rule: %r" % (sample,),
        )

    def test_f2f_a_shadow_host_that_scrolls_counts_its_own_shadow_text(self):
        """The host is the scroller. Its text lives in its own shadow root."""
        payload = self.probe("shadow-host.html")
        self.assertEqual(payload.get("outcome"), "measured", "%r" % (payload,))
        sample = (payload.get("samples") or [{}])[0]
        container = sample.get("container") or {}
        self.assertEqual(container.get("selector"), "#host", "%r" % (sample,))
        self.assertGreater(
            container.get("own_text_chars") or 0,
            0,
            "the host's own shadow root is its text: %r" % (container,),
        )

    def test_f2g_container_selector_is_an_adapter_override(self):
        """``--container-selector`` is the per-editor adapter. The label is ``adapter``."""
        payload = self.probe("override.html", extra=["--container-selector", "#small"])
        self.assertEqual(payload.get("outcome"), "measured", "%r" % (payload,))
        sample = (payload.get("samples") or [{}])[0]
        container = sample.get("container") or {}
        self.assertEqual(container.get("selector"), "#small", "%r" % (sample,))
        self.assertEqual(
            container.get("container_rule") or sample.get("container_rule"),
            "adapter",
            "an adapter selector is labelled adapter: %r" % (sample,),
        )


class ScrollRunnerTests(unittest.TestCase):
    """The runner, end to end, against the fake hosts."""

    def run_runner(self, *, page: str, extra=(), expect_failure: bool = False, fake_accounting: bool = False) -> dict:
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
            "30",
            "--seed",
            "7",
            "--execution-profile",
            PUBLISH_PROFILE,
            *[str(value) for value in extra],
        ]
        if fake_accounting:
            # B1 exposes this injection point; reuse its own deterministic cgroup fake.
            bootstrap = (
                "from functools import partial; from itertools import count; "
                "from perf.tests.test_browser_throttle import snapshot; "
                "from perf.runner import adversarial_c10_scroll as lane; "
                "ticks=count(100); lane.BrowserRun=partial(lane.BrowserRun, "
                "accounting_reader=lambda: snapshot(ticks=next(ticks))); "
                "raise SystemExit(lane.main())"
            )
            cmd = [sys.executable, "-c", bootstrap, *cmd[2:]]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_S, cwd=str(REPO)
        )
        if expect_failure:
            return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "out": out}
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
                "a measured sample must name its container: %r" % (trial,),
            )
            self.assertGreater(
                sample.get("scroll_top_delta") or 0,
                0,
                "a measured sample must have moved the scrollTop: %r" % (trial,),
            )
            self.assertGreater(
                (sample.get("content") or {}).get("moved_px") or 0,
                0,
                "a measured sample must have moved the content: %r" % (trial,),
            )

    # -- B4 --------------------------------------------------------------

    def test_b4_a_profile_that_refuses_the_workload_is_refused_with_a_reason(self):
        result = self.run_runner(page="prose.html", extra=["--execution-profile", "ci_broad"])
        trial = result["trial"]
        self.assertNotEqual(trial.get("outcome"), "measured")
        self.assertEqual(trial.get("outcome"), "not_run", "%r" % (trial,))
        reason = str(trial.get("failure_reason"))
        self.assertIn("prose-50kw", reason, "the refusal must name the workload: %r" % (reason,))
        self.assertEqual(trial.get("samples_ms"), [])

    # -- F3: the fake host and an editor are exclusive ------------------

    def test_f3_the_fake_host_and_an_editor_are_mutually_exclusive(self):
        """A fake measurement must never be filed under a real editor's id."""
        result = self.run_runner(
            page="prose.html", extra=["--editor", "plate"], expect_failure=True
        )
        self.assertNotEqual(
            result["returncode"],
            0,
            "the runner must refuse --fake-host with --editor: %r" % (result,),
        )
        self.assertIn(
            "mutually exclusive",
            result["stderr"],
            "the refusal must say why: %r" % (result,),
        )
        attempts = sorted(Path(result["out"]).glob("**/attempts/*.json"))
        self.assertEqual(
            attempts,
            [],
            "no attempt may be written for a fake host under an editor's id: %r" % (attempts,),
        )

    def test_m7_shared_guarded_is_a_host_class_the_lane_accepts(self):
        """``shared_guarded`` propagates with dedicated_publish and a fake cgroup.

        B7 adds the class to ``perf/schema.py``. This branch's schema may
        still reject it; the lane accepts it anyway and records it.
        """
        self.assertIn("shared_guarded", scroll.HOST_CLASSES)
        result = self.run_runner(
            page="fits.html",
            extra=["--host-class", "shared_guarded"],
            fake_accounting=True,
        )
        env = result["trial"].get("environment") or {}
        self.assertEqual(
            env.get("host_class"),
            "shared_guarded",
            "the trial must record the host class the operator asked for: %r" % (env,),
        )
        self.assertEqual(env.get("execution_profile"), "dedicated_publish")


class ScrollUnitTests(unittest.TestCase):
    """The pure parts of the lane: the profile gate, the environment, the verdict."""

    def verdict(self, sample, **kwargs):
        self.assertTrue(
            hasattr(scroll, "scroll_sample_verdict"),
            "the lane has no sample verdict: a sample that cannot be judged is not measured",
        )
        return scroll.scroll_sample_verdict(sample, **kwargs)

    def test_a_sample_without_a_container_is_refused(self):
        outcome, reason, value = self.verdict(_sample(container={"selector": ""}))
        self.assertEqual(outcome, "failed")
        self.assertIn("container", reason)
        self.assertIsNone(value)

    def test_a_sample_whose_scrolltop_did_not_move_is_refused(self):
        outcome, reason, value = self.verdict(_sample(scroll_top_delta=0))
        self.assertEqual(outcome, "failed")
        self.assertIn("scrollTop", reason)
        self.assertIsNone(value)

    def test_a_sample_whose_content_did_not_move_is_refused(self):
        """A scrollTop that moves without the content moving is not a scroll."""
        outcome, reason, value = self.verdict(
            _sample(content={"moved_px": 0, "top_before": 12.0, "top_after": 12.0})
        )
        self.assertEqual(outcome, "failed")
        self.assertIn("content", reason)
        self.assertIsNone(value)

    def test_a_witness_above_the_skew_bound_is_refused(self):
        outcome, reason, value = self.verdict(
            _sample(
                witness=_witness(
                    clock_skew_ms=9.0,
                    clock_check={
                        "kind": "clock_skew",
                        "acceptable": True,
                        "reason": None,
                        "page_offset_ms": 9.0,
                    },
                )
            )
        )
        self.assertEqual(outcome, "failed")
        self.assertIn("clock_skew_above_bound", reason)
        self.assertIsNone(value)

    def test_an_unscoped_witness_is_refused(self):
        """A whole-frame diff lets shell damage pose as document paint."""
        outcome, reason, value = self.verdict(
            _sample(witness=_witness(document_scoped=False))
        )
        self.assertEqual(outcome, "failed")
        self.assertIn("not_document_scoped", reason)
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

    # -- F4: the publishability follows the profile and the host class ----

    def test_f4_the_publishability_follows_the_profile_and_the_host_class(self):
        self.assertTrue(
            hasattr(scroll, "scroll_publishability"),
            "the lane decides nothing about publication: the gate decides",
        )
        fixture = scroll.scroll_fixture()

        def env_for(host_class: str) -> dict:
            return scroll.scroll_env(
                editor_id="plate",
                editor_version="test",
                execution_profile="dedicated_publish",
                host_class=host_class,
                fixture=fixture,
            )

        publishable, reason = scroll.scroll_publishability(env_for("dedicated"), 3)
        self.assertTrue(
            publishable,
            "a dedicated host running the publish profile may publish: %r" % (reason,),
        )
        self.assertIsNone(reason)

        publishable, reason = scroll.scroll_publishability(env_for("ci_coarse"), 3)
        self.assertFalse(publishable, "a ci_coarse host may not publish visible latency")
        self.assertIn("ci_coarse", str(reason))

        # One sample is a cell, not a distribution. The per-cell n>=2 rule
        # does not apply; publication n is e2_cells.py (n >= 10 per run).
        publishable, reason = scroll.scroll_publishability(env_for("dedicated"), 1)
        self.assertTrue(
            publishable,
            "a one-sample cell must not be stamped I10: %r" % (reason,),
        )
        self.assertNotIn("n>=2", str(reason))
        doc = scroll.scroll_publishability.__doc__ or ""
        self.assertIn("n>=2", doc, "the docstring must say the per-cell n>=2 rule is not applied")
        self.assertIn("e2_cells.py", doc)
        self.assertIn("n >= 10", doc)

    def test_f4b_a_measured_trial_carries_the_gate_s_verdict(self):
        """The trial's own publishability, not a hardcoded false."""
        fixture = scroll.scroll_fixture()
        env = scroll.scroll_env(
            editor_id="plate",
            editor_version="test",
            execution_profile="dedicated_publish",
            host_class="dedicated",
            fixture=fixture,
        )
        out = Path(tempfile.mkdtemp(prefix="b5-publish-"))
        self.addCleanup(shutil.rmtree, str(out), True)
        scroll._write_outcome(
            attempt_dir=out / "attempts",
            outcome="measured",
            reason=None,
            samples=[{"value": value, "record": {"witness": _witness()}} for value in (12.5, 13.5)],
            env=env,
            editor_id="plate",
            lane="browser_visible",
            diagnostic={},
            seed=7,
        )
        trials = sorted((out / "attempts").glob("*.json"))
        self.assertTrue(trials, "no attempt was written")
        trial = json.loads(trials[0].read_text(encoding="utf-8"))
        self.assertIs(
            trial.get("publishable"),
            True,
            "a dedicated host's measured trial must be publishable: %r" % (trial,),
        )
        self.assertIsNone(
            trial.get("publication_block_reason"),
            "a publishable trial must not carry a block reason: %r" % (trial,),
        )

    def test_f4c_a_one_sample_cell_is_not_stamped_i10(self):
        """``run_cli`` writes one sample per cell. That cell is not an I10 failure."""
        fixture = scroll.scroll_fixture()
        env = scroll.scroll_env(
            editor_id="plate",
            editor_version="test",
            execution_profile="dedicated_publish",
            host_class="dedicated",
            fixture=fixture,
        )
        out = Path(tempfile.mkdtemp(prefix="b5-one-sample-"))
        self.addCleanup(shutil.rmtree, str(out), True)
        scroll._write_outcome(
            attempt_dir=out / "attempts",
            outcome="measured",
            reason=None,
            samples=[{"value": 12.5, "record": {"witness": _witness()}}],
            env=env,
            editor_id="plate",
            lane="browser_visible",
            diagnostic={},
            seed=7,
        )
        trials = sorted((out / "attempts").glob("*.json"))
        self.assertTrue(trials, "no attempt was written")
        trial = json.loads(trials[0].read_text(encoding="utf-8"))
        self.assertEqual(trial.get("outcome"), "measured")
        self.assertEqual(len(trial.get("samples_ms") or []), 1)
        self.assertIs(
            trial.get("publishable"),
            True,
            "one sample must not be stamped I10: %r" % (trial.get("publication_block_reason"),),
        )
        self.assertNotIn("n>=2", str(trial.get("publication_block_reason")))
        self.assertIsNone(trial.get("publication_block_reason"))

    # -- F1, round 2: the blink record is not the container's region ------

    def test_f1b_a_blink_region_is_not_the_container(self):
        """The authority refuses a witness whose document_region is not the container.

        The container is ``#doc`` at 800×900. The witness rectangle is the
        40×40 blink. ``changed_pixels == region_pixels`` is not enough.
        """
        from perf.runner.witness import validate_witness
        blink = _witness(
            changed_pixels=1600,
            region_pixels=1600,
            document_region={
                "source": "rect",
                "selector": None,
                "rect_css_px": {"x": 1000, "y": 10, "width": 40, "height": 40},
            },
        )
        self.assertTrue(validate_witness(blink)['ok'], validate_witness(blink))
        outcome, reason, value = self.verdict(
            _sample(
                witness=blink,
                container={
                    "selector": "#doc",
                    "region_rect": {"x": 0, "y": 0, "width": 800, "height": 900},
                },
            )
        )
        self.assertEqual(outcome, "failed", "%r" % (reason,))
        self.assertIn("region", reason.lower())
        self.assertIsNone(value)

        matched = self.verdict(_sample())
        self.assertEqual(matched[0], "measured", "%r" % (matched,))

        shifted = _witness(
            document_region={
                "source": "rect",
                "selector": None,
                "rect_css_px": {"x": 1, "y": 0, "width": 800, "height": 900},
            }
        )
        within, within_reason, _within_value = self.verdict(_sample(witness=shifted))
        self.assertEqual(within, "measured", "1 px is the same box: %r" % (within_reason,))

        outside = _witness(
            document_region={
                "source": "rect",
                "selector": None,
                "rect_css_px": {"x": 1.1, "y": 0, "width": 800, "height": 900},
            }
        )
        refused, refused_reason, refused_value = self.verdict(_sample(witness=outside))
        self.assertEqual(refused, "failed", "%r" % (refused_reason,))
        self.assertIsNone(refused_value)
        self.assertIn("region", refused_reason.lower())

    # -- F3, round 2: every spelling of the flag, before run_cli ----------

    def test_f3b_every_spelling_of_fake_host_is_refused_before_run_cli(self):
        """``--fake-host=X``, ``--editor=plate`` and ``--editor plate`` never reach run_cli."""
        from io import StringIO

        calls = []
        real = scroll.run_cli

        def fake_run_cli(*args, **kwargs):
            calls.append({"argv": list(sys.argv), "args": args, "kwargs": kwargs})
            return 0

        spellings = (
            ["prog", "--fake-host=/tmp/b5-hosts", "--editor=plate"],
            ["prog", "--fake-host=/tmp/b5-hosts", "--editor", "plate"],
            ["prog", "--fake-host", "/tmp/b5-hosts", "--editor=plate"],
        )
        old_argv = sys.argv
        old_err = sys.stderr
        scroll.run_cli = fake_run_cli
        try:
            for argv in spellings:
                calls.clear()
                sys.argv = argv
                sys.stderr = StringIO()
                rc = scroll.main()
                err = sys.stderr.getvalue()
                self.assertEqual(rc, 2, "%r called run_cli (%r) stderr %r" % (argv, calls, err))
                self.assertEqual(calls, [], "%r must be refused before run_cli" % (argv,))
                self.assertIn("mutually exclusive", err)
        finally:
            scroll.run_cli = real
            sys.argv = old_argv
            sys.stderr = old_err

    # -- F6, round 2: a prior throttled row cannot refuse a later cell ----

    def test_f6b_a_prior_throttled_row_does_not_refuse_a_later_clean_cell(self):
        """Only the current sample's own accounting can refuse it."""
        from perf.runner.browser_run import ACTIVE, BrowserRun

        out = Path(tempfile.mkdtemp(prefix="b5-throttle-"))
        self.addCleanup(shutil.rmtree, str(out), True)
        run = BrowserRun(
            out,
            "c10throttle",
            seed=1,
            run_id="throttle",
            snapshot=lambda: {},
            accounting_reader=lambda: {"available": False, "reason": "stub"},
        )
        run.execution_profile = "dedicated_publish"
        run.host_class = "dedicated"
        run.samples.append(
            {
                "outcome": "failed",
                "failure_reason": "cpu_throttled",
                "cpu_accounting": {
                    "available": True,
                    "delta": {"nr_throttled": 1, "throttled_usec": 5},
                },
                "editor_id": "b5-fake",
                "repetition": 0,
            }
        )
        payload = {
            "status": "ok",
            "outcome": "measured",
            "reason": None,
            "samples": [_sample()],
            "scroll_step_px": 600,
            "witness_window_ms": 900,
            "skew_bound_ms": 2,
            "scroll_container_override": None,
        }
        real_probe = scroll._run_probe
        scroll._run_probe = lambda **kwargs: payload
        token = ACTIVE.set(run)
        old_argv = sys.argv
        sys.argv = [
            "adversarial_c10_scroll.py",
            "--fake-host",
            str(HOSTS),
            "--fake-page",
            "prose.html",
            "--out-root",
            str(out / "cell"),
            "--pairs",
            "1",
            "--editor",
            "b5-fake",
        ]
        try:
            scroll._main()
        finally:
            ACTIVE.reset(token)
            scroll._run_probe = real_probe
            sys.argv = old_argv
        trials = sorted((out / "cell").glob("attempts/*.json"))
        self.assertTrue(trials, "the cell wrote no trial")
        trial = json.loads(trials[0].read_text(encoding="utf-8"))
        self.assertNotIn(
            "cpu_throttled",
            str(trial.get("failure_reason")),
            "a prior throttled row refused this cell: %r" % (trial,),
        )
        self.assertEqual(trial.get("outcome"), "measured", "%r" % (trial,))
        self.assertTrue(trial.get("samples_ms"), "%r" % (trial,))

    def test_f6_the_throttle_refusal_is_evidence_not_a_string(self):
        self.assertTrue(
            hasattr(scroll, "throttle_refusal_reason"),
            "the lane has no throttle refusal: a throttled sample must not be published",
        )
        throttled = {
            "outcome": "failed",
            "failure_reason": "cpu_throttled",
            "cpu_accounting": {"available": True, "delta": {"nr_throttled": 1}},
        }
        self.assertEqual(
            scroll.throttle_refusal_reason(throttled),
            "cpu_throttled",
            "a throttled row must be refused: %r" % (throttled,),
        )
        # The same evidence, without the reason string: the accounting says it.
        # Lax layer (owner 2026-11-11): the refusal is governed by
        # throttled_usec above max(1 ms, 1 % of the span); the count alone
        # with a tolerated amount is kept (and disclosed on the row).
        renamed = {
            "outcome": "failed",
            "failure_reason": "the sample was refused",
            "cpu_accounting": {"available": True, "delta": {"nr_throttled": 3, "throttled_usec": 2500}},
        }
        self.assertEqual(
            scroll.throttle_refusal_reason(renamed),
            "cpu_throttled",
            "the accounting is the evidence, not the wording: %r" % (renamed,),
        )
        tolerated = {
            "outcome": "measured",
            "cpu_accounting": {"available": True, "delta": {"nr_throttled": 3, "throttled_usec": 900}},
        }
        self.assertIsNone(
            scroll.throttle_refusal_reason(tolerated),
            "throttling within max(1 ms, 1 %% of the span) is kept and disclosed: %r" % (tolerated,),
        )
        clean = {
            "outcome": "ok",
            "cpu_accounting": {"available": False, "delta": {"nr_throttled": 0}},
        }
        self.assertIsNone(
            scroll.throttle_refusal_reason(clean),
            "a clean row must not be refused: %r" % (clean,),
        )
        self.assertIsNone(
            scroll.throttle_refusal_reason(None),
            "a missing row must not be refused",
        )


if __name__ == "__main__":
    unittest.main()
