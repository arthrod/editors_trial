"""r3typing3: reviewer plants from .scratch/review/ close as regressions."""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from build.perf_e2_tables import typing_table
from perf.analysis.e2_typing import session_refusal
from perf.container.policy import verify_run
from perf.runner import benchmark_typing as bt
from perf.runner.browser_run import typing_session_kept
from perf.tests.test_typing_fix2 import good
from perf.tests.test_typing_fix9 import CAPTION, CAPTION_BLANKED, _read_document, _sampler, _type
from perf.tests.witness_records import publishable_witness_record

REPO = Path(__file__).resolve().parents[2]
SHAKEDOWN_JOB = (
    REPO.parent
    / "e2-logs/hf-data-shakedown2/e2-docen/runs"
    / "20261111T152554289054Z-176854-614682/benchmark_warm_cold"
    / "20261111T152554289054Z-176854-614682-000"
)


def _writer_row(result):
    """Keys ``main_cell`` copies; no refusal_code backfill."""
    row = {
        "schema": "perf.typing/2",
        "session_kind": "throughput",
        "isolation": "fresh_process",
        "values_per_session": 1,
        "criterion_id": "TYPING",
        "editor_id": "plate",
        "outcome": result.get("outcome") or "measured",
        "publishable": False,
        "publication_block_reason": (
            "inspect all witness and resource refusals; publication requires complete session set"
        ),
        "fixture_sha256": "brief-sha",
        "typed_text_sha256": "typed-sha",
        "fixture_words": 1,
        "words_typed": 1,
        "cadence_ms": 0,
        "budget_s": 3600,
        "execution_profile": "dedicated_publish",
        "host_class": "dedicated",
        "host_provenance": {"tree_sha256": "pin-same", "publishable": True},
        "session_wall_s": 30,
        "correctness_oracle": "dom_document_text",
    }
    row.update(result)
    return row


async def _probe_type(text, actual, *, absorbed=None, present_text=True, pay_dom_s=0.0, kind="throughput"):
    clock = {"t": 0.0}
    reads = {"inner": 0}

    def now():
        return clock["t"]

    class Page:
        keyboard = None

        def __init__(self):
            self.keyboard = self

        async def type(self, _c):
            clock["t"] += 0.01

        async def press(self, _k):
            clock["t"] += 0.01

        async def evaluate(self, script, arg=None):
            if isinstance(script, str) and "querySelector" in script and "innerText" in script:
                reads["inner"] += 1
                clock["t"] += pay_dom_s
            return ""

    class Sampler:
        selector = "#e"
        typed_text = ""
        characters_typed = 0

        def __init__(self):
            self.present_text = present_text

        async def mark(self, name):
            if name.startswith("typed_") and name != "typed_100":
                await self.sample()

        async def sample(self):
            if self.present_text:
                await page.evaluate('(s) => document.querySelector(s)?.innerText ?? ""', self.selector)

    page = Page()
    sampler = Sampler()

    async def witness(_c):
        clock["t"] += 0.01
        return {"witness": publishable_witness_record()}

    async def read():
        return {"text": actual, "absorbed_markers": absorbed or []}

    result = await bt.type_document(
        page,
        sampler,
        witness,
        text,
        selector="#e",
        session_kind=kind,
        witness_every=10**9,
        sample_s=10_000,
        clock=now,
        read_document=read,
        present_text=present_text,
    )
    result["_inner_reads"] = reads["inner"]
    return result


# --- ruling 1: refusal_code and reader ---


def test_measured_type_document_carries_explicit_null_refusal_code():
    result = asyncio.run(_probe_type("Hello", "Hello"))
    assert "refusal_code" in result
    assert result["refusal_code"] is None
    trial = _writer_row(result)
    assert "refusal_code" in trial
    assert session_refusal(trial, "throughput") != "crash"
    assert typing_session_kept(trial, "throughput") is True


