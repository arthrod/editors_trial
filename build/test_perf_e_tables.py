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
        sys.stderr.write("(node:1) ExperimentalWarning: noise\\nTypeError: boom at the table\\n    at layout (/x/repos/editor/src/layout.ts:12:3)\\n")
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
    quiet = {"quiet": True, "reasons": [], "load_average": [0.5, 0.5, 0.5], "thresholds": {"load1_max": 4.0}}
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
        # the machine the fixture runs ran on, Mac or Linux container (#120)
        from perf.runner import host as host_probe
        self.assertIn(host_probe.host_record()["cpu_model"], self.facts["perf.e.host"])
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
                    "marks": {}, "mark_counts": {}, "required_marks": [], "wall_ms": 5.0, "cpu_ms": 5.0, "max_rss_bytes": 1,
                    "power_source": "ac", "load_before": [0.5, 0.5, 0.5]}
        run = E.Run(Path("."), {"workloads": {}, "repetitions": 10, "quiet_machine_check_start": {"thresholds": {"load1_max": 4.0}}})
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
        self.assertIn("Plate.js on every document; WordCraft on every document", notes)
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
        # #119 (codex #3): a figure cell that did not reproduce holds no number
        self.assertIn("| not reproduced |", row)
        self.assertNotIn(" vs ", row)
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
                    "mark_counts": {}, "required_marks": [],
                    "wall_ms": 5.0, "cpu_ms": 5.0, "max_rss_bytes": 1, "power_source": power, "load_before": [0.5, 0.5, 0.5]}
        run = E.Run(Path("."), {"workloads": {}, "repetitions": 10, "quiet_machine_check_start": {"thresholds": {"load1_max": 4.0}}})
        run.records["w", "e"] = [rec("ac") for _ in range(9)] + [rec("battery")]
        ok, why = E._samples_publishable(run, "w", "e")
        self.assertFalse(ok)
        self.assertIn("battery", why)



class HostLine(unittest.TestCase):
    """#118: the host sentence says what the machine was, Mac or container."""

    MAC = {"os": "darwin", "cpu_model": "Apple M4 Pro", "cpu_cores_logical": 12, "ram_bytes": 24 * 2**30,
           "os_version": "27.2", "power_source": "ac"}
    BOX = {"os": "linux", "cpu_model": "AMD EPYC 7R13 Processor", "cpu_cores_logical": 64,
           "ram_bytes": 517267300 * 1024, "os_version": "6.12.113-138.209.amzn2023.x86_64", "power_source": "ac",
           "power_supplies": [], "cpu_quota": 16.0, "memory_limit_bytes": 124 * 2**30, "container": True}

    def test_mac_line_is_unchanged(self):
        self.assertEqual(E._host({"host": self.MAC}), "Apple M4 Pro, 12 cores, 24 GiB RAM, macOS 27.2, AC power")

    def test_container_line_names_the_quota_not_the_host_totals(self):
        line = E._host({"host": self.BOX})
        self.assertIn("a CPU quota of 16 of the 64 CPUs its kernel reports", line)
        self.assertIn("124 GiB RAM limit", line)
        self.assertIn("Linux 6.12.113", line)
        self.assertNotIn("macOS", line)
        self.assertNotIn("493 GiB", line)
        self.assertNotIn("no battery", line)  # an empty supply list is not a battery's absence (#120)

    def test_container_kind_is_part_of_the_same_host_rule(self):
        for key in ("container", "cpu_quota", "memory_limit_bytes"):
            with self.subTest(key=key):
                self.assertIn(key, E._SAME_HOST)


class MachineWords(unittest.TestCase):
    """#118: the prose names the kind of machine from the run, never "Mac" by hand."""

    def test_mac(self):
        s = {"host": HostLine.MAC}
        self.assertEqual(E._machine(s), "one Mac")
        self.assertEqual(E._host_note(s), "")

    def test_container(self):
        s = {"host": HostLine.BOX}
        self.assertEqual(E._machine(s), "one Linux container on a machine the run could not identify")
        note = E._host_note(s)
        self.assertIn("every process on that kernel", note)
        self.assertIn("64", note)
        self.assertIn("16", note)
        self.assertIn("cannot see", note)

    def test_facts_carry_both(self):
        import inspect
        src = inspect.getsource(E.facts_from_runs)
        self.assertIn('"perf.e.machine": _machine(s)', src)
        self.assertIn('"perf.e.host_note": _host_note(s, repro.summary)', src)


def _good_rec(**over):
    rec = {"returncode": 0, "timed_out": False, "check": {"complete": True}, "noisy": False,
           "marks": {"model_ready_ms": 1.0, "save_ms": 1.0}, "mark_counts": {"model_ready_ms": 1, "save_ms": 1},
           "required_marks": ["model_ready_ms", "save_ms"], "wall_ms": 5.0, "cpu_ms": 5.0, "max_rss_bytes": 1,
           "power_source": "ac", "resources_complete": True, "load_before": [0.5, 0.5, 0.5]}
    rec.update(over)
    return rec


