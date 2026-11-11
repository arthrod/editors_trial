"""#143: wall-time throughput cannot lose deferred work to witness bookkeeping."""

import asyncio
import inspect
import pytest
from perf.runner.benchmark_typing import type_document
from perf.tests.test_typing_marathon import no_frame
from perf.tests.test_typing_marathon import FakePage
from perf.tests.test_typing_fix3 import TypingSamples
from perf.tests.test_typing_fix2 import good


def test_deferred_work_is_counted_without_key_witnesses():
    async def run():
        now = [0.0]

        class Page(FakePage):
            async def type(self, char):
                await super().type(char)
                now[0] += 0.001 + (0.7 if self.sent % 100 == 0 else 0)

        page = Page()
        calls = []

        async def witness(char):
            calls.append(char)
            await page.type(char)
            now[0] += 0.5
            return {**good(), 'frame_page_ms': 1231}

        options = (
            {'session_kind': 'throughput'} if 'session_kind' in inspect.signature(type_document).parameters else {}
        )
        result = await type_document(
            page, TypingSamples(), witness, 'a' * 1000, selector='#editor', clock=lambda: now[0], **options
        )
        assert result['throughput_chars_s'] == pytest.approx(125)
        assert calls == []
        assert result['typing_wall_s'] == pytest.approx(8)
        assert result['witnesses'] == []

    asyncio.run(run())


@pytest.mark.parametrize('refused', [False, True])
def test_latency_never_publishes_throughput_even_when_witness_refuses(refused):
    async def run():
        now = [0.0]
        page = FakePage()

        async def witness(char):
            await page.type(char)
            now[0] += 1
            return no_frame() if refused else good()

        options = {'session_kind': 'latency'} if 'session_kind' in inspect.signature(type_document).parameters else {}
        result = await type_document(
            page, TypingSamples(), witness, 'ab', selector='#editor', witness_every=1, clock=lambda: now[0], **options
        )
        assert result.get('instrumented', {}).get('throughput_chars_s') == 1
        assert result.get('throughput_chars_s') is None
        assert result['key_to_paint']['n_refused'] == (2 if refused else 0)
        if refused:
            assert result['key_to_paint']['refusal_codes'] == {'no_frame': 2}

    asyncio.run(run())


def test_each_seed_schedules_both_session_kinds():
    from perf.container.policy import publication_jobs

    jobs = [
        args
        for name, args in publication_jobs(['plate', 'folio'], 1, 2, 'shared_guarded')
        if name == 'benchmark_typing'
    ]
    assert len(jobs) == 8
    assert {(a[a.index('--seed') + 1], a[-1], a[a.index('--session-kind') + 1]) for a in jobs} == {
        (seed, editor, kind)
        for seed in ('1', '2')
        for editor in ('plate', 'folio')
        for kind in ('throughput', 'latency')
    }


@pytest.mark.parametrize('kind', ['throughput', 'latency'])
@pytest.mark.parametrize('kept', [9, 10])
def test_integration_kept_gate_uses_only_selected_kind(tmp_path, kind, kept):
    import sys, json
    from pathlib import Path
    from functools import partial
    from perf.runner.browser_run import BrowserRun, CELL, run_cli, write_json

    old = sys.argv

    def cell():
        ok = CELL.get()['repetition'] < kept
        write_json(
            Path(sys.argv[sys.argv.index('--out-root') + 1]) / 'attempts/typing.json',
            {
                'criterion_id': 'TYPING',
                'session_kind': kind,
                'outcome': 'measured',
                'correctness_oracle': 'dom_document_text',
                'throughput_chars_s': 100 if kind == 'throughput' and ok else None,
                'load_ms': 12 if kind == 'latency' else None,
                'key_to_paint': {'median_ms': 16 if kind == 'latency' and ok else None},
                'instrumented': {'throughput_chars_s': 999},
            },
        )
        return 0

    try:
        sys.argv = [
            'test',
            '--out-root',
            str(tmp_path),
            '--run-id',
            'kinds',
            '--editors',
            'plate',
            '--execution-profile',
            'dedicated_publish',
            '--host-class',
            'dedicated',
            '--session-kind',
            kind,
        ]
        run_cli(
            cell,
            'benchmark_typing',
            {'plate': {}},
            run_factory=partial(
                BrowserRun,
                snapshot=lambda: {},
                accounting_reader=lambda: {'available': False, 'reason': 'synthetic unavailable'},
            ),
            facts=(lambda: {}, lambda: {}),
        )
    finally:
        sys.argv = old
    result = json.loads((tmp_path / 'benchmark_typing/kinds/summary.json').read_text())
    assert result['typing_sessions_kept'] == {'plate': {kind: kept}}
    assert (result.get('failure_reason') == 'insufficient_typing_sessions') == (kept < 10)


