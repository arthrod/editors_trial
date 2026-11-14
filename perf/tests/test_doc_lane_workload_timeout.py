"""The document lane's C11, C12 and C15 probes wait their workload's load timeout.

Report E2 campaign (2026-11-14): Plate's prose-250kw C11/C12 attempts record
``load_timeout_ms: 600000`` (the #155 policy), yet the probe was launched
with ``--timeout-ms 300000`` and a 330 s watchdog. ``BROWSER_TARGETS``
entries carry no ``workload_id``, so ``_probe_timeout_ms`` fell back to the
300 s default. C14 already passes its own timeout (#184). The 500k rung
(#188) would have waited 300 s instead of 1,000 s.
"""
import ast
from pathlib import Path

import pytest

from perf.runner import benchmark_document as bd
from perf.runner.load_timeouts import load_timeout_ms

RUNNERS = ('_run_load_samples', '_run_reflow_samples', '_run_find_payloads')


def _flag(cmd, flag):
    return int(cmd[cmd.index(flag) + 1])


@pytest.fixture
def captured(monkeypatch):
    seen = []
    monkeypatch.setattr(bd, '_run_probe', lambda cmd, **kw: seen.append(list(cmd)) or {'status': 'not_applicable'})
    monkeypatch.setattr(bd, 'corpus_opening_text', lambda path: 'Opening')
    monkeypatch.setattr(bd, 'corpus_content_expectation_flags', lambda path: [])
    monkeypatch.setattr(bd, '_in_sample_bracket', lambda editor, cid, fn: fn())
    return seen


TARGET = {'url': 'http://127.0.0.1/x', 'corpus_route': '/corpus.docx'}
CFG = {'doc_selector': '.p', 'page_model': 'continuous_flow', 'edit_selector': '.p', 'find_input_selector': '#find'}


@pytest.mark.parametrize('workload', ['prose-5kw', 'prose-250kw', 'prose-500kw'])
@pytest.mark.parametrize('runner', RUNNERS)
def test_each_runner_passes_the_workload_timeout(captured, runner, workload):
    fn = getattr(bd, runner)
    try:
        fn(editor_id='plate', target=dict(TARGET), cfg=dict(CFG), fixture_path=Path('unused'), count=1,
           workload_id=workload)
    except Exception:
        pass  # the fake probe's payload is not a sample; only the command matters here
    assert captured, runner
    cmd = captured[0]
    assert _flag(cmd, '--timeout-ms') == load_timeout_ms(workload)
    assert bd._subprocess_timeout_s(cmd) == load_timeout_ms(workload) / 1000 + 30


def test_every_call_in_main_names_the_workload():
    source = Path(bd.__file__).read_text()
    main = next(node for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.FunctionDef) and node.name == '_main')
    calls = [node for node in ast.walk(main)
             if isinstance(node, ast.Call) and getattr(node.func, 'id', None) in RUNNERS]
    assert {call.func.id for call in calls} == set(RUNNERS)
    for call in calls:
        assert 'workload_id' in {kw.arg for kw in call.keywords}, (call.func.id, call.lineno)


@pytest.mark.parametrize('reason,code', [
    ('page.waitForFunction: Timeout 300000ms exceeded.', 'editor_timeout'),
    ('page.goto: Timeout 600000ms exceeded.', 'editor_timeout'),
    ('locator.waitFor: timed out waiting for .doc', 'editor_timeout'),
    ('page.evaluate: Target closed', 'editor_crash'),
    ('Page crashed', 'editor_crash'),
    ('Browser has been closed', 'editor_crash'),
    ('frame was detached during waitForFunction: Timeout 300000ms exceeded', 'editor_crash'),
    ('no document surface', 'harness_error'),
])
def test_a_probe_timeout_is_a_timeout_not_a_crash(reason, code):
    # Plate's prose-250kw C11/C12 waits were labelled editor_crash (2026-11-14).
    assert bd._probe_error_refusal_code({'status': 'probe_error', 'reason': reason}) == code
