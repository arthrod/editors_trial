"""Every lane describes a ladder fixture with the paragraph count of the bytes served."""
import pytest

from perf.fixtures.docx_workload import ladder_row_for_env, workload_docx
from perf.fixtures.profiles import size_ladder
from perf.runner.benchmark_warm_cold import _env_for
from perf.runner.browser_run import ACTIVE, BrowserRun

LADDER = ("prose-500w", "prose-5kw", "prose-50kw", "prose-250kw", "complex-corpus")


@pytest.mark.parametrize("workload_id", LADDER)
def test_env_paragraph_count_matches_served_docx(tmp_path, workload_id):
    run = BrowserRun(tmp_path, "pcount", seed=1, run_id="r", snapshot=lambda: {})
    run.execution_profile = "dedicated_publish"
    run.host_class = "shared_guarded"
    token = ACTIVE.set(run)
    try:
        meta = workload_docx(workload_id)
        row = dict(next(r for r in size_ladder() if r["workload_id"] == workload_id))
        assert ladder_row_for_env(row)["paragraphs"] == meta["paragraph_count"]
        env = _env_for(editor_id="plate", editor_version="v", fixture_sha256=meta["sha256"],
                       workload_row=row, docx_size=meta["byte_size"], cache_state="process_cold_fs_warm")
        assert env["fixture_paragraph_count"] == meta["paragraph_count"]
    finally:
        ACTIVE.reset(token)
