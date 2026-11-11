"""Deterministic unit tests: no browser, filesystem, network or wall clock."""
import asyncio
import importlib.util
from types import SimpleNamespace

SPEC = importlib.util.find_spec('perf.runner.benchmark_typing')

def implementation():
    assert SPEC is not None, 'B9 typing runner has not been implemented'
    from perf.runner.benchmark_typing import type_document
    from perf.tests.test_typing_marathon import ResourceSampler
    return type_document, ResourceSampler

def no_frame():
    from perf.tests.witness_records import publishable_witness_record
    from perf.runner.witness import validate_witness
    record = publishable_witness_record()
    record.update(outcome='no_frame', frame_page_ms=None, frames_after=0,
                  changed_pixels=0, diff_ratio=0, max_diff_ratio=0)
    assert validate_witness(record)['reason'] == 'no_frame'
    return record


class FakePage:
    def __init__(self, drop=False, freeze=False):
        self.text = ''; self.sent = 0; self.drop = drop; self.freeze = freeze
        self.keyboard = self
    async def type(self, char):
        self.sent += 1
        if self.freeze:
            raise asyncio.TimeoutError()
        if not (self.drop and self.sent == 3): self.text += char
    async def press(self, key):
        assert key == 'Enter'
        await self.type('\n')
    async def evaluate(self, script, arg=None):
        if 'navigator.storage' in script:
            return {'longtaskCount': self.sent // 5000,
                    'longtaskSumMs': 200 * (self.sent // 5000),
                    'usage': 10 * 1024**2 if self.sent >= 5000 else 0,
                    'usageDetails': {'indexedDB': 10 * 1024**2 if self.sent >= 5000 else 0}}
        return self.text

class FakeCDP:
    def __init__(self, page): self.page = page
    async def send(self, method, args=None):
        if method == 'Performance.getMetrics':
            return {'metrics': [{'name': k, 'value': v} for k, v in {
                'JSHeapUsedSize': self.page.sent // 1000 * 1024**2,
                'JSHeapTotalSize': 20 * 1024**2, 'TaskDuration': 2 if self.page.sent >= 5000 else 0,
                'ScriptDuration': 2 if self.page.sent >= 5000 else 0,
                'LayoutDuration': 0, 'RecalcStyleDuration': 0}.items()]}
        if method == 'Runtime.getHeapUsage':
            return {'usedSize':self.page.sent // 1000 * 1024**2, 'totalSize':20 * 1024**2}
        return {}
    async def events(self, method): return []


def ResourceSampler(run, page, cdp):
    # Adapt test inputs to B8's injected clock/process-reader interfaces.
    from perf.runner.benchmark_typing import TypingResourceSampler
    def processes():
        return [{**p, 'ppid':0, 'cmdline':'chrome --type=renderer', 'start_time':1}
                for p in run.process_snapshot()]
    return TypingResourceSampler(SimpleNamespace(editor_browser_pid=1, profile_dir=getattr(run,'profile_dir',None)),
        page, cdp, clock=SimpleNamespace(monotonic=run.clock), process_reader=processes,
        platform_name='darwin')

class FakeClock:
    def __init__(self): self.value = 0
    def __call__(self): self.value += .001; return self.value

async def exercise(text, *, drop=False, freeze=False):
    type_document, Sampler = implementation()
    page = FakePage(drop, freeze); clock = FakeClock()
    def processes():
        return [{'pid': 1, 'role': 'renderer', 'rss_bytes': 42,
                 'cpu_ms': 2000 if page.sent >= 5000 else 0,
                 'read_bytes': 0, 'write_bytes': 0}]
    run = SimpleNamespace(process_snapshot=processes, profile_size=lambda: 0,
                          network={'received_bytes': 0, 'sent_bytes': None}, clock=clock)
    sampler = Sampler(run, page, FakeCDP(page))
    async def witness(char):
        await page.type(char)
        return no_frame()
    result = await type_document(page, sampler, witness, text, selector='#editor',
        cadence_ms=0, witness_every=100000, sample_s=1, clock=clock)
    return result, sampler.series()

def test_dropped_keystroke_refused():
    result, _ = asyncio.run(exercise('abcdef', drop=True))
    assert result['failure_reason'] == 'text_mismatch'
    assert result['first_divergence_offset'] == 2
    assert result['throughput_chars_s'] is None

def test_growth_cpu_storage_and_long_tasks():
    result, series = asyncio.run(exercise('x' * 10000))
    assert result['failure_reason'] is None
    by_phase = {row['milestone']: row for row in series}
    assert by_phase['typed_50']['js_heap_used_bytes'] == 5 * 1024**2
    assert by_phase['typed_100']['js_heap_used_bytes'] == 10 * 1024**2
    assert by_phase['typed_50']['task_duration_ms'] == 2000
    assert by_phase['typed_50']['processes'][0]['cpu_ms'] == 2000
    assert by_phase['typed_50']['storage_usage_bytes'] == 10 * 1024**2
    assert by_phase['typed_100']['longtask_count'] == 2
    assert by_phase['typed_100']['longtask_sum_ms'] == 400
    assert all(row['backlog_chars'] == 0 for row in series)

def test_frozen_page_has_progress_and_budget_refusal():
    result, _ = asyncio.run(exercise('hello', freeze=True))
    assert result['failure_reason'] == 'budget_exceeded'
    assert result['words_typed'] == 0

def test_paragraphs_use_enter():
    result, _ = asyncio.run(exercise('Heading\n\n1. Argument\nQuote'))
    assert result['failure_reason'] is None

def test_normalization_and_divergence():
    implementation()
    from perf.runner.benchmark_typing import normalize, divergence, latency_summary
    assert normalize('a\r\n\n b\u00a0c') == 'a b c'
    assert divergence('abc','ab') == 2
    assert divergence('abc','axc') == 1
    assert latency_summary([])['median_ms'] is None
    assert latency_summary([no_frame()])['refusals'] == ['no_frame']

def test_sampler_cpu_percent_and_nulls():
    _, Sampler = implementation()
    async def run():
        page = FakePage(); now = [0]; cpu = [0]
        def processes(): return [{'pid':1,'role':'renderer','cpu_ms':cpu[0], 'rss_bytes':None}]
        resources = SimpleNamespace(clock=lambda: now[0], process_snapshot=processes,
                                    profile_size=lambda:None, network={'received_bytes':None})
        sampler = Sampler(resources,page,FakeCDP(page))
        await sampler.mark('load'); now[0] = 4; cpu[0] = 2000
        await sampler.mark('typed_50')
        assert sampler.series()[-1]['cpu_percent_by_role']['renderer'] == 50
        assert sampler.series()[-1]['rss_bytes'] == 'not_available_on_platform'
        import pytest
        with pytest.raises(KeyError): sampler.totals('missing')
        assert sampler.totals('typing')['peak_js_heap_used_bytes'] == 0
        assert sampler.totals('typing')['cpu_ms'] == {'marker':'not_available_on_platform','reason':'single_sample_phase'}
    asyncio.run(run())

def test_sampled_keys_cadence_and_crash():
    type_document, Sampler = implementation()
    async def run():
        page = FakePage(); clock = FakeClock(); sleeps = []
        def processes(): return []
        resources = SimpleNamespace(clock=clock, process_snapshot=processes, profile_size=lambda:0, network={})
        sampler = Sampler(resources,page,FakeCDP(page))
        async def sleep(seconds): sleeps.append(seconds)
        async def witness(char):
            await page.type(char)
            return no_frame()
        result = await type_document(page,sampler,witness,'abc',selector='#e',session_kind='latency',cadence_ms=20,
                                     witness_every=1,clock=clock,sleep=sleep)
        assert sleeps == [.02,.02,.02]
        assert result['key_to_paint']['refusals'] == ['no_frame'] * 3
        async def crash(char): raise RuntimeError('out of memory')
        result = await type_document(page,sampler,crash,'a',selector='#e',session_kind='latency',witness_every=1,clock=clock)
        assert result['failure_reason'] == 'out_of_memory'
    asyncio.run(run())

def test_publication_one_editor_per_typing_job():
    from perf.container.policy import publication_jobs
    jobs = [(name,args) for name,args in publication_jobs(['plate','folio'],1,2,'shared_guarded') if name == 'benchmark_typing']
    assert len(jobs) == 8
    assert all(len(args[args.index('--editors')+1:]) == 1 for _,args in jobs)

def test_latency_retains_subframe_flags_and_accepts_half_distribution():
    from perf.tests.test_typing_fix2 import good
    from perf.runner.benchmark_typing import latency_summary
    record = good()
    summary = latency_summary([record])
    assert summary['median_ms'] == 4.5, summary
    assert summary['sub_frame'] is True
    bad = good(document_scoped=False)
    assert latency_summary([record,bad])['median_ms'] is None
    assert latency_summary([record]*100 + [bad]*100)['median_ms'] == 4.5
    assert latency_summary([record,bad,bad])['median_ms'] is None
    negative = {**record, 'after_page_ms':2000, 'marker_page_ms':2000}
    assert latency_summary([negative])['refusals'] == ['frame_before_arm']

class FakePipe:
    def __init__(self, response=b''): self.response = response; self.written = b''
    def write(self, value): self.written += value
    async def drain(self): pass
    async def readline(self): return self.response

def test_bridge_protocol_errors_and_success():
    from perf.runner.benchmark_typing import Bridge
    async def run():
        import pytest
        incoming = FakePipe(b'{"result":{"ok":true}}\n'); outgoing = FakePipe()
        bridge = Bridge(SimpleNamespace(stdin=outgoing,stdout=incoming))
        assert await bridge.request(op='key',char='x') == {'ok':True}
        assert b'"char": "x"' in outgoing.written
        incoming.response = b'{"error":"frozen"}\n'
        with pytest.raises(RuntimeError, match='frozen'): await bridge.request(op='load')
        incoming.response = b''
        with pytest.raises(RuntimeError, match='exited'): await bridge.request(op='load')
    asyncio.run(run())
