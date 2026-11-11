"""B9 review regressions; real browser cases are explicitly integration tests."""
import asyncio
from types import SimpleNamespace
from pathlib import Path
import pytest
from perf.runner.benchmark_typing import latency_summary, type_document, session
from perf.tests.test_typing_marathon import no_frame
from perf.tests.test_typing_marathon import ResourceSampler
from perf.tests.test_typing_marathon import FakePage, FakeCDP


def good(**overrides):
    from perf.tests.witness_records import publishable_witness_record
    return publishable_witness_record(1234.5, 1230, **overrides)


def test_partial_refusals_keep_distribution_and_counts():
    result = latency_summary([good(), good(document_scoped=False)])
    assert result['median_ms'] is None
    mixed = latency_summary([good()]*100 + [no_frame()]*100)
    assert mixed['median_ms'] == 4.5
    assert mixed['refusal_codes'] == {'no_frame': 100}
    assert result['n_accepted'] == 1 and result['n_refused'] == 1
    assert result['refusal_codes'] == {'not_document_scoped':1}
    assert result['minimum_accepted'] == 2
    assert latency_summary([good()] + [no_frame()]*2)['median_ms'] is None


def test_null_keydown_refuses_without_exception():
    try:
        result = latency_summary([{**good(), 'after_page_ms':None}])
    except TypeError as exc:
        pytest.fail(f'null keydown raised instead of refusing: {exc}')
    assert result['refusals'] == ['no_keydown']


async def typing(text, every=2):
    now = [0.0]
    class Page(FakePage):
        async def type(self, char):
            await super().type(char)
            now[0] += .01
    page = Page()
    def processes(): return []
    resources = SimpleNamespace(clock=lambda:now[0], process_snapshot=processes, profile_size=lambda:100, network={})
    sampler = ResourceSampler(resources,page,FakeCDP(page))
    chars = []
    async def witness(char):
        chars.append(char)
        await page.type(char)
        now[0] += 1
        return {**good(), 'frame_page_ms':1240, 'elapsed_ms':1010}
    result = await type_document(page,sampler,witness,text,selector='#editor', session_kind='latency', witness_every=every,clock=lambda:now[0])
    return result, chars, sampler


@pytest.mark.parametrize('text,expected', [('a §—“b c',['b','c']), ('a§b',['b'])])
def test_schedule_skips_spaces_and_insert_text_characters(text, expected):
    result, chars, _ = asyncio.run(typing(text, every=2))
    assert chars == expected
    assert result['characters_typed'] == len(text) and result['failure_reason'] is None


def test_instrumented_wall_throughput_includes_witness_stalls():
    result, _, _ = asyncio.run(typing('abcdef'))
    assert result['throughput_chars_s'] is None
    assert result['instrumented']['throughput_chars_s'] == pytest.approx(6 / 3.06)
    assert result['unwitnessed_characters'] == 3
    assert result['witness_wall_s'] == pytest.approx(3.03)


def test_integration_profile_delta_uses_load_baseline(tmp_path):
    async def check():
        page = FakePage(); size = tmp_path/'data'; size.write_bytes(b'x'*100)
        def processes(): return []
        run = SimpleNamespace(clock=lambda:0,process_snapshot=processes,profile_size=lambda:0,profile_dir=tmp_path,network={})
        sampler = ResourceSampler(run,page,FakeCDP(page))
        await sampler.mark('load'); size.write_bytes(b'x'*140)
        row = await sampler.mark('end')
        assert row['profile_bytes'] == 40
        assert row['profile_absolute_bytes'] == 140
    asyncio.run(check())


