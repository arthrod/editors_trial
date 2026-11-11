"""Review-doc2 F1: a C14 sample publishes under its own clock, never pooled.

A C14 sample that followed document damage is a compositor-frame time
(``presented_frame``). A sample where no damage followed load is the DOM
document-surface time (``usable_no_damage``): it keeps its clock check, is
never labelled a compositor frame, and the reader never pools the two.
Also the two one-liner NITs from the same review: the 600 s wall-clock kill
is ours (harness_error, F6) and a duplicated anchor text is not a C12 move
(F2).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import perf.runner.benchmark_document as bd
from perf.tests.witness_records import publishable_witness_record

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "perf" / "runner" / "document_probe.mjs"
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
WITNESS_SERVER = REPO / "perf" / "tests" / "fixtures" / "witness" / "server.py"
TIMEOUT_S = 90


def _node():
    return shutil.which("node")


def _playwright_ready() -> bool:
    for candidate in (
        REPO / "harness" / "ui" / "plate" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright-core",
    ):
        if candidate.is_dir():
            return True
    return False


def _load_server():
    spec = importlib.util.spec_from_file_location("fixdoc3_fixture_server", WITNESS_SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _env():
    row = next(
        item
        for item in __import__("perf.fixtures.profiles", fromlist=["size_ladder"]).size_ladder()
        if item["workload_id"] == "micro-paragraphs"
    )
    fixture = bd.build_fixture(row)
    return bd._env_for(
        editor_id="plate",
        editor_version="test-pin",
        fixture=fixture,
        cache_state="process_cold_fs_warm",
    )


def _damage_probe(**overrides):
    probe = {
        "mode": "scale",
        "mechanism": "document_damage",
        "usable_ms": 800.0,
        "presented_frame_ms": 812.5,
        "frames_total": 30,
        "frames_after_usable": 4,
        "clock_skew_ms": 0.2,
        "clock_skew_acceptable": True,
        "witness": publishable_witness_record(812.5, 800.0),
        "document_text": "Article 1. Incidental Taxes",
    }
    probe.update(overrides)
    return probe


def _no_damage_probe(**overrides):
    probe = {
        "mode": "scale",
        "mechanism": "forced_repaint",
        "usable_ms": 140.0,
        "presented_frame_ms": None,
        "frames_total": 11,
        "frames_after_usable": 4,
        "clock_skew_ms": 0.2,
        "clock_skew_acceptable": True,
        "witness": {"outcome": "no_frame", "clock_check": {"frame_interval_ms": 16.7}},
        "forced_witness": {"outcome": "no_frame", "clock_check": {"frame_interval_ms": 16.7}},
        "document_text": "Article 1. Incidental Taxes",
    }
    probe.update(overrides)
    return probe


class C14MeasureAtTheSampleBoundary(unittest.TestCase):
    """The measure is decided where the number is, so the two cannot disagree."""

    def test_a_damage_sample_is_tagged_presented_frame(self):
        sample = bd.c14_measured_sample(_damage_probe())
        self.assertEqual(float(sample), 812.5)
        self.assertEqual(getattr(sample, "measure", None), "presented_frame")

    def test_a_no_damage_sample_is_tagged_usable_no_damage(self):
        sample = bd.c14_measured_sample(_no_damage_probe())
        self.assertEqual(float(sample), 140.0)
        self.assertEqual(getattr(sample, "measure", None), "usable_no_damage")

    def test_the_no_damage_clock_description_is_never_a_compositor_frame(self):
        end = bd.C14_CLOCK_BY_MEASURE["usable_no_damage"]["end"]
        self.assertIn("DOM", end)
        self.assertNotIn("compositor", end.lower())
        frame_end = bd.C14_CLOCK_BY_MEASURE["presented_frame"]["end"]
        self.assertIn("compositor screencast frame", frame_end)

    def test_a_no_damage_sample_still_requires_its_clock_check(self):
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c14_measured_sample(_no_damage_probe(clock_skew_ms=-9.5, clock_skew_acceptable=False))
        self.assertIn("clock skew", caught.exception.reason)
        self.assertEqual(getattr(caught.exception, "refusal_code", None), None)


class C14ScaleSamplesCarryTheMeasure(unittest.TestCase):
    def _run(self, payloads):
        payloads = list(payloads)
        with mock.patch.object(bd, "_run_probe", side_effect=lambda _cmd, *, editor_id: payloads.pop(0)):
            return bd._run_scale_samples(
                editor_id="plate",
                target={"url": "http://127.0.0.1/", "corpus_route": "/corpus.docx"},
                cfg={
                    "doc_selector": ".doc-paragraph",
                    "edit_selector": ".doc-paragraph",
                    "page_model": "continuous_flow",
                },
                fixture_path=Path("unused.docx"),
                count=len(payloads),
            )

    def test_each_sample_row_names_its_measure_and_clock(self):
        samples, diagnostics = self._run([_no_damage_probe()])
        self.assertEqual([float(value) for value in samples], [140.0])
        self.assertEqual(getattr(samples[0], "measure", None), "usable_no_damage")
        row = diagnostics[0]
        self.assertEqual(row["measure"], "usable_no_damage")
        self.assertNotIn("compositor", row["clock"]["end"].lower())
        self.assertIn("DOM", row["clock"]["end"])

    def test_a_damage_sample_row_names_the_compositor_frame(self):
        samples, diagnostics = self._run([_damage_probe()])
        self.assertEqual(getattr(samples[0], "measure", None), "presented_frame")
        self.assertEqual(diagnostics[0]["measure"], "presented_frame")
        self.assertIn("compositor screencast frame", diagnostics[0]["clock"]["end"])

    def test_a_mixed_rung_is_refused_never_pooled(self):
        with self.assertRaises(bd.ProbeRefusal) as caught:
            self._run([_no_damage_probe(), _damage_probe()])
        self.assertIn("mixed C14 measures", caught.exception.reason)
        self.assertIn("not pooled", caught.exception.reason)
        self.assertEqual(getattr(caught.exception, "refusal_code", None), "unverified")
        facts = getattr(caught.exception, "facts", None) or {}
        self.assertEqual(facts.get("sample_measures"), ["usable_no_damage", "presented_frame"])


class C14AttemptRowNamesTheMeasure(unittest.TestCase):
    def _write(self, probe):
        with tempfile.TemporaryDirectory() as tmp:
            path = bd.write_c14_outcome(
                attempt_dir=Path(tmp),
                editor_id="plate",
                lane="browser_slate",
                env=_env(),
                probe=probe,
                label="micro",
                workload_id="micro-paragraphs",
            )
            return json.loads(Path(path).read_text(encoding="utf-8"))

    def test_a_no_damage_attempt_is_the_dom_surface_measure(self):
        trial = self._write(_no_damage_probe())
        self.assertEqual(trial["outcome"], "measured")
        self.assertEqual(trial["measure"], "usable_no_damage")
        diagnostic = trial["diagnostic"]
        self.assertEqual(diagnostic["measurement"], "usable_no_damage")
        self.assertNotIn("compositor", diagnostic["clock"]["end"].lower())
        self.assertIn("DOM", diagnostic["clock"]["end"])
        sample_rows = diagnostic["samples"]
        self.assertTrue(sample_rows)
        self.assertEqual({row.get("measure") for row in sample_rows}, {"usable_no_damage"})
        self.assertTrue(
            all("compositor" not in row["clock"]["end"].lower() for row in sample_rows),
            sample_rows,
        )

    def test_a_damage_attempt_is_the_frame_measure(self):
        trial = self._write(_damage_probe())
        self.assertEqual(trial["measure"], "presented_frame")
        self.assertEqual(trial["diagnostic"]["measurement"], "presented_frame")
        self.assertIn("compositor screencast frame", trial["diagnostic"]["clock"]["end"])
        self.assertEqual(
            {row.get("measure") for row in trial["diagnostic"]["samples"]},
            {"presented_frame"},
        )


def _e2_summary(root: Path, run_id: str, seed: int):
    return {
        "run_id": run_id,
        "seed": seed,
        "execution_profile": "dedicated_publish",
        "host_class": "dedicated",
        "publishable": True,
        "host": {"cpu_model": "fixture CPU"},
        "rendering": {},
        "order": [[i, "plate"] for i in range(30)],
    }


def _write_e2_run(root: Path, run_id: str, seed: int):
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(json.dumps(_e2_summary(root, run_id, seed)), encoding="utf-8")
    return root


def _write_c14_trial(root: Path, rep: int, measure: str, samples: list, sample_measures=None):
    row = {
        "editor_id": "plate",
        "criterion_id": "C14",
        "outcome": "measured",
        "samples_ms": samples,
        "publishable": True,
        "refusal_code": None,
        "sub_frame_samples": [False] * len(samples),
        "workload_id": "prose-500w",
        # 0af7d5d2 (#149): a kept trial must carry a built-editor identity.
        "environment": {"editor_id": "plate", "editor_version": "pin-1", "workload_id": "prose-500w"},
        "measure": measure,
        "diagnostic": {
            "frame_interval_ms": 16.7,
            "size_rung": "prose-500w",
            "workload_id": "prose-500w",
            "measurement": measure,
            "samples": [
                {"measure": m, "witness": {"clock_check": {"frame_interval_ms": 16.7}}}
                for m in (sample_measures or [measure] * len(samples))
            ],
        },
    }
    path = root / "cells" / ("%04d-plate" % rep) / "attempts" / ("c14-%s.json" % measure)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row), encoding="utf-8")


class E2ReaderGroupsC14ByMeasure(unittest.TestCase):
    """The report row names the measure; the two clocks are never pooled."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.primary = _write_e2_run(base / "primary", "a", 1)
        self.repro = _write_e2_run(base / "repro", "b", 2)
        for root in (self.primary, self.repro):
            for rep in range(10):
                _write_c14_trial(root, rep, "presented_frame", [900.0])
                _write_c14_trial(root, rep, "usable_no_damage", [100.0])
        from build import perf_e2_tables as E2

        self.facts = E2.facts_from_runs(self.primary, self.repro)

    def test_the_table_has_one_row_per_measure_with_its_own_median(self):
        table = self.facts["perf.e2.table.C14"]
        self.assertIn("presented_frame", table)
        self.assertIn("usable_no_damage", table)
        self.assertIn("900.0 ms", table)
        self.assertIn("100.0 ms", table)
        pooled = str((900.0 + 100.0) / 2)
        self.assertNotIn(pooled, table)

    def test_the_cells_are_per_measure(self):
        from perf.analysis import e2_cells

        frame = e2_cells.build_run_cell(self.primary, "plate", "C14", measure="presented_frame", workload_id="prose-500w")
        dom = e2_cells.build_run_cell(self.primary, "plate", "C14", measure="usable_no_damage", workload_id="prose-500w")
        self.assertEqual(frame["stats"]["n"], 10)
        self.assertEqual(frame["stats"]["median"], 900.0)
        self.assertEqual(dom["stats"]["n"], 10)
        self.assertEqual(dom["stats"]["median"], 100.0)

    def test_a_trial_that_pools_both_measures_is_refused_by_the_reader(self):
        from perf.analysis import e2_cells

        _write_c14_trial(
            self.primary,
            10,
            "presented_frame",
            [100.0, 900.0],
            sample_measures=["usable_no_damage", "presented_frame"],
        )
        cell = e2_cells.build_run_cell(self.primary, "plate", "C14", measure="presented_frame", workload_id="prose-500w")
        self.assertEqual(cell["refusals"].get("mixed_c14_measures"), 1)


