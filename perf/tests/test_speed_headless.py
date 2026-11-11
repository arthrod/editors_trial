"""Contract for the headless speed runner (arthrod/editors_trial#103).

A fake lane (a tiny Python script) stands in for an editor, so these tests
run without any editor toolchain.
"""

from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from perf.runner import speed_headless as sh
from perf.schema import validate_trial

FAKE = textwrap.dedent(
    """
    import os, shutil, sys, time
    src, dst = sys.argv[1], sys.argv[2]
    mode = os.environ.get("FAKE_MODE", "ok")
    time.sleep(0.01)
    print("PERF model_ready_ms=1.5")
    print("PERF save_ms=0.5")
    print("ENV EDITOR_CONFIG=%s" % os.environ.get("EDITOR_CONFIG", "<unset>"))
    if mode == "drop":
        from perf.fixtures.generate import docx_zip_bytes
        open(dst, "wb").write(docx_zip_bytes(b"nothing here\\n"))
    elif mode == "crash":
        sys.exit(7)
    else:
        shutil.copyfile(src, dst)
    """
)


def _fake_lane(script: Path, mode: str = "ok") -> dict:
    return {
        "cmd": lambda indocx, outdocx, work: [sys.executable, str(script), str(indocx), str(outdocx)],
        "cwd": Path(__file__).resolve().parents[2],
        "env": {"FAKE_MODE": mode, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        "marks": ("model_ready_ms", "save_ms"),
        "boundary": "fake",
    }


class Order(unittest.TestCase):
    def test_every_repetition_runs_every_editor_once(self):
        plan = sh.plan_order(["a", "b", "c"], repetitions=4, seed=7)
        self.assertEqual(len(plan), 4)
        for rep, order in plan:
            self.assertEqual(sorted(order), ["a", "b", "c"])

    def test_orders_are_reshuffled_and_reproducible(self):
        plan = sh.plan_order(list("abcdefgh"), repetitions=6, seed=7)
        self.assertGreater(len({tuple(order) for _, order in plan}), 1)
        self.assertEqual(plan, sh.plan_order(list("abcdefgh"), repetitions=6, seed=7))


class ControlledEnvironment(unittest.TestCase):
    def test_inherited_switches_do_not_leak(self):
        with mock.patch.dict("os.environ", {"EDITOR_CONFIG": "suggested", "OUT_DIR": "/elsewhere"}):
            env = sh.controlled_env({"X": "1"})
        self.assertNotIn("EDITOR_CONFIG", env)
        self.assertNotIn("OUT_DIR", env)
        self.assertEqual(env["PERF_ONLY"], "1")
        self.assertEqual(env["X"], "1")
        self.assertIn("PATH", env)


class Suite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.script = self.root / "fake_editor.py"
        self.script.write_text(FAKE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, lanes, reps=2, workloads=("prose-500w",), warmup=1):
        quiet = {"quiet": True, "reasons": [], "load_average": [0.5, 0.5, 0.5]}
        with mock.patch.object(sh, "quiet_machine_check", return_value=quiet), mock.patch.object(
            sh, "pin_label", side_effect=lambda e: "fake-pin-%s" % e
        ):
            return sh.run_suite(
                lanes=lanes,
                workloads=list(workloads),
                repetitions=reps,
                seed=3,
                out_root=self.root / "out",
                execution_profile="ci_broad",
                timeout_s=60,
                warmup=warmup,
            )

    def test_one_record_per_sample_plus_warmups(self):
        lanes = {"a": _fake_lane(self.script), "b": _fake_lane(self.script)}
        self._run(lanes, reps=2)
        records = sorted((self.root / "out" / "samples").rglob("*.json"))
        self.assertEqual(len(records), 2 * 2 + 2)  # 2 editors x 2 reps + 1 warm-up each
        sample = json.loads(records[-1].read_text())
        for key in (
            "editor_id", "workload_id", "repetition", "order_index", "command", "env_keys", "returncode",
            "marks", "wall_ms", "cpu_ms", "stdout_tail", "stderr_tail", "output_sha256", "check",
            "load_before", "load_after", "started_at", "warmup",
        ):
            self.assertIn(key, sample)

    def test_documents_are_written_where_spotlight_does_not_index(self):
        lanes = {"a": _fake_lane(self.script)}
        self._run(lanes, reps=1)
        record = json.loads(next((self.root / "out" / "samples").rglob("r001.json")).read_text())
        self.assertTrue(any("work.noindex" in part for part in record["command"]))

    def test_inherited_editor_config_does_not_reach_the_lane(self):
        lanes = {"a": _fake_lane(self.script)}
        with mock.patch.dict("os.environ", {"EDITOR_CONFIG": "suggested"}):
            self._run(lanes, reps=1)
        record = next((self.root / "out" / "samples").rglob("r001.json"))
        self.assertIn("ENV EDITOR_CONFIG=<unset>", json.loads(record.read_text())["stdout_tail"])

    def test_trials_validate_and_carry_both_criteria(self):
        lanes = {"a": _fake_lane(self.script)}
        summary = self._run(lanes, reps=3)
        trials = sorted((self.root / "out" / "trials").glob("*.json"))
        self.assertEqual({t.name.split("-")[0] for t in trials}, {"c02", "c16"})
        for t in trials:
            trial = json.loads(t.read_text())
            validate_trial(trial)
            self.assertEqual(trial["outcome"], "measured")
            self.assertEqual(trial["samples_ms"], [1.5, 1.5, 1.5] if t.name.startswith("c02") else [0.5, 0.5, 0.5])
            self.assertEqual(trial["environment"]["workload_id"], "prose-500w")
            self.assertEqual(trial["environment"]["cpu_model"] != "arm", True)
        row = next(r for r in summary["rows"] if r["criterion_id"] == "C02" and r["editor_id"] == "a")
        self.assertEqual(row["n"], 3)
        self.assertEqual(row["median_ms"], 1.5)

    def test_an_output_that_lost_the_document_is_excluded_not_zeroed(self):
        lanes = {"drops": _fake_lane(self.script, mode="drop")}
        summary = self._run(lanes, reps=2)
        row = next(r for r in summary["rows"] if r["criterion_id"] == "C02")
        self.assertEqual(row["outcome"], "failed")
        self.assertIn("correctness", row["failure_reason"])
        self.assertEqual(row["excluded"], 2)
        record = json.loads(next((self.root / "out" / "samples").rglob("r001.json")).read_text())
        self.assertFalse(record["check"]["complete"])
        self.assertFalse(record["check"]["sentinel"])

    def test_a_crash_keeps_the_other_samples(self):
        lanes = {"ok": _fake_lane(self.script), "bad": _fake_lane(self.script, mode="crash")}
        summary = self._run(lanes, reps=2)
        ok = next(r for r in summary["rows"] if r["criterion_id"] == "C02" and r["editor_id"] == "ok")
        bad = next(r for r in summary["rows"] if r["criterion_id"] == "C02" and r["editor_id"] == "bad")
        self.assertEqual(ok["outcome"], "measured")
        self.assertEqual(bad["outcome"], "failed")
        self.assertIn("rc=7", bad["failure_reason"])

    def test_an_editor_that_keeps_failing_stops_being_sampled_on_that_workload(self):
        lanes = {"ok": _fake_lane(self.script), "bad": _fake_lane(self.script, mode="crash")}
        quiet = {"quiet": True, "reasons": [], "load_average": [0.5, 0.5, 0.5]}
        with mock.patch.object(sh, "quiet_machine_check", return_value=quiet), mock.patch.object(
            sh, "pin_label", side_effect=lambda e: "fake-pin-%s" % e
        ):
            summary = sh.run_suite(
                lanes=lanes, workloads=["prose-500w"], repetitions=5, seed=3, out_root=self.root / "out",
                execution_profile="ci_broad", timeout_s=60, warmup=1, max_consecutive_failures=3,
            )
        bad_records = list((self.root / "out" / "samples" / "prose-500w" / "bad").glob("*.json"))
        ok_records = list((self.root / "out" / "samples" / "prose-500w" / "ok").glob("r*.json"))
        self.assertEqual(len(bad_records), 3)  # warm-up + 2 repetitions, then stopped
        self.assertEqual(len(ok_records), 5)
        bad = next(r for r in summary["rows"] if r["editor_id"] == "bad" and r["criterion_id"] == "C02")
        self.assertIn("stopped after 3 consecutive failures", bad["failure_reason"])

    def test_workloads_are_never_pooled(self):
        lanes = {"a": _fake_lane(self.script)}
        summary = self._run(lanes, reps=2, workloads=("prose-500w", "micro-paragraphs"))
        keys = {(r["workload_id"], r["criterion_id"]) for r in summary["rows"] if r["editor_id"] == "a"}
        self.assertEqual(keys, {("prose-500w", "C02"), ("prose-500w", "C16"), ("micro-paragraphs", "C02"), ("micro-paragraphs", "C16")})

    def test_ci_broad_is_never_publishable(self):
        summary = self._run({"a": _fake_lane(self.script)}, reps=2)
        self.assertTrue(all(r["publishable"] is False for r in summary["rows"]))


class QuietGate(unittest.TestCase):
    def test_dedicated_publish_refuses_on_a_noisy_machine(self):
        noisy = {"quiet": False, "reasons": ["1-minute load average 21.42 exceeds 4.00"], "load_average": [21.4, 14, 12]}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(sh, "quiet_machine_check", return_value=noisy):
            with self.assertRaises(sh.NotQuiet) as caught:
                sh.run_suite(
                    lanes={},
                    workloads=["prose-500w"],
                    repetitions=1,
                    seed=1,
                    out_root=Path(tmp) / "out",
                    execution_profile="dedicated_publish",
                    timeout_s=10,
                )
            self.assertIn("load average", str(caught.exception))
            self.assertFalse((Path(tmp) / "out" / "samples").exists())

    def test_dedicated_publish_refuses_battery_power(self):
        quiet = {"quiet": True, "reasons": [], "load_average": [0.5, 0.5, 0.5]}
        real = sh.host_record()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            sh, "quiet_machine_check", return_value=quiet
        ), mock.patch.object(sh, "host_record", return_value=dict(real, power_source="battery")):
            with self.assertRaises(sh.NotQuiet) as caught:
                sh.run_suite(
                    lanes={},
                    workloads=["prose-500w"],
                    repetitions=1,
                    seed=1,
                    out_root=Path(tmp) / "out",
                    execution_profile="dedicated_publish",
                    timeout_s=10,
                )
            self.assertIn("battery", str(caught.exception))
            self.assertFalse((Path(tmp) / "out" / "samples").exists())


