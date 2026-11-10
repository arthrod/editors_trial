#!/usr/bin/env python3
"""#143: one empty-document typing marathon per fresh BrowserRun cell.

Run using uv ... python -I perf/runner/benchmark_typing.py. No paste or model
insertion. Cadence is the declared pause after each key. Throughput and latency
use separate sessions; no instrumentation time is subtracted.
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
from perf.runner.resources import AsyncResourceSampler, NOT_AVAILABLE, COUNTER_DELTA_FIELDS, phase_totals
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
            response = record
            record = response.get('witness', response)
            if response.get('refusal') == 'no_keydown':
                refusals.append('no_keydown'); continue
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
            interval = response.get('frame_interval_ms', record['clock_check']['frame_interval_ms'])
            accepted.append({'ms':value, 'sub_frame': interval is None or value < interval or value < 16})
        except (TypeError, ValueError, KeyError, AttributeError):
            refusals.append('invalid_record')
    values = sorted(r['ms'] for r in accepted)
    minimum = max(math.ceil(len(records) * .5), min(100, len(records)))
    enough = bool(values) and len(values) >= minimum
    return {'median_ms': values[len(values)//2] if enough else None,
            'p90_ms': values[max(0, math.ceil(len(values)*.9)-1)] if enough else None,
            'n_scheduled':len(records), 'n_accepted':len(values), 'n_refused':len(refusals),
            'outcome':'measured' if enough else 'refused',
            'refusal_code':None if enough else 'insufficient_accepted',
            'minimum_accepted':minimum, 'summary_refusal':None if enough else 'insufficient_accepted',
            'refusal_codes':{code:refusals.count(code) for code in sorted(set(refusals))},
            'samples': accepted, 'refusals': refusals,
            'sub_frame': any(r['sub_frame'] for r in accepted)}


def witness_eligible(char):
    # Playwright's US keyboard layout delivers these visible keys via keydown.
    # Spaces/newlines do not require ink; other Unicode uses insertText.
    return len(char) == 1 and '!' <= char <= '~'

async def type_document(page, sampler, witness, text, *, selector, cadence_ms=0, session_kind="throughput",
                        witness_every=100, sample_s=5, clock=time.monotonic,
                        sleep=asyncio.sleep):
    if session_kind not in ("throughput", "latency"):
        raise ValueError("invalid session kind")
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
            sampled = session_kind == "latency" and index >= next_witness and witness_eligible(char)
            if sampled:
                response = await witness(char)
                record = dict(response) if 'witness' in response else {'witness': response}
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
            if index in marks and index < len(text): await sampler.mark(marks[index])
            elif clock() >= next_sample:
                await sampler.sample(); next_sample = clock() + sample_s
        # Yield one browser task turn before the final check. In particular, a
        # zero-delay timer queued by the last input must finish inside this wall.
        await page.evaluate('() => new Promise(resolve => setTimeout(resolve, 0))')
        actual = normalize(await page.evaluate('(s) => document.querySelector(s)?.innerText ?? ""', selector))
        # Close the typing phase after the final DOM round-trip, so deferred
        # work on the last key is present in its resource counters as well.
        await sampler.mark('typed_100')
        expected = normalize(text)
        if actual != expected:
            result.update(failure_reason='text_mismatch', first_divergence_offset=divergence(expected, actual))
    except (asyncio.TimeoutError, asyncio.CancelledError):
        result['failure_reason'] = 'budget_exceeded'
    except Exception as exc:
        result['failure_reason'] = 'out_of_memory' if 'out of memory' in str(exc).lower() else 'crash'
        result['error'] = str(exc)
    elapsed = clock() - start
    rate = sent/elapsed if not result['failure_reason'] and elapsed else None
    result.update(session_kind=session_kind, characters_typed=sent,
                  words_typed=len(text[:sent].split()), typing_wall_s=elapsed,
                  throughput_chars_s=rate if session_kind == 'throughput' else None,
                  throughput_basis='accepted_characters_over_unadjusted_typing_wall',
                  throughput_characters=sent, throughput_excluded_characters=0,
                  typing_unwitnessed_s=typing_unwitnessed, unwitnessed_characters=unwitnessed,
                  witness_wall_s=witness_wall, witnesses=records,
                  instrumented={})
    if session_kind == 'latency':
        result['key_to_paint'] = latency_summary(records)
        result['instrumented']['throughput_chars_s'] = rate
        result['instrumented']['label'] = 'instrumented'
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

# Same observer state consumed by B8's PAGE_SNAPSHOT_JS.
INIT_SCRIPT = """() => {
 window.__resourceLongTasks = {count:0, sum:0, available:true};
 try {
   if (!PerformanceObserver.supportedEntryTypes.includes('longtask')) throw Error('unsupported');
   new PerformanceObserver(list => { for (const e of list.getEntries()) {
     window.__resourceLongTasks.count++; window.__resourceLongTasks.sum += e.duration;
   }}).observe({type:'longtask', buffered:true});
 } catch { window.__resourceLongTasks = {available:false}; }
}"""


class TypingResourceSampler(AsyncResourceSampler):
    """Only typing progress is B9-specific; every resource comes from B8."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.characters_typed = 0
        self.typed_text = ''
        self.selector = '[contenteditable="true"]'
        self.milestone = None
        self.profile_baseline = None

    async def mark(self, milestone):
        self.milestone = milestone
        phase = ('typing' if milestone == 'typing_start' or milestone.startswith('typed_')
                 else 'load' if milestone.startswith('load')
                 else 'quiescence' if milestone in ('quiescence_start', 'quiescence', 'end')
                 else milestone)
        try:
            return await super().mark(phase)
        finally:
            self.milestone = None

    async def sample(self, record=True):
        row = await super().sample(record=record)
        row.update(milestone=self.milestone, characters_typed=self.characters_typed)
        present = await self._async_page.evaluate(
            '(s) => document.querySelector(s)?.innerText ?? ""', self.selector)
        typed = normalize(self.typed_text)
        row.update(milestone=self.milestone, characters_typed=self.characters_typed,
            characters_present=len(normalize(present)), characters_typed_normalized=len(typed),
            backlog_chars=len(typed)-len(normalize(present)))
        absolute = row['profile_directory_bytes']
        if self.milestone == 'load': self.profile_baseline = absolute
        row['profile_absolute_bytes'] = absolute
        row['profile_bytes'] = (absolute-self.profile_baseline
            if isinstance(absolute, int) and isinstance(self.profile_baseline, int) else NOT_AVAILABLE)
        return row

    def report(self):
        rows = self.series()
        phases = {phase:self.totals(phase) for phase in dict.fromkeys(r['phase'] for r in rows)}
        for phase, totals in phases.items():
            phase_rows = [r for r in rows if r['phase'] == phase]
            totals['cpu_ms_by_role'] = {
                role:phase_totals([{**r, 'processes':[p for p in r['processes'] if p['role'] == role]}
                                  for r in phase_rows])['cpu_ms']
                for role in sorted({p['role'] for r in phase_rows for p in r['processes']})}
        peaks = phase_totals(rows) if rows else {}
        return {'phases':phases, 'peak_rss_bytes':peaks.get('peak_rss_bytes'),
                'peak_js_heap_used_bytes':peaks.get('peak_js_heap_used_bytes'),
                'last':rows[-1] if rows else None}

    async def endpoint(self):
        natural = await self.sample()
        gc = await self.sample_after_gc()
        return {**natural, **dict.fromkeys(COUNTER_DELTA_FIELDS, 'not_applicable_endpoint'),
                'js_heap_used_bytes_after_gc':gc['js_heap_used_bytes'] if gc else NOT_AVAILABLE}

