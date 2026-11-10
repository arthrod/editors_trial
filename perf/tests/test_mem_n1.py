"""#136: a browser-lane fresh_process memory trial carries ONE value per launch.

Publication n is enforced per cell (perf.analysis.e2_cells), as for the
document lane; the per-trial I10 n>=2 check must not refuse every launch.
"""
import json

import pytest

from perf.runner import benchmark_memory as memory
from perf.runner import browser_run as api
from perf.tests.test_memory_criteria import _env


@pytest.mark.parametrize("criterion_id,phase", [("C17", "ready"), ("C19", None)])
def test_one_sample_per_launch_is_publishable(tmp_path, criterion_id, phase):
    run = api.BrowserRun(tmp_path, "mem-n1", snapshot=lambda: {})
    run.host_class = "shared_guarded"
    run.execution_profile = "dedicated_publish"
    token = api.ACTIVE.set(run)
    try:
        env = _env(cache_state="process_cold_fs_warm", execution_profile="dedicated_publish")
        assert env["repetition_unit"] == "fresh_process"
        path = memory._write_measured(
            attempt_dir=tmp_path / "attempts", criterion_id=criterion_id, phase=phase,
            editor_id="plate", lane="browser_slate", env=env,
            samples_bytes=[64 * 1024], evidence={}, diagnostic={"host_class": "shared_guarded"})
    finally:
        api.ACTIVE.reset(token)
    trial = json.loads(path.read_text())
    assert trial.get("publication_block_reason") is None, trial.get("publication_block_reason")
    assert trial["publishable"] is True
