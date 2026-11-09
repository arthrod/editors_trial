"""Report E's facts come from the speed runner's own sample files (editors_trial#111).

Two fake editors stand in for real ones; the runner is the real one, on a
simulated quiet, AC-powered host, so the facts builder reads exactly what a
publication run writes.
"""

from __future__ import annotations

import json
import shutil
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
    import subprocess, time
    load = float(os.environ["FAKE_LOAD"]); save = float(os.environ["FAKE_SAVE"])
    print("PERF model_ready_ms=%s" % load)
    print("PERF save_ms=%s" % save)
    if os.environ.get("FAKE_HOST_START"):
        print("PERF host_start_ms=%s" % os.environ["FAKE_HOST_START"])
    if os.environ.get("FAKE_CHILD"):
        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
    if os.environ.get("FAKE_MODE") == "crash":
        sys.exit(1)
    shutil.copyfile(sys.argv[1], sys.argv[2])
    """
)


def _lane(script: Path, load: float, save: float, mode: str = "ok", marks=("model_ready_ms", "save_ms"), **env) -> dict:
    return {
        "cmd": lambda i, o, w: [sys.executable, str(script), str(i), str(o)],
        "cwd": ROOT,
        "env": dict({"FAKE_LOAD": str(load), "FAKE_SAVE": str(save), "FAKE_MODE": mode}, **env),
        "marks": tuple(marks),
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
    ), mock.patch.object(sh, "_build_lanes", return_value={}), mock.patch.object(
        sh, "power_source", return_value="ac"
    ), mock.patch("os.getloadavg", return_value=(0.5, 0.5, 0.5)):
        sh.run_suite(
            lanes=lanes, workloads=["prose-500w"], repetitions=reps, seed=seed, out_root=out,
            execution_profile="dedicated_publish", timeout_s=60, warmup=1,
        )
    return out


_MODULE: dict = {}


def setUpModule():
    tmp = tempfile.TemporaryDirectory()
    _MODULE["tmp"] = tmp
    root = Path(tmp.name)
    script = root / "fake.py"
    script.write_text(FAKE, encoding="utf-8")
    primary = {"wordcraft": _lane(script, 2.0, 1.0), "plate": _lane(script, 100.0, 50.0), "canvas": _lane(script, 1, 1, mode="crash")}
    # The reproduction agrees for wordcraft and plate's load, and not for plate's save.
    repro = {"wordcraft": _lane(script, 2.1, 1.0), "plate": _lane(script, 101.0, 80.0), "canvas": _lane(script, 1, 1, mode="crash")}
    _MODULE["primary"] = _run(root, "primary", primary, reps=10, seed=1)
    _MODULE["repro"] = _run(root, "repro", repro, reps=10, seed=2)


def tearDownModule():
    _MODULE["tmp"].cleanup()


class ReportEFacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.primary, cls.repro = _MODULE["primary"], _MODULE["repro"]
        cls.facts = E.facts_from_runs(cls.primary, cls.repro)

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

    def test_the_summary_has_one_plain_bullet_per_editor_from_published_cells_only(self):
        summary = self.facts["perf.e.summary"].splitlines()
        self.assertEqual(len(summary), 3)
        self.assertEqual([b.split("**")[1] for b in summary], ["canvas-editor + plugin.", "Plate.js.", "WordCraft."])
        wordcraft = summary[2]
        self.assertIn("3.0 ms at 500 words", wordcraft)
        self.assertIn("not published", summary[1])  # plate's round trip did not reproduce
        self.assertIn("crashed (exit 1)", summary[0])
        for word in ("fastest", "slowest", "faster", "slower", "best", "worst", "winner"):
            self.assertNotIn(word, self.facts["perf.e.summary"].lower())

    def test_what_each_timer_includes_and_the_versions_come_from_the_run(self):
        lanes = self.facts["perf.e.lanes"]
        self.assertIn("| WordCraft | fake |", lanes)
        versions = self.facts["perf.e.versions"]
        self.assertIn("Plate.js", versions)
        self.assertIn("node v0", versions)

    def test_the_appendix_prints_no_distribution_for_a_cell_that_did_not_reproduce(self):
        row = next(line for line in self.facts["perf.e.appendix"].splitlines() if line.startswith("| Plate.js"))
        self.assertIn("not reproduced", row)
        self.assertNotIn("150", row)
        wordcraft = next(line for line in self.facts["perf.e.appendix"].splitlines() if line.startswith("| WordCraft"))
        self.assertIn("| 10 | 3.0 |", wordcraft)

    def test_a_whole_process_cell_needs_a_publishable_primary(self):
        def rec(noisy=False, good=True):
            return {"returncode": 0 if good else 1, "timed_out": False, "check": {"complete": good}, "noisy": noisy,
                    "marks": {}, "wall_ms": 5.0, "cpu_ms": 5.0, "max_rss_bytes": 1, "power_source": "ac"}
        run = E.Run(Path("."), {"workloads": {}, "repetitions": 10})
        run.records["w", "e"] = [rec() for _ in range(10)]
        self.assertEqual(E._samples_publishable(run, "w", "e"), (True, None))
        run.records["w", "e"] = [rec() for _ in range(9)]
        self.assertFalse(E._samples_publishable(run, "w", "e")[0])
        run.records["w", "e"] = [rec() for _ in range(9)] + [rec(good=False)]
        self.assertIn("excluded", E._samples_publishable(run, "w", "e")[1])
        run.records["w", "e"] = [rec(noisy=True) for _ in range(2)] + [rec() for _ in range(8)]
        self.assertIn("load limit", E._samples_publishable(run, "w", "e")[1])

    def test_a_save_that_stays_flat_while_load_grows_is_named(self):
        facts = {
            "perf.e.sd.prose-5kw.save.median": 3.0, "perf.e.sd.prose-250kw.save.median": 3.5,
            "perf.e.sd.prose-5kw.load.median": 150.0, "perf.e.sd.prose-250kw.load.median": 2500.0,
            "perf.e.ok.prose-5kw.save.median": 10.0, "perf.e.ok.prose-250kw.save.median": 400.0,
            "perf.e.ok.prose-5kw.load.median": 10.0, "perf.e.ok.prose-250kw.load.median": 300.0,
        }
        text = E._prepared_export(facts, ["sd", "ok"])
        self.assertIn("sd", text)
        self.assertNotIn("ok", text.replace("took", ""))
        self.assertIn("3.0 ms", text)
        self.assertEqual(E._prepared_export({}, ["sd"]), "")

    def test_template_facts_always_exist(self):
        for key in ("perf.e.prepared_export", "perf.e.host_start", "perf.e.table.libreoffice"):
            self.assertIn(key, self.facts)

    def test_save_notes_are_bullets_built_from_what_was_found(self):
        notes = self.facts["perf.e.save_notes"]
        self.assertTrue(notes.startswith("- **The file is the input.**"))
        self.assertIn("Plate.js, WordCraft", notes)
        self.assertNotIn("prepared during", notes)  # no fake editor has a flat save

    def test_a_non_publication_run_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "summary.json"
            data = json.loads((self.primary / "summary.json").read_text())
            data["execution_profile"] = "ci_broad"
            bad.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                E.load_run(Path(tmp))



def _copy(src: Path, dst: Path, edit=None) -> Path:
    shutil.copytree(src, dst)
    if edit:
        data = json.loads((dst / "summary.json").read_text())
        edit(data)
        (dst / "summary.json").write_text(json.dumps(data))
    return dst


class RunsMustBeComparable(unittest.TestCase):
    """codex review of #103, finding 1: a reproduction is another run of the same thing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.primary, self.repro = _MODULE["primary"], _MODULE["repro"]

    def tearDown(self):
        self.tmp.cleanup()

    def refuses(self, repro, word):
        with self.assertRaises(ValueError) as caught:
            E.facts_from_runs(self.primary, repro)
        self.assertIn(word, str(caught.exception))

    def test_a_run_is_not_its_own_reproduction(self):
        self.refuses(self.primary, "same run")

    def test_the_same_seed_is_not_a_reproduction(self):
        self.refuses(_copy(self.repro, self.root / "r", lambda d: d.update(seed=1)), "seed")

    def test_other_documents_are_not_a_reproduction(self):
        self.refuses(_copy(self.repro, self.root / "r", lambda d: d["workloads"]["prose-500w"].update(sha256="0" * 64)), "workload")

    def test_other_code_is_not_a_reproduction(self):
        self.refuses(_copy(self.repro, self.root / "r", lambda d: d["provenance"]["code"].update({"perf/schema.py": "0" * 64})), "provenance")

    def test_other_versions_are_not_a_reproduction(self):
        self.refuses(_copy(self.repro, self.root / "r", lambda d: d["versions"]["editors"]["plate"].update(pin="other")), "versions")

    def test_another_host_is_not_a_reproduction(self):
        self.refuses(_copy(self.repro, self.root / "r", lambda d: d["host"].update(cpu_model="Other CPU")), "host")

    def test_other_timer_boundaries_are_not_a_reproduction(self):
        self.refuses(_copy(self.repro, self.root / "r", lambda d: d["lanes"].update(plate="other")), "lanes")