class GrokReview(unittest.TestCase):
    """#119: grok-4.7's review of the #103 fixes."""

    @classmethod
    def setUpClass(cls):
        cls.primary, cls.repro = _MODULE["primary"], _MODULE["repro"]
        cls.facts = E.facts_from_runs(cls.primary, cls.repro)

    # codex #3, not fixed: the figure cell said "not reproduced (50 vs 80)"
    def test_a_cell_that_did_not_reproduce_holds_no_number(self):
        row = next(l for l in self.facts["perf.e.table.save"].splitlines() if l.startswith("| Plate.js"))
        self.assertIn("| not reproduced |", row)
        self.assertNotIn(" vs ", row)

    def test_both_medians_go_to_a_separate_diagnostic_table(self):
        diag = self.facts["perf.e.not_reproduced"]
        row = next(l for l in diag.splitlines() if l.startswith("| Plate.js") and "save" in l)
        self.assertIn("| 50 |", row)
        self.assertIn("| 80 |", row)

    # new 6
    def test_reproduction_does_not_depend_on_argument_order(self):
        self.assertEqual(E.reproduced(111, 100), E.reproduced(100, 111))
        self.assertTrue(E.reproduced(100, 110))
        self.assertFalse(E.reproduced(100, 112.5))

    # new 7
    def test_an_impossible_time_is_not_called_a_double_print(self):
        self.assertEqual(E._short("marks: save_ms=-1 is not a time"), "harness printed an impossible time")
        self.assertEqual(E._short("marks: save_ms printed 2 times"), "harness printed a time twice")

    # #4
    def test_host_start_needs_the_mark_on_every_good_sample_of_both_runs(self):
        hs = _good_rec(marks={"host_start_ms": 4.0}, mark_counts={"model_ready_ms": 1, "save_ms": 1, "host_start_ms": 1})
        self.assertTrue(E._covers([hs] * 3, "host_start_ms"))
        self.assertFalse(E._covers([hs, _good_rec()], "host_start_ms"))
        self.assertFalse(E._covers([], "host_start_ms"))
        import inspect
        src = inspect.getsource(E._host_start_facts)
        self.assertIn("_covers(good, ", src)
        self.assertIn("_covers(r_good, ", src)

    # #5
    def test_missing_or_impossible_resources_are_incomplete(self):
        no_flag = _good_rec()
        del no_flag["resources_complete"]
        self.assertFalse(E._metric_complete([no_flag] * 10, "cpu")[0])
        self.assertFalse(E._metric_complete([_good_rec(cpu_ms=-5.0)] * 10, "cpu")[0])
        self.assertFalse(E._metric_complete([_good_rec(wall_ms=float("nan"))] * 10, "wall")[0])
        self.assertTrue(E._metric_complete([_good_rec()] * 10, "cpu")[0])

    # #15
    def test_a_sample_without_mark_counts_is_not_good(self):
        rec = _good_rec(marks={"model_ready_ms": 1.0, "save_ms": -1.0})
        del rec["mark_counts"]
        self.assertFalse(E._good(rec))
        self.assertTrue(E._good(_good_rec()))

    # #1
    def test_run_windows_compare_instants_not_strings(self):
        run = E.Run(Path("."), {})
        run.records["w", "e"] = [_good_rec(started_at="2026-11-09 18:00:00+00:00"), _good_rec(started_at="2026-11-09T18:05:00+00:00")]
        lo, hi = E._window(run)
        self.assertLess(lo, hi)
        self.assertEqual((hi - lo).total_seconds(), 300)

    def test_timeout_and_warmup_must_match(self):
        import copy
        for key, value in (("timeout_s", 1), ("warmup", 8)):
            with self.subTest(key=key):
                b = E.Run(self.repro if isinstance(self.repro, Path) else Path("."), {})
                pa, pb = E.load_run(self.primary), E.load_run(self.repro)
                pb.summary = copy.deepcopy(pb.summary)
                pb.summary[key] = value
                with self.assertRaisesRegex(ValueError, key):
                    E.check_comparable(pa, pb)

    # #2
    def test_the_stopped_bypass_is_for_failed_rows_only(self):
        run = E.Run(Path("."), {"repetitions": 30})
        run.rows["w", "e", "C02"] = {"outcome": "measured", "failure_reason": "stopped after 3 consecutive failures"}
        self.assertFalse(E._stopped(run, "w", "e"))
        run.rows["w", "e", "C02"] = {"outcome": "failed", "failure_reason": "rc=1; stopped after 3 consecutive failures"}
        self.assertTrue(E._stopped(run, "w", "e"))

    def test_noisy_is_recomputed_from_the_load_and_the_recorded_limit(self):
        run = E.Run(Path("."), {"repetitions": 10, "quiet_machine_check_start": {"thresholds": {"load1_max": 4.0}}})
        quiet = _good_rec()
        quiet.pop("noisy")
        loud = _good_rec(load_before=[99.0, 99.0, 99.0])
        loud.pop("noisy")
        run.records["w", "e"] = [loud] * 2 + [quiet] * 8
        ok, why = E._samples_publishable(run, "w", "e")
        self.assertFalse(ok)
        self.assertIn("load limit", why)

    def test_too_few_sample_files_block_whole_process_figures(self):
        run = E.Run(Path("."), {"repetitions": 30, "quiet_machine_check_start": {"thresholds": {"load1_max": 4.0}}})
        run.records["w", "e"] = [_good_rec() for _ in range(10)]
        ok, why = E._samples_publishable(run, "w", "e")
        self.assertFalse(ok)
        self.assertIn("for 30 repetitions", why)

    # new 2
    def test_a_quota_is_named_even_when_no_container_was_detected(self):
        box = dict(HostLine.BOX, container=False, cpu_quota=2.0, memory_limit_bytes=2 * 2**30,
                   cpu_cores_logical=128, ram_bytes=512 * 2**30, os_version="6.8")
        line = E._host({"host": box})
        self.assertIn("a CPU quota of 2 of the 128 CPUs its kernel reports", line)
        self.assertIn("2 GiB RAM limit", line)
        self.assertNotIn("512 GiB", line)
        self.assertIn("limited", E._machine({"host": box}))

    # new 4
    def test_the_battery_sentence_comes_from_the_record(self):
        with_battery = dict(HostLine.BOX, power_source="battery", power_supplies=["BAT0"])
        self.assertNotIn("sees no power supply", E._host_note({"host": with_battery}))
        self.assertIn("sees no power supply", E._host_note({"host": HostLine.BOX}))

    # new 5
    def test_canvas_wall_time_says_it_includes_the_harness_wait(self):
        self.assertIn("canvas", E.PROCESS_CAVEATS)
        self.assertIn("500 ms", E.PROCESS_CAVEATS["canvas"]["wall"])

    # #14
    def test_an_end_check_that_was_not_quiet_is_reported(self):
        quiet = {"quiet_machine_check_end": {"quiet": True, "reasons": []}}
        loud = {"quiet_machine_check_end": {"quiet": False, "reasons": ["1-minute load average 30.00 exceeds 21.33"]}}
        self.assertEqual(E._end_check(quiet), "")
        self.assertIn("30.00 exceeds 21.33", E._end_check(loud))
        import inspect
        self.assertIn('"perf.e.end_check"', inspect.getsource(E.facts_from_runs))



