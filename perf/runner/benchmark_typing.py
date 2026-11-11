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
import difflib
import hashlib
import io
import json
import math
import re
import socket
import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from perf.runner.browser_run import ACTIVE, CELL, run_cli, write_json, fixture_path
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS, _start_server, _stop_server
from perf.runner.browser_hosts import select_fixture
from perf.runner.docx_plaintext import docx_body_text, docx_body_text_and_absorbed
from perf.runner.resources import AsyncResourceSampler, NOT_AVAILABLE, COUNTER_DELTA_FIELDS, phase_totals
from perf.runner.witness import validate_witness
from perf.runner.benchmark_document import (
    content_gate_record,
    content_meta_for_workload,
    gate_length_check_for,
)

BRIEF = REPO / 'perf/fixtures/briefs/sg-brief-13000w.txt'

# Auto-numbering triggers a correct word processor may absorb into a real list
# marker when they lead a paragraph: "1.", "a.", "(i)", "iv)", "A)".
_LIST_MARKER = re.compile(
    r'^(?:\((?:\d{1,6}|[A-Za-z]|[ivxlcdmIVXLCDM]{1,7})\)'
    r'|(?:\d{1,6}|[A-Za-z]|[ivxlcdmIVXLCDM]{2,7})[.)])\s*')

# Auto-corrected quotation marks: a correct word processor turns the typed
# straight quote into a typographic one (docen, genoffice). Like the marker
# class this folds a glyph variant, never a character: a missing or extra
# quote still fails the compare.
_QUOTE_FOLD = str.maketrans({
    '\u2018': "'", '\u2019': "'", '\u201a': "'", '\u201b': "'", '`': "'",
    '\u201c': '"', '\u201d': '"', '\u201e': '"', '\u201f': '"',
    '\u00ab': '"', '\u00bb': '"',
})

def normalize_marked(text):
    """Quote-fold and whitespace collapse for the flat body compare.

    List markers stay in the text here — a vanished marker is excused only
  only when list-item evidence pairs at that line (marker_only and
    prefix-marker passes below). Returns (text, 0)."""
    lines = [line.strip() for line in text.translate(_QUOTE_FOLD).split('\n')]
    return ' '.join(' '.join(lines).split()), 0


def prefix_marker_rest(line):
    """Leading list markers with following text: (marker tokens, rest line)."""
    line = line.strip().translate(_QUOTE_FOLD)
    markers = []
    while (match := _LIST_MARKER.match(line)):
        rest = line[match.end():]
        if not rest.strip():
            break
        markers.append(line[:match.end()].rstrip())
        line = rest.strip()
    return markers, line


def line_align_norm(line):
    """Line text for diff alignment — body without a typed prefix marker."""
    if marker_only_of_line(line) is not None:
        return ''
    markers, rest = prefix_marker_rest(line)
    return normalize_marked(rest if markers else line)[0]

def marker_only_of_line(line):
    """The marker string when this line's entire text is markers, else None.

    "v." yields "v."; "1. a." yields its final marker "a."; a line with any
    other text yields None."""
    line = line.strip()
    while (match := _LIST_MARKER.match(line)):
        rest = line[match.end():]
        if not rest.strip():
            return line[:match.end()].rstrip()
        line = rest
    return None


def marker_only_strings(text):
    """The marker strings of paragraphs whose entire text is one marker
    ("v.", "12.", and "1. a." contributes its final marker). The flat
    normalized text cannot show these lines, so the compare gates them
    separately: a dropped one is content loss; an absorbed empty list item
    is not."""
    return [marker for line in text.split('\n')
            if (marker := marker_only_of_line(line)) is not None]


def marker_only_positions(text):
    """``{line_index: marker}`` for every marker-only paragraph — the
    positions absorbed-list evidence must answer for one by one."""
    return {index: marker for index, line in enumerate(text.split('\n'))
            if (marker := marker_only_of_line(line)) is not None}


