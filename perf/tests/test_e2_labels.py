"""#128 E2 labels: writers stamp refusal_code/refusal_detail at the failure site.

A refused trial publishes the family's owner code, not the reader's 'crash'
fallback. Each test fault-injects at the writer failure site and reads the
persisted attempt JSON.
"""
import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from perf.tests.test_schema import _env
from perf.runner import benchmark_document as bdoc
from perf.runner import benchmark_input as binput
from perf.runner import benchmark_memory as bmem
from perf.runner import benchmark_typing as btyping
from perf.runner import benchmark_warm_cold as bwc
from perf.runner import criteria_input_io


def _proc(stdout='', stderr='', returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode, args=['node'])


# ---- F2/R3: a refused C14 rung carries the refusal's real family ------------

def test_c14_rung_refusal_keeps_the_inner_family(tmp_path):
    path = bdoc._write_refusal(
        attempt_dir=tmp_path, criterion_id='C14', editor_id='plate', lane='browser',
        env=_env(), outcome='failed',
        failure_reason='rung small: witness refused: no_frame')
    trial = json.loads(path.read_text())
    assert trial['refusal_code'] != 'crash', trial
    assert trial['refusal_code'] == 'paint_witness_unavailable', trial
    assert trial['refusal_detail'], trial


def test_c14_rung_probe_death_keeps_the_exception_family(tmp_path):
    refusal = bdoc.ProbeRefusal('probe error for plate: Target closed',
                                refusal_code='editor_crash')
    path = bdoc._write_refusal(
        attempt_dir=tmp_path, criterion_id='C14', editor_id='plate', lane='browser',
        env=_env(), outcome='failed',
        failure_reason='rung small: %s' % refusal.reason,
        refusal_code=getattr(refusal, 'refusal_code', None))
    trial = json.loads(path.read_text())
    assert trial['refusal_code'] == 'editor_crash', trial
    assert trial['refusal_detail'] == 'rung small: probe error for plate: Target closed'


# ---- F3/R6: dead probe and not_applicable contract violations ---------------

@pytest.mark.parametrize('rc,code', [(1, 'editor_crash'), (2, 'harness_error')])
def test_b3_probe_death_family(monkeypatch, rc, code):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: _proc(returncode=rc))
    with pytest.raises(bdoc.ProbeRefusal) as caught:
        bdoc._run_probe(['node', 'probe'], editor_id='plate')
    assert caught.value.refusal_code == code


def test_b3_probe_error_family_split(monkeypatch):
    for reason, code in [
        ('Target closed', 'editor_crash'),
        ('page.goto: Timeout 120000ms exceeded', 'editor_crash'),
        ('AssertionError: no selector matches', 'harness_error'),
    ]:
        monkeypatch.setattr(subprocess, 'run', lambda *a, **k: _proc(
            stdout=json.dumps({'status': 'probe_error', 'reason': reason}), returncode=1))
        with pytest.raises(bdoc.ProbeRefusal) as caught:
            bdoc._run_probe(['node', 'probe'], editor_id='plate')
        assert caught.value.refusal_code == code, reason


def test_b3_not_applicable_contract_violation_is_harness_error():
    with pytest.raises(bdoc.ProbeRefusal) as caught:
        bdoc.find_outcomes({'status': 'not_applicable'})
    assert caught.value.refusal_code == 'harness_error'


# ---- F4/R8: B4 failure paths write a refused trial per criterion ------------

def _b4_env_args(tmp_path):
    from perf.fixtures.profiles import size_ladder
    row = next(r for r in size_ladder() if r['workload_id'] == 'micro-paragraphs')
    return row


