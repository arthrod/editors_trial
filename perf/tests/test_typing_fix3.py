"""B9 fix3: witnessed editor cost, latency floor and shared resource contract."""

import asyncio
import pytest
from perf.runner.benchmark_typing import latency_summary, type_document
from perf.tests.test_typing_marathon import no_frame
from perf.tests.test_typing_fix2 import good
from perf.tests.test_typing_marathon import FakePage, exercise


class TypingSamples:
    async def mark(self, phase):
        pass

    async def sample(self):
        pass


@pytest.mark.parametrize('period', [100, 101])
def test_periodic_editor_cost_is_counted_in_throughput_kind(period):
    async def run(every):
        now = [0.0]

        class Page(FakePage):
            async def type(self, char):
                await super().type(char)
                now[0] += 0.001 + (0.2 if self.sent % period == 0 else 0)

        page = Page()

        async def witness(char):
            start = now[0]
            await page.type(char)
            cost = (now[0] - start) * 1000
            now[0] += 0.05
            return {**good(), 'frame_page_ms': 1230 + cost}

        return await type_document(
            page, TypingSamples(), witness, 'a' * 1000, selector='#editor', witness_every=every, clock=lambda: now[0]
        )

    control = asyncio.run(run(10**9))
    witnessed = asyncio.run(run(100))
    assert witnessed['throughput_chars_s'] == pytest.approx(control['throughput_chars_s'], rel=0.1)
    assert witnessed['throughput_characters'] == 1000


@pytest.mark.parametrize(
    'scheduled,accepted,minimum,publishes',
    [(2, 1, 2, False), (100, 99, 100, False), (199, 100, 100, True), (201, 100, 101, False), (0, 0, 0, False)],
)
def test_latency_absolute_and_relative_floor(scheduled, accepted, minimum, publishes):
    summary = latency_summary([good()] * accepted + [no_frame()] * (scheduled - accepted))
    assert summary['refusal_codes'].get('no_frame', 0) == scheduled - accepted
    assert summary['minimum_accepted'] == minimum
    assert (summary['median_ms'] is not None) is publishes
    if not publishes:
        from perf.runner.browser_run import non_failure_outcomes

        assert any(
            row.get('refusal_code') == 'insufficient_accepted'
            for row in non_failure_outcomes({'key_to_paint': summary})
        )


def test_typing_resources_use_shared_counter_and_level_schema():
    result, series = asyncio.run(exercise('x' * 10000))
    assert result['failure_reason'] is None
    last = series[-1]
    assert last.get('js_heap_used_bytes') == 10 * 1024**2
    assert last['storage_indexeddb_bytes'] == 10 * 1024**2
    assert last['longtask_count'] == 2
    assert last['longtask_sum_ms'] == 400
    assert last['task_duration_ms'] == 2000
    # typing is the only measured phase; the closing mark samples the
    # verification read in its own phase.
    assert {row['phase'] for row in series} == {'typing', 'correctness_read'}


@pytest.mark.parametrize('cost', [200, None, False])
def test_refused_witness_only_contributes_instrumented_wall_time(cost):
    async def run():
        now = [0.0]
        page = FakePage()
        original = page.type

        async def key(char):
            await original(char)
            now[0] += 0.001

        page.type = key

        async def witness(char):
            await key(char)
            now[0] += 1
            return {'witness': no_frame(), 'key_operation_ms': cost}

        return await type_document(
            page, TypingSamples(), witness, 'ab', selector='#editor', session_kind='latency', witness_every=2, clock=lambda: now[0]
        )

    result = asyncio.run(run())
    assert result['throughput_characters'] == 2
    assert result['throughput_excluded_characters'] == 0
    assert result['throughput_chars_s'] is None
    assert result['instrumented']['throughput_chars_s'] == pytest.approx(2 / 1.002)
    assert result['key_to_paint']['n_refused'] == 1


def test_shared_phase_deltas_and_endpoint_levels():
    from types import SimpleNamespace
    from perf.tests.test_typing_marathon import ResourceSampler, FakeCDP

    async def run():
        page = FakePage()
        now = [0.0]
        sampler = ResourceSampler(
            SimpleNamespace(
                clock=lambda: now[0],
                process_snapshot=lambda: [{'pid': 1, 'cpu_ms': 2400 if page.sent else 400, 'rss_bytes': 42}],
            ),
            page,
            FakeCDP(page),
        )
        await sampler.mark('load_start')
        await sampler.mark('load')
        await sampler.mark('typing_start')
        page.sent = 10000
        now[0] = 2
        await sampler.mark('typed_100')
        await sampler.mark('quiescence_start')
        report = sampler.report()
        assert report['phases']['load']['cpu_ms'] == 0
        assert report['phases']['typing']['cpu_ms'] == 2000
        assert report['phases']['typing']['cpu_ms_by_role'] == {'renderer': 2000}
        assert report['phases']['typing']['longtask_count'] == 2
        assert report['phases']['quiescence']['cpu_ms'] == {
            'marker': 'not_available_on_platform',
            'reason': 'single_sample_phase',
        }
        end = await sampler.endpoint()
        assert end['cpu_ms'] == 'not_applicable_endpoint'
        assert end['js_heap_used_bytes'] == 10 * 1024**2
        assert end['js_heap_used_bytes_after_gc'] == 10 * 1024**2
        assert report['peak_rss_bytes'] == 42
        assert report['peak_js_heap_used_bytes'] == 10 * 1024**2

    asyncio.run(run())


