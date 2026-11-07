"""Guardrails against fabricated perf samples and spec gaps (must-fix)."""

import json
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import hashlib

import perf.runner.benchmark_ci_contract as bcc
from perf.analysis.anti_ranking import assert_markdown_no_editor_speed_ranking
from perf.analysis.interpretation import evaluate_measured_trial
from perf.analysis.summary_integrity import assert_ci_contract_summary_valid
from perf.fixtures.generate import build_workload, docx_zip_bytes, correctness_fixtures
from perf.fixtures.profiles import size_ladder
from perf.runner.docx_plaintext import docx_body_text
from perf.scenarios.catalog import scenarios


class LibreofficeNoFabricatedModelReady(unittest.TestCase):
    def test_libreoffice_stdout_has_no_perf_model_ready_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            indocx = Path(tmp) / "in.docx"
            outdocx = Path(tmp) / "out.docx"
            indocx.write_bytes(docx_zip_bytes(b"hello\n"))
            wall_ms, out, err, _cpu = bcc._run_libreoffice(indocx, outdocx)
            combined = (out or "") + (err or "")
            self.assertIsNotNone(wall_ms)
            self.assertNotRegex(
                combined,
                re.compile(r"PERF\s+model_ready_ms\s*=", re.I),
                "LibreOffice lane must not fabricate model_ready_ms from wall time",
            )

    def test_libreoffice_stdout_has_no_fabricated_perf_save_ms_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            indocx = Path(tmp) / "in.docx"
            outdocx = Path(tmp) / "out.docx"
            indocx.write_bytes(docx_zip_bytes(b"hello\n"))
            wall_ms, out, err, _cpu = bcc._run_libreoffice(indocx, outdocx)
            combined = (out or "") + (err or "")
            self.assertIsNotNone(wall_ms)
            self.assertNotRegex(
                combined,
                re.compile(r"PERF\s+save_ms\s*=", re.I),
                "LibreOffice lane must not fabricate PERF save_ms= from subprocess wall time",
            )


class LibreofficeC16Honesty(unittest.TestCase):
    """C16 must not report runner-injected save_ms for headless soffice."""

    def test_libreoffice_c16_is_not_run_in_contract_outputs(self):
        root = Path(__file__).resolve().parents[2] / "perf" / "out"
        for sub in ("ci_contract_2026_11_07", "ci_broad_2026_11_07"):
            summary_path = root / sub / "summary.json"
            if not summary_path.is_file():
                continue
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            rows = [
                r
                for r in payload.get("editors", [])
                if r.get("criterion_id") == "C16" and r.get("editor_id") == "libreoffice"
            ]
            self.assertEqual(
                len(rows),
                1,
                "expected exactly one C16 libreoffice row in %s" % summary_path,
            )
            row = rows[0]
            self.assertEqual(
                row.get("outcome"),
                "not_run",
                "LibreOffice C16 must be not_run (no harness save_ms), got %r in %s"
                % (row.get("outcome"), summary_path),
            )
            reason = (row.get("failure_reason") or "").lower()
            self.assertIn("save", reason)
            self.assertIn(
                "perf",
                reason,
                "failure_reason should mention missing PERF save probe: %r" % row.get("failure_reason"),
            )


class C24NoSyntheticWasmLoop(unittest.TestCase):
    def test_c24_decision_is_not_measured_synthetic_samples(self):
        for ed in bcc.EDITORS:
            outcome, failure_reason, extra = bcc.c24_boundary_decision(ed, "ci_contract")
            self.assertNotIn("rng", (failure_reason or "").lower())
            if outcome == "measured":
                self.fail("C24 must not emit measured synthetic wasm samples on ci_contract")
            self.assertIn(outcome, ("not_run", "unverified"))


class InterpretationMeasuredTrials(unittest.TestCase):
    def _scenario(self, cid):
        return next(r for r in scenarios() if r["id"] == cid)

    def _base_env(self):
        row = next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs")
        built = build_workload(row)
        docx = docx_zip_bytes(built["body"])
        return bcc._host_base(
            editor_id="plate",
            editor_version="test",
            execution_profile="ci_contract",
            fixture_sha256=hashlib.sha256(docx).hexdigest(),
            workload_row=row,
            docx_size=len(docx),
            cache_state="process_cold_fs_warm",
            repetition_unit="fresh_process",
            run_kind="timing",
            feature_profile_name="P0",
        )

    def test_c02_measured_requires_unicode_preservation_when_i01_listed(self):
        scen = self._scenario("C02")
        self.assertIn("I01", scen.get("correctness", []))
        row = next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs")
        built = build_workload(row)
        body = built["body"] + correctness_fixtures()["unicode"]
        docx_in = docx_zip_bytes(body)
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "in.docx"
            in_path.write_bytes(docx_in)
            text_out = docx_body_text(in_path)
        stats = {
            "n": 1,
            "median": 1.0,
            "p90": 2.0,
            "p95": 2.0,
            "p99": 2.0,
            "mad": 0.0,
            "ci95_low": 0.0,
            "ci95_high": 2.0,
            "minimum": 1.0,
            "maximum": 1.0,
            "cache_state": "process_cold_fs_warm",
            "repetition_unit": "fresh_process",
        }
        ok, reason = evaluate_measured_trial(
            scen, self._base_env(), doc_output_text=text_out, summary_stats=stats
        )
        self.assertTrue(ok, reason)


class SummaryPublication(unittest.TestCase):
    def test_ranking_rows_reject_non_publishable_medians(self):
        payload = {
            "execution_profile": "ci_contract",
            "editors": [
                {
                    "criterion_id": "C02",
                    "editor_id": "plate",
                    "outcome": "measured",
                    "median_ms": 10.0,
                    "publishable": False,
                },
                {
                    "criterion_id": "C02",
                    "editor_id": "folio",
                    "outcome": "measured",
                    "median_ms": 5.0,
                    "publishable": True,
                },
            ],
        }
        with self.assertRaises(ValueError) as caught:
            assert_ci_contract_summary_valid(payload)
        self.assertIn("non-publishable", str(caught.exception).lower())

    def test_dedicated_publish_scheduler_rows_have_execution_profile_reason_on_ci(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with patch.object(bcc, "date") as mock_date:
                mock_date.today = lambda: date(2099, 1, 1)
                argv = ["prog", "--dry-run", "--out-root", str(out)]
                with patch.object(sys, "argv", argv):
                    self.assertEqual(bcc.main(), 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        c20 = [r for r in summary["editors"] if r["criterion_id"] == "C20"]
        self.assertEqual(len(c20), 14)
        for r in c20:
            self.assertEqual(r["outcome"], "not_run")
            self.assertIn("execution_profile", r["failure_reason"])


class AntiRankingMarkdown(unittest.TestCase):
    def test_accepts_neutral_prose(self):
        assert_markdown_no_editor_speed_ranking("Latency varies by workload and host.\n")

    def test_rejects_times_faster_between_editors(self):
        with self.assertRaises(ValueError) as caught:
            assert_markdown_no_editor_speed_ranking(
                "Plate is 3x faster than Folio on load.\n"
            )
        self.assertIn("faster", str(caught.exception).lower())


if __name__ == "__main__":
    unittest.main()
