"""Warm/cold attempts must count toward container verify_run (#s2b)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from perf.container.policy import cell_counts, verify_run
from perf.runner.browser_run import ACTIVE, BrowserRun, CELL, run_cli


def test_warm_cold_measured_attempts_are_not_diagnostic_on_disk(tmp_path, monkeypatch):
  """RED: _persist_attempt copied BrowserRun diagnostic rows into attempts/."""
  from perf.runner import benchmark_warm_cold as wc

  recorded = {}

  def fake_sample(self, name, trial):
      row = {**trial, "accounting_scope": "diagnostic", "cpu_accounting": {"available": True}}
      path = tmp_path / f"{name}.json"
      path.write_text(json.dumps(row))
      recorded["row"] = row
      return path

  monkeypatch.setattr(BrowserRun, "sample", fake_sample)

  trial = {
      "criterion_id": "C03",
      "editor_id": "plate",
      "outcome": "measured",
      "latency_ms": 12.0,
      "samples_ms": [12.0],
      "layer": "browser_visible",
      "boundary": "first_usable",
      "environment": {"cache_state": "cold"},
  }
  token = ACTIVE.set(BrowserRun(tmp_path / "run", "benchmark_warm_cold", run_id="s2b", seed=1))
  cell_token = CELL.set({"repetition": 0, "editor_id": "plate"})
  attempt_dir = tmp_path / "attempts"
  attempt_dir.mkdir()
  try:
      wc._persist_attempt(attempt_dir, "C03", "plate", trial)
  finally:
      CELL.reset(cell_token)
      ACTIVE.reset(token)

  attempt = json.loads(next(attempt_dir.glob("*.json")).read_text())
  assert attempt.get("outcome") == "measured"
  assert attempt.get("accounting_scope") is None
  assert attempt.get("cpu_accounting") == {"available": True}


def test_verify_run_accepts_warm_cold_with_measured_c03(tmp_path):
  attempt = tmp_path / "0000-plate" / "attempts"
  attempt.mkdir(parents=True)
  (attempt / "c03-plate-abcd.json").write_text(
      json.dumps({"criterion_id": "C03", "editor_id": "plate", "outcome": "measured"})
  )
  data = {
      "runner": "benchmark_warm_cold",
      "rendering": {"renderer": "swiftshader"},
      "samples": [
          {
              "outcome": "ok",
              "editor_id": "plate",
              "cell_directory": str(tmp_path / "0000-plate"),
          }
      ],
  }
  counts = cell_counts(data)
  assert counts["measured"] == 1
  verify_run(data)


def test_publication_typing_kept_gate_still_raises_without_shakedown(monkeypatch):
  data = {
      "runner": "benchmark_typing",
      "execution_profile": "dedicated_publish",
      "session_kind": "throughput",
      "rendering": {"renderer": "swiftshader"},
      "typing_sessions_kept": {"plate": {"throughput": 0}},
      "samples": [],
  }
  monkeypatch.delenv("PERF_SHAKEDOWN", raising=False)
  with pytest.raises(ValueError, match="insufficient_typing_sessions"):
      verify_run(data)


def test_shakedown_typing_skips_publication_kept_gate(tmp_path, monkeypatch):
  data = {
      "runner": "benchmark_typing",
      "execution_profile": "dedicated_publish",
      "session_kind": "throughput",
      "publishable": False,
      "rendering": {"renderer": "swiftshader"},
      "typing_sessions_kept": {"plate": {"throughput": 0}},
      "failure_reason": "insufficient_typing_sessions",
      "samples": [{"outcome": "ok", "editor_id": "plate"}],
  }
  monkeypatch.setenv("PERF_SHAKEDOWN", "1")
  # Publication gate only: measured-trial accounting is tested elsewhere.
  verify_run(data)