HOG = textwrap.dedent(
    """
    import shutil, sys, time
    block = bytearray(%d)
    for i in range(0, len(block), 4096):
        block[i] = 1
    t = time.process_time()
    while time.process_time() - t < %f:
        pass
    print("PERF model_ready_ms=1.0")
    print("PERF save_ms=1.0")
    shutil.copyfile(sys.argv[1], sys.argv[2])
    """
)


class PerSampleResources(unittest.TestCase):
    """CPU and peak memory belong to the sample's own process tree."""

    def _sample(self, nbytes, cpu_s, timeout=60):
        from perf.fixtures.docx_workload import workload_docx

        meta = workload_docx("prose-500w")
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "hog.py"
            script.write_text(HOG % (nbytes, cpu_s), encoding="utf-8")
            lane = _fake_lane(script)
            return sh.run_sample(lane, "hog", meta, sh._expectation(meta), Path(tmp) / "w", timeout)

    def test_peak_memory_of_the_sample_is_recorded(self):
        big = self._sample(200 * 1024 * 1024, 0.0)
        small = self._sample(1024, 0.0)
        self.assertGreater(big["max_rss_bytes"], 200 * 1024 * 1024)
        self.assertLess(small["max_rss_bytes"], 100 * 1024 * 1024)

    def test_cpu_time_is_the_samples_own(self):
        busy = self._sample(1024, 0.5)
        self.assertGreater(busy["cpu_ms"], 450)
        self.assertLess(busy["cpu_ms"], 5000)

    def test_timeout_kills_and_is_recorded(self):
        from perf.fixtures.docx_workload import workload_docx

        meta = workload_docx("prose-500w")
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "hang.py"
            script.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
            t0 = __import__("time").monotonic()
            rec = sh.run_sample(_fake_lane(script), "hang", meta, sh._expectation(meta), Path(tmp) / "w", 1.0)
            self.assertLess(__import__("time").monotonic() - t0, 15)
        self.assertTrue(rec["timed_out"])
        self.assertEqual(sh._sample_failure(rec), "timeout")