def test_smoke_plan_schedules_both_kinds_integration():
    import subprocess, sys

    result = subprocess.run(
        [sys.executable, '-m', 'perf.container.run', '--smoke', '--dry-run'], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if 'perf.container.smoke benchmark_typing ' in line]
    assert len(lines) == 2
    assert any('--session-kind throughput' in line for line in lines)
    assert any('--session-kind latency' in line for line in lines)


@pytest.mark.parametrize('kind', ['throughput', 'latency'])
def test_integration_session_publication_fields(tmp_path, kind):
    from pathlib import Path
    from types import SimpleNamespace
    from perf.runner.benchmark_typing import session
    from perf.runner.browser_hosts import StaticHost

    host = StaticHost(Path(__file__).parent / 'fixtures')
    try:
        result, rows = asyncio.run(
            session(
                {'url': host.url + '/typing_fair.html', 'edit_selector': '#editor', 'ready_selector': '.status-ok'},
                'a' * 100,
                SimpleNamespace(
                    session_kind=kind, budget_s=60, cadence_ms=0, sample_s=5, witness_every=100, quiescence_s=0
                ),
                tmp_path,
            )
        )
    finally:
        host.stop()
    assert result['failure_reason'] is None, result
    assert result['instrumented']['label'] == 'instrumented'
    resources = result if kind == 'throughput' else result['instrumented']
    assert {'load', 'typing', 'quiescence'} <= resources['resources']['phases'].keys()
    assert {'after_load', 'end'} == resources['resource_endpoints'].keys()
    assert rows and resources['milestones']['typed_100']['characters_typed'] == 100
    if kind == 'throughput':
        assert result['published_fields'] == ['throughput_chars_s', 'resources', 'resource_endpoints']
        assert result['throughput_chars_s'] == 100 / result['typing_wall_s']
        assert result['witnesses'] == []
        assert 'key_to_paint' not in result
        assert 'load_ms' not in result
    else:
        assert result['published_fields'] == ['load_ms', 'key_to_paint']
        assert result['load_ms'] is not None
        assert result['key_to_paint']['n_scheduled'] == 1
        assert result['throughput_chars_s'] is None
        assert result['instrumented']['throughput_chars_s'] == 100 / result['typing_wall_s']
        assert all(field not in result for field in ('resources', 'resource_endpoints', 'milestones'))


def test_timeout_retains_partial_progress():
    async def run():
        now = [0.0]

        class Page(FakePage):
            async def type(self, char):
                now[0] += 1
                if self.sent == 3:
                    raise asyncio.TimeoutError()
                await super().type(char)

        page = Page()

        async def witness(char):
            raise AssertionError('throughput requested a witness')

        result = await type_document(
            page, TypingSamples(), witness, 'abcdef', selector='#editor', clock=lambda: now[0]
        )
        assert result['failure_reason'] == 'budget_exceeded'
        assert result['characters_typed'] == 3
        assert result['typing_wall_s'] == 4
        assert result['throughput_chars_s'] is None

    asyncio.run(run())


