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