def test_writer_row_without_refusal_code_reads_as_crash():
    result = asyncio.run(_probe_type("Hello", "Hello"))
    trial = _writer_row(result)
    del trial["refusal_code"]
    assert session_refusal(trial, "throughput") == "crash"
    assert typing_session_kept(trial, "throughput") is False


# --- ruling 2: list markers ---


def test_vanished_prefix_marker_without_list_item_refuses():
    result = asyncio.run(_probe_type("1. Hello", "Hello"))
    assert result["failure_reason"] == "text_mismatch"
    assert typing_session_kept({**result, "correctness_oracle": "dom_document_text"}, "throughput") is False


def test_id_cite_vanished_refuses():
    result = asyncio.run(_probe_type("Id. at 12.", "at 12."))
    assert result["failure_reason"] == "text_mismatch"
    assert result["throughput_chars_s"] is None


def test_slot_widen_does_not_excuse_marker_only_line():
    result = asyncio.run(
        _probe_type("Hello\nv.\nworld", "Hello\n\n\nworld", absorbed=[{"index": 2, "marker": None}])
    )
    assert result["failure_reason"] == "text_mismatch"
    assert typing_session_kept({**result, "correctness_oracle": "dom_document_text"}, "throughput") is False


def test_prefix_marker_tolerated_with_absorbed_item_at_line():
    from perf.tests.test_typing_fix9 import FakePage

    result = _type(
        FakePage(),
        CAPTION,
        read_document=_read_document(CAPTION_BLANKED, [{"index": 2, "marker": "i."}, {"index": 5, "marker": "ii."}]),
    )
    assert result["failure_reason"] is None


def test_extra_empty_numbered_paragraph_does_not_refuse_when_text_matches():
    head = "alpha\nv.\nbeta\nv.\ngamma\nv.\ndelta\nv.\nomega"
    result = asyncio.run(
        _probe_type(head, head + "\n", absorbed=[{"index": head.count("\n") + 1, "marker": None}])
    )
    assert result["failure_reason"] is None, result


# --- ruling 4: focused read-only DOM surface ---


def test_focused_readonly_dom_refuses_before_keys(tmp_path):
    pytest.importorskip("playwright.async_api")
    pytest.importorskip("psutil")
    from types import SimpleNamespace

    from perf.runner.benchmark_typing import session
    from perf.runner.browser_hosts import StaticHost

    host = StaticHost(Path(__file__).parent / "fixtures")
    try:
        result, _rows = asyncio.run(
            session(
                {
                    "url": host.url + "/focused_readonly.html",
                    "edit_selector": "#editor",
                    "ready_selector": ".status-ok",
                    "typing_usable_selector": ".status-ok",
                },
                "abc",
                SimpleNamespace(
                    budget_s=30,
                    cadence_ms=0,
                    sample_s=5,
                    witness_every=100,
                    quiescence_s=0,
                ),
                tmp_path,
            )
        )
    finally:
        host.stop()
    assert result["failure_reason"] == "no_editable_surface", result
    assert result["characters_typed"] == 0
    assert result.get("refusal_code") == "unverified"


# --- ruling 5: no in-wall DOM text read on model surfaces ---


def test_model_surface_skips_present_text_sampling_inside_typing_wall():
    result = asyncio.run(_probe_type("x" * 80, "x" * 80, present_text=False, pay_dom_s=0.25))
    assert result["_inner_reads"] == 0
    assert result["failure_reason"] is None


# --- ruling 7: fixture_docx_sha256 identity ---