def test_integration_throughput_bridge_stops_screencast_before_typing(tmp_path):
    """Observe real CDP start/stop calls; the wrapper forwards every command unchanged."""
    import json, socket
    from pathlib import Path
    from perf.runner.benchmark_typing import Bridge
    from perf.runner.browser_hosts import StaticHost
    from playwright.async_api import async_playwright

    source = Path(__file__).parents[1] / 'runner/typing_session.mjs'
    script = source.read_text().replace("'./witness.mjs'", json.dumps((source.parent / 'witness.mjs').as_uri()))
    # The observed copy runs from tmp_path; every sibling import needs an
    # absolute URI or node exits ERR_MODULE_NOT_FOUND at launch.
    script = script.replace("'./chrome_trace.mjs'", json.dumps((source.parent / 'chrome_trace.mjs').as_uri()))
    script = script.replace("'./edit_surface.mjs'", json.dumps((source.parent / 'edit_surface.mjs').as_uri()))
    # lax layer (owner 2026-11-11): the session takes its load timeouts from
    # the shared policy module; the observed copy needs its absolute URI too.
    script = script.replace("'./load_timeout.mjs'", json.dumps((source.parent / 'load_timeout.mjs').as_uri()))
    script = script.replace(
        'let clock, interval;',
        """
const send = cdp.send.bind(cdp);
cdp.send = async (method, params) => {
  const result = await send(method, params);
  if (method === 'Page.startScreencast' || method === 'Page.stopScreencast')
    console.error('TRACE ' + method);
  return result;
};
let clock, interval;""",
    )
    bridge_script = tmp_path / 'observed.mjs'
    bridge_script.write_text(script)
    host = StaticHost(Path(__file__).parent / 'fixtures')

    async def run():
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        process = await asyncio.create_subprocess_exec(
            'node',
            str(bridge_script),
            str(port),
            str(tmp_path / 'profile'),
            'throughput',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        bridge = Bridge(process)
        try:
            await asyncio.wait_for(process.stdout.readline(), 30)
            await bridge.request(
                op='load', url=host.url + '/typing_fair.html', selector='#editor', ready_selector='.status-ok'
            )
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
                page = browser.contexts[0].pages[0]
                await page.keyboard.type('abc')
                assert await page.locator('#editor').inner_text() == 'abc'
            with pytest.raises(RuntimeError, match='key witnesses forbidden'):
                await bridge.request(op='key', char='d', selector='#editor')
            await bridge.request(
                op='load', url=host.url + '/typing_fair.html', selector='#editor', ready_selector='.status-ok'
            )
        finally:
            process.terminate()
            await asyncio.wait_for(process.wait(), 15)
        traces = [line for line in (await process.stderr.read()).decode().splitlines() if line.startswith('TRACE ')]
        # Both load operations stop their recorder before replying; typing between
        # them never starts one. A missing stop or an unsolicited start changes this.
        assert traces == ['TRACE Page.startScreencast', 'TRACE Page.stopScreencast'] * 2

    try:
        asyncio.run(run())
    finally:
        host.stop()


def test_integration_budget_after_typing_refuses_rate_and_keeps_progress(tmp_path):
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
                SimpleNamespace(
                    session_kind='throughput',
                    budget_s=15,
                    cadence_ms=0,
                    sample_s=5,
                    witness_every=100,
                    quiescence_s=60,
                ),
                tmp_path,
            )
        )
    finally:
        host.stop()
    assert result['failure_reason'] == 'budget_exceeded'
    assert result['characters_typed'] == 3
    assert result['progress']['characters_typed'] == 3
    assert result['progress']['elapsed_s'] >= 15
    assert result['throughput_chars_s'] is None


def test_final_typing_sample_follows_deferred_editor_work():
    async def run():
        page = FakePage()
        now = [0.0]
        completed = [False]
        captured = []
        original = page.evaluate

        async def evaluate(script, arg=None):
            value = await original(script, arg)
            if 'setTimeout' in script:
                completed[0] = True  # an explicit task turn drains already queued work
                now[0] += 0.7
            return value

        page.evaluate = evaluate

        class Samples(TypingSamples):
            async def mark(self, phase):
                captured.append((phase, completed[0]))

        async def witness(char):
            raise AssertionError('throughput requested a witness')

        result = await type_document(page, Samples(), witness, 'abc', selector='#editor', clock=lambda: now[0])
        assert result['failure_reason'] is None
        # The typing phase closes before the correctness read's own phase.
        assert captured[-2:] == [('typed_100', True), ('correctness_read', True)]
        assert result['typing_wall_s'] == 0.7
        assert result['throughput_chars_s'] == pytest.approx(3 / 0.7)

    asyncio.run(run())
