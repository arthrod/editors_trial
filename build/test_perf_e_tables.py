"""Report E's facts come from the speed runner's own sample files (editors_trial#111).

Two fake editors stand in for real ones; the runner is the real one, on a
simulated quiet, AC-powered host, so the facts builder reads exactly what a
publication run writes.
"""

from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT))

import perf_e_tables as E
from perf.analysis.anti_ranking import assert_markdown_no_editor_speed_ranking
from perf.runner import speed_headless as sh

FAKE = textwrap.dedent(
    """
    import os, shutil, sys
    load = float(os.environ["FAKE_LOAD"]); save = float(os.environ["FAKE_SAVE"])
    print("PERF model_ready_ms=%s" % load)
    print("PERF save_ms=%s" % save)
    if os.environ.get("FAKE_MODE") == "crash":
        sys.exit(1)
    shutil.copyfile(sys.argv[1], sys.argv[2])
    """
)


def _lane(script: Path, load: float, save: float, mode: str = "ok") -> dict:
    return {
        "cmd": lambda i, o, w: [sys.executable, str(script), str(i), str(o)],
        "cwd": ROOT,
        "env": {"FAKE_LOAD": str(load), "FAKE_SAVE": str(save), "FAKE_MODE": mode},
        "marks": ("model_ready_ms", "save_ms"),
        "boundary": "fake",
    }


def _run(root: Path, name: str, lanes: dict, reps: int, seed: int) -> Path:
    quiet = {"quiet": True, "reasons": [], "load_average": [0.5, 0.5, 0.5]}
    host = dict(sh.host_record(), power_source="ac")
    attest = {"tools": {"node": "v0", "bun": "0", "python": "3"}, "editors": {e: {"pin": "p", "matches_pin": True, "checkouts": {}, "packages": {}, "binaries": {}} for e in lanes}}
    out = root / name
    with mock.patch.object(sh, "quiet_machine_check", return_value=quiet), mock.patch.object(
        sh, "host_record", return_value=host
    ), mock.patch.object(sh, "attest_versions", return_value=attest), mock.patch.object(
        sh, "pin_label", side_effect=lambda e: "pin-%s" % e
    ), mock.patch("os.getloadavg", return_value=(0.5, 0.5, 0.5)):
        sh.run_suite(
            lanes=lanes, workloads=["prose-500w"], repetitions=reps, seed=seed, out_root=out,
            execution_profile="dedicated_publish", timeout_s=60, warmup=1,
        )
    return out


class ReportEFacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        script = root / "fake.py"
        script.write_text(FAKE, encoding="utf-8")
        primary = {"wordcraft": _lane(script, 2.0, 1.0), "plate": _lane(script, 100.0, 50.0), "canvas": _lane(script, 1, 1, mode="crash")}
        # The reproduction agrees for wordcraft and plate's load, and not for plate's save.
        repro = {"wordcraft": _lane(script, 2.1, 1.0), "plate": _lane(script, 101.0, 80.0), "canvas": _lane(script, 1, 1, mode="crash")}
        cls.primary = _run(root, "primary", primary, reps=10, seed=1)
        cls.repro = _run(root, "repro", repro, reps=10, seed=2)
        cls.facts = E.facts_from_runs(cls.primary, cls.repro)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_round_trip_is_the_per_sample_sum_of_load_and_save(self):
        self.assertEqual(self.facts["perf.e.wordcraft.prose-500w.load.median"], 2.0)
        self.assertEqual(self.facts["perf.e.wordcraft.prose-500w.save.median"], 1.0)
        self.assertEqual(self.facts["perf.e.wordcraft.prose-500w.roundtrip.median"], 3.0)
        self.assertEqual(self.facts["perf.e.wordcraft.prose-500w.roundtrip.n"], 10)
        self.assertEqual(self.facts["perf.e.plate.prose-500w.load.median"], 100.0)
        # plate's save (50 vs 80) and so its round trip (150 vs 181) do not reproduce: no figure.
        self.assertNotIn("perf.e.plate.prose-500w.save.median", self.facts)
        self.assertNotIn("perf.e.plate.prose-500w.roundtrip.median", self.facts)

    def test_a_figure_is_published_only_when_the_second_run_reproduces_it(self):
        table = self.facts["perf.e.table.load"]
        self.assertIn("100", table)
        save = self.facts["perf.e.table.save"]
        self.assertIn("not reproduced", save)  # plate's save: 50 vs 80
        self.assertNotIn("| 50 ", save)
        self.assertIn("perf.e.plate.prose-500w.save.reproduced", self.facts)
        self.assertFalse(self.facts["perf.e.plate.prose-500w.save.reproduced"])
        self.assertTrue(self.facts["perf.e.wordcraft.prose-500w.load.reproduced"])

    def test_tiny_figures_reproduce_within_the_absolute_tolerance(self):
        self.assertTrue(E.reproduced(0.6, 0.7))
        self.assertTrue(E.reproduced(1000.0, 1080.0))
        self.assertFalse(E.reproduced(1000.0, 1200.0))

    def test_a_crash_is_shown_as_a_failure_never_a_number(self):
        table = self.facts["perf.e.table.roundtrip"]
        row = next(line for line in table.splitlines() if line.startswith("| canvas"))
        self.assertIn("failed", row)
        self.assertNotIn("perf.e.canvas.prose-500w.roundtrip.median", self.facts)

    def test_rows_are_alphabetical_not_ranked(self):
        table = self.facts["perf.e.table.roundtrip"]
        rows = [line.split("|")[1].strip() for line in table.splitlines()[2:]]
        self.assertEqual(rows, sorted(rows, key=str.casefold))

    def test_tables_pass_the_anti_ranking_guard_and_name_their_context(self):
        for key in ("perf.e.table.roundtrip", "perf.e.table.load", "perf.e.table.save", "perf.e.table.process", "perf.e.appendix"):
            assert_markdown_no_editor_speed_ranking(self.facts[key])
        self.assertIn("process_cold_fs_warm", self.facts["perf.e.context.load"])
        self.assertIn("Apple", self.facts["perf.e.host"])
        self.assertIn("AC", self.facts["perf.e.host"])

    def test_appendix_carries_the_full_distribution(self):
        appendix = self.facts["perf.e.appendix"]
        for column in ("n", "median", "p90", "p95", "p99", "MAD", "95% CI", "min", "max"):
            self.assertIn(column, appendix)

    def test_run_identity_and_counts(self):
        self.assertEqual(self.facts["perf.e.n"], 10)
        self.assertEqual(self.facts["perf.e.repro_n"], 10)
        self.assertNotEqual(self.facts["perf.e.run_id"], self.facts["perf.e.repro_run_id"])
        self.assertEqual(self.facts["perf.e.seed"], 1)
        self.assertEqual(self.facts["perf.e.repro_seed"], 2)

    def test_an_output_identical_to_its_input_is_detected_from_the_hashes(self):
        # the fake editors copy their input, so every one of them is a pass-through
        self.assertIn("WordCraft", self.facts["perf.e.passthrough"])
        self.assertIn("Plate.js", self.facts["perf.e.passthrough"])

    def test_every_failed_or_unreproduced_cell_is_listed_with_its_reason(self):
        listing = self.facts["perf.e.exceptions"]
        self.assertIn("canvas-editor + plugin", listing)
        self.assertIn("crashed (exit 1)", listing)
        self.assertIn("Plate.js", listing)
        self.assertIn("not reproduced", listing)

    def test_lost_correctness_strings_are_reported(self):
        self.assertEqual(self.facts["perf.e.correctness_lost"], "none")

    def test_a_non_publication_run_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "summary.json"
            data = json.loads((self.primary / "summary.json").read_text())
            data["execution_profile"] = "ci_broad"
            bad.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                E.load_run(Path(tmp))


if __name__ == "__main__":
    unittest.main()
