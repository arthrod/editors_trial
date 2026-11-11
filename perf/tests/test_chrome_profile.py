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


class ChromeProfileExclusion(unittest.TestCase):
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
                "environment": {"editor_id": "plate", "workload_id": "prose-500w"},
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