async def session(target, text, args, directory):
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
    kind = getattr(args, 'session_kind', 'throughput')
    profile = directory / 'browser-profile'; profile.mkdir(parents=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
    stderr = (directory/'browser.log').open('wb')
    process = await asyncio.create_subprocess_exec('node', str(Path(__file__).with_name('typing_session.mjs')),
        str(port), str(profile), kind, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=stderr)
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
                await page.evaluate(INIT_SCRIPT)
                cdp = await context.new_cdp_session(page)
                browser_cdp = await browser.new_browser_cdp_session()
                processes = (await browser_cdp.send('SystemInfo.getProcessInfo'))['processInfo']
                browser_pid = next(p['id'] for p in processes if p['type'] == 'browser')
                resources = SimpleNamespace(editor_browser_pid=browser_pid, profile_dir=profile)
                sampler = TypingResourceSampler(resources, page, cdp)
                sampler.selector = target['edit_selector']
                await sampler.install()
                await sampler.mark('load_start')
                load = await bridge.request(op='load', url=target['url'], selector=target['edit_selector'],
                    ready_selector=target.get('ready_selector'), ready_js=target.get('ready_js'))
                verdict = validate_witness(load['witness'])
                result.update(load_witness=load, load_ms=load['witness']['frame_page_ms'] if verdict['ok'] else None,
                              load_refusal=verdict['reason'])
                await sampler.mark('load')
                result['resource_endpoints'] = {'after_load':await sampler.endpoint()}
                surface = page.locator(target['edit_selector']).first
                if not await surface.evaluate('(el) => el.isContentEditable'):
                    raise SessionRefusal('no_correctness_adapter')
                if normalize(await surface.inner_text()):
                    raise SessionRefusal('document_not_empty')
                await surface.click()
                async def witness(char): return await bridge.request(op='key', char=char, selector=target['edit_selector'])
                result.update(await type_document(page, sampler, witness, text, selector=target['edit_selector'],
                    cadence_ms=args.cadence_ms, session_kind=kind, witness_every=args.witness_every, sample_s=args.sample_s))
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
                    await sampler.mark('quiescence_start')
                    await asyncio.sleep(args.quiescence_s)
                    await sampler.mark('quiescence')
                    await sampler.mark('end')
                    result['resource_endpoints']['end'] = await sampler.endpoint()
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
    result['session_kind'] = kind
    if result['failure_reason']:
        result['throughput_chars_s'] = None
    if sampler and result['failure_reason'] == 'budget_exceeded':
        result['characters_typed'] = sampler.characters_typed
        result['words_typed'] = len(sampler.typed_text.split())
    result['progress'] = {'characters_typed':result['characters_typed'],
                          'elapsed_s':result['session_wall_s']}
    if sampler:
        result['resources'] = sampler.report()
        result['milestones'] = {r['milestone']:r for r in sampler.series() if r.get('milestone')}
    result.setdefault('instrumented', {})['label'] = 'instrumented'
    diagnostic_fields = ('resources', 'resource_endpoints', 'milestones') if kind == 'latency' else ('load_ms', 'load_refusal')
    for field in diagnostic_fields:
        if field in result: result['instrumented'][field] = result.pop(field)
    result['published_fields'] = (['load_ms', 'key_to_paint'] if kind == 'latency'
                                  else ['throughput_chars_s', 'resources', 'resource_endpoints'])
    return result, sampler.series() if sampler else []

def main_cell(argv=None, *, start_host=_start_server, stop_host=_stop_server):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--editors', nargs='+', default=list(BROWSER_TARGETS))
    ap.add_argument('--out-root', type=Path, required=True)
    ap.add_argument('--session-kind', choices=('throughput', 'latency'), default='throughput')
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
            'schema':'perf.typing/2', 'session_kind':args.session_kind, 'isolation':'fresh_process', 'values_per_session':1, 'criterion_id':'TYPING', 'editor_id':editor,
            'run_id':run.run_id, 'seed':run.seed, 'repetition':(CELL.get() or {}).get('repetition')}
        trial.update(result, outcome='refused' if result.get('failure_reason') else 'measured',
            publishable=False, publication_block_reason='inspect all witness and resource refusals; publication requires complete session set',
            fixture_sha256=hashlib.sha256(BRIEF.read_bytes()).hexdigest(),
            typed_text_sha256=hashlib.sha256(text.encode()).hexdigest(), fixture_words=len(text.split()),
            cadence_ms=args.cadence_ms, session_kind=args.session_kind, witness_every=args.witness_every, sample_s=args.sample_s,
            budget_s=args.budget_s, quiescence_s=args.quiescence_s,
            execution_profile=run.execution_profile, host_class=run.host_class,
            host_provenance=run.hosts.get(editor), time_series='resources.json',
            resource_series_label='instrumented' if args.session_kind == 'latency' else 'measurement')
        if trial.get('failure_reason'): trial['throughput_chars_s'] = None
        write_json(directory/'resources.json',series)
        write_json(directory/'attempts'/'typing.json',trial)
        print(json.dumps({'editor':editor,'failure_reason':trial.get('failure_reason'),'words_typed':trial.get('words_typed')}))
    return 0

_main = main_cell  # B6's common smoke dispatcher entrypoint.

def main():
    return run_cli(main_cell,'benchmark_typing',BROWSER_TARGETS)

if __name__ == '__main__': raise SystemExit(main())