class WholeMachineContainer(unittest.TestCase):
    """#118/#120: a container allowed every CPU its kernel reports. A quota is a
    ceiling, not a reservation (codex #5): the words say what the run recorded
    (the quota, the DMI vendor, the steal), never "to itself"."""

    WHOLE = dict(HostLine.BOX, cpu_cores_logical=32, cpu_quota=32.0, memory_limit_bytes=256 * 2**30)

    def test_line_says_every_cpu_its_kernel_reports(self):
        line = E._host({"host": self.WHOLE})
        self.assertIn("all 32 CPUs its kernel reports", line)
        self.assertNotIn("shared", line)

    def test_no_tenancy_or_cloud_claim_without_evidence(self):
        machine = E._machine({"host": self.WHOLE})
        note = E._host_note({"host": self.WHOLE})
        for text in (machine, note):
            self.assertNotIn("to itself", text)
            self.assertNotIn("cloud", text)
            self.assertNotIn("virtual machine", text)

    def test_a_partial_quota_says_so(self):
        self.assertIn("a CPU quota of 16 of the 64", E._host({"host": HostLine.BOX}))


class CodexReview120(unittest.TestCase):
    """#120: codex (gpt-6-astra) review of 86f6d26..39e5435."""

    EC2 = dict(HostLine.BOX, cpu_cores_logical=32, cpu_quota=32.0, memory_limit_bytes=274999996416,
               ram_bytes=264744833024, machine_vendor="Amazon EC2", machine_product="r6a.8xlarge", hypervisor=True)

    @staticmethod
    def _run(limit=4.0):
        return E.Run(Path("."), {"repetitions": 10, "quiet_machine_check_start": {"thresholds": {"load1_max": limit}}})

    # 1
    def test_invalid_load_evidence_is_noisy(self):
        run = self._run()
        for load in ([float("nan"), 0, 0], [-1.0, 0, 0], ["0.1", 0, 0], [None, 0, 0]):
            with self.subTest(load=load):
                self.assertTrue(E._noisy(run, _good_rec(load_before=load)))
        self.assertFalse(E._noisy(run, _good_rec()))

    def test_an_invalid_threshold_is_noisy(self):
        for limit in (float("nan"), -1.0, "4"):
            with self.subTest(limit=limit):
                self.assertTrue(E._noisy(self._run(limit), _good_rec(load_before=[999.0, 0, 0])))
                self.assertTrue(E._noisy(self._run(limit), _good_rec()))

    # 2
    def test_null_mark_counts_is_not_good(self):
        self.assertFalse(E._good(_good_rec(mark_counts=None, marks={"model_ready_ms": -5.0, "save_ms": 1.0})))
        self.assertFalse(E._good(_good_rec(mark_counts=[])))

    def test_a_published_mark_must_be_a_time(self):
        loose = dict(required_marks=[], mark_counts={})
        recs = [_good_rec(marks={"model_ready_ms": -5.0, "save_ms": float("nan")}, **loose),
                _good_rec(marks={"model_ready_ms": 2.0, "save_ms": 3.0}, **loose)]
        self.assertEqual(E._values(recs, "load"), [2.0])
        self.assertEqual(E._values(recs, "save"), [3.0])
        self.assertEqual(E._values(recs, "roundtrip"), [5.0])

    # 3
    def test_host_start_must_be_one_valid_time(self):
        ok = _good_rec(marks={"host_start_ms": 4.0}, mark_counts={"model_ready_ms": 1, "save_ms": 1, "host_start_ms": 1})
        twice = dict(ok, mark_counts=dict(ok["mark_counts"], host_start_ms=2))
        uncounted = dict(ok, mark_counts={"model_ready_ms": 1, "save_ms": 1})
        negative = dict(ok, marks={"host_start_ms": -5.0})
        nan = dict(ok, marks={"host_start_ms": float("nan")})
        self.assertTrue(E._covers([ok] * 3, "host_start_ms"))
        for bad in (twice, uncounted, negative, nan):
            with self.subTest(bad=bad["marks"], counts=bad["mark_counts"]):
                self.assertFalse(E._covers([ok, bad], "host_start_ms"))

    # 5, 6: the words come from evidence the run recorded
    def test_ec2_container_is_named_from_dmi(self):
        s = {"host": self.EC2}
        self.assertEqual(E._machine(s), "one Linux container on a virtual machine (Amazon EC2 r6a.8xlarge)")
        line = E._host(s)
        self.assertIn("all 32 CPUs its kernel reports", line)
        self.assertIn("247 GiB RAM", line)  # the limit is above the RAM: no limit in effect
        self.assertNotIn("limit", line)
        self.assertNotIn("no battery", line)
        self.assertIn("AC power", line)

    def test_steal_share_comes_from_the_run(self):
        def run(steal0, total0, steal1, total1):
            return {"host": self.EC2,
                    "quiet_machine_check_start": {"cpu_ticks": {"steal": steal0, "total": total0}},
                    "quiet_machine_check_end": {"cpu_ticks": {"steal": steal1, "total": total1}}}
        a, b = run(100, 100000, 600, 1100000), run(0, 0, 2000, 1000000)
        self.assertAlmostEqual(E._steal_pct(a), 0.05)
        self.assertAlmostEqual(E._steal_pct(b), 0.2)
        self.assertIsNone(E._steal_pct({"host": self.EC2}))
        self.assertIsNone(E._steal_pct(run(5, 10, 4, 20)))  # counters went back: not evidence
        note = E._host_note(a, b)
        self.assertIn("0.05%", note)
        self.assertIn("0.20%", note)
        self.assertIn("steal", note)
        self.assertIn("AC power is inferred from the machine's vendor (Amazon EC2)", note)
        self.assertNotIn("to itself", note)

    def test_no_steal_sentence_without_ticks(self):
        self.assertNotIn("steal", E._host_note({"host": self.EC2}))

    def test_mac_note_stays_empty(self):
        self.assertEqual(E._host_note({"host": HostLine.MAC}, {"host": HostLine.MAC}), "")


