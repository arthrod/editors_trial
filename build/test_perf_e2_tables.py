"""Report E2 facts from browser publication runs (synthetic trial trees)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT))

import perf_e2_tables as E2
import render_reports
from perf.analysis.anti_ranking import assert_markdown_no_editor_speed_ranking
from perf.runner import speed_headless as sh

DISPLAY = {
    "plate": "Plate.js",
    "wordcraft": "WordCraft",
    "docen": "Docen",
}


def _env(editor: str = "plate") -> dict:
    return {
        "host_class": "shared_guarded",
        "execution_profile": "dedicated_publish",
        "editor_id": editor,
        "power_source": "ac",
    }


def _trial(editor: str, criterion: str, outcome: str, samples=None, **extra) -> dict:
    row = {
        "schema_version": 1,
        "criterion_id": criterion,
        "editor_id": editor,
        "outcome": outcome,
        "samples_ms": samples or [],
        "layer": "browser_visible",
        "boundary": "input_to_next_paint",
        "environment": _env(editor),
        "diagnostic": {"frame_interval_ms": 16.7},
    }
    row.update(extra)
    return row


def _write_trial(root: Path, rep: int, editor: str, criterion: str, **kwargs) -> None:
    cell = root / "cells" / f"{rep:04d}-{editor}" / "attempts"
    cell.mkdir(parents=True, exist_ok=True)
    path = cell / f"{criterion.lower()}.json"
    path.write_text(json.dumps(_trial(editor, criterion, **kwargs)), encoding="utf-8")


def _summary(root: Path, *, run_id: str, seed: int, editors: list[str], reps: int = 30) -> dict:
    host = dict(
        sh.host_record(),
        power_source="ac",
        container=True,
        cpu_quota=8,
        machine_vendor="Amazon EC2",
        machine_product="r6a.16xlarge",
        hypervisor=True,
    )
    return {
        "run_id": run_id,
        "seed": seed,
        "execution_profile": "dedicated_publish",
        "host_class": "shared_guarded",
        "order": [[i, e] for i in range(reps) for e in editors],
        "host": host,
        "rendering": {
            "headless": True,
            "browser_version": "130.0.6723.31",
            "renderer": "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)",
        },
        "versions": {
            "editors": {e: {"pin": f"pin-{e}"} for e in editors},
            "tools": {"playwright": "1.64.1", "node": "v22"},
        },
        "cpu_steal_percent": 0.027,
        "cpu_throttle_refused_samples": 2,
        "cpu_accounting": {"samples_total": reps * len(editors), "samples_refused": 2},
        "samples": [],
    }


def _write_run(root: Path, **summary_kw) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    summary = _summary(root, **summary_kw)
    (root / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return root


class ReportE2Facts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def _pair(self, primary_kw, repro_kw, writer):
        primary = _write_run(self.base / "primary", **primary_kw)
        repro = _write_run(self.base / "repro", **repro_kw)
        writer(primary)
        writer(repro)
        return primary, repro

    def test_nine_kept_samples_not_enough(self):
        primary, _ = self._pair(
            {"run_id": "a", "seed": 1, "editors": ["plate"]},
            {"run_id": "b", "seed": 2, "editors": ["plate"]},
            lambda root: [_write_trial(root, i, "plate", "C07", outcome="measured", samples=[20.0]) for i in range(9)],
        )
        facts = E2.facts_from_runs(primary, self.base / "repro")
        table = facts["perf.e2.table.C07"]
        self.assertIn("not enough samples", table)
        self.assertIn("n = 9 of 30", table)

    def test_ten_kept_samples_publish_when_runs_agree(self):
        def fill(root):
            for i in range(10):
                _write_trial(root, i, "plate", "C07", outcome="measured", samples=[20.0])

        primary, repro = self._pair(
            {"run_id": "a", "seed": 1, "editors": ["plate"]},
            {"run_id": "b", "seed": 2, "editors": ["plate"]},
            fill,
        )
        facts = E2.facts_from_runs(primary, repro)
        table = facts["perf.e2.table.C07"]
        self.assertIn("20.0 ms", table)
        self.assertNotIn("not reproduced", table)

    def test_non_reproducing_pair_shows_both_medians(self):
        primary = _write_run(self.base / "primary", run_id="a", seed=1, editors=["plate"])
        repro = _write_run(self.base / "repro", run_id="b", seed=2, editors=["plate"])
        for i in range(10):
            _write_trial(primary, i, "plate", "C07", outcome="measured", samples=[20.0])
            _write_trial(repro, i, "plate", "C07", outcome="measured", samples=[50.0])
        facts = E2.facts_from_runs(primary, repro)
        table = facts["perf.e2.table.C07"]
        self.assertIn("not reproduced", table)
        self.assertIn("20.0 ms", table)
        self.assertIn("50.0 ms", table)
        self.assertIn("Plate.js", facts["perf.e2.not_reproduced"])
        self.assertIn("50.0 ms", facts["perf.e2.not_reproduced"])

    def test_sub_frame_median_bucket(self):
        def fill(root):
            for i in range(10):
                _write_trial(
                    root,
                    i,
                    "plate",
                    "C07",
                    outcome="measured",
                    samples=[9.9],
                    sub_frame_samples=[True],
                )

        primary, repro = self._pair(
            {"run_id": "a", "seed": 1, "editors": ["plate"]},
            {"run_id": "b", "seed": 2, "editors": ["plate"]},
            fill,
        )
        facts = E2.facts_from_runs(primary, repro)
        self.assertIn("< 1 frame (16.7 ms)", facts["perf.e2.table.C07"])
        self.assertNotIn("9.9", facts["perf.e2.table.C07"])

    def test_refused_only_cell_lists_reasons(self):
        def fill(root):
            for i in range(5):
                _write_trial(root, i, "plate", "C07", outcome="failed", failure_reason="timeout")

        primary, repro = self._pair(
            {"run_id": "a", "seed": 1, "editors": ["plate"]},
            {"run_id": "b", "seed": 2, "editors": ["plate"]},
            fill,
        )
        facts = E2.facts_from_runs(primary, repro)
        table = facts["perf.e2.table.C07"]
        self.assertIn("not enough samples", table)
        self.assertIn("timeout", table)

    def test_not_run_editor_shows_recorded_reason(self):
        primary = _write_run(self.base / "primary", run_id="a", seed=1, editors=["plate", "docen"])
        repro = _write_run(self.base / "repro", run_id="b", seed=2, editors=["plate", "docen"])
        for i in range(10):
            _write_trial(primary, i, "plate", "C07", outcome="measured", samples=[20.0])
            _write_trial(repro, i, "plate", "C07", outcome="measured", samples=[20.0])
            _write_trial(primary, i, "docen", "C07", outcome="not_run", failure_reason="host_build: dev_server")
            _write_trial(repro, i, "docen", "C07", outcome="not_run", failure_reason="host_build: dev_server")
        facts = E2.facts_from_runs(primary, repro)
        table = facts["perf.e2.table.C07"]
        self.assertIn("Docen", table)
        self.assertRegex(table, r"not run|host_build|dev_server")

    def test_same_seed_refusal(self):
        primary = _write_run(self.base / "primary", run_id="a", seed=1, editors=["plate"])
        repro = _write_run(self.base / "repro", run_id="b", seed=1, editors=["plate"])
        with self.assertRaises(ValueError) as ctx:
            E2.facts_from_runs(primary, repro)
        self.assertIn("seed", str(ctx.exception).lower())

    def test_rows_are_alphabetical(self):
        primary = _write_run(self.base / "primary", run_id="a", seed=1, editors=["plate", "wordcraft"])
        repro = _write_run(self.base / "repro", run_id="b", seed=2, editors=["plate", "wordcraft"])
        for i in range(10):
            for editor in ("plate", "wordcraft"):
                _write_trial(primary, i, editor, "C07", outcome="measured", samples=[20.0])
                _write_trial(repro, i, editor, "C07", outcome="measured", samples=[20.0])
        facts = E2.facts_from_runs(primary, repro)
        rows = [
            line.split("|")[1].strip()
            for line in facts["perf.e2.table.C07"].splitlines()[2:]
            if line.startswith("|")
        ]
        self.assertEqual(rows, sorted(rows, key=str.casefold))

    def test_mutated_median_changes_rendered_report(self):
        primary = _write_run(self.base / "primary", run_id="a", seed=1, editors=["plate"])
        repro = _write_run(self.base / "repro", run_id="b", seed=2, editors=["plate"])
        for i in range(10):
            _write_trial(primary, i, "plate", "C07", outcome="measured", samples=[20.0])
            _write_trial(repro, i, "plate", "C07", outcome="measured", samples=[20.0])
        facts = E2.facts_from_runs(primary, repro)
        tpl = (render_reports.TEMPLATES / "reports/Report E2 - Speed in the Browser (2026).md").read_text()
        rendered_a = render_reports.reportgen.render(tpl, facts)
        facts["perf.e2.table.C07"] = facts["perf.e2.table.C07"].replace("20.0 ms", "99.9 ms")
        rendered_b = render_reports.reportgen.render(tpl, facts)
        self.assertNotEqual(rendered_a, rendered_b)

    def test_tables_pass_anti_ranking_guard(self):
        primary = _write_run(self.base / "primary", run_id="a", seed=1, editors=["plate", "wordcraft"])
        repro = _write_run(self.base / "repro", run_id="b", seed=2, editors=["plate", "wordcraft"])
        for i in range(10):
            for editor in ("plate", "wordcraft"):
                _write_trial(primary, i, editor, "C07", outcome="measured", samples=[20.0 + i])
                _write_trial(repro, i, editor, "C07", outcome="measured", samples=[20.0 + i])
        facts = E2.facts_from_runs(primary, repro)
        for key in facts:
            if key.startswith("perf.e2.table."):
                assert_markdown_no_editor_speed_ranking(facts[key])


if __name__ == "__main__":
    unittest.main()
