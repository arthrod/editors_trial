"""Integration: real B9 key witnesses must survive B1c and the latency reader."""
import asyncio
import json
import socket
from pathlib import Path

from perf.runner.benchmark_typing import Bridge, latency_summary
from perf.runner.browser_hosts import StaticHost
from perf.runner.witness import validate_witness


def test_live_typing_witness_schema(tmp_path):
    host = StaticHost(Path(__file__).parent / 'fixtures')

    async def probe():
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        process = await asyncio.create_subprocess_exec(
            'node', str(Path(__file__).parents[1] / 'runner/typing_session.mjs'),
            str(port), str(tmp_path / 'profile'), 'latency',
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        bridge = Bridge(process)
        try:
            assert json.loads(await asyncio.wait_for(process.stdout.readline(), 30))['ready']
            load = await bridge.request(op='load', url=host.url + '/typing_fair.html',
                                        selector='#editor', ready_selector='.status-ok')
            load_verdict = validate_witness(load['witness'])
            assert load_verdict['ok'], load_verdict
            for char in ('a', 'b'):
                response = await bridge.request(op='key', char=char, selector='#editor')
                record = response.get('witness', response)
                verdict = validate_witness(record)
                print(json.dumps({'load': load, 'key': response, 'verdict': verdict}))
                assert verdict['ok'], verdict
                summary = latency_summary([response])
                assert summary['n_accepted'] == 1, summary
                assert summary['median_ms'] == record['frame_page_ms'] - record['after_page_ms']
                assert record['clock_check']['frame_interval_ms'] > 0
        finally:
            if process.returncode is None:
                process.terminate()
            await asyncio.wait_for(process.communicate(), 15)

    try:
        asyncio.run(probe())
    finally:
        host.stop()


def test_session_metadata_preserves_interval_and_no_keydown_refusal():
    from perf.tests.test_witness import WitnessValidatorTests
    witness = WitnessValidatorTests.good_record()
    assert validate_witness(witness)['ok']
    envelope = {'witness': witness, 'frame_interval_ms': 100.0}
    summary = latency_summary([envelope])
    assert summary['n_accepted'] == 1, summary
    assert summary['sub_frame'] is True  # captured latency is 63.599 ms
    envelope['refusal'] = 'no_keydown'
    assert latency_summary([envelope])['refusals'] == ['no_keydown']


def test_typing_accounting_does_not_modify_raw_witness():
    from types import SimpleNamespace
    from perf.tests.test_witness import WitnessValidatorTests
    from perf.tests.test_typing_marathon import FakePage, FakeCDP, ResourceSampler
    from perf.runner.benchmark_typing import type_document

    async def check():
        page = FakePage()
        sampler = ResourceSampler(SimpleNamespace(clock=lambda: 0,
            process_snapshot=lambda: [], profile_size=lambda: 0, network={}), page, FakeCDP(page))
        emitted = []
        async def witness(char):
            await page.type(char)
            record = WitnessValidatorTests.good_record()
            emitted.append(record)
            return record
        result = await type_document(page, sampler, witness, 'abc', selector='#editor',
                                     session_kind='latency', witness_every=1, clock=lambda: 0)
        assert result['key_to_paint']['n_accepted'] == 3, result['key_to_paint']
        assert all(validate_witness(record)['ok'] for record in emitted)
        assert all('bridge_elapsed_ms' in row for row in result['witnesses'])
    asyncio.run(check())