class SummaryMustMatchSamples(unittest.TestCase):
    """codex review of #103, finding 2: the summary is reconciled with the sample files."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_row_median_that_the_samples_do_not_give_is_refused(self):
        def edit(d):
            row = next(r for r in d["rows"] if r["editor_id"] == "wordcraft" and r["criterion_id"] == "C02")
            row["median_ms"] = 1.0
        with self.assertRaises(ValueError) as caught:
            E.load_run(_copy(_MODULE["primary"], self.root / "p", edit))
        self.assertIn("median", str(caught.exception))

    def test_a_missing_sample_file_is_refused(self):
        run = _copy(_MODULE["primary"], self.root / "p")
        (run / "samples" / "prose-500w" / "wordcraft" / "r005.json").unlink()
        with self.assertRaises(ValueError) as caught:
            E.load_run(run)
        self.assertIn("wordcraft", str(caught.exception))

    def test_a_sample_from_another_run_is_refused(self):
        run = _copy(_MODULE["primary"], self.root / "p")
        path = run / "samples" / "prose-500w" / "wordcraft" / "r005.json"
        data = json.loads(path.read_text())
        data["run_id"] = "someone-else"
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError) as caught:
            E.load_run(run)
        self.assertIn("another run", str(caught.exception))


class Gates(unittest.TestCase):
    """codex review of #103, findings 3, 4, 5, 11 and 19."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        script = root / "fake.py"
        script.write_text(FAKE, encoding="utf-8")
        hs = ("model_ready_ms", "save_ms", "host_start_ms")

        def lanes(lo_sleep, host_start):
            return {
                "libreoffice": _lane(script, 1, 1, marks=(), FAKE_SLEEP=str(lo_sleep)),
                "superdoc": _lane(script, 20, 3, marks=hs, FAKE_HOST_START=str(host_start)),
                "docen": _lane(script, 5, 5, FAKE_CHILD="1"),
                "folio": _lane(script, 5, 5),
            }
        cls.primary = _run(root, "primary", lanes(0.05, 40), reps=10, seed=11)
        cls.repro = _run(root, "repro", lanes(0.40, 80), reps=10, seed=12)
        cls.facts = E.facts_from_runs(cls.primary, cls.repro)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_libreoffice_prints_no_median_that_did_not_reproduce(self):
        table = self.facts["perf.e.table.libreoffice"]
        row = next(line for line in table.splitlines() if line.startswith("| 500 words"))
        self.assertIn("not reproduced (", row)
        self.assertNotIn("agrees", row)

    def test_host_start_is_published_only_when_reproduced(self):
        self.assertNotIn("perf.e.superdoc.prose-500w.host_start.median", self.facts)
        self.assertEqual(self.facts["perf.e.host_start"], "")

    def test_cpu_and_memory_of_a_sample_with_a_survivor_are_not_published(self):
        row = next(line for line in self.facts["perf.e.table.process"].splitlines() if line.startswith("| Docen"))
        self.assertIn("incomplete", row)
        self.assertNotIn("perf.e.docen.prose-500w.cpu.median", self.facts)
        self.assertNotIn("perf.e.docen.prose-500w.rss.median", self.facts)
        folio = next(line for line in self.facts["perf.e.table.process"].splitlines() if line.startswith("| Folio"))
        self.assertNotIn("incomplete", folio)

    def test_the_round_trip_is_described_as_the_two_clocks_summed(self):
        text = self.facts["perf.e.context.roundtrip"]
        self.assertIn("load clock plus the save clock", text)
        self.assertNotIn("from a fresh process", text)


