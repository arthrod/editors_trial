"""Findings of the adversarial review of the headless speed runner (#103).

Each class names the codex (gpt-6-astra) finding it pins. A fake lane (a tiny
Python script) stands in for an editor, so these run without editor toolchains.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

from perf.fixtures.docx_workload import deterministic_zip, docx_paragraph_texts, workload_docx
from perf.fixtures.profiles import size_ladder
from perf.runner import host
from perf.runner import speed_headless as sh

REPO = Path(__file__).resolve().parents[2]
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
QUIET = {"quiet": True, "reasons": [], "load_average": [0.5, 0.5, 0.5]}

# A lane whose marks, output and children are set from the environment.
FAKE = textwrap.dedent(
    """
    import os, shutil, subprocess, sys
    src, dst = sys.argv[1], sys.argv[2]
    for line in os.environ.get("FAKE_MARKS", "model_ready_ms=1.5;save_ms=0.5").split(";"):
        if line:
            print("PERF " + line)
    if os.environ.get("FAKE_CHILD"):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        print("CHILD %d" % child.pid, flush=True)
    noise = int(os.environ.get("FAKE_NOISE", "0"))
    if noise:
        sys.stdout.write("o" * noise + "\\n")
        sys.stderr.write("e" * noise + "\\n")
    shutil.copyfile(src, dst)
    sys.exit(int(os.environ.get("FAKE_RC", "0")))
    """
)


def _paragraphs_xml(paragraphs: list[str]) -> bytes:
    body = "".join(
        '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % p.replace("&", "&amp;").replace("<", "&lt;")
        for p in paragraphs
    )
    return ('<?xml version="1.0"?><w:document xmlns:w="%s"><w:body>%s</w:body></w:document>' % (W, body)).encode("utf-8")


def _docx(path: Path, document_xml: bytes) -> Path:
    path.write_bytes(deterministic_zip([("word/document.xml", document_xml)]))
    return path


def _input_paragraphs(meta: dict) -> list[str]:
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(meta["docx"])) as zf:
        return docx_paragraph_texts(zf.read("word/document.xml"))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.script = self.root / "fake_lane.py"
        self.script.write_text(FAKE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def lane(self, marks=("model_ready_ms", "save_ms"), **env):
        return {
            "cmd": lambda i, o, w: [sys.executable, str(self.script), str(i), str(o)],
            "cwd": REPO,
            "env": dict({"PYTHONPATH": str(REPO)}, **env),
            "marks": tuple(marks),
            "boundary": "fake",
        }

    def suite(self, lanes, reps=2, workloads=("prose-500w",), warmup=1, profile="ci_broad"):
        with mock.patch.object(sh, "quiet_machine_check", return_value=QUIET), mock.patch.object(
            sh, "pin_label", side_effect=lambda e: "fake-pin-%s" % e
        ):
            return sh.run_suite(
                lanes=lanes, workloads=list(workloads), repetitions=reps, seed=3, out_root=self.root / "out",
                execution_profile=profile, timeout_s=60, warmup=warmup,
            )

    def row(self, summary, editor, criterion="C02"):
        return next(r for r in summary["rows"] if r["editor_id"] == editor and r["criterion_id"] == criterion)


# ------------------------------------------------- findings 6, 7 and 17 ----

class OneExtractor(unittest.TestCase):
    """Finding 7: input and output text come from one paragraph-aware extractor."""

    def test_nested_paragraph_text_is_counted_once(self):
        xml = (
            '<w:document xmlns:w="%s"><w:body><w:p><w:r><w:t>outer</w:t></w:r><w:r><w:pict>'
            "<w:txbxContent><w:p><w:r><w:t>inner</w:t></w:r></w:p></w:txbxContent>"
            "</w:pict></w:r><w:r><w:t> tail</w:t></w:r></w:p></w:body></w:document>" % W
        ).encode()
        self.assertEqual(docx_paragraph_texts(xml), ["outer tail", "inner"])

    def test_entities_and_any_prefix_are_read(self):
        xml = ('<x:document xmlns:x="%s"><x:body><x:p><x:r><x:t>caf&#233; &amp; co</x:t></x:r></x:p></x:body></x:document>' % W).encode()
        self.assertEqual(docx_paragraph_texts(xml), ["café & co"])

    def test_deleted_text_is_not_text(self):
        xml = ('<w:document xmlns:w="%s"><w:body><w:p><w:r><w:delText>gone</w:delText></w:r><w:r><w:t>kept</w:t></w:r></w:p></w:body></w:document>' % W).encode()
        self.assertEqual(docx_paragraph_texts(xml), ["kept"])

    def test_every_workload_checks_complete_against_itself(self):
        for row in size_ladder():
            wid = row["workload_id"]
            if wid == "prose-250kw":
                continue  # same builder as prose-50kw; 13 MB of XML is slow here
            with self.subTest(workload=wid), tempfile.TemporaryDirectory() as tmp:
                meta = workload_docx(wid)
                path = Path(tmp) / "same.docx"
                path.write_bytes(meta["docx"])
                result = sh.check_output(path, sh._expectation(meta))
                self.assertEqual(result["token_overlap"], 1.0)
                self.assertEqual(result["word_ratio"], 1.0)
                self.assertTrue(result["complete"], result)

    def test_corpus_word_count_uses_the_checker_extractor(self):
        meta = workload_docx("complex-corpus")
        words = sum(len(p.split()) for p in _input_paragraphs(meta))
        self.assertEqual(meta["word_count"], words)


class StrictCheck(Base):
    """Finding 6: a saved file must hold the document, once, ending with the sentinel."""

    def setUp(self):
        super().setUp()
        self.meta = workload_docx("prose-500w")
        self.expect = sh._expectation(self.meta)
        self.paras = _input_paragraphs(self.meta)
        self.assertIn(self.meta["sentinel"], self.paras[-1])

    def check(self, paragraphs):
        return sh.check_output(_docx(self.root / "o.docx", _paragraphs_xml(paragraphs)), self.expect)

    def test_the_same_paragraphs_pass(self):
        self.assertTrue(self.check(self.paras)["complete"])

    def test_a_trailing_empty_paragraph_is_allowed(self):
        self.assertTrue(self.check([*self.paras, ""])["complete"])

    def test_a_duplicated_document_fails(self):
        result = self.check(self.paras + self.paras)
        self.assertFalse(result["complete"])
        self.assertGreater(result["word_ratio"], 1.9)

    def test_replaced_words_fail_even_at_the_same_count(self):
        # replace whole paragraphs, in order, until 5 percent of the words are gone
        total = sum(len(p.split()) for p in self.paras)
        replaced, gone = [], 0
        for p in self.paras[:-1]:
            if gone < 0.05 * total:
                replaced.append(" ".join("lorem" for _ in p.split()))
                gone += len(p.split())
            else:
                replaced.append(p)
        replaced.append(self.paras[-1])
        result = self.check(replaced)
        self.assertEqual(result["word_ratio"], 1.0)
        self.assertLess(result["token_overlap"], 0.98)
        self.assertFalse(result["complete"])

    def test_the_sentinel_must_close_the_document(self):
        moved = [self.paras[-1], *self.paras[:-1]]
        result = self.check(moved)
        self.assertTrue(result["sentinel"])
        self.assertFalse(result["sentinel_last"])
        self.assertFalse(result["complete"])

    def test_a_workload_without_a_sentinel_does_not_need_one(self):
        meta = workload_docx("micro-paragraphs")
        self.assertIsNone(meta["sentinel"])
        path = self.root / "m.docx"
        path.write_bytes(meta["docx"])
        result = sh.check_output(path, sh._expectation(meta))
        self.assertIsNone(result["sentinel"])
        self.assertTrue(result["complete"])


# ------------------------------------------------- findings 8, 15 and 4 ----

class Marks(Base):
    """Findings 8 and 15: every required PERF mark, exactly once, or the sample fails."""

    def test_a_missing_mark_fails_every_criterion_of_the_sample(self):
        summary = self.suite({"a": self.lane(FAKE_MARKS="model_ready_ms=1.5")})
        for criterion in ("C02", "C16"):
            row = self.row(summary, "a", criterion)
            self.assertEqual(row["outcome"], "failed")
            self.assertIn("marks: missing save_ms", row["failure_reason"])

    def test_a_mark_printed_twice_fails_the_sample(self):
        summary = self.suite({"a": self.lane(FAKE_MARKS="model_ready_ms=1.5;save_ms=0.5;save_ms=0.7")})
        row = self.row(summary, "a", "C02")
        self.assertEqual(row["outcome"], "failed")
        self.assertIn("save_ms printed 2 times", row["failure_reason"])

    def test_a_mark_that_is_not_a_time_fails_the_sample_not_the_run(self):
        for bad in ("inf", "nan", "-1"):
            with self.subTest(value=bad):
                summary = self.suite({"a": self.lane(FAKE_MARKS="model_ready_ms=1.5;save_ms=%s" % bad)}, reps=1)
                row = self.row(summary, "a", "C16")
                self.assertEqual(row["outcome"], "failed")
                self.assertIn("not a time", row["failure_reason"])
                self.tearDown()
                self.setUp()

    def test_the_record_keeps_mark_counts(self):
        self.suite({"a": self.lane()}, reps=1)
        record = json.loads(next((self.root / "out" / "samples").rglob("r001.json")).read_text())
        self.assertEqual(record["mark_counts"], {"model_ready_ms": 1, "save_ms": 1})
        self.assertEqual(record["required_marks"], ["model_ready_ms", "save_ms"])

    def test_superdoc_must_report_its_host_start(self):
        self.assertIn("host_start_ms", sh.default_lanes()["superdoc"]["marks"])

    def test_host_start_median_uses_only_reported_values(self):
        marks = ("model_ready_ms", "save_ms", "host_start_ms")
        summary = self.suite({"a": self.lane(marks, FAKE_MARKS="model_ready_ms=1.5;save_ms=0.5;host_start_ms=40")}, reps=3)
        self.assertEqual(self.row(summary, "a")["host_start_ms_median"], 40.0)

    def test_a_missing_host_start_fails_the_sample_instead_of_reading_zero(self):
        marks = ("model_ready_ms", "save_ms", "host_start_ms")
        summary = self.suite({"a": self.lane(marks)}, reps=2)
        row = self.row(summary, "a")
        self.assertEqual(row["outcome"], "failed")
        self.assertIn("marks: missing host_start_ms", row["failure_reason"])


# ---------------------------------------------------------- finding 13 ----

class Descendants(Base):
    """Finding 13: a process the lane leaves running is found, killed and flagged."""

    def test_a_child_left_running_is_flagged_and_killed(self):
        meta = workload_docx("prose-500w")
        lane = self.lane(FAKE_CHILD="1")
        record = sh.run_sample(lane, "a", meta, sh._expectation(meta), self.root / "w", 60)
        pid = int(next(line.split()[1] for line in record["stdout_tail"].splitlines() if line.startswith("CHILD")))
        self.assertFalse(record["resources_complete"])
        self.assertGreaterEqual(record["survivors"], 1)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            self.fail("child %d still running" % pid)

    def test_a_lane_that_waits_for_its_children_is_complete(self):
        meta = workload_docx("prose-500w")
        record = sh.run_sample(self.lane(), "a", meta, sh._expectation(meta), self.root / "w", 60)
        self.assertTrue(record["resources_complete"])
        self.assertEqual(record["survivors"], 0)


# ---------------------------------------------------------- finding 14 ----

def _ps(rows):
    return "\n".join("%d %d %.1f %s" % row for row in rows) + "\n"


class QuietCheck(unittest.TestCase):
    """Finding 14: the quiet check fails closed and excludes only its own process tree."""

    def check(self, ps_text):
        def fake_run(cmd):
            return ps_text if cmd[0] == "ps" else None

        with mock.patch.object(host, "_run", side_effect=fake_run), mock.patch.object(
            host, "_load_average", return_value=(0.5, 0.5, 0.5)
        ), mock.patch.object(host, "_logical_cpus", return_value=12):
            return host.quiet_machine_check()

    def test_no_process_list_is_not_quiet(self):
        result = self.check(None)
        self.assertFalse(result["quiet"])
        self.assertTrue(any("process list" in r for r in result["reasons"]))

    def test_own_descendants_are_excluded(self):
        me = os.getpid()
        result = self.check(_ps([(me, 1, 5.0, "python3 runner"), (me + 1, me, 90.0, "node harness/plate")]))
        self.assertTrue(result["quiet"], result["reasons"])

    def test_own_ancestors_are_excluded(self):
        me, parent = os.getpid(), os.getppid()
        rows = [(parent, 1, 0.0, "zsh -c python3 build/word_verdicts.py-looking command"), (me, parent, 5.0, "python3 runner")]
        result = self.check(_ps(rows))
        self.assertTrue(result["quiet"], result["reasons"])

    def test_a_foreign_runner_is_not_excluded_by_its_name(self):
        me = os.getpid()
        result = self.check(_ps([(me, 1, 5.0, "python3 x"), (99999, 1, 90.0, "python3 perf/runner/speed_headless.py")]))
        self.assertFalse(result["quiet"])
        self.assertTrue(any("perf/runner/speed_headless.py" in r for r in result["reasons"]))

    def _crowd(self, *extra):
        me = os.getpid()
        rows = [(me, 1, 5.0, "python3 x")] + [(1000 + k, 1, 1.0, "proc%d" % k) for k in range(30)]
        return self.check(_ps(rows + list(extra)))

    def test_a_word_driver_is_a_job_however_idle(self):
        result = self._crowd((5001, 1, 0.0, "python3 build/word_verdicts.py --set broken"))
        self.assertTrue(result["heavy_trial_job_seen"])
        self.assertFalse(result["quiet"])

    def test_an_osascript_driving_word_is_a_job(self):
        result = self._crowd((5002, 1, 0.0, "osascript -e tell application \"Microsoft Word\" to open"))
        self.assertTrue(result["heavy_trial_job_seen"])

    def test_an_open_idle_word_is_not_a_job(self):
        # AGENTS.md section 3 forbids another Word *job*; Word left open at 0 % CPU is none.
        result = self._crowd((5000, 1, 0.0, "/Applications/Microsoft Word.app/Contents/MacOS/Microsoft Word"))
        self.assertFalse(result["heavy_trial_job_seen"])
        self.assertTrue(result["quiet"], result["reasons"])

    def test_a_busy_word_is_not_quiet(self):
        result = self._crowd((5000, 1, 80.0, "/Applications/Microsoft Word.app/Contents/MacOS/Microsoft Word"))
        self.assertFalse(result["quiet"])


class PowerPerSample(Base):
    """Finding 14: power is recorded per sample, and a battery sample blocks publication."""

    def test_each_record_carries_its_power_source(self):
        self.suite({"a": self.lane()}, reps=1)
        record = json.loads(next((self.root / "out" / "samples").rglob("r001.json")).read_text())
        self.assertIn(record["power_source"], ("ac", "battery", "unknown"))

    def _rows(self, power):
        meta = workload_docx("prose-500w")
        good = {
            "timed_out": False, "returncode": 0, "check": {"complete": True, "word_ratio": 1.0, "correctness": {}},
            "marks": {"model_ready_ms": 2.0, "save_ms": 1.0}, "mark_counts": {"model_ready_ms": 1, "save_ms": 1},
            "required_marks": ["model_ready_ms", "save_ms"], "noisy": False, "wall_ms": 50.0, "cpu_ms": 40.0,
            "max_rss_bytes": 1000, "resources_complete": True,
        }
        records = [dict(good, power_source=power[k % len(power)]) for k in range(10)]
        with mock.patch.object(sh, "pin_label", side_effect=lambda e: "fake-pin-%s" % e):
            return sh._rows_for(self.lane(), "a", meta, records, sh.host_record(), "dedicated", "dedicated_publish", self.root / "o", "rid")

    def test_all_on_ac_is_publishable(self):
        self.assertTrue(all(r["publishable"] for r in self._rows(["ac"])))

    def test_one_battery_sample_blocks_publication(self):
        rows = self._rows(["ac"] * 9 + ["battery"])
        self.assertTrue(all(r["publishable"] is False for r in rows))
        self.assertIn("battery", rows[0]["publication_block_reason"])


# ---------------------------------------------------------- finding 16 ----

class WarmUp(unittest.TestCase):
    def test_a_publication_run_needs_a_warm_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as caught:
                sh.run_suite(
                    lanes={}, workloads=["prose-500w"], repetitions=10, seed=1, out_root=Path(tmp) / "out",
                    execution_profile="dedicated_publish", timeout_s=10, warmup=0,
                )
            self.assertIn("warm-up", str(caught.exception))
            self.assertFalse((Path(tmp) / "out").exists())


class WorkloadCap(Base):
    """Smoke run 2026-11-09: a capped workload aborted the run after two workloads, losing the summary."""

    def test_a_workload_the_profile_does_not_allow_is_refused_before_any_sample(self):
        with self.assertRaises(ValueError):
            self.suite({"a": self.lane()}, reps=1, workloads=("prose-500w", "complex-corpus"))
        self.assertFalse((self.root / "out" / "samples").exists())


# ---------------------------------------------------------- finding 18 ----

class Evidence(Base):
    """Finding 18: a failed sample keeps its full logs and its output file."""

    def test_a_failed_sample_keeps_full_logs_and_output(self):
        self.suite({"a": self.lane(FAKE_RC="7", FAKE_NOISE="9000")}, reps=1)
        sample_dir = self.root / "out" / "samples" / "prose-500w" / "a"
        self.assertEqual(len((sample_dir / "r001.stdout.log").read_text()), 9000 + 1 + len("PERF model_ready_ms=1.5\nPERF save_ms=0.5\n"))
        self.assertGreater(len((sample_dir / "r001.stderr.log").read_text()), 9000)
        self.assertTrue((sample_dir / "r001.out.docx").is_file())
        record = json.loads((sample_dir / "r001.json").read_text())
        self.assertEqual(record["evidence"], {"stdout": "r001.stdout.log", "stderr": "r001.stderr.log", "output": "r001.out.docx"})

    def test_a_good_sample_keeps_tails_only(self):
        self.suite({"a": self.lane()}, reps=1)
        sample_dir = self.root / "out" / "samples" / "prose-500w" / "a"
        self.assertFalse(list(sample_dir.glob("r001.*.log")))
        self.assertIsNone(json.loads((sample_dir / "r001.json").read_text())["evidence"])


# ---------------------------------------------------------- finding 12 ----

class Attestation(unittest.TestCase):
    def test_declared_and_installed_package_versions_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "node_modules" / "pkg").mkdir(parents=True)
            (root / "package.json").write_text(json.dumps({"dependencies": {"pkg": "1.2.3"}}))
            (root / "node_modules" / "pkg" / "package.json").write_text(json.dumps({"version": "1.2.4"}))
            self.assertEqual(sh._package_record(root, "pkg"), {"declared": "1.2.3", "installed": "1.2.4", "matches": False})
            (root / "node_modules" / "pkg" / "package.json").write_text(json.dumps({"version": "1.2.3"}))
            self.assertTrue(sh._package_record(root, "pkg")["matches"])

    def test_changed_tracked_files_are_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
            subprocess.run([*git[:3], "init", "-q"], check=True)
            (repo / "a.txt").write_text("a")
            (repo / "b.txt").write_text("b")
            subprocess.run([*git, "add", "."], check=True)
            subprocess.run([*git, "commit", "-qm", "x"], check=True)
            self.assertEqual(sh._dirty_tracked(repo), [])
            (repo / "a.txt").write_text("changed")
            (repo / "b.txt").unlink()
            (repo / "new.txt").write_text("untracked")
            self.assertEqual(sh._dirty_tracked(repo), [["M", "a.txt"], ["D", "b.txt"]])

    def test_only_listed_deletions_are_allowed(self):
        ok, why = sh._dirty_verdict("repos/office-open", [["D", "scripts/coverage/xsd.ts"]])
        self.assertTrue(ok)
        self.assertIn("scripts/coverage/", why)
        self.assertFalse(sh._dirty_verdict("repos/office-open", [["M", "scripts/coverage/xsd.ts"]])[0])
        self.assertFalse(sh._dirty_verdict("repos/office-open", [["D", "packages/docx/src/index.ts"]])[0])
        self.assertFalse(sh._dirty_verdict("repos/plate", [["D", "scripts/coverage/xsd.ts"]])[0])
        self.assertEqual(sh._dirty_verdict("repos/plate", []), (True, None))

    def test_finder_ds_store_noise_is_not_a_checkout_change(self):
        # macOS Finder drops untracked .DS_Store files into every directory;
        # they are not the editors' code, so the verdict allows them (the
        # reason names them) while any other untracked file still refuses.
        ok, why = sh._dirty_verdict("repos/docen", [["?", ".DS_Store"]])
        self.assertTrue(ok)
        self.assertIn(".DS_Store", why)
        ok2, why2 = sh._dirty_verdict(
            "repos/docen", [["?", ".DS_Store"], ["?", "scratch.ts"]]
        )
        self.assertFalse(ok2)
        # Finder drops them in subdirectories too.
        ok3, why3 = sh._dirty_verdict(
            "repos/fiduswriter-document-ts", [["?", "demo/.DS_Store"], ["?", ".DS_Store"]]
        )
        self.assertTrue(ok3)
        self.assertFalse(
            sh._dirty_verdict("repos/fiduswriter-document-ts", [["M", "demo/.DS_Store"]])[0]
        )
        self.assertFalse(sh._dirty_verdict("repos/docen", [["M", ".DS_Store"]])[0])

    def test_docsplus_attests_the_copy_it_runs(self):
        self.assertIn("harness/docsplus/repo-copy", sh.ATTEST["docsplus"]["checkouts"])

    def test_dedicated_publish_refuses_a_package_mismatch(self):
        versions = {"tools": {}, "editors": {"a": {"matches_pin": True, "packages_match": False, "clean": True,
                                                    "pin": "p", "checkouts": {}, "packages": {"x": {"matches": False}}}}}
        self._refuses(versions, "package")

    def test_dedicated_publish_refuses_a_dirty_checkout(self):
        versions = {"tools": {}, "editors": {"a": {"matches_pin": True, "packages_match": True, "clean": False,
                                                    "pin": "p", "checkouts": {}, "dirty": {"repos/a": [["M", "f"]]}}}}
        self._refuses(versions, "dirty")

    def _refuses(self, versions, word):
        on_ac = dict(sh.host_record(), power_source="ac")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(sh, "quiet_machine_check", return_value=QUIET), \
                mock.patch.object(sh, "host_record", return_value=on_ac), mock.patch.object(sh, "_build_lanes"), \
                mock.patch.object(sh, "attest_versions", return_value=versions):
            with self.assertRaises(sh.PinMismatch) as caught:
                sh.run_suite(lanes={"a": {"cmd": None, "cwd": Path(tmp)}}, workloads=["prose-500w"], repetitions=10,
                             seed=1, out_root=Path(tmp) / "out", execution_profile="dedicated_publish", timeout_s=10)
            self.assertIn(word, str(caught.exception))
            self.assertFalse((Path(tmp) / "out" / "samples").exists())

    def test_a_publication_run_builds_wordcraft_first_and_stops_if_the_build_fails(self):
        self.assertEqual(sh.BUILD_STEPS["wordcraft"][0][:3], ["cargo", "build", "--release"])
        failed = subprocess.CompletedProcess(["cargo"], 101, stdout="", stderr="error[E0425]: oops")
        with mock.patch.object(sh.subprocess, "run", return_value=failed):
            with self.assertRaises(sh.BuildFailed) as caught:
                sh._build_lanes(["plate", "wordcraft"])
        self.assertIn("E0425", str(caught.exception))


class Provenance(Base):
    """Finding 1 (runner side): the summary names the code that produced it."""

    def test_summary_names_runner_repo_and_lane_files(self):
        summary = self.suite({"a": self.lane()}, reps=1)
        prov = summary["provenance"]
        self.assertEqual(prov["runner_sha256"], hashlib.sha256((REPO / "perf/runner/speed_headless.py").read_bytes()).hexdigest())
        self.assertRegex(prov["repo_head"], r"^[0-9a-f]{40}$")
        self.assertIn("a", prov["lanes"])

    @unittest.skipUnless((REPO / "harness" / "fidus" / "roundtrip.mts").exists(), "harness not checked out")
    def test_lane_files_are_hashed(self):
        lanes = sh.default_lanes()
        fidus = sh.lane_files(lanes["fidus"])
        self.assertEqual(fidus["harness/fidus/roundtrip.mts"], hashlib.sha256((REPO / "harness/fidus/roundtrip.mts").read_bytes()).hexdigest())
        plate = sh.lane_files(lanes["plate"])
        self.assertIn("harness/plate/roundtrip.ts", plate)
        self.assertIn("harness/plate/aliases.ts", plate)
        self.assertTrue(any(k.startswith("harness/canvas/") for k in sh.lane_files(lanes["canvas"])))
        self.assertIn("harness/css-stub.mjs", sh.lane_files(lanes["genoffice"]))


if __name__ == "__main__":
    unittest.main()


class RelativeOutRoot(Base):
    """#118: the publication launcher passes a relative --out-root. The
    LibreOffice lane builds its profile URI with Path.as_uri(), which raises
    on a relative path, so both runs died on the first LibreOffice sample."""

    def test_lanes_get_absolute_paths_from_a_relative_out_root(self):
        seen = []
        lane = self.lane()
        base_cmd = lane["cmd"]

        def cmd(i, o, w):
            seen.append((i.is_absolute(), o.is_absolute(), w.is_absolute(), (w / "lo-profile").as_uri()))
            return base_cmd(i, o, w)

        lane["cmd"] = cmd
        old = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, old)
        with mock.patch.object(sh, "quiet_machine_check", return_value=QUIET), mock.patch.object(
            sh, "pin_label", side_effect=lambda e: "fake-pin-%s" % e
        ):
            summary = sh.run_suite(lanes={"a": lane}, workloads=["prose-500w"], repetitions=1, seed=3,
                                   out_root=Path("out"), execution_profile="ci_broad", timeout_s=60, warmup=1)
        self.assertTrue(seen)
        self.assertTrue(all(i and o and w for i, o, w, _ in seen), seen)
        self.assertTrue((self.root / "out" / "summary.json").is_file())
        self.assertEqual(self.row(summary, "a")["outcome"], "measured")


class MissingBinary(Base):
    """#119 (grok #12): a lane binary that is not there refuses a publication run."""

    def test_a_missing_binary_is_a_pin_mismatch(self):
        versions = {"tools": {}, "editors": {"a": {"pin": "p", "matches_pin": True, "clean": True, "packages_match": None,
                                                   "binaries": {"wc-harness": None}, "checkouts": {}, "packages": {}}}}
        with mock.patch.object(sh, "attest_versions", return_value=versions), mock.patch.object(
            sh, "_build_lanes", return_value={}
        ), mock.patch.object(sh, "power_source", return_value="ac"), mock.patch.object(
            sh, "host_record", return_value=dict(sh.host_record(), power_source="ac")
        ):
            with self.assertRaisesRegex(sh.PinMismatch, "wc-harness"):
                self.suite({"a": self.lane()}, reps=10, profile="dedicated_publish")
