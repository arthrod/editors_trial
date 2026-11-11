"""Integration only: actual local browser and fake editor (never editor timings)."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
import pytest
from perf.runner.benchmark_typing import session
from perf.runner.browser_hosts import StaticHost

@pytest.mark.parametrize('mode,size', [('drop',30), ('heap',10000), ('cpu',6000),
                                      ('storage',6000), ('longtask',10000), ('freeze',100)])
def test_real_browser_fake_editor(mode, size, tmp_path):
    pytest.importorskip('playwright.async_api')
    pytest.importorskip('psutil')
    host = StaticHost(Path(__file__).parent/'fixtures')
    target = {'url':host.url+'/typing_editor.html?mode='+mode,
              'edit_selector':'#editor','ready_selector':'.status-ok'}
    args = SimpleNamespace(budget_s=12 if mode == 'freeze' else 180, cadence_ms=0,
                           sample_s=.5, witness_every=1000, quiescence_s=1)
    try:
        result, rows = asyncio.run(session(target,'x'*size,args,tmp_path))
    finally: host.stop()
    print('SESSION', result.get('failure_reason'), result.get('error'))
    if mode == 'drop':
        assert result['failure_reason'] == 'text_mismatch', result
        assert result['first_divergence_offset'] == 29
    elif mode == 'freeze':
        assert result['failure_reason'] == 'budget_exceeded', result
        assert 0 < result['characters_typed'] < size
        assert result['progress']['characters_typed'] == result['characters_typed']
        assert result['progress']['elapsed_s'] >= args.budget_s
    else:
        assert result['failure_reason'] is None, result
        phases = {r['milestone']:r for r in rows if r.get('milestone')}
        end, start = phases['end'], phases['typing_start']
        if mode == 'heap':
            assert end['js_heap_used_bytes'] - start['js_heap_used_bytes'] >= 8*1024**2
        elif mode == 'cpu':
            assert result['resources']['phases']['typing']['task_duration_ms'] >= 2000
            assert result['resources']['phases']['typing']['renderer_cpu_ms'] >= 1500
        elif mode == 'storage':
            assert end['storage_usage_bytes'] >= 10*1024**2
        elif mode == 'longtask':
            assert result['resources']['phases']['typing']['longtask_count'] >= 2
            assert result['resources']['phases']['typing']['longtask_sum_ms'] >= 400

def test_host_failure_writes_one_trial_and_series(tmp_path):
    """Integration: real output artifacts, fake failed host; no editor measurement."""
    import json
    from perf.runner.benchmark_typing import main_cell
    from perf.runner.browser_run import ACTIVE, BrowserRun
    run = BrowserRun(tmp_path/'runs', 'benchmark_typing', snapshot=lambda:{})
    token = ACTIVE.set(run)
    def failed_host(editor,target): raise RuntimeError('synthetic build unavailable')
    try:
        assert main_cell(['--editors','plate','--words','1000','--out-root',str(tmp_path/'cell')],
                         start_host=failed_host) == 0
    finally: ACTIVE.reset(token)
    trial = json.loads((tmp_path/'cell/attempts/typing.json').read_text())
    assert trial['failure_reason'] == 'host_start_failed'
    assert trial['throughput_chars_s'] is None
    assert trial['fixture_words'] == 1000
    assert json.loads((tmp_path/'cell/resources.json').read_text()) == []

@pytest.mark.parametrize('options', [['--words','-1'],['--cadence-ms','-1'], ['--sample-s','0']])
def test_cli_rejects_invalid_settings(options, tmp_path):
    from perf.runner.benchmark_typing import main_cell
    with pytest.raises(SystemExit) as caught:
        main_cell(['--out-root',str(tmp_path),*options])
    assert caught.value.code == 2

@pytest.mark.parametrize('mode,reason', [('readonly','no_correctness_adapter'), ('prefilled','document_not_empty')])
def test_unsupported_or_nonempty_surface_refuses_before_typing(mode, reason, tmp_path):
    pytest.importorskip('playwright.async_api'); pytest.importorskip('psutil')
    host = StaticHost(Path(__file__).parent/'fixtures')
    try:
        result, rows = asyncio.run(session({'url':host.url+'/typing_editor.html?mode='+mode,
            'edit_selector':'#editor','ready_selector':'.status-ok'},'abc',
            SimpleNamespace(budget_s=30,cadence_ms=0,sample_s=5,witness_every=100,quiescence_s=0),tmp_path))
    finally: host.stop()
    assert result['failure_reason'] == reason, result
    assert result['characters_typed'] == 0
    assert result['session_wall_s'] > 0
    assert rows

@pytest.mark.parametrize('module', ['playwright', 'psutil'])
def test_missing_dependency_is_named_and_not_a_host_failure(tmp_path, module):
    """Integration: dependency loading fails at startup; preserve its classification."""
    import json
    from perf.runner.benchmark_typing import main_cell
    from perf.runner.browser_run import ACTIVE, BrowserRun
    run = BrowserRun(tmp_path/'runs', 'benchmark_typing', snapshot=lambda: {})
    token = ACTIVE.set(run)
    def missing_dependency(editor, target):
        raise ModuleNotFoundError(f"No module named '{module}'", name=module)
    try:
        main_cell(['--editors', 'plate', '--words', '1', '--out-root', str(tmp_path/'cell')],
                  start_host=missing_dependency)
    finally:
        ACTIVE.reset(token)
    trial = json.loads((tmp_path/'cell/attempts/typing.json').read_text())
    assert trial['failure_reason'] == 'dependency_missing', trial
    assert trial['refusal_code'] == 'dependency_missing'
    assert trial['missing_module'] == module
    assert trial['outcome'] == 'refused'
    assert trial['throughput_chars_s'] is None


def test_session_dependency_failure_is_not_relabelled_as_crash(tmp_path, monkeypatch):
    from perf.runner import benchmark_typing as lane
    class MissingSampler:
        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError("No module named 'psutil'", name='psutil')
    monkeypatch.setattr(lane, 'TypingResourceSampler', MissingSampler)
    result, rows = asyncio.run(lane.session(
        {'url':'about:blank', 'edit_selector':'#editor'}, 'x',
        SimpleNamespace(budget_s=30, cadence_ms=0, sample_s=5,
                        witness_every=100, quiescence_s=0), tmp_path))
    assert result['failure_reason'] == 'dependency_missing', result
    assert result['refusal_code'] == 'dependency_missing'
    assert result['missing_module'] == 'psutil'
