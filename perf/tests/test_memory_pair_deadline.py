"""A memory pair's deadline covers both loads and the burst; a failure keeps its stage record (#194).

Review D: Docen's and canvas-editor's prose-250kw C17/C19 timed out with
"probe produced no line before the timeout". The pair had one 720 s deadline
(load timeout + 120 s) for two loads, a 120-character burst (Docen types at
about 8.7 s per keystroke at that size), quiescence, close, retention and
reopen; and the diagnostic dropped every phase the pair had reached.
"""
from __future__ import annotations

import sys

import pytest

from perf.runner import benchmark_memory as bm
from perf.runner.load_timeouts import load_timeout_ms


@pytest.mark.parametrize("workload", ["prose-500w", "prose-250kw", "prose-500kw"])
def test_the_deadline_covers_two_loads_a_burst_and_the_retention_series(workload):
    load_s = load_timeout_ms(workload) / 1000.0
    deadline = bm._pair_deadline_s(60.0, workload, (1.0, 5.0, 30.0))
    assert deadline >= 3 * load_s + 30.0 + 120.0
    assert bm._pair_deadline_s(10_000.0, workload, (1.0,)) == 10_000.0  # a larger --probe-timeout wins


def test_a_timed_out_pair_names_the_phases_it_reached(monkeypatch):
    child = [sys.executable, "-c",
             "import sys, time; print('PHASE ready {\"browser_pid\": 4242}', flush=True); "
             "sys.stdin.readline(); time.sleep(30)"]
    monkeypatch.setattr(bm, "_probe_command", lambda *a, **k: child)
    monkeypatch.setattr(bm, "_pair_deadline_s", lambda *a, **k: 3.0)
    monkeypatch.setattr(bm, "_sample_roots", lambda roots: {"rss_bytes": 1, "process_count": 1,
                                                            "sampled_at_unix_ms": 0})
    monkeypatch.setattr(bm, "UI", ".")
    with pytest.raises(TimeoutError) as caught:
        bm._run_browser_pair(target={"url": "http://127.0.0.1:1/"}, corpus_path="x.docx", burst=120,
                             quiescence_ms=1000, retain_seconds=(1.0,), probe_timeout_s=1.0,
                             editor_id="docen", workload="prose-250kw")
    assert getattr(caught.value, "phases_reached", None) == ["ready"]
    pair = bm._failed_pair(0, caught.value, server_started=True)
    diagnostic = bm._pair_diagnostic(pair)
    assert diagnostic["error"] == "probe produced no line before the timeout"
    assert diagnostic["phases_reached"] == ["ready"]
    assert diagnostic["stalled_after"] == "ready"