def _stub_b4_launch(tmp_path, monkeypatch):
    row = _b4_env_args(tmp_path)
    fixture = tmp_path / 'fixture.docx'
    fixture.write_bytes(b'x')
    monkeypatch.setattr(binput, '_fixture', lambda e, workload_id='micro-paragraphs': (fixture, 'a' * 64, 1, row))
    import perf.runner.browser_hosts as hosts
    monkeypatch.setattr(hosts, 'select_fixture', lambda *a: None)
    monkeypatch.setattr(binput, '_stop_server', lambda s: None)
    # 3ce91fad passed the workload to _probe_env; the stub takes it too.
    monkeypatch.setattr(binput, '_probe_env', lambda *a, **k: {})
    return row


def test_b4_host_start_failure_writes_host_build_trials(tmp_path, monkeypatch):
    _stub_b4_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(binput, '_start_server',
                        lambda *a: (_ for _ in ()).throw(RuntimeError('no host')))
    attempts = tmp_path / 'attempts'
    row = binput.run_editor('plate', attempts)
    assert row['outcome'] == 'failed'
    trials = [json.loads(p.read_text()) for p in sorted(attempts.glob('*.json'))]
    assert len(trials) == len(binput.CRITERIA)
    for trial in trials:
        assert trial['outcome'] == 'failed', trial
        assert trial['refusal_code'] == 'host_build', trial
        assert trial['refusal_detail'], trial


def test_b4_probe_timeout_writes_editor_timeout_trials(tmp_path, monkeypatch):
    _stub_b4_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(binput, '_start_server', lambda *a: object())

    def timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd='node', timeout=1)
    monkeypatch.setattr(subprocess, 'run', timeout)
    attempts = tmp_path / 'attempts'
    binput.run_editor('plate', attempts)
    trials = [json.loads(p.read_text()) for p in sorted(attempts.glob('*.json'))]
    assert len(trials) == len(binput.CRITERIA)
    assert {t['refusal_code'] for t in trials} == {'editor_timeout'}


def test_b4_probe_exit_writes_editor_crash_trials(tmp_path, monkeypatch):
    _stub_b4_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(binput, '_start_server', lambda *a: object())
    monkeypatch.setattr(subprocess, 'run',
                        lambda *a, **k: _proc(stderr='E: editor gone', returncode=1))
    attempts = tmp_path / 'attempts'
    binput.run_editor('plate', attempts)
    trials = [json.loads(p.read_text()) for p in sorted(attempts.glob('*.json'))]
    assert len(trials) == len(binput.CRITERIA)
    assert {t['refusal_code'] for t in trials} == {'editor_crash'}


def test_b4_non_json_stdout_writes_harness_error_trials(tmp_path, monkeypatch):
    _stub_b4_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(binput, '_start_server', lambda *a: object())
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: _proc(stdout='not json'))
    attempts = tmp_path / 'attempts'
    binput.run_editor('plate', attempts)
    trials = [json.loads(p.read_text()) for p in sorted(attempts.glob('*.json'))]
    assert len(trials) == len(binput.CRITERIA)
    assert {t['refusal_code'] for t in trials} == {'harness_error'}


def test_b4_contract_violation_writes_harness_error_trial(tmp_path):
    payload = {
        'probe': 'criteria_input', 'schema': 'perf.criteria_input/1',
        'criteria_requested': ['C04'],
        'criteria': {'C04': {'outcome': 'bogus'}},
        'editor_id': 'plate',
    }
    written = criteria_input_io.write_trials_from_payload(
        payload, tmp_path, editor_version='plate', fixture_sha256='a' * 64,
        workload_row=_b4_env_args(tmp_path), docx_size=1)
    assert written['C04']['written'] is False
    path = Path(written['C04']['path'])
    trial = json.loads(path.read_text())
    assert trial['outcome'] == 'failed', trial
    assert trial['refusal_code'] == 'harness_error', trial
    assert trial['refusal_detail'], trial


# ---- F5/R2: B9 typing refusal labels ---------------------------------------