class TimeoutKillIsOursNotTheEditors(unittest.TestCase):
    """Review F6 one-liner: our own 600 s kill is a harness error."""

    def test_the_wall_clock_kill_is_labelled_harness_error(self):
        cmd = [
            "/usr/bin/node", "/app/perf/runner/document_probe.mjs", "--mode", "scale",
            "--timeout-ms", str(bd.PROBE_TIMEOUT_S * 1000),
        ]
        expired = subprocess.TimeoutExpired(cmd, bd.PROBE_TIMEOUT_S)
        with mock.patch.object(bd.subprocess, "run", side_effect=expired):
            with self.assertRaises(bd.ProbeRefusal) as caught:
                bd._run_probe(cmd, editor_id="folio")
        self.assertIn("630", caught.exception.reason)
        self.assertEqual(caught.exception.refusal_code, "harness_error")


class DuplicateAnchorTextIsNotAMove(unittest.TestCase):
    """Review F2 one-liner: a text re-find must be unique to re-find at all."""

    server = None
    base_url = ""
    corpus = None

    @classmethod
    def setUpClass(cls):
        if _node() is None:
            raise unittest.SkipTest("node is not on PATH")
        if not _playwright_ready():
            raise unittest.SkipTest("harness/ui has no playwright package")
        cls.server, _thread, cls.base_url = _load_server().serve(HOSTS)
        cls._corpus_dir = tempfile.TemporaryDirectory()
        cls.corpus = Path(cls._corpus_dir.name) / "corpus.docx"
        cls.corpus.write_bytes(b"PK\x03\x04fixdoc3")

    @classmethod
    def tearDownClass(cls):
        if cls.server is not None:
            cls.server.shutdown()
            cls.server.server_close()
        if cls.corpus is not None:
            cls._corpus_dir.cleanup()

    def test_a_replaced_anchor_with_duplicated_text_refuses(self):
        cmd = [
            _node(),
            str(PROBE),
            "--mode",
            "reflow",
            "--url",
            "%s/b3_fixdoc3_dup_anchor.html" % self.base_url,
            "--corpus",
            str(self.corpus),
            "--doc-selector",
            ".doc-paragraph",
            "--page-model",
            "continuous_flow",
            "--edit-selector",
            ".doc-paragraph",
            "--timeout-ms",
            "20000",
        ]
        started = time.monotonic()
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=TIMEOUT_S)
        elapsed = time.monotonic() - started
        self.assertEqual(
            proc.returncode,
            0,
            "document_probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s" % (proc.returncode, proc.stdout, proc.stderr),
        )
        payload = json.loads(proc.stdout)
        payload["_elapsed_s"] = elapsed
        before = (payload.get("before") or {}).get("anchor_top")
        after = payload.get("anchor_top_after")
        self.assertIsInstance(before, (int, float), payload)
        self.assertEqual(payload.get("error"), "anchor_identity_ambiguous", payload)
        # The real anchor never moved: it was replaced in place at the same top.
        self.assertNotIsInstance(after, (int, float), payload)
        self.assertFalse(payload.get("moved"), payload)
        with self.assertRaises(bd.ProbeRefusal) as caught:
            bd.c12_measured_sample(payload)
        self.assertTrue(
            "did not move down" in caught.exception.reason or "anchor_identity_ambiguous" in caught.exception.reason,
            caught.exception.reason,
        )

    def test_a_rerendered_anchor_with_stable_duplicate_text_measures(self):
        cmd = [
            _node(),
            str(PROBE),
            "--mode",
            "reflow",
            "--url",
            "%s/b3_fixdoc3_dup_rerender.html" % self.base_url,
            "--corpus",
            str(self.corpus),
            "--doc-selector",
            ".doc-paragraph",
            "--page-model",
            "continuous_flow",
            "--edit-selector",
            ".doc-paragraph",
            "--timeout-ms",
            "20000",
        ]
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=TIMEOUT_S)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        before = (payload.get("before") or {}).get("anchor_top")
        after = payload.get("anchor_top_after")
        self.assertIsInstance(before, (int, float), payload)
        self.assertIsInstance(after, (int, float), payload)
        self.assertGreater(after, before, payload)
        self.assertTrue(payload.get("moved"), payload)
        self.assertEqual((payload.get("before") or {}).get("anchor_occurrence"), 1)
        sample = bd.c12_measured_sample(payload)
        self.assertIsInstance(sample, float)