class GlmReview121(unittest.TestCase):
    """#121: glm-5.3's review of the #120 fixes."""

    EC2 = CodexReview120.EC2

    @staticmethod
    def _summary(host, ticks0=None, ticks1=None):
        s = {"host": host}
        if ticks0 is not None:
            s["quiet_machine_check_start"] = {"cpu_ticks": ticks0}
            s["quiet_machine_check_end"] = {"cpu_ticks": ticks1}
        return s

    # 3
    def test_steal_from_the_second_run_only_is_named_as_the_second_run(self):
        first = self._summary(self.EC2)
        second = self._summary(self.EC2, {"steal": 0, "total": 1000000}, {"steal": 20000, "total": 2000000})
        note = E._host_note(first, second)
        self.assertIn("2.00% during the second run", note)
        self.assertNotIn("during the run", note)

    def test_a_tiny_steal_is_not_printed_as_zero(self):
        a = self._summary(self.EC2, {"steal": 0, "total": 0}, {"steal": 1, "total": 1000000})
        note = E._host_note(a, a)
        self.assertNotIn("0.00%", note)
        self.assertIn("less than 0.01%", note)

    # 4
    def test_the_evidence_fields_are_part_of_the_same_host_rule(self):
        for key in ("machine_vendor", "machine_product", "hypervisor"):
            with self.subTest(key=key):
                self.assertIn(key, E._SAME_HOST)

    # 5, 7
    def test_a_named_bare_metal_machine_is_named(self):
        dell = dict(HostLine.BOX, machine_vendor="Dell Inc.", machine_product="PowerEdge R740", hypervisor=False)
        self.assertEqual(E._machine({"host": dell}), "one Linux container on a machine (Dell Inc. PowerEdge R740)")

    def test_no_article_is_guessed_for_a_vendor(self):
        for vendor in ("innotek GmbH", "oVirt", "Ubuntu", "amazon ec2"):
            with self.subTest(vendor=vendor):
                h = dict(HostLine.BOX, machine_vendor=vendor, machine_product=None, hypervisor=True)
                self.assertEqual(E._machine({"host": h}), "one Linux container on a virtual machine (%s)" % vendor)

    def test_unidentified_stays_unidentified(self):
        self.assertEqual(E._machine({"host": HostLine.BOX}), "one Linux container on a machine the run could not identify")
        vm = dict(HostLine.BOX, hypervisor=True)
        self.assertEqual(E._machine({"host": vm}), "one Linux container on a virtual machine")

    # 2 (wording)
    def test_unknown_power_is_said(self):
        h = dict(HostLine.BOX, power_source="unknown")
        note = E._host_note({"host": h})
        self.assertIn("recorded as unknown", note)
        self.assertNotIn("inferred", note)

    def test_power_evidence_is_named(self):
        rack = dict(HostLine.BOX, machine_vendor="Dell Inc.", hypervisor=False, power_evidence="server chassis")
        self.assertIn("inferred from the machine's chassis type (a server)", E._host_note({"host": rack}))
        cloud = dict(self.EC2, power_evidence="cloud vendor")
        self.assertIn("inferred from the machine's vendor (Amazon EC2)", E._host_note({"host": cloud}))
        # a record from before power_evidence existed: the vendor is the only rule that could have said ac
        self.assertIn("inferred from the machine's vendor (Amazon EC2)", E._host_note({"host": self.EC2}))

    # 9
    def test_small_memory_limits_are_not_rounded_away(self):
        def line(limit):
            return E._host({"host": dict(HostLine.BOX, memory_limit_bytes=limit)})
        self.assertIn("512 MiB RAM limit", line(512 * 2**20))
        self.assertIn("1.5 GiB RAM limit", line(3 * 2**29))
        self.assertIn("124 GiB RAM limit", line(124 * 2**30))

    # 10
    def test_a_good_record_without_marks_publishes_nothing(self):
        rec = _good_rec(required_marks=[], mark_counts={})
        del rec["marks"]
        for metric in ("load", "save", "roundtrip"):
            with self.subTest(metric=metric):
                self.assertEqual(E._values([rec], metric), [])