class RulesFromTheRun(unittest.TestCase):
    """The report states the check and the exceptions the run applied, read from the run."""

    def test_check_limits_come_from_the_run(self):
        rules = {"check_limits": {"default": [0.98, 1.02], "corpus": [0.5, 1.5]}}
        text = E._check_text({"publication_rules": rules})
        self.assertIn("98 percent", text)
        self.assertIn("2 percent longer", text)
        self.assertIn("50 percent", text)
        self.assertIn("1.5 times", text)

    def test_listed_checkout_exceptions_are_named(self):
        versions = {"editors": {"office-open": {"dirty_allowed": {"repos/office-open": "27 deletions under scripts/coverage/: reason"}},
                                "plate": {"dirty_allowed": {}}}}
        self.assertEqual(E._dirty_allowed({"versions": versions}), "office-open: 27 deletions under scripts/coverage/: reason")
        self.assertEqual(E._dirty_allowed({"versions": {"editors": {}}}), "none")


class SecondReview(unittest.TestCase):
    """MiniMax (pi) review of the #103 fixes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_new1_a_summary_flag_cannot_make_a_cell_publishable(self):
        def edit(d):
            for r in d["rows"]:
                if r["editor_id"] == "canvas":
                    r.update(outcome="measured", publishable=True, n=0)
        run = _copy(_MODULE["primary"], self.root / "p", edit)
        with self.assertRaises(ValueError):
            E.load_run(run)  # canvas crashed: its rows cannot claim measured

    def test_new1_eligibility_is_rederived_from_the_samples(self):
        run = E.load_run(_MODULE["primary"])
        for rec in run.records["prose-500w", "wordcraft"][:3]:
            rec["power_source"] = "battery"
        self.assertEqual(E._status(run, "prose-500w", "wordcraft", "load")[0], "unpublishable")

    def test_new2_a_copy_with_new_identities_is_not_a_reproduction(self):
        dst = self.root / "copy"
        shutil.copytree(_MODULE["primary"], dst)
        old_id = json.loads((dst / "summary.json").read_text())["run_id"]
        for path in dst.rglob("*.json"):
            path.write_text(path.read_text().replace(old_id, "forged0000"))
        data = json.loads((dst / "summary.json").read_text())
        data["seed"] = 99
        (dst / "summary.json").write_text(json.dumps(data))
        with self.assertRaises(ValueError) as caught:
            E.facts_from_runs(_MODULE["primary"], dst)
        self.assertIn("overlap", str(caught.exception))

    def test_new6_a_duplicated_sample_is_refused(self):
        def edit(d):
            d["repetitions"] = 11
        run = _copy(_MODULE["primary"], self.root / "p", edit)
        for editor in ("wordcraft", "plate"):
            src = run / "samples" / "prose-500w" / editor / "r005.json"
            rec = json.loads(src.read_text())
            rec["repetition"] = 11
            (src.parent / "r011.json").write_text(json.dumps(rec))
        with self.assertRaises(ValueError) as caught:
            E.load_run(run)
        self.assertIn("same start", str(caught.exception))


class Units(unittest.TestCase):
    def test_round_trip_pairs_each_load_with_its_own_save(self):
        def rec(load, save):
            return {"timed_out": False, "returncode": 0, "check": {"complete": True},
                    "marks": {"model_ready_ms": load, "save_ms": save},
                    "mark_counts": {"model_ready_ms": 1, "save_ms": 1}, "required_marks": ["model_ready_ms", "save_ms"]}
        recs = [rec(1, 100), rec(1, 1), rec(100, 1)]
        self.assertEqual(E._values(recs, "roundtrip"), [101, 2, 101])
        self.assertEqual(E._stats(E._values(recs, "roundtrip"), "process_cold_fs_warm")["median"], 101)

    def test_a_sample_with_a_doubled_mark_is_not_good(self):
        rec = {"timed_out": False, "returncode": 0, "check": {"complete": True}, "marks": {"model_ready_ms": 1, "save_ms": 1},
               "mark_counts": {"model_ready_ms": 1, "save_ms": 2}, "required_marks": ["model_ready_ms", "save_ms"]}
        self.assertFalse(E._good(rec))

    def test_a_sample_off_ac_power_blocks_a_whole_process_cell(self):
        def rec(power):
            return {"returncode": 0, "timed_out": False, "check": {"complete": True}, "noisy": False, "marks": {},
                    "wall_ms": 5.0, "cpu_ms": 5.0, "max_rss_bytes": 1, "power_source": power}
        run = E.Run(Path("."), {"workloads": {}, "repetitions": 10})
        run.records["w", "e"] = [rec("ac") for _ in range(9)] + [rec("battery")]
        ok, why = E._samples_publishable(run, "w", "e")
        self.assertFalse(ok)
        self.assertIn("battery", why)


if __name__ == "__main__":
    unittest.main()