def absorbed_positions(read):
    """``{line_index: marker}`` the editor reports as absorbed list items.

    Entries are ``{'index': i, 'marker': label-or-None}``; a bare integer is
    an index with an unknown label, and any other shape has no position at
    all — evidence without a position can never excuse a missing marker.
    """
    positions = {}
    for entry in (read.get('absorbed_markers') or []):
        if isinstance(entry, dict):
            index, marker = entry.get('index'), entry.get('marker')
        elif isinstance(entry, (int, float)) and not isinstance(entry, bool):
            index, marker = entry, None
        else:
            index, marker = -1, str(entry)
        if isinstance(index, (int, float)) and not isinstance(index, bool) and index >= 0:
            positions[int(index)] = marker
    return positions

def stripped_marker_strings(text):
    """Every paragraph-leading marker normalisation removes — the strings
    tolerance may excuse, never a bare count."""
    stripped = []
    for line in text.split('\n'):
        line = line.strip()
        while (match := _LIST_MARKER.match(line)):
            rest = line[match.end():]
            if not rest.strip():
                break
            stripped.append(line[:match.end()].rstrip())
            line = rest
    return stripped

def normalize(text):
    return normalize_marked(text)[0]

# Page context: list markers an editor absorbed out of the text and still
# exposes as element attributes (folio's data-list-marker). Only items with
# no text of their own count — those are the marker-only paragraphs. Each
# entry carries the item's line index inside the read text: evidence is
# positional, never a count.
ABSORBED_MARKERS_JS = """(s) => {
  const els = Array.from(document.querySelectorAll(s));
  if (!els.length) return [];
  const linesOf = (node) => {
    const t = String(node.innerText ?? '');
    if (t) return t.split('\\n').length;
    const style = getComputedStyle(node);
    return (style.display === 'none' || style.visibility === 'hidden') ? 0 : 1;
  };
  const indexWithin = (root, node) => {
    let count = 0;
    for (let cur = node; cur && cur !== root; cur = cur.parentElement) {
      for (let sib = cur.previousElementSibling; sib; sib = sib.previousElementSibling)
        count += linesOf(sib);
    }
    return count;
  };
  const absorbed = [];
  let base = 0;
  for (const el of els) {
    for (const node of el.querySelectorAll('[data-list-marker]')) {
      if (String(node.innerText || node.textContent || '').trim()) continue;
      absorbed.push({index: base + indexWithin(el, node),
        marker: String(node.getAttribute('data-list-marker') || '').trim()});
    }
    base += String(el.innerText ?? '').split('\\n').length;
  }
  return absorbed;
}"""