class CodexReview122(unittest.TestCase):
    """#122: codex's review of the #121 fixes."""

    EC2 = CodexReview120.EC2

    # 5
    def test_the_recorded_power_is_stated(self):
        battery = dict(HostLine.BOX, power_source="battery", machine_vendor="Apple Inc.")
        note = E._host_note({"host": battery})
        self.assertIn("recorded as battery", note)
        self.assertNotIn("unknown", note)

    def test_a_legacy_record_names_no_rule_it_cannot_show(self):
        dell = dict(HostLine.BOX, machine_vendor="Dell Inc.")  # ac, no power_evidence
        note = E._host_note({"host": dell})
        self.assertNotIn("inferred", note)
        self.assertIn("does not say why", note)
        # before 8e98f66 recorded power_evidence, a cloud vendor was a container's only no-supply AC rule (#123)
        self.assertIn("inferred from the machine's vendor (Amazon EC2)", E._host_note({"host": self.EC2}))

    # 6
    def test_steal_is_described_by_its_scope_only(self):
        s = {"host": self.EC2, "quiet_machine_check_start": {"cpu_ticks": {"steal": 0, "total": 0}},
             "quiet_machine_check_end": {"cpu_ticks": {"steal": 50, "total": 100000}}}
        note = E._host_note(s, s)
        self.assertNotIn("physical server", note)
        self.assertNotIn("shows only", note)
        self.assertIn("steal", note)
        self.assertIn("memory or I/O", note)


class MiniMaxReview123(unittest.TestCase):
    """#123: MiniMax-M3's review of the #122 fixes."""

    EC2 = CodexReview120.EC2

    def _note(self, **over):
        return E._host_note({"host": dict(HostLine.BOX, **over)})

    # 4, 15
    def test_steal_says_cpu_only_and_shows_when_the_hypervisor_is_unknown(self):
        s = {"host": dict(self.EC2, hypervisor=None),
             "quiet_machine_check_start": {"cpu_ticks": {"steal": 0, "total": 0}},
             "quiet_machine_check_end": {"cpu_ticks": {"steal": 50, "total": 100000}}}
        note = E._host_note(s)
        self.assertIn("counts CPU time only", note)
        self.assertIn("0.05% during the run", note)
        self.assertNotIn("steal", E._host_note(dict(s, host=dict(self.EC2, hypervisor=False))))

    # 5
    def test_every_evidence_value_is_named(self):
        self.assertIn("an online power supply", self._note(power_evidence="supply"))
        self.assertIn("no battery", self._note(power_evidence="no battery on bare metal"))
        self.assertIn("no battery", self._note(power_evidence="no supply on bare metal"))
        for ev in ("supply", "no battery on bare metal", "cloud vendor", "server chassis"):
            with self.subTest(ev=ev):
                self.assertNotIn("does not say why", self._note(power_evidence=ev, machine_vendor="Amazon EC2"))

    # 6
    def test_a_missing_vendor_is_not_printed_as_none(self):
        note = self._note(power_evidence="cloud vendor", machine_vendor=None)
        self.assertNotIn("None", note)
        self.assertIn("does not name", note)

    # 7
    def test_legacy_records_are_read_with_the_list_of_their_time(self):
        self.assertEqual(E.LEGACY_CLOUD_VENDORS,
                         ("Amazon EC2", "Google", "DigitalOcean", "Hetzner", "Scaleway", "Alibaba Cloud"))
        with mock.patch.object(E, "LEGACY_CLOUD_VENDORS", ("Google",)):
            self.assertIn("does not say why", self._note(machine_vendor="Amazon EC2"))

    # 8
    def test_no_power_source_is_not_called_unreadable(self):
        h = dict(HostLine.BOX)
        del h["power_source"]
        note = E._host_note({"host": h})
        self.assertNotIn("unreadable", note)
        self.assertIn("was not recorded", note)

    # 17
    def test_the_chassis_sentence_states_its_condition(self):
        self.assertIn("no hypervisor", self._note(power_evidence="server chassis"))


