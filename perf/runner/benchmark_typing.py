#!/usr/bin/env python3
"""#143: one empty-document typing marathon per fresh BrowserRun cell.

Run using uv ... python -I perf/runner/benchmark_typing.py. No paste or model
insertion. Cadence is a minimum inter-key pause, including witness overhead.
The B9 record schema is additive: resources are bytes/ms, never samples_ms.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import math
import socket
import sys
import time
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from perf.runner.browser_run import ACTIVE, CELL, run_cli, write_json, fixture_path
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS, _start_server, _stop_server
from perf.runner.browser_hosts import select_fixture
from perf.runner.typing_resources import ResourceSampler, INIT_SCRIPT
from perf.runner.witness import validate_witness

BRIEF = REPO / 'perf/fixtures/briefs/sg-brief-13000w.txt'

def normalize(text):
    # DOM engines use different block separators. Preserve all words/punctuation,
    # including order and duplicates, while normalizing block whitespace only.
    return ' '.join(text.split())

def divergence(expected, actual):
    return next((i for i, (a,b) in enumerate(zip(expected, actual)) if a != b), min(len(expected), len(actual)))

def latency_summary(records):
    # A distribution requires at least half of the scheduled witnesses.
    accepted = []; refusals = []
    for record in records:
        try:
            if record.get('after_page_ms') is None and record.get('outcome') == 'witnessed':
                refusals.append('no_keydown'); continue
            if record.get('refusal') == 'no_keydown':
                refusals.append('no_keydown'); continue
            verdict = validate_witness(record)
            if not verdict['ok']:
                refusals.append(verdict['reason']); continue
            value = record['frame_page_ms'] - record['after_page_ms']
            if not math.isfinite(value) or value < 0:
                refusals.append('negative_latency'); continue
            interval = record.get('frame_interval_ms')
            accepted.append({'ms':value, 'sub_frame': interval is None or value < interval or value < 16})
        except (TypeError, ValueError, KeyError, AttributeError):
            refusals.append('invalid_record')
    values = sorted(r['ms'] for r in accepted)
    minimum = max(1, math.ceil(len(records) * .5))
    enough = len(values) >= minimum
    return {'median_ms': values[len(values)//2] if enough else None,
            'p90_ms': values[max(0, math.ceil(len(values)*.9)-1)] if enough else None,
            'n_scheduled':len(records), 'n_accepted':len(values), 'n_refused':len(refusals),
            'minimum_accepted':minimum, 'summary_refusal':None if enough else 'insufficient_accepted',
            'refusal_codes':{code:refusals.count(code) for code in sorted(set(refusals))},
            'samples': accepted, 'refusals': refusals,
            'sub_frame': any(r['sub_frame'] for r in accepted)}


def witness_eligible(char):
    # Playwright's US keyboard layout delivers these visible keys via keydown.
    # Spaces/newlines do not require ink; other Unicode uses insertText.
    return len(char) == 1 and '!' <= char <= '~'

async def type_document(page, sampler, witness, text, *, selector, cadence_ms=0,
                        witness_every=100, sample_s=5, clock=time.monotonic,
                        sleep=asyncio.sleep):
    sampler.selector = selector
    start = clock(); next_sample = start + sample_s
    next_witness = witness_every; witness_wall = 0; typing_unwitnessed = 0; unwitnessed = 0
    sampler.typed_text = ''
    records = []; sent = 0; marks = {math.ceil(len(text)*p/100):f'typed_{p}' for p in (25,50,75,100)}
    result = {'failure_reason':None, 'first_divergence_offset':None}
    try:
        await sampler.mark('typing_start')
        for index, char in enumerate(text, 1):
            key_start = clock()
            sampled = index >= next_witness and witness_eligible(char)
            if sampled:
                record = await witness(char)
                record['bridge_elapsed_ms'] = (clock() - key_start) * 1000
                records.append(record)
                witness_wall += record['bridge_elapsed_ms'] / 1000
                next_witness = index + witness_every
            else:
                if char == '\n': await page.keyboard.press('Enter')
                else: await page.keyboard.type(char)
                unwitnessed += 1
            if cadence_ms: await sleep(cadence_ms/1000)
            if not sampled: typing_unwitnessed += clock() - key_start
            sent = index; sampler.characters_typed = sent
            sampler.typed_text = text[:sent]
            if index in marks: await sampler.mark(marks[index])
            elif clock() >= next_sample:
                await sampler.sample(); next_sample = clock() + sample_s
        actual = normalize(await page.evaluate('(s) => document.querySelector(s)?.innerText ?? ""', selector))
        expected = normalize(text)
        if actual != expected:
            result.update(failure_reason='text_mismatch', first_divergence_offset=divergence(expected, actual))
    except (asyncio.TimeoutError, asyncio.CancelledError):
        result['failure_reason'] = 'budget_exceeded'
    except Exception as exc:
        result['failure_reason'] = 'out_of_memory' if 'out of memory' in str(exc).lower() else 'crash'
        result['error'] = str(exc)
    elapsed = clock() - start
    result.update(characters_typed=sent, words_typed=len(text[:sent].split()), typing_wall_s=elapsed,
                  throughput_chars_s=unwitnessed/typing_unwitnessed if not result['failure_reason'] and typing_unwitnessed else None,
                  throughput_basis='unwitnessed_keys_including_declared_cadence',
                  throughput_wall_chars_s=sent/elapsed if not result['failure_reason'] and elapsed else None,
                  throughput_wall_basis='all_characters_over_typing_wall_including_instrumentation',
                  typing_unwitnessed_s=typing_unwitnessed, unwitnessed_characters=unwitnessed,
                  witness_wall_s=witness_wall,
                  key_to_paint=latency_summary(records), witnesses=records)
    return result

class SessionRefusal(RuntimeError):
    pass


class Bridge:
    def __init__(self, process): self.process = process
    async def request(self, **command):
        self.process.stdin.write((json.dumps(command)+'\n').encode())
        await self.process.stdin.drain()
        line = await self.process.stdout.readline()
        if not line: raise RuntimeError('browser witness bridge exited')
        response = json.loads(line)
        if 'error' in response: raise RuntimeError(response['error'])
        return response['result']

class ProcessResources:
    def __init__(self, browser_cdp, profile):
        self.browser_cdp = browser_cdp; self.profile = profile
        self.network = {'received_bytes':0, 'sent_bytes':None,
                        'sent_reason':'CDP exposes no complete request wire-byte counter'}
        self.clock = time.monotonic
    async def process_snapshot(self):
        import psutil
        rows = []
        for item in (await self.browser_cdp.send('SystemInfo.getProcessInfo'))['processInfo']:
            row = {'pid':item['id'], 'role':item['type'], 'cpu_ms':item['cpuTime']*1000,
                   'rss_bytes':None, 'read_bytes':None, 'write_bytes':None}
            try:
                proc = psutil.Process(item['id']); row['rss_bytes'] = proc.memory_info().rss
                if hasattr(proc, 'io_counters'):
                    io = proc.io_counters(); row.update(read_bytes=io.read_bytes, write_bytes=io.write_bytes)
                else: row['io_unavailable_reason'] = 'per-process disk counters unavailable on this OS'
            except (psutil.Error, OSError) as exc: row['unavailable_reason'] = type(exc).__name__
            rows.append(row)
        return rows
    def profile_size(self):
        try: return sum(p.stat().st_size for p in self.profile.rglob('*') if p.is_file())
        except OSError: return None

async def session(target, text, args, directory):
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
    profile = directory / 'browser-profile'; profile.mkdir(parents=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
    stderr = (directory/'browser.log').open('wb')
    process = await asyncio.create_subprocess_exec('node', str(Path(__file__).with_name('typing_session.mjs')),
        str(port), str(profile), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=stderr)
    bridge = Bridge(process); sampler = None; result = {'failure_reason':None, 'characters_typed':0, 'words_typed':0}
    started = time.monotonic()
    try:
        async with asyncio.timeout(args.budget_s):
            line = await process.stdout.readline()
            if not line: raise RuntimeError('browser launch failed; see browser.log')
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
                context = browser.contexts[0]; page = context.pages[0]
                await context.add_init_script('('+INIT_SCRIPT+')()')
                cdp = await context.new_cdp_session(page); await cdp.send('Performance.enable'); await cdp.send('Network.enable')
                resources = ProcessResources(await browser.new_browser_cdp_session(), profile)
                cdp.on('Network.loadingFinished', lambda event: resources.network.__setitem__('received_bytes', resources.network['received_bytes']+event['encodedDataLength']))
                sampler = ResourceSampler(resources, page, cdp); sampler.selector = target['edit_selector']
                load = await bridge.request(op='load', url=target['url'], selector=target['edit_selector'],
                    ready_selector=target.get('ready_selector'), ready_js=target.get('ready_js'))
                verdict = validate_witness(load['witness'])
                result.update(load_witness=load, load_ms=load['witness']['frame_page_ms'] if verdict['ok'] else None,
                              load_refusal=verdict['reason'])
                await sampler.mark('load')
                surface = page.locator(target['edit_selector']).first
                if not await surface.evaluate('(el) => el.isContentEditable'):
                    raise SessionRefusal('no_correctness_adapter')
                if normalize(await surface.inner_text()):
                    raise SessionRefusal('document_not_empty')
                await surface.click()
                async def witness(char): return await bridge.request(op='key', char=char, selector=target['edit_selector'])
                result.update(await type_document(page, sampler, witness, text, selector=target['edit_selector'],
                    cadence_ms=args.cadence_ms, witness_every=args.witness_every, sample_s=args.sample_s))
                if not result['failure_reason']:
                    # No unverified generic save button: require a host-declared path.
                    save = target.get('typing_save_selector')
                    result['save_ms'] = None; result['save_reason'] = 'host_has_no_declared_save_path'
                    if save:
                        t0 = time.monotonic()
                        try:
                            async with page.expect_download() as download:
                                await page.locator(save).click()
                            await (await download.value).save_as(directory/'export.docx')
                        except PlaywrightTimeoutError as exc:
                            result['save_reason'] = 'save_timeout'
                            raise SessionRefusal('save_timeout') from exc
                        result.update(save_ms=(time.monotonic()-t0)*1000, save_reason=None)
                    await sampler.mark('save')
                    await asyncio.sleep(args.quiescence_s)
                    await sampler.mark('quiescence')
                    await sampler.mark('end')
    except SessionRefusal as exc: result['failure_reason'] = str(exc)
    except (TimeoutError, asyncio.CancelledError): result['failure_reason'] = 'budget_exceeded'
    except Exception as exc:
        result.update(failure_reason='out_of_memory' if 'out of memory' in str(exc).lower() else 'crash', error=str(exc))
    finally:
        if process.returncode is None:
            try: await asyncio.wait_for(bridge.request(op='close'), 3)
            except (Exception, asyncio.CancelledError): pass
        if process.returncode is None:
            process.terminate()
            try: await asyncio.wait_for(process.wait(), 5)
            except TimeoutError: process.kill(); await process.wait()
        stderr.close()
    result['session_wall_s'] = time.monotonic()-started
    if sampler:
        result['resources'] = sampler.totals()
        result['milestones'] = {r['phase']:r for r in sampler.series() if r['phase'] != 'periodic'}
    return result, sampler.series() if sampler else []

def main_cell(argv=None, *, start_host=_start_server, stop_host=_stop_server):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--editors', nargs='+', default=list(BROWSER_TARGETS))
    ap.add_argument('--out-root', type=Path, required=True)
    ap.add_argument('--cadence-ms', type=float, default=0)
    ap.add_argument('--witness-every', type=int, default=100)
    ap.add_argument('--sample-s', type=float, default=5)
    ap.add_argument('--budget-s', type=float, default=3600)
    ap.add_argument('--quiescence-s', type=float, default=5)
    ap.add_argument('--words', type=int, default=None, help='smoke-only prefix; full fixture by default')
    args = ap.parse_args(argv)
    if args.cadence_ms < 0 or min(args.witness_every,args.sample_s,args.budget_s) <= 0 or args.quiescence_s < 0:
        ap.error('cadence/quiescence must be nonnegative; sample interval, witness interval and budget positive')
    if args.words is not None and args.words <= 0: ap.error('--words must be positive')
    text = BRIEF.read_text().rstrip()
    if args.words:
        import re
        tokens = list(re.finditer(r'\S+', text)); text = text[:tokens[min(args.words,len(tokens))-1].end()]
    from perf.fixtures.generate import docx_zip_bytes
    # Zero-text DOCX, not select-all/delete after loading a populated document.
    empty = fixture_path('typing-empty', docx_zip_bytes(b'\n'), args.out_root/'empty.docx')
    for editor in args.editors:
        target = dict(BROWSER_TARGETS[editor]);
        if editor == 'superdoc': target['typing_save_selector'] = '#export-docx'
        directory = args.out_root; directory.mkdir(parents=True,exist_ok=True)
        select_fixture(target, empty); server = None
        try:
            server = start_host(editor,target)
            result, series = asyncio.run(session(target,text,args,directory))
        except Exception as exc: result, series = {'failure_reason':'host_start_failed','error':str(exc)}, []
        finally:
            if server: stop_host(server)
        run = ACTIVE.get()
        trial = {
            'schema':'perf.typing/1', 'isolation':'fresh_process', 'values_per_session':1, 'criterion_id':'TYPING', 'editor_id':editor,
            'run_id':run.run_id, 'seed':run.seed, 'repetition':(CELL.get() or {}).get('repetition')}
        trial.update(result, outcome='refused' if result.get('failure_reason') else 'measured',
            publishable=False, publication_block_reason='B9 provisional resource adapter; inspect all witness and resource refusals',
            fixture_sha256=hashlib.sha256(BRIEF.read_bytes()).hexdigest(),
            typed_text_sha256=hashlib.sha256(text.encode()).hexdigest(), fixture_words=len(text.split()),
            cadence_ms=args.cadence_ms, witness_every=args.witness_every, sample_s=args.sample_s,
            budget_s=args.budget_s, quiescence_s=args.quiescence_s,
            execution_profile=run.execution_profile, host_class=run.host_class,
            host_provenance=run.hosts.get(editor), time_series='resources.json')
        if trial.get('failure_reason'): trial['throughput_chars_s'] = None
        write_json(directory/'resources.json',series)
        write_json(directory/'attempts'/'typing.json',trial)
        print(json.dumps({'editor':editor,'failure_reason':trial.get('failure_reason'),'words_typed':trial.get('words_typed')}))
    return 0

_main = main_cell  # B6's common smoke dispatcher entrypoint.

def main():
    return run_cli(main_cell,'benchmark_typing',BROWSER_TARGETS)

if __name__ == '__main__': raise SystemExit(main())