class VersionAttestation(unittest.TestCase):
    """The run records what it measured, read from disk, not from a label."""

    def test_checkouts_packages_binaries_and_tools_are_read(self):
        att = sh.attest_versions(["plate", "superdoc", "docxodus", "wordcraft", "fidus", "libreoffice"])
        for tool in ("node", "bun", "python"):
            self.assertRegex(att["tools"][tool], r"\d+\.\d+")
        plate = att["editors"]["plate"]
        self.assertRegex(plate["checkouts"]["repos/plate"], r"^[0-9a-f]{9}$")
        self.assertEqual(plate["pin"], sh.pin_label("plate"))
        self.assertTrue(plate["matches_pin"])
        self.assertEqual(set(att["editors"]["fidus"]["checkouts"]), {"repos/fiduswriter-document-ts", "repos/fiduswriter"})
        for editor, package in (("superdoc", "@superdoc/sdk"), ("docxodus", "docxodus")):
            record = att["editors"][editor]["packages"][package]
            self.assertRegex(record["installed"], r"^\d+\.\d+\.\d+")
            self.assertTrue(record["matches"], record)
        self.assertIn("LibreOffice", att["editors"]["libreoffice"]["version"])
        binary = sh.REPO / sh.ATTEST["wordcraft"]["binaries"]["wc-harness"]
        if not binary.is_file():
            self.skipTest(f"environment: Wordcraft release binary is absent: {binary}; no hash can be attested")
        self.assertIsNotNone(att["editors"]["wordcraft"]["binaries"]["wc-harness"], "wc-harness binary attestation is absent")
        self.assertRegex(att["editors"]["wordcraft"]["binaries"]["wc-harness"], r"^[0-9a-f]{64}$")

    def test_a_checkout_off_its_pin_is_flagged(self):
        with mock.patch.object(sh, "_git_head", return_value="deadbeef0"):
            att = sh.attest_versions(["plate"])
        self.assertFalse(att["editors"]["plate"]["matches_pin"])

    def test_dedicated_publish_refuses_a_checkout_off_its_pin(self):
        quiet = {"quiet": True, "reasons": [], "load_average": [0.5, 0.5, 0.5]}
        on_ac = dict(sh.host_record(), power_source="ac")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            sh, "quiet_machine_check", return_value=quiet
        ), mock.patch.object(sh, "host_record", return_value=on_ac), mock.patch.object(
            sh, "_git_head", return_value="deadbeef0"
        ):
            with self.assertRaises(sh.PinMismatch):
                sh.run_suite(
                    lanes={"plate": {"cmd": None, "cwd": Path(tmp)}},
                    workloads=["prose-500w"],
                    repetitions=1,
                    seed=1,
                    out_root=Path(tmp) / "out",
                    execution_profile="dedicated_publish",
                    timeout_s=10,
                )
            self.assertFalse((Path(tmp) / "out" / "samples").exists())

    def test_summary_carries_the_attestation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "fake_editor.py"
            script.write_text(FAKE, encoding="utf-8")
            quiet = {"quiet": True, "reasons": [], "load_average": [0.5, 0.5, 0.5]}
            with mock.patch.object(sh, "quiet_machine_check", return_value=quiet), mock.patch.object(
                sh, "pin_label", side_effect=lambda e: "fake-pin-%s" % e
            ):
                summary = sh.run_suite(
                    lanes={"a": _fake_lane(script)},
                    workloads=["prose-500w"],
                    repetitions=1,
                    seed=1,
                    out_root=root / "out",
                    execution_profile="ci_broad",
                    timeout_s=60,
                )
        self.assertIn("versions", summary)
        self.assertIn("a", summary["versions"]["editors"])


class OutputCheck(unittest.TestCase):
    def test_check_reads_any_prefix_and_entities(self):
        from perf.fixtures.docx_workload import deterministic_zip

        xml = (
            '<?xml version="1.0"?><x:document xmlns:x="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<x:body><x:p><x:r><x:t>caf&#233; ZZ-END-OF-DOCUMENT prose-500w</x:t></x:r></x:p></x:body></x:document>"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "o.docx"
            path.write_bytes(deterministic_zip([("word/document.xml", xml.encode())]))
            words = ["café", "ZZ-END-OF-DOCUMENT", "prose-500w"]
            expect = {"sentinel": "ZZ-END-OF-DOCUMENT prose-500w", "tokens": __import__("collections").Counter(words),
                      "expected_words": 3, "word_count": 3, "shape": "prose"}
            result = sh.check_output(path, expect)
        self.assertTrue(result["parse_ok"])
        self.assertTrue(result["sentinel"])
        self.assertTrue(result["complete"])
        self.assertIn("café", result["text_head"])


if __name__ == "__main__":
    unittest.main()
