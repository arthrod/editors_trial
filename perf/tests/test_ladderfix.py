"""Publication ladder: warm/cold prose-corpus bytes and corpus paragraph counts."""
import hashlib
import json
import sys

import pytest

from perf.fixtures.docx_workload import workload_docx, workload_for_lane
from perf.fixtures.profiles import size_ladder
from perf.runner import adversarial_c10_scroll as scroll
from perf.runner import benchmark_document as bdoc
from perf.runner import benchmark_input as binput
from perf.runner import benchmark_memory as bmem
from perf.runner import benchmark_warm_cold as bwc
from perf.runner import criteria_input_io
from perf.runner.browser_run import ACTIVE, BrowserRun

LADDER = ("prose-500w", "prose-5kw", "prose-50kw", "prose-250kw", "complex-corpus")


@pytest.mark.parametrize("workload_id", LADDER)
def test_warm_cold_ladder_builds_fixture_and_matching_env(tmp_path, monkeypatch, workload_id):
    meta = workload_for_lane(workload_id, "warm_cold")
    expected_sha = meta["sha256"]

    out_root = tmp_path / "cell"
    run = BrowserRun(tmp_path, "warm", seed=1, run_id="r", snapshot=lambda: {})
    run.execution_profile = "dedicated_publish"
    run.host_class = "shared_guarded"

    def passthrough_sample(self, name, trial):
        path = self.directory / "samples" / ("%s.json" % name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(trial))
        return path

    monkeypatch.setattr(BrowserRun, "sample", passthrough_sample)
    token = ACTIVE.set(run)
    monkeypatch.setattr(bwc, "_start_server", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stub")))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark_warm_cold",
            "--workload",
            workload_id,
            "--editors",
            "plate",
            "--pairs",
            "1",
            "--out-root",
            str(out_root),
        ],
    )
    try:
        bwc._main()
        fixture = next(iter(run.fixtures.values()))
    finally:
        ACTIVE.reset(token)

    assert fixture.is_file()
    assert fixture.read_bytes() == meta["docx"]
    trials = list((out_root / "attempts").glob("*.json"))
    assert trials
    env = json.loads(trials[0].read_text())["environment"]
    assert env["fixture_sha256"] == expected_sha
    assert env["fixture_byte_size"] == meta.get("byte_size", len(meta["docx"]))


def test_complex_corpus_envs_carry_paragraph_count(tmp_path):
    workload_id = "complex-corpus"
    expected = workload_docx(workload_id)["paragraph_count"]
    row = next(r for r in size_ladder() if r["workload_id"] == workload_id)

    fixture = scroll.scroll_fixture(workload_id)
    scroll_env = scroll.scroll_env(
        editor_id="plate",
        editor_version="v",
        execution_profile="dedicated_publish",
        host_class="shared_guarded",
        fixture=fixture,
    )
    assert scroll_env["fixture_paragraph_count"] == expected

    built = bdoc.build_fixture(row)
    doc_env = bdoc._env_for(
        editor_id="plate",
        editor_version="v",
        fixture=built,
        cache_state="warm_steady",
    )
    assert doc_env["fixture_paragraph_count"] == expected

    _path, sha, size, input_row = binput._fixture("plate", workload_id)
    input_env = criteria_input_io.env_for("plate", "plate", sha, input_row, size, "warm_steady")
    assert input_env["fixture_paragraph_count"] == expected

    mem_run = BrowserRun(tmp_path, "mem", snapshot=lambda: {})
    mem_run.execution_profile = "dedicated_publish"
    mem_run.host_class = "shared_guarded"
    token = ACTIVE.set(mem_run)
    try:
        memory_env = bmem._env_for(
            editor_id="plate",
            editor_version="v",
            fixture_sha=sha,
            docx_size=size,
            workload_row=row,
            cache_state="warm_steady",
            execution_profile="dedicated_publish",
        )
    finally:
        ACTIVE.reset(token)
    assert memory_env["fixture_paragraph_count"] == expected