class RealHostScaleSamples(unittest.TestCase):
    """Real hosts, real corpus bytes, real screencast witness, production path.

    A static host publishes usable_no_damage with both witnesses no_frame; a
    host with late in-region damage publishes presented_frame. The attempt row
    names the measure and its clock on both paths.
    """

    server = None
    base_url = ""
    corpus = None

    @classmethod
    def setUpClass(cls):
        if _node() is None:
            raise unittest.SkipTest("node is not on PATH")
        if not _playwright_ready():
            raise unittest.SkipTest("harness/ui has no playwright package")
        cls.server, _thread, cls.base_url = _load_server().serve(HOSTS)
        cls._corpus_dir = tempfile.TemporaryDirectory()
        cls.corpus = Path(cls._corpus_dir.name) / "corpus.docx"
        cls.corpus.write_bytes(b"PK\x03\x04fixdoc3")

    @classmethod
    def tearDownClass(cls):
        if cls.server is not None:
            cls.server.shutdown()
            cls.server.server_close()
        if cls.corpus is not None:
            cls._corpus_dir.cleanup()

    def _probe_payload(self, host: str) -> dict:
        cmd = [
            _node(),
            str(PROBE),
            "--mode",
            "scale",
            "--url",
            "%s/%s" % (self.base_url, host),
            "--corpus",
            str(self.corpus),
            "--doc-selector",
            ".doc-paragraph",
            "--page-model",
            "continuous_flow",
            "--settle-ms",
            "0",
            "--timeout-ms",
            "20000",
        ]
        return bd._run_probe(cmd, editor_id="plate")

    def _samples_and_attempt(self, host: str):
        payload = self._probe_payload(host)
        target = {"url": "http://127.0.0.1/", "corpus_route": "/corpus.docx"}
        cfg = {"doc_selector": ".doc-paragraph", "page_model": "continuous_flow"}
        with mock.patch.object(bd, "_probe_cmd", return_value=["unused"]), mock.patch.object(
            bd, "_run_probe", return_value=payload
        ):
            samples, diagnostics = bd._run_scale_samples(
                editor_id="plate", target=target, cfg=cfg, fixture_path=self.corpus, count=1
            )
        path = bd.write_c14_outcome(
            attempt_dir=Path(tempfile.mkdtemp()),
            editor_id="plate",
            lane="browser_slate",
            env=_env(),
            probe=payload,
            label="micro",
            workload_id="micro-paragraphs",
        )
        trial = json.loads(Path(path).read_text(encoding="utf-8"))
        return payload, samples, diagnostics, trial

    def test_a_static_host_publishes_usable_no_damage(self):
        payload, samples, diagnostics, trial = self._samples_and_attempt("b3_fixdoc2_space.html")
        self.assertEqual(payload["mechanism"], "forced_repaint")
        self.assertEqual((payload.get("witness") or {}).get("outcome"), "no_frame")
        self.assertEqual((payload.get("forced_witness") or {}).get("outcome"), "no_frame")
        self.assertEqual(getattr(samples[0], "measure", None), "usable_no_damage")
        self.assertEqual(samples[0], payload["usable_ms"])
        self.assertEqual(diagnostics[0]["measure"], "usable_no_damage")
        self.assertEqual(trial["measure"], "usable_no_damage")
        self.assertNotIn("compositor", trial["diagnostic"]["clock"]["end"].lower())

    def test_a_late_damage_host_publishes_presented_frame(self):
        payload, samples, diagnostics, trial = self._samples_and_attempt("b3_fixdoc3_late_damage.html")
        self.assertEqual(payload["mechanism"], "document_damage")
        self.assertEqual((payload.get("witness") or {}).get("outcome"), "witnessed")
        self.assertEqual(getattr(samples[0], "measure", None), "presented_frame")
        self.assertEqual(samples[0], payload["presented_frame_ms"])
        self.assertEqual(diagnostics[0]["measure"], "presented_frame")
        self.assertEqual(trial["measure"], "presented_frame")
        self.assertIn("compositor screencast frame", trial["diagnostic"]["clock"]["end"])


class C14RungRefusalsNameBothMeasures(unittest.TestCase):
    def test_a_rung_refusal_writes_one_attempt_per_measure(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = bd.write_c14_rung_refusals(
                attempt_dir=Path(tmp),
                editor_id="plate",
                lane="browser_slate",
                env=_env(),
                label="prose-500w",
                workload_id="prose-500w",
                reason="rung prose-500w: mixed C14 measures in one rung (presented_frame, usable_no_damage); the two clocks are not pooled",
                outcome="unverified",
                refusal_code="unverified",
            )
            self.assertEqual(len(paths), 2)
            trials = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
            self.assertEqual({trial["measure"] for trial in trials}, set(bd.C14_MEASURES))
            for trial in trials:
                self.assertEqual(trial["outcome"], "unverified")
                self.assertEqual(trial["diagnostic"]["workload_id"], "prose-500w")
                self.assertIn("not pooled", trial["failure_reason"])


if __name__ == "__main__":
    unittest.main()