def test_integration_floor_refusal_reaches_summary_cell(tmp_path):
    import json, sys
    from functools import partial
    from perf.runner.browser_run import BrowserRun, run_cli, write_json

    old = sys.argv

    def cell():
        directory = __import__('pathlib').Path(sys.argv[sys.argv.index('--out-root') + 1])
        write_json(
            directory / 'attempts' / 'typing.json',
            {
                'criterion_id': 'TYPING',
                'session_kind': 'latency',
                'outcome': 'measured',
                'load_ms': 12,
                'throughput_chars_s': 100,
                'key_to_paint': latency_summary([good(), no_frame()]),
            },
        )
        return 0

    try:
        sys.argv = ['test', '--out-root', str(tmp_path), '--run-id', 'floor', '--session-kind', 'latency', '--editors', 'plate']
        run_cli(
            cell,
            'benchmark_typing',
            {'plate': {}},
            run_factory=partial(
                BrowserRun, snapshot=lambda: {}, accounting_reader=lambda: {'available': False, 'reason': 'test'}
            ),
            facts=(lambda: {}, lambda: {}),
        )
    finally:
        sys.argv = old
    result = json.loads((tmp_path / 'benchmark_typing/floor/summary.json').read_text())
    assert result['samples']
    for row in result['samples']:
        assert row['typing_session_kept'] is False
        assert any(r.get('refusal_code') == 'insufficient_accepted' for r in row['non_failure_outcomes'])


def test_progress_read_failure_preserves_resource_row_for_finalization():
    from types import SimpleNamespace
    from perf.tests.test_typing_marathon import ResourceSampler, FakeCDP

    class ClosingPage(FakePage):
        async def evaluate(self, script, arg=None):
            if 'navigator.storage' in script:
                return await super().evaluate(script, arg)
            raise RuntimeError('page closed during progress read')

    async def run():
        page = ClosingPage()
        sampler = ResourceSampler(SimpleNamespace(clock=lambda: 0, process_snapshot=lambda: []), page, FakeCDP(page))
        with pytest.raises(RuntimeError, match='page closed'):
            await sampler.mark('typing_start')
        assert sampler.series()[0].get('milestone') == 'typing_start'
        assert sampler.report()['phases']['typing']['sample_count'] == 1

    asyncio.run(run())


def test_integration_load_longtask_baseline_is_initialized(tmp_path):
    from pathlib import Path
    from types import SimpleNamespace
    from perf.runner.benchmark_typing import session
    from perf.runner.browser_hosts import StaticHost

    host = StaticHost(Path(__file__).parent / 'fixtures')
    try:
        result, _ = asyncio.run(
            session(
                {'url': host.url + '/typing_fair.html', 'edit_selector': '#editor', 'ready_selector': '.status-ok'},
                'abc',
                SimpleNamespace(budget_s=60, cadence_ms=0, sample_s=5, witness_every=100, quiescence_s=0),
                tmp_path,
            )
        )
    finally:
        host.stop()
    assert result['failure_reason'] is None, result
    load = result['resources']['phases']['load']
    assert isinstance(load['longtask_count'], int), load
    assert load['longtask_count'] >= 0


@pytest.mark.parametrize('refused', [False, True])
def test_instrumented_wall_counts_cadence_once_even_on_refusal(refused):
    async def run():
        now = [0.0]
        page = FakePage()

        async def witness(char):
            await page.type(char)
            now[0] += 1.01
            return {'witness': no_frame(), 'key_operation_ms': 10} if refused else {**good(), 'frame_page_ms': 1240}

        async def sleep(seconds):
            now[0] += seconds

        return await type_document(
            page,
            TypingSamples(),
            witness,
            'ab',
            selector='#editor',
            session_kind='latency',
            witness_every=1,
            cadence_ms=20,
            clock=lambda: now[0],
            sleep=sleep,
        )

    result = asyncio.run(run())
    assert result['throughput_chars_s'] is None
    assert result['instrumented']['throughput_chars_s'] == pytest.approx(2 / 2.06)
    assert result['typing_wall_s'] == pytest.approx(2.06)
    assert result['witness_wall_s'] == pytest.approx(2.02)
    if refused:
        assert result['key_to_paint']['refusal_codes'] == {'no_frame': 2}