@pytest.mark.parametrize('repeat', [1,2])
def test_integration_fair_load_and_normalized_dom_backlog(tmp_path, repeat):
    from perf.runner.browser_hosts import StaticHost
    host = StaticHost(Path(__file__).parent/'fixtures')
    try:
        result, rows = asyncio.run(session({'url':host.url+'/typing_fair.html',
            'edit_selector':'#editor','ready_selector':'.status-ok'}, 'Heading\n\nWords here\n\nEnd §—“x',
            SimpleNamespace(budget_s=60,cadence_ms=0,sample_s=5,witness_every=5,quiescence_s=0),tmp_path))
    finally: host.stop()
    assert result['instrumented']['load_ms'] is not None, result.get('load_witness')
    assert result['failure_reason'] is None, result
    assert result['characters_typed'] > 0
    assert rows[-1]['backlog_chars'] == 0


def test_publication_flags_and_typing_only_minimum():
    from perf.container.policy import publication_jobs
    from perf.runner import browser_run as br
    assert getattr(br, 'TYPING_PUBLICATION_SESSIONS', None) == 12
    assert getattr(br, 'TYPING_PUBLICATION_MIN_KEPT', None) == 10
    for name, args in publication_jobs(['plate'], 1, 2, 'shared_guarded'):
        if name == 'benchmark_typing':
            for flag, value in [('--repetitions','12'),('--cadence-ms','0'),('--budget-s','3600')]:
                assert flag in args and args[args.index(flag)+1] == value
    import sys
    old = sys.argv
    class ReachedFactory(Exception): pass
    def factory(*a, **kw): raise ReachedFactory()
    try:
        for runner, n, accepted in [('benchmark_typing',12,True),('benchmark_typing',11,False),
                                     ('benchmark_input',12,False),('benchmark_input',30,True)]:
            sys.argv = ['test','--execution-profile','dedicated_publish','--host-class','dedicated',
                        '--repetitions',str(n)]
            with pytest.raises(ReachedFactory if accepted else SystemExit):
                br.run_cli(lambda:0,runner,{'plate':{}},run_factory=factory)
    finally: sys.argv = old


def test_integration_save_timeout_is_named(tmp_path):
    from perf.runner.browser_hosts import StaticHost
    host = StaticHost(Path(__file__).parent/'fixtures')
    try:
        result, _ = asyncio.run(session({'url':host.url+'/typing_fair.html',
            'edit_selector':'#editor','ready_selector':'.status-ok','typing_save_selector':'.status-ok'}, 'abc',
            SimpleNamespace(budget_s=90,cadence_ms=0,sample_s=5,witness_every=100,quiescence_s=0),tmp_path))
    finally: host.stop()
    assert result['failure_reason'] == 'save_timeout', result
    assert result['characters_typed'] == 3


@pytest.mark.parametrize('kept,refused', [(9, True),(10, False)])
def test_integration_typing_kept_gate_per_editor(tmp_path, kept, refused):
    """Real BrowserRun artifacts; fake cell, host facts, and accounting."""
    import sys, json
    from functools import partial
    from perf.runner.browser_run import BrowserRun, CELL, ACTIVE, run_cli, write_json
    old = sys.argv
    def cell():
        run = ACTIVE.get(); current = CELL.get()
        directory = Path(sys.argv[sys.argv.index('--out-root')+1])
        reason = 'text_mismatch' if current['editor_id'] == 'plate' and current['repetition'] >= kept else None
        write_json(directory/'attempts'/'typing.json', {'criterion_id':'TYPING', 'session_kind':'throughput', 'outcome':'refused' if reason else 'measured',
            'correctness_oracle':'dom_document_text', 'failure_reason':reason, 'load_ms':12, 'throughput_chars_s':100, 'key_to_paint':{'median_ms':16}})
        return 0
    try:
        sys.argv = ['test','--execution-profile','dedicated_publish','--host-class','dedicated',
                    '--out-root',str(tmp_path),'--run-id','gate','--editors','plate','folio']
        run_cli(cell,'benchmark_typing',{'plate':{},'folio':{}},
            run_factory=partial(BrowserRun,snapshot=lambda:{},accounting_reader=lambda:{'available':False,'reason':'synthetic unavailable accounting'}),
            facts=(lambda:{},lambda:{}))
    finally: sys.argv = old
    result = json.loads((tmp_path/'benchmark_typing/gate/summary.json').read_text())
    assert len(result['samples']) == 24
    assert result['typing_sessions_kept'] == {'plate':{'throughput':kept},'folio':{'throughput':12}}
    assert (result.get('failure_reason') == 'insufficient_typing_sessions') is refused