CANVAS_COMPLEX_STDERR = (
    "(node:91065) ExperimentalWarning: localStorage is not available because --localstorage-file was not provided.\n"
    "\x1b[41m\x1b[1m FAIL \x1b[22m\x1b[49m roundtrip.test.ts > canvas-editor docx plugin round trip\n"
    "\x1b[31m\x1b[1mTypeError\x1b[22m: Cannot read properties of undefined (reading 'width')\x1b[39m\n"
    "\x1b[36m \x1b[2m❯\x1b[22m Object.computeRowColInfo ../../repos/canvas-editor/src/editor/core/draw/particle/table/TableParticle.ts:\x1b[2m724:45\x1b[22m\x1b[39m\n"
    "    \x1b[90m724|\x1b[39m           width += colgroup[col + colIndex].width\n"
    "\x1b[90m \x1b[2m❯\x1b[22m TableParticle.TableParticle.computeRowColInfo roundtrip.test.ts:\x1b[2m72:12\x1b[22m\x1b[39m\n"
)
CANVAS_WORKER_STDERR = (
    "(node:79559) ExperimentalWarning: localStorage is not available because --localstorage-file was not provided.\n"
    "node:events:505\n    throw er; // Unhandled 'error' event\n    ^\n\n"
    "Error: Worker exited unexpectedly\n"
    "    at Worker.emitUnexpectedExit (file:///work/editors_trial/repos/canvas-editor/node_modules/.pnpm/vitest@4.1.12/node_modules/vitest/dist/chunks/cli-api.js:3090:33)\n"
    "    at Worker.emit (node:events:514:20)\n"
)


def _hand_run(editors, lanes=None, versions=None):
    summary = {"workloads": {"prose-500w": {}}, "repetitions": 10, "lanes": lanes or {}, "versions": versions or {}}
    return E.Run(Path("."), summary, records={("prose-500w", e): [] for e in editors})


def _cells(line: str) -> int:
    return line.strip().strip("|").count("|") + 1


class PublicationDraft(unittest.TestCase):
    """Defects found reading the first rendered draft of Report E (#111)."""

    def test_each_lane_has_a_load_column_and_a_save_column(self):
        run = _hand_run(["canvas", "libreoffice"], lanes={
            "canvas": "executeImportDocx | executeExportDocx (jsdom; canvas and workers mocked)",
            "libreoffice": "soffice --convert-to docx: whole conversion, no load/save split"})
        table = E._lanes(run).splitlines()
        self.assertEqual(table[0], "| Editor | Load timer ends at | Save timer covers |")
        self.assertEqual({_cells(line) for line in table}, {3})
        self.assertIn("| canvas-editor + plugin | executeImportDocx | executeExportDocx (jsdom; canvas and workers mocked) |", table)
        self.assertIn("| LibreOffice (baseline) | soffice --convert-to docx: whole conversion, no load/save split | — |", table)

    def test_package_versions_read_as_versions(self):
        same = {"editors": {"docxodus": {"pin": "p", "packages": {"docxodus": {"declared": "15.0.0", "installed": "15.0.0", "matches": True}}}}}
        row = next(l for l in E._versions(_hand_run(["docxodus"], versions=same)).splitlines() if l.startswith("| Docxodus"))
        self.assertIn("docxodus 15.0.0", row)
        self.assertNotIn("{", row)
        self.assertNotIn("declared", row)
        off = {"editors": {"docxodus": {"pin": "p", "packages": {"docxodus": {"declared": "15.0.0", "installed": "15.1.0", "matches": False}}}}}
        row = next(l for l in E._versions(_hand_run(["docxodus"], versions=off)).splitlines() if l.startswith("| Docxodus"))
        self.assertIn("docxodus 15.1.0 (declared 15.0.0)", row)

    def test_libreoffice_has_its_own_table_not_a_row_of_n_a(self):
        run = _hand_run(["libreoffice", "wordcraft"])
        for metric in ("load", "save", "roundtrip"):
            table = E._table({}, run, run, metric)
            self.assertNotIn("LibreOffice", table)
            self.assertIn("| WordCraft |", table)
        appendix = E._appendix({}, run)
        self.assertNotIn("LibreOffice", appendix)
        self.assertIn("| WordCraft |", appendix)

    def test_the_error_line_is_the_first_error_and_the_editor_frame(self):
        self.assertEqual(E._error_line(CANVAS_COMPLEX_STDERR),
                         "TypeError: Cannot read properties of undefined (reading 'width') at canvas-editor/src/editor/core/draw/particle/table/TableParticle.ts:724")
        # vitest's own frame under node_modules is not the editor's code
        self.assertEqual(E._error_line(CANVAS_WORKER_STDERR), "Error: Worker exited unexpectedly")
        self.assertIsNone(E._error_line("(node:1) ExperimentalWarning: only a warning\n"))
        self.assertIsNone(E._error_line(None))

    def test_a_failed_cell_quotes_its_last_error(self):
        facts = E.facts_from_runs(_MODULE["primary"], _MODULE["repro"])
        line = next(l for l in facts["perf.e.exceptions"].splitlines() if l.startswith("- canvas-editor + plugin, 500 words, load"))
        self.assertIn("last error: `TypeError: boom at the table at editor/src/layout.ts:12`", line)

    def test_save_notes_agree_in_number_with_their_editors(self):
        one = E._save_notes({"perf.e.passthrough_scope": "GenOffice on every document", "perf.e.passthrough_n": 1,
                             "perf.e.prepared_export": "SuperDoc's save took 9.8 ms at 5,000 words and 13 ms at 250,000 words, while its load grew 13 times",
                             "perf.e.flat_save_rewrites": True})
        self.assertIn("this editor wrote back the exact bytes it was given: GenOffice on every document.", one)
        self.assertIn("it keeps the original package there; its save time", one)
        self.assertIn("Its saved file is not the input", one)
        self.assertNotIn("these editors", one)
        self.assertNotIn("Their", one)
        two = E._save_notes({"perf.e.passthrough_scope": "GenOffice on every document; Folio on every document", "perf.e.passthrough_n": 2,
                             "perf.e.prepared_export": "A's save took 1 ms; B's save took 2 ms", "perf.e.flat_save_rewrites": True})
        self.assertIn("these editors wrote back the exact bytes they were given: GenOffice on every document; Folio on every document.", two)
        self.assertIn("Their saved files are not the input", two)


