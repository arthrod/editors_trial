"""Chrome profile repetitions are diagnostic only (#fixtrace)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from functools import partial
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

_TREE = {"host_provenance": {"tree_sha256": "tree-fixture", "host_build": "production", "publishable": True}}


class ChromeProfileExclusion(unittest.TestCase):
    def test_truncated_profile_invoke_does_not_refuse_measured_launch(self):
        """Reviewer planted tree: truncated diagnostic json must not refuse the measured launch."""
        from perf.analysis.e2_cells import build_run_cell

        measured = {
            "criterion_id": "C11",
            "editor_id": "plate",
            "outcome": "measured",
            "publishable": True,
            "refusal_code": None,
            "samples_ms": [100.0],
            "sub_frame_samples": [False],
            "diagnostic": {"frame_interval_ms": 16.0},
            "environment": {"editor_id": "plate", "editor_version": "pin-1", "workload_id": "prose-500w"},
            **_TREE,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rep in range(12):
                cell = root / "cells" / f"{rep:04d}-plate"
                attempts = cell / "attempts"
                attempts.mkdir(parents=True)
                (attempts / "c11.json").write_text(json.dumps(measured))
            invoke = root / "cells" / "0011-plate" / "profile-invoke" / "attempts"
            invoke.mkdir(parents=True)
            (invoke / "c11-partial.json").write_text("{")
            (root / "samples").mkdir()
            for rep in range(12):
                (root / "samples" / f"{rep:04d}-plate.json").write_text(
                    json.dumps(
                        {
                            "editor_id": "plate",
                            "repetition": rep,
                            "outcome": "ok",
                            "accounting_scope": "sample",
                            "cell_directory": str(root / "cells" / f"{rep:04d}-plate"),
                        }
                    )
                )
            (root / "summary.json").write_text(
                json.dumps({"order": [(i, "plate") for i in range(12)], "publishable": True})
            )
            cell_row = build_run_cell(root, "plate", "C11", scheduled=12)
            self.assertEqual(len(cell_row["kept_ms"]), 12)
            self.assertNotIn("unreadable_trial", cell_row.get("refusals", {}))

    def test_verify_lane_profiles_skips_diagnostic_garbage(self):
        from perf.container.run import verify_lane_profiles

        trial = {
            "criterion_id": "C11",
            "editor_id": "plate",
            "outcome": "measured",
            "environment": {"execution_profile": "dedicated_publish", "host_class": "shared_guarded"},
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attempts = root / "cells" / "0011-plate" / "attempts"
            attempts.mkdir(parents=True)
            (attempts / "c11.json").write_text(json.dumps(trial))
            garbage = root / "cells" / "0011-plate" / "profile-invoke" / "attempts"
            garbage.mkdir(parents=True)
            (garbage / "c11-partial.json").write_text("{")
            verify_lane_profiles(root, "dedicated_publish", "shared_guarded")

    def test_profile_invoke_attempts_do_not_blank_cell(self):
        """Reviewer demo: nested profile-invoke attempts must not create conflicting_trials."""
        from perf.analysis.e2_cells import build_run_cell

        measured = {
            "criterion_id": "C11",
            "editor_id": "plate",
            "outcome": "measured",
            "publishable": True,
            "refusal_code": None,
            "samples_ms": [100.0],
            "sub_frame_samples": [False],
            "diagnostic": {"frame_interval_ms": 16.0},
            "environment": {"editor_id": "plate", "editor_version": "pin-1", "workload_id": "prose-500w"},
            **_TREE,
        }
        nested = {**measured, "accounting_scope": "sample"}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rep in range(12):
                cell = root / "cells" / f"{rep:04d}-plate"
                attempts = cell / "attempts"
                attempts.mkdir(parents=True)
                (attempts / "c11.json").write_text(json.dumps(measured))
                invoke = cell / "profile-invoke" / "attempts"
                invoke.mkdir(parents=True)
                (invoke / "c11.json").write_text(json.dumps(nested))
            (root / "samples").mkdir()
            for rep in range(12):
                (root / "samples" / f"{rep:04d}-plate.json").write_text(
                    json.dumps(
                        {
                            "editor_id": "plate",
                            "repetition": rep,
                            "outcome": "ok",
                            "accounting_scope": "sample",
                            "cell_directory": str(root / "cells" / f"{rep:04d}-plate"),
                        }
                    )
                )
            (root / "summary.json").write_text(
                json.dumps({"order": [(i, "plate") for i in range(12)], "publishable": True})
            )
            cell_row = build_run_cell(root, "plate", "C11", scheduled=12)
            self.assertEqual(len(cell_row["kept_ms"]), 12)
            self.assertNotIn("conflicting_trials", cell_row.get("refusals", {}))

    def test_pins_ignore_profiled_rows(self):
        from build.perf_e2_tables import Run, _pins, check_comparable

        measured = {
            "criterion_id": "C11",
            "editor_id": "plate",
            "outcome": "measured",
            "environment": {"editor_version": "abc123"},
        }
        profiled = {
            "criterion_id": "C11",
            "editor_id": "plate",
            "outcome": "profiled",
            "accounting_scope": "diagnostic",
            "publishable": False,
        }

        def seed(root: Path, *, extra_profiled: bool) -> None:
            attempts = root / "cells" / "0000-plate" / "attempts"
            attempts.mkdir(parents=True)
            (attempts / "c11.json").write_text(json.dumps(measured))
            if extra_profiled:
                (attempts / "profile-c11.json").write_text(json.dumps(profiled))
            (root / "summary.json").write_text(
                json.dumps(
                    {
                        "publishable": True,
                        "run_id": root.name,
                        "seed": 1 if root.name == "runA" else 2,
                        "execution_profile": "dedicated_publish",
                        "host_class": "shared_guarded",
                        "order": [(0, "plate")],
                        "host": {
                            "hostname": "h",
                            "kernel": "k",
                            "cpus": 4,
                            "memory_bytes": 1,
                            "container": False,
                        },
                        "rendering": {
                            "browser_version": "1",
                            "playwright_version": "1",
                            "vendor": "v",
                            "renderer": "r",
                            "headless": True,
                        },
                        "versions": {},
                    }
                )
            )

        with tempfile.TemporaryDirectory() as tmp:
            primary = Path(tmp) / "runA"
            repro = Path(tmp) / "runB"
            seed(primary, extra_profiled=True)
            seed(repro, extra_profiled=False)
            self.assertEqual(_pins(primary), {"plate": ["abc123"]})
            check_comparable(Run(primary, json.loads((primary / "summary.json").read_text())), Run(repro, json.loads((repro / "summary.json").read_text())))

    def test_criterion_table_groups_exclude_profiled(self):
        from build.perf_e2_tables import _criterion_table

        measured = {
            "criterion_id": "C10",
            "editor_id": "plate",
            "outcome": "measured",
            "publishable": True,
            "environment": {"workload_id": "prose-500w"},
            "diagnostic": {},
            **_TREE,
        }
        profiled = {
            "criterion_id": "C10",
            "editor_id": "plate",
            "outcome": "profiled",
            "accounting_scope": "diagnostic",
            "publishable": False,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attempts = root / "cells" / "0000-plate" / "attempts"
            attempts.mkdir(parents=True)
            (attempts / "c10.json").write_text(json.dumps(measured))
            (attempts / "profile-c10.json").write_text(json.dumps(profiled))
            (root / "summary.json").write_text(json.dumps({"order": [(0, "plate")], "publishable": True}))
            facts: dict = {}
            table = _criterion_table(facts, [root, root], "C10", ["plate"])
            self.assertNotIn("unspecified", table)

    def test_profile_pass_samples_are_diagnostic(self):
        from perf.runner.browser_run import BrowserRun, run_cli, ACTIVE, write_json

        samples_written: list[dict] = []

        def main():
            import argparse

            parser = argparse.ArgumentParser()
            parser.add_argument("--out-root", type=Path)
            parser.add_argument("--editors", nargs="+")
            args = parser.parse_args()
            run = ACTIVE.get()
            if run is not None and os.environ.get("PERF_CHROME_PROFILE") == "1":
                path = run.sample(
                    "c11-plate-diag",
                    {
                        "criterion_id": "C11",
                        "editor_id": "plate",
                        "outcome": "not_run",
                        "failure_reason": "profile_probe",
                    },
                )
                samples_written.append(json.loads(path.read_text()))
            attempts = args.out_root / "attempts"
            attempts.mkdir(parents=True, exist_ok=True)
            write_json(attempts / "c11.json", {"criterion_id": "C11", "editor_id": "plate", "outcome": "measured"})
            return 0

        original = sys.argv
        with tempfile.TemporaryDirectory() as tmp:
            try:
                sys.argv = [
                    "fake",
                    "--out-root",
                    tmp,
                    "--repetitions",
                    "1",
                    "--seed",
                    "1",
                    "--chrome-profile",
                    "--editors",
                    "plate",
                ]
                run_cli(
                    main,
                    "benchmark_document",
                    {"plate": {}},
                    run_factory=partial(BrowserRun, snapshot=lambda: {}),
                    facts=(lambda: {"container": False}, lambda: {"renderer": "fake"}),
                )
            finally:
                sys.argv = original
            summary = json.loads(next(Path(tmp).rglob("summary.json")).read_text())
            self.assertEqual(summary["cells_total"], 1)
            self.assertEqual(len(samples_written), 1)
            self.assertEqual(samples_written[0]["accounting_scope"], "diagnostic")

    def test_e2_cells_ignores_profiled_attempts(self):
        from perf.analysis.e2_cells import build_run_cell

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cell = root / "cells" / "0000-plate" / "attempts"
            cell.mkdir(parents=True)
            measured = {
                "criterion_id": "C11",
                "editor_id": "plate",
                "layer": "browser_visible",
                "boundary": "first_contentful_paint",
                "outcome": "measured",
                "publishable": True,
                "refusal_code": None,
                "samples_ms": [100.0],
                "sub_frame_samples": [False],
                "diagnostic": {"frame_interval_ms": 16.0},
                "environment": {"editor_id": "plate", "editor_version": "pin-1", "workload_id": "prose-500w"},
                **_TREE,
            }
            profiled = {
                **measured,
                "outcome": "profiled",
                "accounting_scope": "diagnostic",
                "publishable": False,
                "samples_ms": [],
            }
            (cell / "c11.json").write_text(json.dumps(measured))
            (cell / "profile-c11.json").write_text(json.dumps(profiled))
            (root / "samples").mkdir()
            for rep in range(30):
                (root / "samples" / f"{rep:04d}-plate.json").write_text(
                    json.dumps(
                        {
                            "editor_id": "plate",
                            "repetition": rep,
                            "outcome": "ok",
                            "accounting_scope": "sample",
                            "cell_directory": str(root / "cells" / f"{rep:04d}-plate"),
                        }
                    )
                )
                attempts = root / "cells" / f"{rep:04d}-plate" / "attempts"
                attempts.mkdir(parents=True, exist_ok=True)
                (attempts / "c11.json").write_text(json.dumps(measured))
                if rep == 0:
                    (attempts / "profile-c11.json").write_text(json.dumps(profiled))
            (root / "summary.json").write_text(
                json.dumps({"order": [(i, "plate") for i in range(30)], "publishable": True})
            )
            cell_row = build_run_cell(root, "plate", "C11")
            self.assertEqual(len(cell_row["kept_ms"]), 30)
            self.assertEqual(cell_row["scheduled"], 30)

    def test_cell_counts_skips_profiled(self):
        from perf.container.policy import cell_counts

        data = {
            "samples": [
                {
                    "editor_id": "plate",
                    "outcome": "ok",
                    "accounting_scope": "sample",
                    "cell_directory": "/fake/cell",
                }
            ]
        }
        trials = [
            {"criterion_id": "C11", "editor_id": "plate", "outcome": "measured"},
            {
                "criterion_id": "C11",
                "editor_id": "plate",
                "outcome": "profiled",
                "accounting_scope": "diagnostic",
                "publishable": False,
            },
        ]

        def reader(_row):
            return trials

        counts = cell_counts(data, trial_reader=reader)
        self.assertEqual(counts["measured"], 1)
        self.assertEqual(counts["trials_total"], 1)

    def test_profile_env_only_on_profile_pass(self):
        from perf.runner.browser_run import BrowserRun, run_cli, write_json

        env_seen = []

        def main():
            env_seen.append(os.environ.get("PERF_CHROME_PROFILE"))
            env_seen.append(os.environ.get("PERF_CHROME_PROFILE_DIR"))
            import argparse

            parser = argparse.ArgumentParser()
            parser.add_argument("--out-root", type=Path)
            parser.add_argument("--editors", nargs="+")
            args = parser.parse_args()
            write_json(args.out_root / "summary.json", {"outcome": "ok"})
            return 0

        original = sys.argv
        with tempfile.TemporaryDirectory() as tmp:
            try:
                sys.argv = [
                    "fake",
                    "--out-root",
                    tmp,
                    "--repetitions",
                    "1",
                    "--seed",
                    "1",
                    "--chrome-profile",
                    "--editors",
                    "plate",
                ]
                run_cli(
                    main,
                    "fake",
                    {"plate": {}},
                    run_factory=partial(BrowserRun, snapshot=lambda: {}),
                    facts=(lambda: {"container": False}, lambda: {"renderer": "fake"}),
                )
            finally:
                sys.argv = original
        self.assertEqual(env_seen[0], None)
        self.assertEqual(env_seen[1], None)
        self.assertEqual(env_seen[2], "1")
        self.assertTrue(env_seen[3].endswith("/cells/0000-plate/profile"))


class ChromeProfileAttempts(unittest.TestCase):
    def test_record_profile_traces_failure_does_not_abort_run(self):
        from perf.runner.browser_run import BrowserRun, run_cli, write_json

        original = sys.argv
        with tempfile.TemporaryDirectory() as tmp:
            try:
                sys.argv = [
                    "fake",
                    "--out-root",
                    tmp,
                    "--repetitions",
                    "1",
                    "--seed",
                    "1",
                    "--chrome-profile",
                    "--editors",
                    "plate",
                ]

                def main():
                    import argparse

                    parser = argparse.ArgumentParser()
                    parser.add_argument("--out-root", type=Path)
                    parser.add_argument("--editors", nargs="+")
                    args = parser.parse_args()
                    profile = args.out_root / "profile"
                    profile.mkdir(parents=True, exist_ok=True)
                    (profile / "trace-c11.json.gz").write_bytes(b"not-gzip")
                    attempts = args.out_root / "attempts"
                    attempts.mkdir(parents=True, exist_ok=True)
                    write_json(attempts / "c11.json", {"criterion_id": "C11", "editor_id": "plate", "outcome": "measured"})
                    return 0

                with mock.patch(
                    "perf.runner.chrome_profile.record_profile_traces",
                    side_effect=OSError("disk full"),
                ):
                    exit_code = run_cli(
                        main,
                        "benchmark_document",
                        {"plate": {}},
                        run_factory=partial(BrowserRun, snapshot=lambda: {}),
                        facts=(lambda: {"container": False}, lambda: {"renderer": "fake"}),
                    )
                self.assertIn(exit_code, (0, 3))
                summary_path = next(Path(tmp).rglob("summary.json"))
                self.assertTrue(summary_path.is_file())
            finally:
                sys.argv = original

    def test_finalize_writes_profile_attempt(self):
        from perf.runner.chrome_profile import record_profile_traces
        from perf.runner.artifacts import write_attempt

        with tempfile.TemporaryDirectory() as tmp:
            cell = Path(tmp)
            profile = cell / "profile"
            profile.mkdir(parents=True)
            trace = profile / "trace-c11.json.gz"
            trace.write_bytes(b"not-real-gzip")
            (cell / "attempts").mkdir()
            paths = record_profile_traces(cell, "plate", "C11", write_fn=write_attempt)
            self.assertEqual(len(paths), 1)
            row = json.loads(paths[0].read_text())
            self.assertEqual(row["outcome"], "profiled")
            self.assertEqual(row["accounting_scope"], "diagnostic")
            self.assertFalse(row["publishable"])
            self.assertIn("chrome_trace", row)


if __name__ == "__main__":
    unittest.main()