def test_typing_table_fixture_docx_mismatch_withholds_figure(fs):
    async def seed_row(docx_hash):
        result = await _probe_type("Hello", "Hello")
        row = _writer_row(result)
        row["refusal_code"] = None
        row["throughput_chars_s"] = 100.0
        row["fixture_docx_sha256"] = docx_hash
        row["fixture_words"] = 12805
        row["words_typed"] = 12805
        row["session_wall_s"] = 30
        return row

    hashes = ["aaa"] * 12 + ["bbb"] * 12
    rows = [asyncio.run(seed_row(h)) for h in hashes]
    root = Path("/pub")
    for seed in (0, 1):
        job = root / f"seed{seed}"
        job.mkdir(parents=True)
        (job / "summary.json").write_text(
            json.dumps(
                {
                    "run_id": f"run-{seed}",
                    "seed": seed,
                    "execution_profile": "dedicated_publish",
                    "host_class": "dedicated",
                    "publishable": True,
                    "host": {"os": "mac", "cpu": "same"},
                    "versions": {"harness": "1"},
                    "rendering": {
                        "browser_version": "c",
                        "playwright_version": "p",
                        "vendor": "g",
                        "renderer": "r",
                        "headless": True,
                    },
                    "order": [[i, "plate"] for i in range(12)],
                }
            )
        )
        for index, row in enumerate(rows[seed * 12 : (seed + 1) * 12]):
            path = job / "cells" / f"{index:04d}-plate" / "attempts" / "typing.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(row))
    text = typing_table({}, [root / "seed0", root / "seed1"], "plate", "throughput")
    assert "fixture mismatch" in text


# --- ruling 8: warm/cold attempts on disk ---


def test_persist_attempt_strips_only_accounting_scope(tmp_path, monkeypatch):
    from perf.runner import benchmark_warm_cold as wc
    from perf.runner.browser_run import ACTIVE, BrowserRun, CELL

    def fake_sample(self, name, trial):
        row = {
            **trial,
            "accounting_scope": "diagnostic",
            "cpu_accounting": {"available": True},
            "publication_block_reason": "deferred",
            "brackets_force_closed": True,
        }
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(row))
        return path

    monkeypatch.setattr(BrowserRun, "sample", fake_sample)
    token = ACTIVE.set(BrowserRun(tmp_path / "run", "benchmark_warm_cold", run_id="s2b", seed=1))
    cell_token = CELL.set({"repetition": 0, "editor_id": "plate"})
    attempt_dir = tmp_path / "attempts"
    attempt_dir.mkdir()
    try:
        wc._persist_attempt(
            attempt_dir,
            "C03",
            "plate",
            {
                "criterion_id": "C03",
                "editor_id": "plate",
                "outcome": "measured",
                "latency_ms": 12.0,
                "samples_ms": [12.0],
                "layer": "browser_visible",
                "boundary": "first_usable",
                "environment": {"cache_state": "cold"},
            },
        )
    finally:
        CELL.reset(cell_token)
        ACTIVE.reset(token)

    attempt = json.loads(next(attempt_dir.glob("*.json")).read_text())
    assert attempt.get("accounting_scope") is None
    assert attempt.get("cpu_accounting") == {"available": True}
    assert attempt.get("publication_block_reason") == "deferred"


def test_verify_run_on_shakedown_warm_cold_job_without_leniency_measured_gate(tmp_path, monkeypatch):
    if not SHAKEDOWN_JOB.is_dir():
        pytest.skip("shakedown job folder missing")
    job_dst = tmp_path / "job"
    shutil.copytree(SHAKEDOWN_JOB, job_dst)
    summary = json.loads((job_dst / "summary.json").read_text())
    data = {
        "runner": "benchmark_warm_cold",
        "rendering": summary.get("rendering") or {"renderer": "swiftshader"},
        "samples": [
            {
                "outcome": "ok",
                "editor_id": "plate",
                "cell_directory": str(job_dst / "cells" / "0000-plate"),
            }
        ],
    }
    monkeypatch.delenv("PERF_SHAKEDOWN", raising=False)
    counts_before = __import__("perf.container.policy", fromlist=["cell_counts"]).cell_counts(data)
    assert counts_before["measured"] > 0
    verify_run(data)