def _hash_run(rows, input_sha=None):
    """rows: {(workload, editor): [output sha256 per good sample]}"""
    wls = sorted({w for w, _ in rows})
    summary = {"workloads": {w: {"sha256": (input_sha or {}).get(w, "in-" + w)} for w in wls}, "repetitions": 10}
    records = {k: [_good_rec(output_sha256=h) for h in v] for k, v in rows.items()}
    return E.Run(Path("."), summary, records=records)


class CodexReview124(unittest.TestCase):
    """#124: codex (gpt-6-astra) review of the Report E commits (#111)."""

    def test_1_passthrough_is_scoped_to_the_documents_it_holds_for(self):
        rows = {("prose-500w", "genoffice"): ["in-prose-500w"] * 3, ("complex-corpus", "genoffice"): ["other"] * 3,
                ("prose-500w", "wordcraft"): ["in-prose-500w"] * 3, ("complex-corpus", "wordcraft"): ["in-complex-corpus"] * 3}
        primary = _hash_run(rows)
        scope = E._passthrough_scope(primary, primary)
        self.assertIn("GenOffice on the 500 words document (it rewrote complex.docx)", scope)
        self.assertIn("WordCraft on every document", scope)
        note = E._save_notes({"perf.e.passthrough_scope": scope, "perf.e.passthrough_n": 2})
        self.assertNotIn("every sample: GenOffice", note)
        self.assertIn("In both runs", note)

    def test_1_one_differing_sample_in_the_second_run_removes_the_document(self):
        primary = _hash_run({("prose-500w", "genoffice"): ["in-prose-500w"] * 3})
        repro = _hash_run({("prose-500w", "genoffice"): ["in-prose-500w", "in-prose-500w", "other"]})
        self.assertEqual(E._passthrough_scope(primary, repro), "")

    def test_2_a_flat_save_is_an_observation_not_a_cause(self):
        facts = {"perf.e.sd.prose-5kw.save.median": 3.0, "perf.e.sd.prose-250kw.save.median": 3.5,
                 "perf.e.sd.prose-5kw.load.median": 150.0, "perf.e.sd.prose-250kw.load.median": 2500.0}
        found = E._prepared_export(facts, ["sd"])
        note = E._save_notes({"perf.e.prepared_export": found, "perf.e.flat_save_rewrites": True})
        self.assertNotIn("prepared during load", note)
        self.assertNotIn("before the save timer starts", note)
        self.assertIn("The save barely grows with the document.", note)
        self.assertIn("not the input", note)
        self.assertIn("was not traced", note)
        unknown = E._save_notes({"perf.e.prepared_export": found, "perf.e.flat_save_rewrites": False})
        self.assertNotIn("not the input", unknown)

    def test_2_the_file_is_not_the_input_only_when_the_hashes_say_so(self):
        rewrote = _hash_run({("prose-250kw", "sd"): ["new"] * 3})
        kept = _hash_run({("prose-250kw", "sd"): ["new", "in-prose-250kw", "new"]})
        self.assertTrue(E._rewrites(rewrote, rewrote, ["sd"], "prose-250kw"))
        self.assertFalse(E._rewrites(kept, kept, ["sd"], "prose-250kw"))
        self.assertFalse(E._rewrites(rewrote, rewrote, [], "prose-250kw"))

    def test_4_a_second_separator_stays_inside_the_save_cell(self):
        run = _hand_run(["wordcraft"], lanes={"wordcraft": "load | save | extra"})
        table = E._lanes(run).splitlines()
        self.assertEqual({_cells(line.replace("\\|", "")) for line in table}, {3})
        self.assertIn("| WordCraft | load | save \\| extra |", table)

    def test_4_zero_or_one_separator_also_gives_three_cells(self):
        run = _hand_run(["wordcraft", "docen"], lanes={"wordcraft": "whole conversion", "docen": "load | save"})
        table = E._lanes(run).splitlines()
        self.assertEqual({_cells(line) for line in table}, {3})
        self.assertIn("| WordCraft | whole conversion | — |", table)
        self.assertIn("| Docen | load | save |", table)

    def test_5_the_last_error_is_the_latest_failed_sample_s_or_none(self):
        run = E.Run(Path("."), {"workloads": {"w": {}}, "repetitions": 10}, records={("w", "e"): [
            _good_rec(returncode=1, started_at="2026-01-01T00:00:00+00:00", stderr_tail="TypeError: old failure\n"),
            _good_rec(returncode=137, started_at="2026-01-02T00:00:00+00:00", stderr_tail="Killed\n")]})
        self.assertIsNone(E._last_error(run, "w", "e"))
        run.records["w", "e"][1]["stderr_tail"] = "RangeError: new failure\n"
        self.assertEqual(E._last_error(run, "w", "e"), "RangeError: new failure")