def _stub_typing_empty_docx(tmp_path, monkeypatch):
    """main_cell hashes the empty DOCX after the session; the stub must materialise it."""
    from perf.fixtures.generate import docx_zip_bytes

    data = docx_zip_bytes(b'\n', section_properties=True)
    path = tmp_path / 'empty.docx'

    def materialise(*_a, **_k):
        path.write_bytes(data)
        return path

    monkeypatch.setattr(btyping, 'fixture_path', materialise)
    monkeypatch.setattr(btyping, 'select_fixture', lambda *a: None)


def _run_main_cell(tmp_path, monkeypatch, session_result):
    _stub_typing_empty_docx(tmp_path, monkeypatch)

    async def fake_session(target, text, args, directory):
        return session_result, []
    monkeypatch.setattr(btyping, 'session', fake_session)
    run = SimpleNamespace(run_id='r1', seed=1, execution_profile='ci_broad',
                          host_class='ci_coarse', hosts={})
    token = btyping.ACTIVE.set(run)
    try:
        btyping.main_cell(
            ['--out-root', str(tmp_path), '--editors', 'plate'],
            start_host=lambda e, t: object(), stop_host=lambda s: None)
    finally:
        btyping.ACTIVE.reset(token)
    return json.loads((tmp_path / 'attempts' / 'typing.json').read_text())


def test_b9_budget_exceeded_labels_editor_timeout(tmp_path, monkeypatch):
    trial = _run_main_cell(tmp_path, monkeypatch,
                           {'failure_reason': 'budget_exceeded', 'characters_typed': 3,
                            'refusal_code': 'editor_timeout'})
    assert trial['refusal_code'] == 'editor_timeout', trial
    assert trial['refusal_detail'] == 'budget_exceeded'


def test_b9_host_start_failed_labels_host_build(tmp_path, monkeypatch):
    _stub_typing_empty_docx(tmp_path, monkeypatch)
    run = SimpleNamespace(run_id='r1', seed=1, execution_profile='ci_broad',
                          host_class='ci_coarse', hosts={})
    token = btyping.ACTIVE.set(run)

    def broken(e, t):
        raise RuntimeError('no host')
    try:
        btyping.main_cell(['--out-root', str(tmp_path), '--editors', 'plate'],
                          start_host=broken, stop_host=lambda s: None)
    finally:
        btyping.ACTIVE.reset(token)
    trial = json.loads((tmp_path / 'attempts' / 'typing.json').read_text())
    assert trial['refusal_code'] == 'host_build', trial


def test_b9_insufficient_accepted_labels_witness_unavailable(tmp_path, monkeypatch):
    trial = _run_main_cell(tmp_path, monkeypatch,
                           {'failure_reason': None,
                            'key_to_paint': {'refusal_code': 'insufficient_accepted',
                                             'median_ms': None}})
    assert trial['refusal_code'] == 'witness_unavailable', trial
    assert trial['refusal_detail'] == 'insufficient_accepted'


def test_b9_text_mismatch_labels_correctness_failure():
    from perf.tests.test_typing_marathon import FakePage
    from perf.tests.test_typing_fix3 import TypingSamples

    async def run():
        async def witness(char):
            raise AssertionError('no witness expected')
        page = FakePage(drop=True)
        return await btyping.type_document(
            page, TypingSamples(), witness, 'abcdef', selector='#editor',
            clock=lambda: 0.0)

    result = asyncio.run(run())
    assert result['failure_reason'] == 'text_mismatch'
    assert result['refusal_code'] == 'correctness_failure'


def test_b9_type_budget_exceeded_labels_editor_timeout():
    from perf.tests.test_typing_marathon import FakePage
    from perf.tests.test_typing_fix3 import TypingSamples

    async def run():
        async def witness(char):
            raise AssertionError('no witness expected')
        page = FakePage(freeze=True)
        return await btyping.type_document(
            page, TypingSamples(), witness, 'ab', selector='#editor',
            clock=lambda: 0.0)

    result = asyncio.run(run())
    assert result['failure_reason'] == 'budget_exceeded'
    assert result['refusal_code'] == 'editor_timeout'