async def read_document_text(page, *, selector, model_js=None):
    """The whole document's text: the declared model adapter, else the
    editable surface's innerText. The surface may match many elements —
    docxodus wires one contenteditable per block — so every match's
    innerText joins with a paragraph separator."""
    if model_js is None:
        return await page.evaluate(
            '(s) => Array.from(document.querySelectorAll(s))'
            '.map((el) => String(el.innerText ?? el.textContent ?? "")).join("\\n")', selector)
    payload = await page.evaluate(model_js)
    if isinstance(payload, dict):
        docx = payload.get('docx_bytes')
        if isinstance(docx, list):
            return docx_body_text(io.BytesIO(bytes(docx)), paragraph_separator='\n')
        payload = payload.get('text')
    return payload if isinstance(payload, str) else None

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
                        sleep=asyncio.sleep, present_selector=None, model_js=None, expected_text=None,
                        read_document=None, flag_verifier=None, correctness_oracle=None,
                        present_text=True):
    if session_kind not in ("throughput", "latency"):
        raise ValueError("invalid session kind")
    # `selector` reads the document text; `present_selector` reads what the
    # user can SEE (the painted region), which may repaint asynchronously
    # (folio's visible pages lag the editable ProseMirror by ~200 ms).
    # `present_text` says that region's innerText is meaningful at all — a
    # model or flag surface only burns the sample evaluate for a null.
    sampler.selector = present_selector or selector
    sampler.present_text = present_text
    oracle = (correctness_oracle
              or ('model_document_text' if (read_document is not None or model_js)
                  else 'dom_document_text'))
    if read_document is None:
        async def read_document():
            return {'text': await read_document_text(page, selector=selector, model_js=model_js),
                    'absorbed_markers': (await page.evaluate(ABSORBED_MARKERS_JS, selector)
                                         if model_js is None else [])}
    start = clock(); next_sample = start + sample_s
    next_witness = witness_every; witness_wall = 0; typing_unwitnessed = 0; unwitnessed = 0
    sampler.typed_text = ''
    records = []; sent = 0; marks = {math.ceil(len(text)*p/100):f'typed_{p}' for p in (25,50,75,100)}
    result = {'failure_reason':None, 'first_divergence_offset':None, 'tolerated_list_markers':0}
    if expected_text is not None:
        result['expected_text_override'] = True
    elapsed = None
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
        # The wall ends when the last key's already-queued work has drained;
        # the correctness read below (a whole-document export on model
        # surfaces) is measurement, not typing — and never bills its work to
        # the typing resource phase.
        elapsed = clock() - start
        await sampler.mark('typed_100')
        if flag_verifier is not None:
            verdict = await flag_verifier()
            flag = verdict.get('flag')
            trusted = verdict.get('trusted_keys') or 0
            # No unverified timings are published: a flag surface exposes no
            # document text, so a session on it can never prove what was
            # typed. Record the flag and key count as evidence — and only
            # evidence — whatever they say.
            result.update(correctness_oracle='editor_modified_flag', text_correctness=None,
                          verified=['modified_flag', 'trusted_keys'],
                          modified_flag=flag, trusted_keys=trusted,
                          expected_min_keys=verdict.get('min_keys'),
                          failure_reason='document_text_not_readable',
                          refusal_code='unverified')
            if not flag or flag.get('modified') is not True:
                result['edit_refusal'] = ('modified_flag_unreadable' if not flag
                                          else 'modified_flag_unchanged')
            elif trusted < result['expected_min_keys']:
                result['edit_refusal'] = 'trusted_keys_below_min'
        else:
            read = None
            try:
                read = await read_document()
                # Worker-driven renderers commit asynchronously and in bursts:
                # superdoc's second page mounted ~1s after the last key, so a
                # snapshot read truncated the document mid-paragraph (real-run
                # RED: divergence at normalized 1582, two marker-only
                # paragraphs missing). Judge the settled document — the text
                # must stay unchanged across a continuous window, not just one
                # poll that caught a commit stall.
                deadline = time.monotonic() + 15
                stable_since = time.monotonic()
                while read is not None and time.monotonic() < deadline:
                    await asyncio.sleep(0.1)
                    nxt = await read_document()
                    if nxt != read:
                        read = nxt
                        stable_since = time.monotonic()
                    elif time.monotonic() - stable_since >= 1.5:
                        break
            except Exception as exc:
                if re.search(r'crash|closed|detached', str(exc), re.I):
                    raise
                transport = classify_bridge_error(exc)
                if transport:
                    result.update(failure_reason=transport[0], refusal_code=transport[1], error=str(exc))
                else:
                    result.update(failure_reason='no_correctness_adapter', refusal_code='unverified',
                                  error=str(exc))
            if read is not None:
                actual_text = read.get('text') if isinstance(read, dict) else read
                if actual_text is None:
                    result.update(failure_reason='no_correctness_adapter', refusal_code='unverified')
                else:
                    expected_source = text if expected_text is None else expected_text
                    expected_marker_at = marker_only_positions(expected_source)
                    actual_lines = actual_text.split('\n')
                    actual_marker_at = marker_only_positions(actual_text)
                    absorbed_at = absorbed_positions(read if isinstance(read, dict) else {})
                    # The two texts are on different line bases — a DOM read
                    # may emit extra blank lines per paragraph, a model read a
                    # header line — so an expected paragraph index cannot be
                    # looked up in the actual text directly. Align the
                    # normalized line sequences instead; the slot a marker
                    # paragraph occupies is its aligned line widened to the
                    # blank/marker run around it (or its replace block). A
                    # marker is answered only by a trace inside its own slot:
                    # its marker-only line, or the empty absorbed item AT
                    # that position — never by an item elsewhere, and one
                    # item never answers for two paragraphs.
                    expected_lines = expected_source.split('\n')
                    expected_norm = [line_align_norm(line) for line in expected_lines]
                    actual_norm = [line_align_norm(line) for line in actual_lines]
                    opcodes = difflib.SequenceMatcher(
                        None, expected_norm, actual_norm, autojunk=False).get_opcodes()

                    def slot_for(index):
                        for tag, a1, a2, b1, b2 in opcodes:
                            if a1 <= index < a2:
                                if tag != 'equal':
                                    return range(b1, b2)
                                j = b1 + (index - a1)
                                return range(j, j + 1)
                        return range(len(actual_norm), len(actual_norm))

                    used_text, used_absorbed = set(), set()
                    missing = []
                    tolerated = []
                    tolerated_by_line = []
                    for i, exp_line in enumerate(expected_lines):
                        markers, rest = prefix_marker_rest(exp_line)
                        if not markers:
                            continue
                        slot = slot_for(i)
                        paired = False
                        for j in slot:
                            act_markers, act_rest = prefix_marker_rest(actual_lines[j])
                            if normalize_marked(act_rest)[0] != normalize_marked(rest)[0]:
                                continue
                            if act_markers:
                                paired = True
                                break
                            if j in absorbed_at and j not in used_absorbed:
                                used_absorbed.add(j)
                                for marker in markers:
                                    tolerated.append(marker)
                                    tolerated_by_line.append({'index': i, 'marker': marker})
                                paired = True
                                break
                        if not paired:
                            for marker in markers:
                                missing.append({'index': i, 'marker': marker})
                    marker_only_tolerated = set()
                    for i, marker in sorted(expected_marker_at.items()):
                        slot = slot_for(i)
                        hit = next((j for j in slot
                                    if j in actual_marker_at and j not in used_text), None)
                        if hit is not None:
                            used_text.add(hit)
                            if actual_marker_at[hit] != marker:
                                tolerated.append(marker)
                            continue
                        hit = next((j for j in slot
                                    if j in absorbed_at and j not in used_absorbed), None)
                        if hit is not None:
                            used_absorbed.add(hit)
                            tolerated.append(marker)
                            marker_only_tolerated.add(i)
                            continue
                        missing.append({'index': i, 'marker': marker})
                    surplus = ([{'index': j, 'marker': actual_marker_at[j]}
                                for j in sorted(actual_marker_at) if j not in used_text]
                               + [{'index': j, 'marker': absorbed_at[j]}
                                  for j in sorted(absorbed_at) if j not in used_absorbed])
                    tolerated_idx = {t['index'] for t in tolerated_by_line}
                    compare_lines = []
                    for idx, line in enumerate(expected_lines):
                        if idx in marker_only_tolerated:
                            compare_lines.append('')
                        else:
                            markers, rest = prefix_marker_rest(line)
                            if markers and idx in tolerated_idx:
                                compare_lines.append(rest)
                            else:
                                compare_lines.append(line)
                    actual, _ = normalize_marked(actual_text)
                    expected, _ = normalize_marked('\n'.join(compare_lines))
                    if actual == expected and not missing:
                        surplus = [s for s in surplus if s.get('marker') is not None]
                    marker_gap = bool(surplus) or bool(missing)
                    result.update(tolerated_list_markers=tolerated_by_line,
                                  tolerated_marker_strings=sorted(tolerated),
                                  tolerated_quote_autocorrect_chars=sum(
                                      1 for ch in actual_text if ord(ch) in _QUOTE_FOLD),
                                  correctness_oracle=oracle,
                                  marker_only={'expected': marker_only_strings(expected_source),
                                               'in_text': marker_only_strings(actual_text),
                                               'absorbed': [{'index': i, 'marker': absorbed_at[i]}
                                                            for i in sorted(absorbed_at)],
                                               'missing': missing,
                                               'surplus': surplus})
                    if actual != expected or marker_gap:
                        result.update(failure_reason='text_mismatch', refusal_code='correctness_failure',
                                      first_divergence_offset=(divergence(expected, actual)
                                                               if actual != expected else None))
        # The verification work (document read, flag poll, export) gets its
        # own resource phase after the typing wall closes.
        await sampler.mark('correctness_read')
    except (asyncio.TimeoutError, asyncio.CancelledError):
        result['failure_reason'] = 'budget_exceeded'
        result['refusal_code'] = 'editor_timeout'
    except Exception as exc:
        result['failure_reason'] = 'out_of_memory' if 'out of memory' in str(exc).lower() else 'crash'
        result['error'] = str(exc)
    elapsed = clock() - start if elapsed is None else elapsed
    rate = sent/elapsed if not result['failure_reason'] and elapsed else None
    outcome = ('measured' if not result['failure_reason']
               else 'unverified' if result.get('refusal_code') == 'unverified' else 'refused')
    result.update(session_kind=session_kind, characters_typed=sent, outcome=outcome,
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
    if not result.get('failure_reason'):
        result['refusal_code'] = None
    elif 'refusal_code' not in result:
        result['refusal_code'] = 'crash'
    return result


class SessionRefusal(RuntimeError):
    def __init__(self, reason, refusal_code=None):
        super().__init__(reason)
        self.refusal_code = refusal_code


_BRIDGE_LINE_CHUNK = 1 << 16


async def read_bridge_line(stream):
    """Read one JSON line; default StreamReader.readline() refuses >64 KiB."""
    if not hasattr(stream, 'read'):
        return await stream.readline()
    chunks = []
    while True:
        chunk = await stream.read(_BRIDGE_LINE_CHUNK)
        if not chunk:
            return b'' if not chunks else b''.join(chunks)
        chunks.append(chunk)
        if chunk.endswith(b'\n'):
            return b''.join(chunks)


_BRIDGE_TRANSPORT_MARKERS = (
    'chunk is longer than limit',
    'browser witness bridge exited',
    'witness bridge',
)


def classify_bridge_error(exc):
    """Transport failures are harness errors, never a missing correctness adapter."""
    message = str(exc)
    if any(marker in message for marker in _BRIDGE_TRANSPORT_MARKERS):
        return 'witness_bridge_transport', 'harness_error'
    return None


class Bridge:
    def __init__(self, process): self.process = process
    async def request(self, **command):
        self.process.stdin.write((json.dumps(command)+'\n').encode())
        await self.process.stdin.drain()
        line = await read_bridge_line(self.process.stdout)
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
        # DOM surfaces read the painted region's innerText per sample. Model
        # and flag surfaces have no readable DOM text — the read is wasted.
        self.present_text = True

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
        typed = normalize(self.typed_text)
        if self.present_text:
            present = await self._async_page.evaluate(
                '(s) => document.querySelector(s)?.innerText ?? ""', self.selector)
            row.update(characters_present=len(normalize(present)),
                       characters_typed_normalized=len(typed),
                       backlog_chars=len(typed)-len(normalize(present)))
        else:
            row.update(characters_present=None, characters_typed_normalized=len(typed),
                       backlog_chars=None)
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
    bridge = Bridge(process); sampler = None; result = {'failure_reason':None, 'characters_typed':0, 'words_typed':0, 'tolerated_list_markers':0}
    started = time.monotonic()
    try:
        async with asyncio.timeout(args.budget_s):
            line = await read_bridge_line(process.stdout)
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
                # The shared edit_selector must match the OTHER lanes' surfaces;
                # B9 loads a zero-text document, so typing may need different
                # elements: `typing_edit_selector` is the element whose text is
                # the document (or the focus target on model/flag surfaces),
                # `typing_present_selector` the visible region whose innerText
                # is paint progress, `typing_click_selector` the element that
                # takes the focus click (e.g. a lazy ProseMirror mounts on the
                # first page click), `typing_load_click_selector` the lazy-mount
                # click that must happen inside the load measurement (absent
                # for an editor whose editable exists without one),
                # `typing_load_present_selector` the region painted at load
                # when it differs (docxodus edits in a view that replaces the
                # loaded viewer), `typing_wait_selector` the element waited on
                # before edit prep (the mode button when the editable mounts
                # later), `typing_usable_js` the first-usable expression,
                # `typing_model_js` a model adapter for the correctness read,
                # `typing_ready_js` overrides a ready_js that requires
                # non-empty text — impossible here.
                edit_sel = target.get('typing_edit_selector', target['edit_selector'])
                present_sel = target.get('typing_present_selector', edit_sel)
                click_sel = target.get('typing_click_selector', edit_sel)
                load_click_sel = target.get('typing_load_click_selector')
                load_present_sel = target.get('typing_load_present_selector', present_sel)
                load_wait_sel = (
                    target.get('typing_load_wait_selector')
                    or target.get('typing_wait_selector')
                    or target.get('ready_selector')
                )
                model_js = target.get('typing_model_js')
                ready_js = target['typing_ready_js'] if 'typing_ready_js' in target else target.get('ready_js')
                usable_selector = target.get('typing_usable_selector')
                if usable_selector:
                    # CSP-blocked hosts (genoffice) cannot pass eval-based ready gates.
                    ready_js = None
                usable_js = target.get('typing_usable_js') or ready_js
                editor_id = target.get('editor_id', '')
                sampler = TypingResourceSampler(resources, page, cdp)
                sampler.selector = present_sel
                await sampler.install()
                await sampler.mark('load_start')
                ready_selector = (
                    target.get('typing_ready_selector')
                    or target.get('typing_load_wait_selector')
                    or target.get('ready_selector')
                )
                load = await bridge.request(op='load', url=target['url'], selector=edit_sel,
                    present_selector=None if load_present_sel == edit_sel else load_present_sel,
                    load_click_selector=load_click_sel,
                    load_wait_selector=load_wait_sel,
                    wait_selector=target.get('typing_wait_selector'),
                    usable_js=usable_js, usable_selector=usable_selector, editor_id=editor_id,
                    ready_selector=ready_selector, ready_js=ready_js)
                if load.get('usable_ms') is None:
                    refusal = load.get('refusal') or 'paint_witness_unavailable'
                    code = ('unverified' if refusal == 'no_correctness_adapter'
                            else 'paint_witness_unavailable')
                    raise SessionRefusal(refusal, refusal_code=code)
                if (load.get('frame_interval_ms') is None
                        or not isinstance(load.get('frame_interval_ms'), (int, float))):
                    raise SessionRefusal('frame_interval_unavailable', refusal_code='witness_unavailable')
                verdict = validate_witness(load['witness'])
                result.update(load_witness=load, load_ms=load['witness']['frame_page_ms'] if verdict['ok'] else None,
                              load_refusal=verdict['reason'])
                await sampler.mark('load')
                result['resource_endpoints'] = {'after_load':await sampler.endpoint()}
                # The shared adapter owns edit-mode entry and caret placement;
                # a zero-text document has no text line, so the caret click
                # goes to the declared surface (empty_document).
                await bridge.request(op='enter_edit_mode', editor_id=editor_id,
                                     text_line_timeout_ms=0)
                placed = await bridge.request(op='place_caret', editor_id=editor_id,
                    selector=click_sel, empty_document=True, focus_timeout_ms=15000)
                surface_kind = (placed or {}).get('surface') or 'dom'
                flag_verifier = None; read_document = None; oracle_name = 'dom_document_text'
                if model_js is not None:
                    oracle_name = 'model_document_text'
                    async def read_document():
                        payload = await page.evaluate(model_js)
                        if isinstance(payload, dict) and isinstance(payload.get('docx_bytes'), list):
                            body, absorbed = docx_body_text_and_absorbed(io.BytesIO(bytes(payload['docx_bytes'])))
                            return {'text': body, 'absorbed_markers': absorbed}
                        value = payload.get('text') if isinstance(payload, dict) else payload
                        return {'text': value if isinstance(value, str) else None, 'absorbed_markers': []}
                elif surface_kind == 'flag':
                    await bridge.request(op='arm_trusted_keys')
                    min_keys = len(text) - text.count('\n')
                    async def flag_verifier():
                        # The dirty marker is the app's window title, emitted on
                        # an egui frame — the title may lag the last key by a
                        # frame or two, so poll briefly before judging it.
                        flag = None
                        # Software-rasterised WordCraft can take seconds to
                        # emit the dirty title after a long burst.
                        deadline = time.monotonic() + 15
                        while True:
                            flag = await bridge.request(op='modified_flag', editor_id=editor_id)
                            if not flag or flag.get('modified') is True or time.monotonic() >= deadline:
                                break
                            await asyncio.sleep(0.1)
                        keys = await bridge.request(op='trusted_key_count')
                        return {'flag': flag,
                                'trusted_keys': (keys or {}).get('keys'),
                                'min_keys': min_keys}
                elif surface_kind == 'model':
                    oracle_name = 'model_document_text'
                # The bridge's readers join every element matching the surface —
                # docxodus mounts one contenteditable per block, genoffice and
                # folio one region per page. A querySelector first-match would
                # truncate the document at its first paragraph.
                if read_document is None and surface_kind in ('dom', 'model'):
                    async def read_document():
                        return await bridge.request(op='read_document', editor_id=editor_id,
                                                    selector=edit_sel)
                if read_document is not None:
                    baseline = await read_document()
                    if baseline.get('text') is None:
                        raise SessionRefusal('no_correctness_adapter', refusal_code='unverified')
                    if normalize(baseline['text']):
                        raise SessionRefusal('document_not_empty')
                    # Refuse before typing when nothing can take the input: a
                    # read-only document surface and focus that never reached
                    # an editor (editable=False AND unfocused) mean the keys
                    # would go to the page, not a document.
                    if surface_kind == 'dom' and baseline.get('editable') is False:
                        if not placed.get('focused'):
                            raise SessionRefusal('no_correctness_adapter', refusal_code='unverified')
                        if placed.get('input_editable') is False:
                            raise SessionRefusal('no_editable_surface', refusal_code='unverified')
                if not placed.get('focused'):
                    result['focus_refusal'] = 'editor_focus_not_acquired'
                async def witness(char): return await bridge.request(op='key', char=char, selector=present_sel)
                result.update(await type_document(page, sampler, witness, text, selector=edit_sel,
                    cadence_ms=args.cadence_ms, session_kind=kind, witness_every=args.witness_every, sample_s=args.sample_s,
                    present_selector=present_sel, expected_text=getattr(args, 'expected_text', None),
                    read_document=read_document, flag_verifier=flag_verifier,
                    correctness_oracle=oracle_name,
                    present_text=(surface_kind == 'dom' and model_js is None)))
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
                            raise SessionRefusal('save_timeout', refusal_code='editor_timeout') from exc
                        result.update(save_ms=(time.monotonic()-t0)*1000, save_reason=None)
                    await sampler.mark('save')
                    await sampler.mark('quiescence_start')
                    await asyncio.sleep(args.quiescence_s)
                    await sampler.mark('quiescence')
                    await sampler.mark('end')
                    result['resource_endpoints']['end'] = await sampler.endpoint()
    except ModuleNotFoundError as exc:
        result.update(failure_reason='dependency_missing', refusal_code='dependency_missing',
                      missing_module=exc.name, error=str(exc))
    except SessionRefusal as exc:
        result['failure_reason'] = str(exc)
        if getattr(exc, 'refusal_code', None):
            result['refusal_code'] = exc.refusal_code
    except (TimeoutError, asyncio.CancelledError):
        result['failure_reason'] = 'budget_exceeded'
        result['refusal_code'] = 'editor_timeout'
    except Exception as exc:
        transport = classify_bridge_error(exc)
        if transport:
            result.update(failure_reason=transport[0], refusal_code=transport[1], error=str(exc))
        else:
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
    import os
    if os.environ.get('PERF_CHROME_PROFILE') == '1':
        cap = float(os.environ.get('PERF_CHROME_PROFILE_BUDGET_S', '60'))
        args.budget_s = min(args.budget_s, cap)
    if args.cadence_ms < 0 or min(args.witness_every,args.sample_s,args.budget_s) <= 0 or args.quiescence_s < 0:
        ap.error('cadence/quiescence must be nonnegative; sample interval, witness interval and budget positive')
    if args.words is not None and args.words <= 0: ap.error('--words must be positive')
    text = BRIEF.read_text().rstrip()
    if args.words:
        tokens = list(re.finditer(r'\S+', text)); text = text[:tokens[min(args.words,len(tokens))-1].end()]
    from perf.fixtures.generate import docx_zip_bytes
    # Zero-text DOCX, not select-all/delete after loading a populated document.
    # section_properties: docxodus's paginated mount only wires body paragraphs
    # inside a page box; a sectPr-less body leaves the lone <w:p/> outside the
    # edit root with no editable surface at all.
    empty = fixture_path('typing-empty', docx_zip_bytes(b'\n', section_properties=True),
                         args.out_root/'empty.docx')
    for editor in args.editors:
        target = dict(BROWSER_TARGETS[editor]); target['editor_id'] = editor
        if editor == 'superdoc': target['typing_save_selector'] = '#export-docx'
        directory = args.out_root; directory.mkdir(parents=True,exist_ok=True)
        select_fixture(target, empty); server = None
        try:
            server = start_host(editor,target)
            result, series = asyncio.run(session(target,text,args,directory))
        except ModuleNotFoundError as exc:
            result, series = {'failure_reason': 'dependency_missing',
                              'refusal_code': 'dependency_missing',
                              'missing_module': exc.name, 'error': str(exc)}, []
        except Exception as exc: result, series = {'failure_reason':'host_start_failed','refusal_code':'host_build','error':str(exc)}, []
        finally:
            if server: stop_host(server)
        run = ACTIVE.get()
        typing_gate = content_gate_record(
            content_meta_for_workload('prose-500w'),
            gate_length_check_for(editor, content_meta_for_workload('prose-500w')),
        )
        trial = {
            'schema':'perf.typing/2', 'session_kind':args.session_kind, 'isolation':'fresh_process', 'values_per_session':1, 'criterion_id':'TYPING', 'editor_id':editor,
            'run_id':run.run_id, 'seed':run.seed, 'repetition':(CELL.get() or {}).get('repetition')}
        trial.update(result, outcome=(result.get('outcome') or
                ('unverified' if result.get('refusal_code') == 'unverified'
                 else 'refused' if result.get('failure_reason') else 'measured')),
            publishable=False, publication_block_reason='inspect all witness and resource refusals; publication requires complete session set',
            fixture_sha256=hashlib.sha256(BRIEF.read_bytes()).hexdigest(),
            fixture_docx_sha256=hashlib.sha256(empty.read_bytes()).hexdigest(),
            typed_text_sha256=hashlib.sha256(text.encode()).hexdigest(), fixture_words=len(text.split()),
            cadence_ms=args.cadence_ms, session_kind=args.session_kind, witness_every=args.witness_every, sample_s=args.sample_s,
            budget_s=args.budget_s, quiescence_s=args.quiescence_s,
            execution_profile=run.execution_profile, host_class=run.host_class,
            host_provenance=run.hosts.get(editor), time_series='resources.json',
            resource_series_label='instrumented' if args.session_kind == 'latency' else 'measurement')
        trial.update(typing_gate)
        if trial.get('failure_reason'):
            trial['throughput_chars_s'] = None
            trial.setdefault('refusal_detail', trial['failure_reason'])
        if not trial.get('failure_reason'):
            trial['refusal_code'] = None
        key_to_paint = trial.get('key_to_paint') or {}
        if trial.get('refusal_code') is None and key_to_paint.get('refusal_code') == 'insufficient_accepted':
            trial['refusal_code'] = 'witness_unavailable'
            trial['refusal_detail'] = 'insufficient_accepted'
        write_json(directory/'resources.json',series)
        write_json(directory/'attempts'/'typing.json',trial)
        print(json.dumps({'editor':editor,'failure_reason':trial.get('failure_reason'),'words_typed':trial.get('words_typed')}))
    return 0

_main = main_cell  # B6's common smoke dispatcher entrypoint.

def main():
    return run_cli(main_cell,'benchmark_typing',BROWSER_TARGETS)

if __name__ == '__main__': raise SystemExit(main())
