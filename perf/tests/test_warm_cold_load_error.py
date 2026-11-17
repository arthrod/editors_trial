"""#261: an editor's own load error is the recorded reason, not the first line of Node's stack."""
from perf.runner import benchmark_warm_cold as wc

STDERR = """node:internal/modules/run_main:123
    triggerUncaughtException(
    ^

page.waitForFunction: Error: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width')
    at TableParticle.computeRowColInfo (http://127.0.0.1:5204/@fs/x/TableParticle.ts:544:40)
    at LayoutEngine.computeRowList (http://127.0.0.1:5204/@fs/x/LayoutEngine.ts:248:29)

Node.js v22.23.5
"""


def test_the_editors_own_load_error_is_the_reason():
    reason = wc.probe_failure_reason(RuntimeError(STDERR))
    assert reason.startswith("editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width')")
    assert "node:internal" not in reason and len(reason) <= 420


def test_any_other_probe_failure_keeps_its_text():
    assert wc.probe_failure_reason(RuntimeError("probe timed out after 300 s")) == "browser_probe: probe timed out after 300 s"


def test_an_editors_load_failure_is_a_failed_trial_filed_as_a_crash():
    """#261: the input lane files it under 'crash'; this lane wrote 'not_run', as if nothing had been tried."""
    reason = wc.probe_failure_reason(RuntimeError(STDERR))
    assert wc.probe_failure_outcome(reason) == "failed"
    assert wc.refusal_code_for(wc.probe_failure_outcome(reason), reason) == "crash"


def test_a_probe_that_failed_for_another_reason_is_still_not_run():
    reason = wc.probe_failure_reason(RuntimeError("probe timed out after 300 s"))
    assert wc.probe_failure_outcome(reason) == "not_run"
    assert wc.refusal_code_for("not_run", reason) == "not_run"


def test_the_written_trial_carries_the_outcome_it_is_given(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(wc, "validate_environment", lambda env: None)
    seen = {}
    monkeypatch.setattr(wc, "_persist_attempt", lambda attempt_dir, cid, editor, trial: seen.update(trial) or tmp_path)
    wc._write_not_run(attempt_dir=tmp_path, criterion_id="C05", layer="browser_visible", boundary="presented_frame",
                      editor_id="canvas", lane="editor", env={"cache_state": "warm_steady"},
                      failure_reason="editor_load_failed: TypeError: x", outcome="failed")
    assert seen["outcome"] == "failed" and seen["failure_reason"].startswith("editor_load_failed:")
    assert json.dumps(seen["samples_ms"]) == "[]"