class PiReview126(unittest.TestCase):
    """#126: pi (zai/glm-5.3) review of the #124 fixes."""

    def test_1_a_document_rewritten_in_one_run_and_unknown_in_the_other_is_not_every_document(self):
        primary = _hash_run({("prose-500w", "e"): ["in-prose-500w"] * 3, ("complex-corpus", "e"): ["other"] * 3})
        repro = _hash_run({("prose-500w", "e"): ["in-prose-500w"] * 3, ("complex-corpus", "e"): []})
        scope = E._passthrough_scope(primary, repro)
        self.assertNotIn("every document", scope)
        self.assertIn("e on the 500 words document (it rewrote complex.docx)", scope)

    def test_1_a_document_with_no_good_sample_in_one_run_is_named_as_not_known(self):
        primary = _hash_run({("prose-500w", "e"): ["in-prose-500w"] * 3, ("complex-corpus", "e"): ["in-complex-corpus"] * 3})
        repro = _hash_run({("prose-500w", "e"): ["in-prose-500w"] * 3, ("complex-corpus", "e"): []})
        scope = E._passthrough_scope(primary, repro)
        self.assertNotIn("every document", scope)
        self.assertIn("e on the 500 words document (not known for complex.docx)", scope)

    def test_2_a_missing_output_hash_is_not_a_rewrite(self):
        rows = {("prose-500w", "e"): ["in-prose-500w"] * 3, ("complex-corpus", "e"): [None] * 3}
        scope = E._passthrough_scope(_hash_run(rows), _hash_run(rows))
        self.assertNotIn("rewrote", scope)
        self.assertIn("not known for complex.docx", scope)

    def test_2_a_recorded_differing_hash_beside_a_missing_one_is_a_rewrite(self):
        rows = {("prose-500w", "e"): ["in-prose-500w"] * 3, ("complex-corpus", "e"): [None, "other", None]}
        scope = E._passthrough_scope(_hash_run(rows), _hash_run(rows))
        self.assertIn("(it rewrote complex.docx)", scope)

    def _run(self, recs):
        return E.Run(Path("."), {"workloads": {"w": {}}, "repetitions": 10}, records={("w", "e"): recs})

    def test_3_a_newer_timeout_is_the_last_error_not_an_older_crash(self):
        run = self._run([
            _good_rec(returncode=1, started_at="2026-01-01T00:00:00+00:00", stderr_tail="TypeError: old crash\n"),
            _good_rec(returncode=None, timed_out=True, started_at="2026-01-02T00:00:00+00:00", stderr_tail="Error: TIMEOUT kill\n")])
        self.assertEqual(E._last_error(run, "w", "e"), "Error: TIMEOUT kill")

    def test_3_a_newer_exit_0_sample_that_failed_its_marks_hides_the_older_crash(self):
        run = self._run([
            _good_rec(returncode=1, started_at="2026-01-01T00:00:00+00:00", stderr_tail="TypeError: old crash\n"),
            _good_rec(started_at="2026-01-02T00:00:00+00:00", mark_counts={"model_ready_ms": 2, "save_ms": 1}, stderr_tail="")])
        self.assertIsNone(E._last_error(run, "w", "e"))

    def test_3_a_tie_goes_to_the_last_listed_sample(self):
        run = self._run([
            _good_rec(returncode=1, started_at="2026-01-01T00:00:00+00:00", stderr_tail="Error: first\n"),
            _good_rec(returncode=1, started_at="2026-01-01T00:00:00+00:00", stderr_tail="Error: second\n")])
        self.assertEqual(E._last_error(run, "w", "e"), "Error: second")

    def test_4_plural_notes_agree(self):
        note = E._save_notes({"perf.e.prepared_export": "A's save took 1 ms; B's save took 2 ms",
                              "perf.e.passthrough_scope": "X on every document; Y on every document"})
        self.assertIn("Where the editors do that work was not traced", note)
        self.assertIn("these editors wrote back", note)
        one = E._save_notes({"perf.e.prepared_export": "A's save took 1 ms", "perf.e.passthrough_scope": "X on every document"})
        self.assertIn("Where the editor does that work was not traced", one)
        self.assertIn("this editor wrote back", one)


if __name__ == "__main__":
    unittest.main()