# ---- R4: B8 memory failed trials get their family ---------------------------

def test_b8_failed_memory_trial_carries_family(tmp_path):
    from perf.tests.test_memory_criteria import _env as mem_env
    path = bmem._write_outcome(
        attempt_dir=tmp_path, criterion_id='C17', phase='ready', editor_id='plate',
        lane='browser', env=mem_env(), outcome='failed',
        failure_reason='plate exited 1: boom', evidence={'state': 'process_failed'},
        refusal_code='editor_crash')
    trial = json.loads(path.read_text())
    assert trial['refusal_code'] == 'editor_crash', trial
    assert trial['refusal_detail'] == 'plate exited 1: boom'


def test_b8_pair_error_family_split():
    assert bmem._pair_error_family(TimeoutError('no line')) == 'editor_timeout'
    exc = RuntimeError('probe exited (1) without a RESULT')
    exc.refusal_family = 'editor_crash'
    assert bmem._pair_error_family(exc) == 'editor_crash'
    assert bmem._pair_error_family(ValueError('bad sample')) == 'harness_error'


def test_b8_probe_failure_writes_family(tmp_path, monkeypatch):
    from perf.tests.test_memory_criteria import _env as mem_env
    monkeypatch.setattr(bmem, '_start_server', lambda *a: SimpleNamespace(pid=1))
    monkeypatch.setattr(bmem, '_port_is_free', lambda *a, **k: True)
    monkeypatch.setattr(bmem, '_stop_server', lambda s: None)
    monkeypatch.setattr(bmem, '_env_for', lambda **k: mem_env())
    monkeypatch.setattr(bmem, 'browser_harness_editor_version', lambda *a: ('v1', None))
    monkeypatch.setattr(bmem, 'load_average', lambda: None)

    def dead_pair(*a, **k):
        raise TimeoutError('probe produced no line before the timeout')
    monkeypatch.setattr(bmem, '_run_browser_pair', dead_pair)
    args = SimpleNamespace(pairs=1, burst=0, quiescence_ms=0, retain_seconds=[],
                           probe_timeout=5, execution_profile='ci_broad',
                           host_class='ci_coarse',
                           # lax layer (owner 2026-11-11): _run_browser_pair
                           # takes the workload for its load-timeout env.
                           workload='micro-paragraphs')
    target = {'url': 'http://127.0.0.1:1', 'lane': 'browser'}
    bmem._browser_rows(
        editor_id='plate', lane='browser', target=target, attempt_dir=tmp_path,
        args=args, fixture_path=tmp_path / 'f.docx', fixture_sha='a' * 64,
        docx_size=1, workload_row={'workload_id': 'micro-paragraphs'})
    trials = [json.loads(p.read_text()) for p in sorted(tmp_path.rglob('*.json'))]
    assert trials
    assert all(t['refusal_code'] == 'editor_timeout' for t in trials
               if t.get('outcome') == 'failed'), trials


# ---- R5: B2 unmapped witness reasons ---------------------------------------

@pytest.mark.parametrize('reason,code', [
    ('nonfinite_time', 'witness_unavailable'),
    ('monotonic_origin_missing', 'witness_unavailable'),
    ('negative_input_latency', 'witness_unavailable'),
    ('input_probe_error: RuntimeError boom', 'harness_error'),
])
def test_b2_witness_reasons_map_to_families(tmp_path, reason, code):
    path = bwc._persist_attempt(tmp_path, 'C05', 'plate', {
        'criterion_id': 'C05', 'editor_id': 'plate', 'layer': 'browser_visible',
        'boundary': 'presented_frame', 'environment': _env(), 'outcome': 'failed',
        'failure_reason': reason, 'samples_ms': [], 'latency_ms': None, 'claims': []})
    trial = json.loads(path.read_text())
    assert trial['refusal_code'] == code, trial
