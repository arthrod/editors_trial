"""B8 memory lane: phase-aware launch identity and run host_class metadata."""
import json
import sys
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from perf.container.run import verify_lane_profiles
from perf.runner import browser_run as api
from perf.runner import benchmark_memory as memory
from perf.tests.test_memory_criteria import _env, _workload_row


@pytest.mark.parametrize(
    "phases,quarantine",
    [
        (["peak_during_run", "retained_after_close"], False),
        (["peak_during_run", "peak_during_run"], True),
    ],
)
def test_run_cli_distinct_measurement_phases_not_quarantined(tmp_path, monkeypatch, phases, quarantine):
    def main():
        root = Path(sys.argv[sys.argv.index("--out-root") + 1])
        for index, phase in enumerate(phases):
            api.write_json(
                root / "attempts" / f"{index}.json",
                {
                    "criterion_id": "C17",
                    "outcome": "measured",
                    "samples_ms": [1024],
                    "measurement_phase": phase,
                },
            )
        return 0

    monkeypatch.setattr(
        sys,
        "argv",
        ["fake", "--out-root", str(tmp_path), "--run-id", "memory-phases", "--editors", "plate"],
    )
    code = api.run_cli(
        main,
        "benchmark_memory",
        {"plate": {}},
        run_factory=partial(api.BrowserRun, snapshot=lambda: {}),
        facts=(lambda: {}, lambda: {}),
    )
    assert code == (3 if quarantine else 0)
    summary = json.loads((tmp_path / "benchmark_memory/memory-phases/summary.json").read_text())
    row = summary["samples"][0]
    if quarantine:
        assert row["failure_reason"] == "multiple_attempts_per_launch"
        assert not list((tmp_path / "benchmark_memory/memory-phases/cells").rglob("attempts/*.json"))
    else:
        assert row["outcome"] == "ok"
        assert len(list(Path(row["cell_directory"]).glob("attempts/*.json"))) == 2


def test_browser_rows_diagnostic_host_class_follows_active_run(tmp_path, monkeypatch):
    run = api.BrowserRun(tmp_path, "memfix", snapshot=lambda: {})
    run.host_class = "shared_guarded"
    run.execution_profile = "dedicated_publish"
    token = api.ACTIVE.set(run)
    attempt_dir = tmp_path / "attempts"
    attempt_dir.mkdir()
    args = SimpleNamespace(
        burst=0,
        quiescence_ms=0,
        retain_seconds=(1.0,),
        pairs=1,
        probe_timeout=5,
        execution_profile="dedicated_publish",
    )
    monkeypatch.setattr(memory, "_port_is_free", lambda host, port: True)
    monkeypatch.setattr(memory, "_start_server", lambda editor_id, target: SimpleNamespace(pid=99))
    monkeypatch.setattr(memory, "_stop_server", lambda server: None)
    monkeypatch.setattr(memory, "_run_browser_pair", lambda **kwargs: {"error": "synthetic probe failure"})
    target = memory.BROWSER_TARGETS["plate"]
    memory._browser_rows(
        editor_id="plate",
        lane="browser_slate",
        target=target,
        attempt_dir=attempt_dir,
        args=args,
        fixture_path=tmp_path / "fixture.docx",
        fixture_sha="a" * 64,
        docx_size=4096,
        workload_row=_workload_row(),
    )
    api.ACTIVE.reset(token)
    diagnostics = json.loads(next(attempt_dir.glob("*.json")).read_text())["diagnostic"]
    assert diagnostics["host_class"] == "shared_guarded"


def test_memory_summary_host_class_and_verify_lane_profiles(tmp_path, monkeypatch):
    run = api.BrowserRun(tmp_path, "memfix", snapshot=lambda: {})
    run.host_class = "shared_guarded"
    run.execution_profile = "dedicated_publish"
    token = api.ACTIVE.set(run)
    out_root = tmp_path / "memory-out"
    out_root.mkdir()
    (out_root / "micro-paragraphs.docx").write_bytes(b"x" * 64)
    (out_root / "micro-paragraphs-in.docx").write_bytes(b"x" * 64)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark_memory",
            "--editor",
            "office-open",
            "--workload",
            "micro-paragraphs",
            "--pairs",
            "1",
            "--out-root",
            str(out_root),
        ],
    )
    monkeypatch.setattr(memory, "_process_rows", lambda **kwargs: [])
    assert memory._main() == 0
    summary = json.loads((out_root / "summary.json").read_text())
    assert summary["host_class"] == "shared_guarded"
    assert summary["publication_block_reason"] == "summary is not a trial; trials carry publishability"
    api.ACTIVE.reset(token)

    run_dir = tmp_path / "lane"
    cell = run_dir / "cells" / "0000-office-open"
    cell.mkdir(parents=True)
    attempts = cell / "attempts"
    attempts.mkdir()
    trial = json.loads(next((out_root / "attempts").glob("*.json")).read_text())
    (attempts / "c17.json").write_text(json.dumps(trial))
    (cell / "summary.json").write_text(
        json.dumps({"execution_profile": "dedicated_publish", "host_class": "shared_guarded"})
    )
    verify_lane_profiles(run_dir, "dedicated_publish", "shared_guarded")


def test_shared_guarded_memory_trial_publishable_with_valid_samples(tmp_path):
    run = api.BrowserRun(tmp_path, "memfix", snapshot=lambda: {})
    run.host_class = "shared_guarded"
    run.execution_profile = "dedicated_publish"
    token = api.ACTIVE.set(run)
    attempt_dir = tmp_path / "attempts"
    attempt_dir.mkdir()
    path = memory._write_measured(
        attempt_dir=attempt_dir,
        criterion_id="C17",
        phase="ready",
        editor_id="plate",
        lane="browser_slate",
        env=_env(cache_state="process_cold_fs_warm", execution_profile="dedicated_publish"),
        samples_bytes=[64 * 1024, 65 * 1024],
        evidence={},
        diagnostic={"host_class": "shared_guarded"},
    )
    api.ACTIVE.reset(token)
    trial = json.loads(path.read_text())
    assert trial["environment"]["host_class"] == "shared_guarded"
    assert trial["publishable"] is True
    assert trial.get("publication_block_reason") is None
