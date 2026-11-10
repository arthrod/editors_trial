"""Issue #136: publication sample counts, e2 cells, sub-frame text, shared_guarded."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import pytest
from functools import partial
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.analysis import e2_cells  # noqa: E402
from perf.runner import browser_run as api  # noqa: E402
from perf.runner.browser_run import run_cli  # noqa: E402
from perf.runner.criteria_input_io import assert_payload_shape, trials_from_payload  # noqa: E402
from perf.runner.policy import publication_decision  # noqa: E402
from perf.runner.browser_run import PUBLICATION_REPETITIONS  # noqa: E402
from perf.runner.speed_headless import MIN_PUBLISH_N  # noqa: E402
from perf.schema import validate_environment  # noqa: E402
from perf.tests.test_b4_input_criteria import (  # noqa: E402
    B4_FIXTURES,
    EXPECTED_BODY,
    WARM_COLD,
    _entry,
    _payload,
    _witness,
    fixture_identity,
)
from perf.tests.test_input_criteria import PAINT_MECHANISM  # noqa: E402

UI = REPO / "harness" / "ui"


def _env(**overrides):
    base = {
        "host_class": "dedicated",
        "cache_state": "warm_steady",
        "run_kind": "timing",
        "repetition_unit": "fresh_process",
        "execution_profile": "dedicated_publish",
        "headless": True,
        "feature_profile": "P0",
        "cpu_model": "x",
        "os": "linux",
        "arch": "x86_64",
        "power_source": "ac",
        "editor_id": "plate",
        "editor_version": "1",
        "workload_id": "micro-paragraphs",
        "fixture_sha256": "a" * 64,
        "fixture_byte_size": 512,
        "fixture_paragraph_count": 2,
        "paragraph_shape": "short",
        "unicode_class": "ascii",
        "match_count": 0,
        "ram_bytes": 8_000_000_000,
        "interpretation_conditions": [f"I{i:02d}" for i in range(1, 13)],
        "page_cache_dropped": False,
        "display_refresh_hz": None,
    }
    base.update(overrides)
    return base


def _trial(editor: str, criterion: str, outcome: str, samples=None, **extra):
    row = {
        "schema_version": 1,
        "criterion_id": criterion,
        "editor_id": editor,
        "outcome": outcome,
        "samples_ms": samples or [],
        "layer": "browser_visible",
        "boundary": "input_to_next_paint",
        "environment": _env(editor_id=editor),
        "diagnostic": {"frame_interval_ms": 16.7},
    }
    row.update(extra)
    row.setdefault('publishable', outcome == 'measured')
    row.setdefault('refusal_code', None if outcome == 'measured' else 'crash')
    frame = row.get('diagnostic', {}).get('frame_interval_ms')
    row.setdefault('sub_frame_samples', [bool(frame and isinstance(x, (int, float)) and x < frame) for x in (samples or [])])
    return row


def _write_trial(root: Path, rep: int, editor: str, criterion: str, **kwargs):
    cell_dir = root / "cells" / f"{rep:04d}-{editor}"
    cell = cell_dir / "attempts"
    cell.mkdir(parents=True, exist_ok=True)
    path = cell / f"{criterion.lower()}.json"
    trial = _trial(editor, criterion, **kwargs)
    path.write_text(json.dumps(trial), encoding="utf-8")
    sample_dir = root / "samples"
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample = {
        "outcome": "ok",
        "editor_id": editor,
        "repetition": rep,
        "cell_directory": str(cell_dir),
    }
    if kwargs.get("outcome") != "measured" or kwargs.get("publishable") is False:
        sample["outcome"] = "failed"
        sample["failure_reason"] = kwargs.get("publication_block_reason") or kwargs.get("failure_reason") or "unmeasured"
    (sample_dir / f"{rep:04d}-{editor}.json").write_text(json.dumps(sample), encoding="utf-8")
    return path


def _write_summary(root: Path, editor: str, repetitions: int, **extra):
    order = [(rep, editor) for rep in range(repetitions)]
    (root / "summary.json").write_text(
        json.dumps({"order": order, "publishable": True, **extra}),
        encoding="utf-8",
    )


class PublicationRepetitions(unittest.TestCase):
    def test_dedicated_publish_schedules_thirty_per_editor_without_count_flag(self):
        calls = []

        def main():
            calls.append(1)
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            original = sys.argv
            try:
                sys.argv = [
                    "fake",
                    "--out-root",
                    tmp,
                    "--seed",
                    "7",
                    "--execution-profile",
                    "dedicated_publish",
                    "--host-class",
                    "dedicated",
                    "--editors",
                    "a",
                    "b",
                ]
                code = run_cli(
                    main,
                    "fake",
                    {"a": {}, "b": {}},
                    count_flag="--samples",
                    default_count=3,
                    run_factory=partial(api.BrowserRun, snapshot=lambda: {}),
                    facts=(lambda: {}, lambda: {}),
                )
                self.assertEqual(code, 0)
                summary = json.loads(next(Path(tmp).glob("fake/*/summary.json")).read_text())
                self.assertEqual(len(summary["order"]), PUBLICATION_REPETITIONS * 2)
                self.assertEqual(len(calls), PUBLICATION_REPETITIONS * 2)
            finally:
                sys.argv = original

    def test_dedicated_publish_refuses_equals_form_count_below_thirty(self):
        original = sys.argv
        try:
            sys.argv = [
                "fake",
                "--samples=29",
                "--execution-profile",
                "dedicated_publish",
                "--host-class",
                "dedicated",
            ]
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf), self.assertRaises(SystemExit) as caught:
                run_cli(
                    lambda: self.fail("must not run"),
                    "fake",
                    {"a": {}},
                    count_flag="--samples",
                )
            self.assertEqual(caught.exception.code, 2)
            self.assertIn("#136", buf.getvalue())
        finally:
            sys.argv = original

    def test_dedicated_publish_refuses_explicit_count_below_thirty(self):
        original = sys.argv
        try:
            sys.argv = [
                "fake",
                "--samples",
                "29",
                "--execution-profile",
                "dedicated_publish",
                "--host-class",
                "dedicated",
            ]
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf), self.assertRaises(SystemExit) as caught:
                run_cli(
                    lambda: self.fail("must not run"),
                    "fake",
                    {"a": {}},
                    count_flag="--samples",
                )
            self.assertEqual(caught.exception.code, 2)
            self.assertIn("#136", buf.getvalue())
        finally:
            sys.argv = original


@pytest.mark.usefixtures("fs")
class E2Cells(unittest.TestCase):
    def test_nine_kept_samples_not_enough(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        for rep in range(9):
            _write_trial(root, rep, "plate", "C07", outcome="measured", samples=[20.0])
        _write_summary(root, "plate", 30)
        cell = e2_cells.build_run_cell(root, "plate", "C07", scheduled=30)
        text = e2_cells.publication_text(cell)
        self.assertIn("not enough samples", text)
        self.assertIn(f"n = 9 of 30", text)

    def test_ten_kept_samples_publish_figure(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        for rep in range(10):
            _write_trial(root, rep, "plate", "C07", outcome="measured", samples=[20.0])
        _write_summary(root, "plate", 30)
        cell = e2_cells.build_run_cell(root, "plate", "C07", scheduled=30)
        text = e2_cells.publication_text(cell)
        self.assertIn("20.0 ms", text)
        self.assertNotIn("not enough", text)

    def test_reproduction_failure_blocks_publication(self):
        primary = Path(tempfile.mkdtemp())
        reproduction = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(primary, ignore_errors=True))
        self.addCleanup(lambda: __import__("shutil").rmtree(reproduction, ignore_errors=True))
        for rep in range(10):
            _write_trial(primary, rep, "plate", "C07", outcome="measured", samples=[20.0])
        for rep in range(9):
            _write_trial(reproduction, rep, "plate", "C07", outcome="measured", samples=[20.0])
        for seed, root in enumerate((primary, reproduction)):
            (root / "summary.json").write_text(json.dumps({
                "run_id": str(seed), "seed": seed,
                "execution_profile": "dedicated_publish", "publishable": True,
                "order": [[i, "plate"] for i in range(30)],
            }))
        text = e2_cells.publish_dual_runs(primary, reproduction, "plate", "C07", scheduled=30)
        self.assertIn("not enough samples", text)

    def test_reproduction_median_mismatch_not_published(self):
        primary = Path(tempfile.mkdtemp())
        reproduction = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(primary, ignore_errors=True))
        self.addCleanup(lambda: __import__("shutil").rmtree(reproduction, ignore_errors=True))
        for rep in range(10):
            _write_trial(primary, rep, "plate", "C07", outcome="measured", samples=[20.0])
            _write_trial(reproduction, rep, "plate", "C07", outcome="measured", samples=[900.0])
        _write_summary(primary, "plate", 30, execution_profile="dedicated_publish", run_id="primary", seed=1)
        _write_summary(reproduction, "plate", 30, execution_profile="dedicated_publish", run_id="reproduction", seed=2)
        text = e2_cells.publish_dual_runs(primary, reproduction, "plate", "C07", scheduled=30)
        self.assertIn("not reproduced", text)

    def test_sub_frame_median_renders_bucket_not_number(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        for rep in range(10):
            _write_trial(
                root,
                rep,
                "plate",
                "C07",
                outcome="measured",
                samples=[9.9],
                sub_frame_samples=[True],
            )
        _write_summary(root, "plate", 30)
        cell = e2_cells.build_run_cell(root, "plate", "C07", scheduled=30)
        text = e2_cells.publication_text(cell)
        self.assertIn("< 1 frame (16.7 ms)", text)
        self.assertNotIn("9.9", text)

    def test_median_twenty_ms_renders_number(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        for rep in range(10):
            _write_trial(root, rep, "plate", "C07", outcome="measured", samples=[20.0])
        _write_summary(root, "plate", 30)
        text = e2_cells.publication_text(e2_cells.build_run_cell(root, "plate", "C07", scheduled=30))
        self.assertIn("20.0 ms", text)


class SharedGuarded(unittest.TestCase):
    def test_schema_admits_shared_guarded_on_dedicated_publish(self):
        validate_environment(_env(host_class="shared_guarded"))

    def test_ci_coarse_unchanged(self):
        with self.assertRaises(ValueError):
            validate_environment(_env(host_class="ci_coarse"))

    def test_shared_guarded_refused_without_accounting(self):
        original = sys.argv
        try:
            sys.argv = [
                "fake",
                "--execution-profile",
                "dedicated_publish",
                "--host-class",
                "shared_guarded",
            ]
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                run_cli(
                    lambda: self.fail("must not run"),
                    "fake",
                    {"a": {}},
                    run_factory=partial(
                        api.BrowserRun,
                        snapshot=lambda: {},
                        accounting_reader=lambda: {"available": False, "reason": "missing"},
                    ),
                    facts=(lambda: {}, lambda: {}),
                )
            self.assertEqual(caught.exception.code, 2)
        finally:
            sys.argv = original

    def test_shared_guarded_refused_with_unlimited_quota(self):
        original = sys.argv
        try:
            sys.argv = [
                "fake",
                "--execution-profile",
                "dedicated_publish",
                "--host-class",
                "shared_guarded",
            ]
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                run_cli(
                    lambda: self.fail("must not run"),
                    "fake",
                    {"a": {}},
                    run_factory=partial(
                        api.BrowserRun,
                        snapshot=lambda: {},
                        accounting_reader=lambda: {
                            "available": True,
                            "nr_periods": 0,
                            "nr_throttled": 0,
                            "throttled_usec": 0,
                            "cpu_ticks": {"total": 1, "steal": 0},
                            "loadavg": [0.0, 0.0, 0.0],
                            "cpu_max": "max 100000",
                            "cpu_count_visible": 8,
                            "cgroup_path": "/sys/fs/cgroup",
                        },
                    ),
                    facts=(lambda: {}, lambda: {}),
                )
            self.assertEqual(caught.exception.code, 2)
        finally:
            sys.argv = original

    def test_shared_guarded_admitted_with_accounting(self):
        calls = []

        def main():
            calls.append(1)
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            original = sys.argv
            try:
                sys.argv = [
                    "fake",
                    "--out-root",
                    tmp,
                    "--execution-profile",
                    "dedicated_publish",
                    "--host-class",
                    "shared_guarded",
                    "--editors",
                    "a",
                ]
                code = run_cli(
                    main,
                    "fake",
                    {"a": {}},
                    run_factory=partial(
                        api.BrowserRun,
                        snapshot=lambda: {},
                        accounting_reader=lambda: {
                            "available": True,
                            "nr_periods": 0,
                            "nr_throttled": 0,
                            "throttled_usec": 0,
                            "cpu_ticks": {"total": 1, "steal": 0},
                            "loadavg": [0.0, 0.0, 0.0],
                            "cpu_max": "50000 100000",
                            "cpu_count_visible": 8,
                            "cgroup_path": "/sys/fs/cgroup",
                        },
                    ),
                    facts=(lambda: {}, lambda: {}),
                )
                self.assertEqual(code, 0)
                self.assertEqual(len(calls), PUBLICATION_REPETITIONS)
                summary = json.loads(next(Path(tmp).glob("fake/*/summary.json")).read_text())
                self.assertEqual(summary["host_class"], "shared_guarded")
                self.assertIn("cpu_throttle_refused_samples", summary)
                self.assertIn("cpu_steal_percent", summary)
            finally:
                sys.argv = original

    def test_policy_os_cache_cold_not_for_shared_guarded(self):
        with self.assertRaises(ValueError):
            publication_decision(
                {
                    "host_class": "shared_guarded",
                    "cache_state": "os_cache_cold",
                    "run_kind": "timing",
                    "repetition_unit": "fresh_process",
                },
                "browser_visible",
            )


class SubFrameProbe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil_which("node") is None:
            raise unittest.SkipTest("node required for criteria probe")
        if not UI.is_dir():
            raise unittest.SkipTest("harness ui missing")
        if not WARM_COLD.is_file():
            raise unittest.SkipTest("warm_cold_browser.mjs missing")

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        from perf.fixtures.generate import docx_zip_bytes

        self.docx = Path(self._tmpdir.name) / "corpus.docx"
        self.docx.write_bytes(docx_zip_bytes(EXPECTED_BODY.encode("utf-8")))
        self.body_file = Path(self._tmpdir.name) / "expected.txt"
        self.body_file.write_text(EXPECTED_BODY, encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _load_b4_server(self):
        spec = importlib.util.spec_from_file_location("b4_host_server", B4_FIXTURES / "server.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(module)
        return module

    def _run_host(self, page: str, *, criteria: str = "C07"):
        server = self._load_b4_server()
        httpd, thread, base = server.serve(B4_FIXTURES)
        try:
            env = {
                **os.environ,
                "PERF_EXPECTED_BODY_PATH": str(self.body_file),
                "PERF_CORRECTNESS_ADAPTER": "dom_innerText",
            }
            proc = subprocess.run(
                [
                    "node",
                    str(WARM_COLD),
                    "--driver",
                    "playwright",
                    "--editor",
                    "b4-fake",
                    "--criteria",
                    criteria,
                    "--url",
                    base + page,
                    "--corpus",
                    str(self.docx),
                    "--corpus-route",
                    "/corpus.docx",
                    "--ready-selector",
                    "#ready",
                    "--edit-selector",
                    "#doc",
                    "--quiescence-ms",
                    "200",
                    "--quiescence-timeout",
                    "3000",
                    "--frame-timeout",
                    "4000",
                    "--bulk-chars",
                    "100",
                ],
                cwd=str(UI),
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr[-1500:] + proc.stdout[-500:])
            return json.loads(proc.stdout)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_sub_frame_payload_kept_measured(self):
        entry = _entry(
            samples_ms=[9.5, 10.1, 8.8],
            sub_frame_samples=[True, True, True],
            trial_hints={"cache_state": "warm_steady", "repetition_unit": "fresh_process"},
        )
        payload = _payload({"C07": entry}, witness=_witness())
        assert_payload_shape(payload)
        row, sha, size = fixture_identity()
        trial = trials_from_payload(
            payload,
            editor_version="b4-fake",
            fixture_sha256=sha,
            workload_row=row,
            docx_size=size,
        )["C07"]
        self.assertEqual(trial["outcome"], "measured")
        self.assertTrue(trial.get("sub_frame_samples"))

    def test_sub_frame_fake_host_when_probe_works(self):
        payload = self._run_host("sub_frame.html", criteria="C07")
        c07 = payload["criteria"]["C07"]
        if c07["outcome"] != "measured":
            self.skipTest(f"fake host did not measure in this environment: {c07.get('failure_reason')}")
        flags = c07.get("sub_frame_samples") or []
        self.assertTrue(any(flags), c07)


class B7FixRound(unittest.TestCase):
    def test_throttle_refused_sample_not_counted_as_kept(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        _write_trial(root, 0, "plate", "C07", outcome="measured", samples=[20.0])
        sample_path = root / "samples" / "0000-plate.json"
        row = json.loads(sample_path.read_text())
        row.update(outcome="failed", failure_reason="cpu_throttled", refusal_code="cpu_throttled")
        sample_path.write_text(json.dumps(row), encoding="utf-8")
        _write_summary(root, "plate", 30)
        cell = e2_cells.build_run_cell(root, "plate", "C07", scheduled=30)
        self.assertEqual(cell["kept_ms"], [])
        self.assertIn("cpu_throttled", cell["refusals"])

    def test_failed_run_summary_blocks_cell_figure(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        for rep in range(10):
            _write_trial(root, rep, "plate", "C07", outcome="measured", samples=[20.0])
        _write_summary(
            root,
            "plate",
            30,
            outcome="failed",
            failure_reason="repos_modified",
            publishable=False,
            publication_block_reason="cpu_accounting_unavailable",
        )
        text = e2_cells.publication_text(e2_cells.build_run_cell(root, "plate", "C07", scheduled=30))
        self.assertIn("run not publishable", text)

    def test_n_counts_repetitions_not_clicks(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        for rep in range(4):
            _write_trial(root, rep, "plate", "C07", outcome="measured", samples=[10.0, 20.0, 30.0])
        _write_summary(root, "plate", 30)
        cell = e2_cells.build_run_cell(root, "plate", "C07", scheduled=30)
        self.assertEqual(cell["stats"]["n"], 4)
        self.assertIn("not enough samples", e2_cells.publication_text(cell))

    def test_no_frame_interval_withholds_numeric_sub_frame(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        for rep in range(10):
            _write_trial(
                root,
                rep,
                "plate",
                "C07",
                outcome="measured",
                samples=[20.0],
                sub_frame_samples=[True],
                diagnostic={},
            )
            trial_path = root / "cells" / f"{rep:04d}-plate" / "attempts" / "c07.json"
            trial = json.loads(trial_path.read_text())
            trial["diagnostic"] = {}
            trial_path.write_text(json.dumps(trial), encoding="utf-8")
        _write_summary(root, "plate", 30)
        text = e2_cells.publication_text(e2_cells.build_run_cell(root, "plate", "C07", scheduled=30))
        self.assertIn("sub_frame_flag_mismatch", text)
        self.assertIn("n = 0", text)

    def test_non_publishable_trial_not_counted(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        for rep in range(10):
            _write_trial(
                root,
                rep,
                "plate",
                "C07",
                outcome="measured",
                samples=[20.0],
                publishable=False,
                publication_block_reason="visible latency requires fresh_process",
            )
        _write_summary(root, "plate", 30)
        cell = e2_cells.build_run_cell(root, "plate", "C07", scheduled=30)
        self.assertEqual(cell["kept_ms"], [])
        self.assertEqual(cell["refusals"].get("publishable_not_true"), 10)

    def test_run_cli_exposes_profile_through_active_context(self):
        seen = []

        def main():
            seen.append((list(sys.argv), api.execution_profile(), api.host_class()))
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            original = sys.argv
            try:
                sys.argv = [
                    "fake",
                    "--out-root",
                    tmp,
                    "--execution-profile",
                    "dedicated_publish",
                    "--host-class",
                    "shared_guarded",
                    "--editors",
                    "a",
                ]
                run_cli(
                    main,
                    "fake",
                    {"a": {}},
                    count_flag="--samples",
                    default_count=3,
                    run_factory=partial(
                        api.BrowserRun,
                        snapshot=lambda: {},
                        accounting_reader=lambda: {
                            "available": True,
                            "nr_periods": 0,
                            "nr_throttled": 0,
                            "throttled_usec": 0,
                            "cpu_ticks": {"total": 1, "steal": 0},
                            "loadavg": [0.0, 0.0, 0.0],
                            "cpu_max": "50000 100000",
                            "cpu_count_visible": 8,
                            "cgroup_path": "/sys/fs/cgroup",
                        },
                    ),
                    facts=(lambda: {}, lambda: {}),
                )
                self.assertEqual(len(seen), PUBLICATION_REPETITIONS)
                for argv, profile, host in seen:
                    self.assertNotIn("--host-class", argv)
                    self.assertNotIn("--execution-profile", argv)
                    self.assertEqual(profile, "dedicated_publish")
                    self.assertEqual(host, "shared_guarded")
            finally:
                sys.argv = original


class PolicyConflict(unittest.TestCase):
    def test_c07_in_process_iteration_blocks_visible_publication(self):
        with self.assertRaises(ValueError) as caught:
            publication_decision(
                {
                    "host_class": "dedicated",
                    "cache_state": "warm_steady",
                    "run_kind": "timing",
                    "repetition_unit": "in_process_iteration",
                },
                "browser_visible",
            )
        self.assertIn("fresh_process", str(caught.exception))


def shutil_which(cmd):
    from shutil import which

    return which(cmd)


if __name__ == "__main__":
    unittest.main()