def test_summary_malformed_record_preserves_completed_typing():
    async def check():
        page = FakePage()
        def processes(): return []
        sampler = ResourceSampler(SimpleNamespace(clock=lambda:0, process_snapshot=processes,
            profile_size=lambda:0,network={}),page,FakeCDP(page))
        async def witness(char):
            await page.type(char)
            return {**good(),'frame_interval_ms':'malformed'}
        result = await type_document(page,sampler,witness,'abc',selector='#editor',session_kind='latency',witness_every=1,clock=lambda:0)
        assert result['characters_typed'] == 3
        assert result['failure_reason'] is None
        assert result['key_to_paint']['refusals'] == ['witness_schema_invalid']*3
    asyncio.run(check())


def test_integration_hf_image_prepares_python_dependencies():
    image = (Path(__file__).parents[1]/'container/Dockerfile').read_text()
    assert 'pip install --no-cache-dir playwright==1.64.1 psutil==' in image
    assert 'ENV PATH=/home/user/python-runtime/bin:$PATH' in image


def test_integration_bridge_insert_text_refuses_no_keydown_and_bounds_masks(tmp_path):
    """Exercise bridge directly; production scheduling normally skips §."""
    from perf.runner.browser_hosts import StaticHost
    from perf.runner.benchmark_typing import Bridge
    import socket
    host = StaticHost(Path(__file__).parent/'fixtures')
    async def probe():
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
        process = await asyncio.create_subprocess_exec('node',str(Path(__file__).parents[1]/'runner/typing_session.mjs'),
            str(port),str(tmp_path/'profile'),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL)
        bridge = Bridge(process)
        try:
            await asyncio.wait_for(process.stdout.readline(),30)
            await bridge.request(op='load',url=host.url+'/typing_fair.html',selector='#editor',ready_selector='.status-ok')
            # keyboard input needs a focused editor: the fake fixture focuses itself.
            record = await bridge.request(op='key',char='§',selector='#editor')
            assert record['witness']['after_page_ms'] is None
            assert record['refusal'] == 'no_keydown'
            assert latency_summary([record])['refusals'] == ['no_keydown']
            await bridge.request(op='key',char='a',selector='#editor')
            await bridge.request(op='key',char='b',selector='#editor')
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
                page = browser.contexts[0].pages[0]
                masks = await page.evaluate("() => [...document.querySelectorAll('style')].filter(el => el.textContent === '* { caret-color: transparent !important }').length")
                assert masks == 1, f'witness instrumentation accumulated {masks} global stylesheets'
        finally:
            if process.returncode is None:
                process.terminate()
            await asyncio.wait_for(process.wait(),15)
    try: asyncio.run(probe())
    finally: host.stop()


def test_publication_consumer_refuses_nine_kept_typing_sessions():
    from perf.container.policy import verify_run
    data = {'runner':'benchmark_typing','execution_profile':'dedicated_publish',
            'rendering':{'renderer':'test'},'samples':[{'editor_id':'plate','outcome':'ok','cell_directory':'fake-cell'}],
            'session_kind':'throughput', 'typing_sessions_kept':{'plate':{'throughput':9}}}
    def trials(row): return [{'editor_id':'plate','criterion_id':'TYPING','outcome':'measured'}]
    with pytest.raises(ValueError, match='insufficient_typing_sessions'):
        verify_run(data, trial_reader=trials)
    data['typing_sessions_kept']['plate']['throughput'] = 10
    assert verify_run(data, trial_reader=trials) is data
    data['runner'] = 'benchmark_input'
    data['typing_sessions_kept']['plate']['throughput'] = 0
    assert verify_run(data, trial_reader=trials) is data
