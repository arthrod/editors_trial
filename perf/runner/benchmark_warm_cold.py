#!/usr/bin/env python3
"""Warm vs non-warm browser contrast on harness UI hosts (Playwright / Puppeteer)."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
import math
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.adapters.capabilities import default_lane, pin_label  # noqa: E402
from perf.runner.harness_ui_versions import browser_harness_editor_version  # noqa: E402
from perf.analysis.publication_gate import trial_publishable_flags  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402
from perf.fixtures.generate import build_workload, correctness_fixtures, docx_zip_bytes  # noqa: E402
from perf.fixtures.profiles import assert_workload_allowed, feature_profile, size_ladder  # noqa: E402
from perf.runner.browser_run import execution_profile, host_class, run_cli, fixture_path as run_fixture, write_json, record_process
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.benchmark_ci_contract import (  # noqa: E402
    INTERPRETATION_CONDITIONS,
    _finalize_publishable,
    _host_base,
    _ram_bytes,
    _host as _contract_host,
    _trial_dict,
)
from perf.runner.cause_attribution import (  # noqa: E402
    C05_PROBE_KEY,
    C06_PROBE_KEY,
    assert_same_probe_paired,
    assert_warm_cold_distinct,
    attribute_delta,
    probe_medians,
)
from perf.runner.cause_attribution import _median as median  # noqa: E402
from perf.runner.witness import DEFAULT_MIN_PIXELS, DEFAULT_SKEW_BOUND_MS, validate_witness
from perf.layers.classify import assert_visible_evidence
from perf.layers.event_timing import event_timing_status, samples_ms as event_samples_ms
from perf.runner.browser_run import ACTIVE
from perf.schema import validate_environment, validate_trial  # noqa: E402

UI = REPO / "harness" / "ui"
EDITOR_REPOS = (REPO / "repos") if (REPO / "repos").is_dir() else (REPO / "harness").resolve().parent / "repos"
PROBE = REPO / "perf" / "runner" / "warm_cold_browser.mjs"

PAIR_SAMPLES = 3
EXECUTION_PROFILE = "ci_broad"

# Editors with a harness/ui dev server target (Microsoft Word and CLI-only lanes omitted).
BROWSER_TARGETS: dict[str, dict] = {
    "plate": {
        "lane": "browser_slate",
        "cwd": UI / "plate",
        "command": ["pnpm", "exec", "vite", "--port", "5208", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5208/",
        "corpus_route": "/corpus.docx",
        "ready_selector": ".status-ok",
        "edit_selector": '[contenteditable="true"]',
        "driver": "playwright",
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
    "docxodus": {
        "lane": "wasm_editor",
        "cwd": UI / "docxodus",
        "command": ["pnpm", "exec", "vite", "--port", "5210", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5210/",
        "corpus_route": "/corpus.docx",
        "ready_selector": "#status",
        "ready_js": "window.__docxodus && window.__docxodus.rendered",
        "wait_after_ready": "500",
        "edit_selector": "#pages",
        "driver": "playwright",
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
    "superdoc": {
        "lane": "browser",
        "cwd": UI / "superdoc",
        "command": ["npm", "exec", "--", "vite", "--port", "5199", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5199/",
        "corpus_route": "/sample.docx",
        "ready_selector": "#editor .superdoc__document",
        "wait_after_ready": "2000",
        "edit_selector": "#editor .superdoc__document",
        "driver": "playwright",
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
    "genoffice": {
        "lane": "editor",
        "cwd": UI / "genoffice",
        "command": ["npm", "exec", "--", "vite", "--config", "vite.config.mjs", "--port", "5201", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5201/",
        "corpus_route": "/corpus.docx",
        "ready_selector": ".doc-page",
        "wait_after_ready": "8000",
        "edit_selector": ".doc-page",
        "driver": "playwright",
        "env": {"GENOFFICE_REPO": str(EDITOR_REPOS / "genoffice")},
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
    "canvas": {
        "lane": "editor",
        "cwd": UI / "canvas",
        "command": ["pnpm", "exec", "vite", "--port", "5204", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5204/?src=/sample.docx",
        "corpus_route": "/sample.docx",
        "ready_selector": "#editor",
        "ready_js": "window.__DOCX_IMPORTED__ === true",
        "wait_after_ready": "800",
        "edit_selector": "#editor canvas",
        "driver": "playwright",
        "skip_edit": False,
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
    "docsplus": {
        "lane": "app",
        "cwd": UI / "docsplus" / "host",
        "command": ["bash", "start.sh"],
        "url": "http://127.0.0.1:5215/editor",
        "corpus_route": "/corpus.docx",
        "ready_selector": '#perf-status[data-state="ready"]',
        "ready_js": "window.__DOCSPLUS_READY__ === true",
        "edit_selector": ".tiptap__editor .ProseMirror",
        "driver": "playwright",
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
    "docen": {
        "lane": "editor",
        "cwd": UI / "docen-host",
        "command": ["pnpm", "exec", "vite", "--port", "5214", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5214/",
        "corpus_route": "/corpus.docx",
        "ready_selector": '#host[data-ready="1"]',
        "ready_js": "window.__DOCEN_READY__ === true",
        "wait_after_ready": "300",
        "edit_selector": "docen-document .canvas-pages > div:first-child",
        "driver": "playwright",
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
    "fidus": {
        "lane": "app",
        "cwd": UI / "fidus-host",
        "command": ["node", "proxy.mjs", "--port", "5221"],
        "url": "http://localhost:5221/",
        "corpus_route": "/corpus.docx",
        "ready_selector": 'html[data-fidus-host-ready="1"]',
        "edit_selector": "#document-editable .ProseMirror",
        "driver": "playwright",
        "env": {"FIDUS_PY": "/tmp/fidusvenv2/bin/python"},
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
    "wordcraft": {
        "lane": "wasm_ui",
        "cwd": UI / "wordcraft-host",
        "command": ["node", "server.mjs"],
        "url": "http://127.0.0.1:5219/",
        "corpus_route": "/corpus.docx",
        "ready_selector": '#wc-ready[data-state="rendered"]',
        "ready_js": "window.__WORDCRAFT_READY__ === true",
        "edit_selector": "#wordcraft_canvas",
        "driver": "playwright",
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
    "apryse": {
        "lane": "webviewer",
        "cwd": REPO / "harness" / "apryse",
        "command": ["pnpm", "exec", "vite", "--config", "vite.perf.config.mjs",
                    "--port", "5213", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5213/perf.html",
        "corpus_route": "/corpus.docx",
        "ready_selector": '#ready[data-state="rendered"]',
        "ready_js": "window.__aprysePerf && window.__aprysePerf.state === 'rendered'",
        "wait_after_ready": "500",
        "edit_selector": "#pageContainer1",
        "driver": "playwright",
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
    # no office-open browser target: the library exposes no interactive UI, so
    # first_usable/presented_frame would measure our own host, not the editor.
    "eigenpal": {
        "lane": "browser",
        "cwd": EDITOR_REPOS / "eigenpal-docx-editor" / "examples" / "vite",
        "command": ["node", "../../node_modules/vite/bin/vite.js", "--port", "5218", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5218/?perfE2e=1&fixture=corpus.docx&reviewRail=0",
        "corpus_route": "/corpus.docx",
        "ready_selector": ".docx-page[data-materialized=\"true\"]",
        "ready_js": "window.__DOCX_EDITOR_E2E__?.ready() === true && window.__DOCX_EDITOR_E2E__?.fontMeasurer() === 'shaped' && (() => { const p = document.querySelector('.docx-page[data-materialized=\"true\"]'); if (!p) return false; const r = p.getBoundingClientRect(); return getComputedStyle(p).visibility === 'visible' && r.width > 0 && r.height > 0 && !document.querySelector('[data-docx-opening-preview], [data-docx-layout-pending]'); })()",
        "edit_selector": ".docx-page-content [data-paragraph-id][data-start]",
        "driver": "playwright",
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
    "folio": {
        "lane": "editor",
        "cwd": EDITOR_REPOS / "folio" / "packages" / "playground",
        "command": ["bun", "run", "dev", "--", "--port", "5217", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5217/?file=corpus.docx",
        "corpus_route": "/fixtures/corpus.docx",
        "ready_selector": "[data-page-number]",
        "ready_js": "Array.from(document.querySelectorAll('[data-page-number]')).some((el) => (el.innerText || '').trim().length > 0)",
        "edit_selector": "[data-page-number]",
        "driver": "playwright",
        "env": {"FOLIO_PLAYGROUND_PORT": "5217"},
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
}


def _apryse_key_present() -> bool:
    for name in ("APRYSE_LICENSE_KEY", "PDFTRON_LICENSE_KEY", "TRIAL_KEY", "APRYSE_API_KEY"):
        if os.environ.get(name, "").strip():
            return True
    return False


def warm_equals_cold(cold_samples: list[float], warm_samples: list[float]) -> bool:
    """True when the strict copy guard fires; recorded, not raised.

    The probe stamps with integer ``Date.now()`` milliseconds, so a fast edit
    can produce two legitimately equal arrays (all 83 ms). Aborting a
    five-minute pass over that coincidence destroys good data; the flag stays
    in the attempt so a real copy is still visible.
    """
    try:
        assert_warm_cold_distinct(cold_samples, warm_samples)
    except ValueError:
        return True
    return False


def _attempt_ref(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path.resolve())


def _legacy_start_server(editor_id: str, target: dict) -> subprocess.Popen:
    cwd = target["cwd"]
    if not cwd.is_dir():
        raise FileNotFoundError("missing harness host %s" % cwd)
    env = os.environ.copy()
    env.setdefault("NODE_OPTIONS", "--no-deprecation")
    if target.get("env"):
        env.update(target["env"])
    proc = subprocess.Popen(
        target["command"],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    deadline = time.time() + 90.0
    while time.time() < deadline:
        if proc.poll() is not None:
            err = (proc.stderr.read() or b"").decode("utf-8", errors="replace")
            raise RuntimeError("%s server exited: %s" % (editor_id, err[:500]))
        try:
            import urllib.request

            with urllib.request.urlopen(target["url"], timeout=2.0) as resp:
                if resp.status < 500:
                    return proc
        except Exception:
            time.sleep(0.4)
    proc.kill()
    raise TimeoutError("%s server did not become ready" % editor_id)


def _start_server(editor_id: str, target: dict):
    from perf.runner.browser_hosts import start_host
    return start_host(editor_id, target, _legacy_start_server)


def _stop_server(proc) -> None:
    if hasattr(proc, "stop"):
        proc.stop()
        return
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)


def _run_browser_probe(
    *,
    target: dict,
    corpus_path: Path,
    pairs: int,
) -> dict:
    from perf.runner.browser_hosts import select_fixture
    select_fixture(target, corpus_path)
    node = shutil.which("node") or "node"
    cmd = [
        node,
        str(PROBE),
        "--driver",
        target.get("driver", "playwright"),
        "--url",
        target["url"],
        "--corpus",
        str(corpus_path.resolve()),
        "--corpus-route",
        target["corpus_route"],
        "--ready-selector",
        target.get("ready_selector", ""),
        "--edit-selector",
        target["edit_selector"],
        "--pairs",
        str(pairs),
    ]
    if target.get("sample_route"):
        cmd.extend(["--sample-route", target["sample_route"]])
    if target.get("ready_text"):
        cmd.extend(["--ready-text", target["ready_text"]])
    if target.get("ready_js"):
        cmd.extend(["--ready-js", target["ready_js"]])
    if target.get("pre_edit_click"):
        cmd.extend(["--pre-edit-click", target["pre_edit_click"]])
    if target.get("wait_after_ready"):
        cmd.extend(["--wait-after-ready", str(target["wait_after_ready"])])
    if target.get("skip_edit"):
        cmd.extend(["--skip-edit", "true"])
    active = ACTIVE.get()
    with active.begin_sample() if active is not None else nullcontext():
        proc = subprocess.run(
            cmd, cwd=str(UI), capture_output=True, text=True, timeout=600,
        )
        record_process(proc)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or "probe failed")
        payload = json.loads(proc.stdout)
        probe_accounting = None
        if active is not None:
            path = active.sample('probe-' + uuid.uuid4().hex, {'outcome': 'ok'})
            probe_accounting = json.loads(path.read_text())
    for index, pair in enumerate(payload.get('pairs', [])):
        for arm in ('cold', 'warm'):
            data = pair.get(arm, {})
            for cid, observations in (('C05', [data]), ('C06', data.get('burst', []))):
                for iteration, observation in enumerate(observations):
                    if 'mechanism' not in observation:
                        continue
                    row = input_sample_record(observation, cid)
                    row.update(arm=arm, pair=index, iteration=iteration,
                               server_cold=pair.get('server_cold', index == 0))
                    if probe_accounting and probe_accounting.get('failure_reason') == 'cpu_throttled':
                        row.update(outcome='failed', failure_reason='cpu_throttled', latency_ms=None)
                    if probe_accounting:
                        row['probe_cpu_accounting'] = probe_accounting['cpu_accounting']
                    if row['outcome'] != 'measured':
                        observation['outcome'] = 'failed'
                        observation['edit_ms'] = None
                        observation['failure_reason'] = row['failure_reason']
                        if cid == 'C05':
                            data['single_edit_ms'] = None
                        else:
                            data['sustained_typing_median_ms'] = None
                    if active is not None:
                        with active.begin_sample():
                            active.sample('input-' + uuid.uuid4().hex, row)
    return payload


def _finite_clock_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _witness_clock_skew_ms(witness):
    if not isinstance(witness, dict):
        return None
    for key in ('clock_skew_ms', 'skew_ms'):
        value = witness.get(key)
        if _finite_clock_number(value):
            return float(value)
    nested = witness.get('clock_check')
    if isinstance(nested, dict):
        for key in ('page_offset_ms', 'skew_ms'):
            value = nested.get(key)
            if _finite_clock_number(value):
                return float(value)
    return None


def _witness_declared_bound_ms(witness):
    if not isinstance(witness, dict):
        return None
    nested = witness.get('clock_check')
    if isinstance(nested, dict) and nested.get('bound_ms') is not None:
        return nested.get('bound_ms')
    return witness.get('bound_ms')


def input_sample_record(observation, criterion_id):
    """Validate page-clock evidence; preserve censor/refusal without making zeros."""
    row = dict(observation)
    row['criterion_id'] = criterion_id
    skew = row.get('clock_skew') or {}
    value = skew.get('skew_ms')
    declared_bound = skew.get('bound_ms')
    bound = DEFAULT_SKEW_BOUND_MS
    reason = row.get('failure_reason')
    witness = row.get('witness')
    witness_skew = _witness_clock_skew_ms(witness)
    witness_bound = _witness_declared_bound_ms(witness)
    if reason:
        pass  # Preserve the actual sample refusal before secondary missing evidence.
    elif isinstance(value, bool) or not isinstance(value, (int, float)):
        reason = 'clock_skew_unavailable'
    elif declared_bound is not None and (
        isinstance(declared_bound, bool)
        or not isinstance(declared_bound, (int, float))
        or not math.isfinite(declared_bound)
        or float(declared_bound) != bound
    ):
        reason = 'clock_skew_bound_not_constant'
    elif not math.isfinite(value) or abs(value) > bound:
        reason = 'clock_skew_above_bound'
    elif not skew.get('acceptable'):
        reason = 'clock_skew_unavailable'
    elif witness_bound is not None and (
        isinstance(witness_bound, bool)
        or not isinstance(witness_bound, (int, float))
        or not math.isfinite(witness_bound)
        or float(witness_bound) != bound
    ):
        reason = 'clock_bound_mismatch'
    elif witness_skew is not None and abs(witness_skew) > bound:
        reason = 'clock_skew_above_bound'
    elif (
        witness_skew is not None
        and _finite_clock_number(value)
        and abs(witness_skew - float(value)) > bound
    ):
        reason = 'clock_disagreement'
    if not reason and criterion_id in ('C05', 'C06') and 'edit_ms' in row:
        proof = row.get('edit_confirmation') or {}
        pixels = proof.get('changed_pixels')
        rects = proof.get('visible_rects')
        visible = isinstance(rects, list) and bool(rects) and all(
            isinstance(r, dict) and all(isinstance(r.get(k), (int, float))
                and not isinstance(r.get(k), bool) and math.isfinite(r[k])
                for k in ('x', 'y', 'width', 'height'))
            and r['width'] > 0 and r['height'] > 0 for r in rects)
        if (proof.get('confirmed') is not True or not visible
                or isinstance(pixels, bool) or not isinstance(pixels, (int, float))
                or not math.isfinite(pixels) or pixels < DEFAULT_MIN_PIXELS):
            reason = 'expected_edit_not_confirmed'
        verdict = validate_witness(row.get('witness'), bound_ms=bound)
        if not reason and verdict['refused']:
            reason = verdict['reason']
    timing = dict(row.get('event_timing') or {})
    entries = [event_timing_status(e['duration'], 16) for e in timing.get('entries', [])]
    timing['samples_ms'] = event_samples_ms(entries)
    timing['normalized_entries'] = entries
    row['event_timing'] = timing
    row['latency_ms'] = None if reason else row.get('edit_ms')
    row['outcome'] = 'failed' if reason else row.get('outcome', 'measured')
    row['failure_reason'] = reason
    return row


def validate_ready_attempts(rows):
    """Check every C02/C03 combination, including server-cold and warm C03."""
    from perf.runner.cause_attribution import assert_c02_c03_distinct_boundaries

    rows = list(rows)
    for c02 in rows:
        if c02.get('criterion_id') != 'C02':
            continue
        for c03 in rows:
            if c03.get('criterion_id') == 'C03' and c03.get('editor_id') == c02.get('editor_id'):
                assert_c02_c03_distinct_boundaries(c02, c03)


def _persist_attempt(attempt_dir, criterion_id, editor_id, trial):
    """Every written trial is an accounted BrowserRun sample, not just a cell."""
    trial = {**trial, 'measure': (trial.get('environment') or {}).get('cache_state', '')}
    reason = str(trial.get('failure_reason') or '')
    outcome = trial.get('outcome')
    code = (None if outcome == 'measured' else
            'cpu_throttled' if reason.startswith('cpu_throttled') else
            'unverified' if reason.startswith('expected_edit_not_confirmed') else
            outcome if outcome in ('not_run', 'not_applicable', 'unsupported', 'unverified') else
            'malformed_samples' if reason.startswith(('record_', 'not_a_witness_record', 'unknown_outcome', 'invalid_record', 'no_outcome')) else
            'paint_witness_unavailable' if reason.startswith(('clock_', 'frame_', 'witness_', 'no_frame', 'missing_input', 'caret_', 'not_document_scoped', 'no_pixel_evidence', 'pixel_evidence_')) else
            'crash')
    trial.setdefault('refusal_code', code)
    active = ACTIVE.get()
    name = "%s-%s-%s" % (criterion_id.lower(), editor_id, uuid.uuid4().hex[:10])
    if active is not None:
        sample_path = active.sample(name, trial)
        recorded = json.loads(sample_path.read_text())
        if recorded.get('failure_reason') == 'cpu_throttled':
            # B1 strips measurements; restore identity and refusal reasons, never numbers.
            identity = {key: trial[key] for key in ('criterion_id', 'measure', 'layer', 'boundary', 'environment', 'editor_id', 'lane') if key in trial}
            reasons = set(trial.get('failure_reasons') or [])
            if trial.get('failure_reason'):
                reasons.add(trial['failure_reason'])
            reasons.add('cpu_throttled')
            trial = {**identity, **recorded, 'failure_reasons': sorted(reasons),
                     'samples_ms': [], 'latency_ms': None,
                     'summary_stats': None, 'publication_block_reason': 'cpu_throttled'}
        else:
            trial = recorded
    return write_attempt(attempt_dir, name, trial)


def _write_measured_attempt(
    *,
    attempt_dir: Path,
    criterion_id: str,
    layer: str,
    boundary: str,
    editor_id: str,
    lane: str,
    env: dict,
    samples_ms: list[float],
    cache_state: str,
    diagnostic: dict | None = None,
) -> Path:
    diagnostic = diagnostic or {}
    if criterion_id == "C06":
        diagnostic = {**diagnostic, "keys": 3, "isolated": True}
    if criterion_id == 'C05':
        assert_visible_evidence('C05', diagnostic.get('mechanism'))
    observations = diagnostic.get('observations', [])
    group_lengths = [len(entry) if isinstance(entry, list) else 1 for entry in observations]
    observations = [item for entry in observations for item in (entry if isinstance(entry, list) else [entry])]
    if criterion_id in ('C05', 'C06'):
        if not observations:
            raise ValueError('missing input observations')
        checked = [input_sample_record(item, criterion_id) for item in observations]
        rejected = [item for item in checked if item['outcome'] != 'measured' or item['latency_ms'] is None]
        if rejected:
            reason = rejected[0].get('failure_reason') or 'missing_input_latency'
            trial = _trial_dict(criterion_id=criterion_id, layer=layer, boundary=boundary,
                outcome='failed', env=env, samples_ms=[], failure_reason=reason,
                editor_id=editor_id, lane=lane,
                diagnostic={**diagnostic, 'observations':checked})
            trial['failure_reasons'] = sorted({item.get('failure_reason') or 'missing_input_latency' for item in rejected})
            trial.update(mechanism=diagnostic.get('mechanism'),
                         clock_skew=[item.get('clock_skew') for item in checked])
            return _persist_attempt(attempt_dir, criterion_id, editor_id, trial)
        diagnostic = {**diagnostic, 'observations':checked,
                      'clock_skew':[item['clock_skew'] for item in checked]}
        intervals = [item['witness']['clock_check']['frame_interval_ms'] for item in checked]
        diagnostic['frame_intervals_ms'] = intervals
        interval_reason = None
        selected = []
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                   and math.isfinite(value) and value > 0 for value in intervals):
            interval_reason = 'frame_interval_unavailable'
        else:
            offset = 0
            lengths = [len(checked)] if len(samples_ms) == 1 else group_lengths
            for sample, length in zip(samples_ms, lengths):
                group = checked[offset:offset + length]
                offset += length
                matches = [item['witness']['clock_check']['frame_interval_ms']
                           for item in group if item['latency_ms'] == sample]
                if matches:
                    selected.append(min(matches))
            if len(selected) != len(samples_ms):
                interval_reason = 'frame_interval_unavailable'
            elif len(set(selected)) != 1:
                # The report contract has one witnessed interval per trial.
                # Do not relabel samples from different calibrations.
                interval_reason = 'frame_interval_inconsistent'
        if interval_reason:
            trial = _trial_dict(criterion_id=criterion_id, layer=layer, boundary=boundary,
                outcome='failed', env=env, samples_ms=[], failure_reason=interval_reason,
                editor_id=editor_id, lane=lane, diagnostic=diagnostic)
            trial['refusal_code'] = 'paint_witness_unavailable'
            return _persist_attempt(attempt_dir, criterion_id, editor_id, trial)
        diagnostic['frame_interval_ms'] = selected[0]
    for skew in diagnostic.get('clock_skew') or []:
        check = input_sample_record({'clock_skew':skew}, criterion_id)
        if check['failure_reason']:
            trial = _trial_dict(criterion_id=criterion_id, layer=layer, boundary=boundary,
                outcome='failed', env=env, samples_ms=[], failure_reason=check['failure_reason'],
                editor_id=editor_id, lane=lane, diagnostic=diagnostic)
            trial['clock_skew'] = diagnostic['clock_skew']
            return _persist_attempt(attempt_dir, criterion_id, editor_id, trial)
    if criterion_id == 'C03':
        intervals = [clock.get('frame_interval_ms') for clock in diagnostic.get('clock_skew') or []
                     if clock.get('acceptable') is True]
        if intervals and all(isinstance(value, (int, float)) and not isinstance(value, bool)
                             and math.isfinite(value) and value > 0 for value in intervals):
            diagnostic = {**diagnostic, 'frame_interval_ms': min(intervals), 'frame_intervals_ms': intervals}
    stats = summarize(samples_ms, cache_state, env["repetition_unit"], seed=0)
    pub, reason = trial_publishable_flags(env, layer, None if env["repetition_unit"] == "fresh_process" else stats["n"])
    pub, reason = _finalize_publishable(pub, reason, env)
    trial = _trial_dict(
        criterion_id=criterion_id,
        layer=layer,
        boundary=boundary,
        outcome="measured",
        env=env,
        samples_ms=samples_ms,
        editor_id=editor_id,
        lane=lane,
        summary_stats=stats,
        publishable=pub,
        publication_block_reason=reason,
        diagnostic=diagnostic,
    )
    trial['clock_skew'] = diagnostic.get('clock_skew')
    interval = diagnostic.get('frame_interval_ms')
    if isinstance(interval, (int, float)) and not isinstance(interval, bool) and math.isfinite(interval) and interval > 0:
        trial['sub_frame_samples'] = [sample < interval for sample in samples_ms]
    if criterion_id in ('C05', 'C06'):
        trial['mechanism'] = diagnostic.get('mechanism')
        trial['clock_skew'] = diagnostic.get('clock_skew')
    validate_trial(trial)
    return _persist_attempt(attempt_dir, criterion_id, editor_id, trial)


def _write_input_refusal(*, observations, failure_reason, **kwargs):
    checked = [input_sample_record(o, kwargs['criterion_id']) for o in observations]
    reason = next((o['failure_reason'] for o in checked if o.get('failure_reason')), failure_reason)
    trial = _trial_dict(
        **{k: v for k, v in kwargs.items() if k != 'attempt_dir'},
        outcome='failed', samples_ms=[], failure_reason=reason,
        diagnostic={'observations': checked, 'aggregation': 'all samples required',
                    **({'keys': 3, 'isolated': True} if kwargs['criterion_id'] == 'C06' else {})},
    )
    trial['failure_reasons'] = sorted({o['failure_reason'] for o in checked if o.get('failure_reason')} or {failure_reason})
    return _persist_attempt(kwargs['attempt_dir'], kwargs['criterion_id'], kwargs['editor_id'], trial)


def _write_not_run(
    *,
    attempt_dir: Path,
    criterion_id: str,
    layer: str,
    boundary: str,
    editor_id: str,
    lane: str,
    env: dict,
    failure_reason: str,
) -> Path:
    trial = _trial_dict(
        criterion_id=criterion_id,
        layer=layer,
        boundary=boundary,
        outcome="not_run",
        env=env,
        samples_ms=[],
        failure_reason=failure_reason,
        editor_id=editor_id,
        lane=lane,
    )
    validate_environment(env)
    return _persist_attempt(attempt_dir, criterion_id, editor_id, trial)


def _env_for(
    *,
    editor_id: str,
    editor_version: str,
    fixture_sha256: str,
    workload_row: dict,
    docx_size: int,
    cache_state: str,
) -> dict:
    env = _host_base(
        editor_id=editor_id,
        editor_version=editor_version,
        execution_profile=execution_profile(EXECUTION_PROFILE),
        fixture_sha256=fixture_sha256,
        workload_row=workload_row,
        docx_size=docx_size,
        cache_state=cache_state,
        repetition_unit="fresh_process",
        run_kind="timing",
        feature_profile_name="P0",
    )
    env["interpretation_conditions"] = list(INTERPRETATION_CONDITIONS)
    return env


def _paired_summary_row(
    *,
    criterion_id: str,
    editor_id: str,
    boundary: str,
    cold_median: float,
    warm_median: float,
    cause: str,
    cold_path: str,
    warm_path: str,
    probes: dict,
) -> dict:
    return {
        "criterion_id": criterion_id,
        "editor_id": editor_id,
        "boundary": boundary,
        "cold_median_ms": cold_median,
        "warm_median_ms": warm_median,
        "delta_ms": warm_median - cold_median,
        "attributed_cause": cause,
        "cold_attempt": cold_path,
        "warm_attempt": warm_path,
        "probes": probes,
        "publishable": False,
    }


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", default="micro-paragraphs")
    parser.add_argument("--out-root", type=Path, default=None)
    parser.add_argument("--pairs", type=int, default=PAIR_SAMPLES)
    parser.add_argument("--editors", nargs="*", default=None)
    args = parser.parse_args()

    workload_row = next(w for w in size_ladder() if w["workload_id"] == args.workload)
    assert_workload_allowed(execution_profile(EXECUTION_PROFILE), args.workload)
    built = build_workload(workload_row)
    cfs = correctness_fixtures()
    augmented_body = built["body"] + b"\n" + cfs["unicode"]
    docx_body = docx_zip_bytes(augmented_body)
    sha = hashlib.sha256(docx_body).hexdigest()
    docx_size = len(docx_body)

    run_day = date.today().isoformat().replace("-", "_")
    out_root = args.out_root or (REPO / "perf" / "out" / ("warm_cold_%s" % run_day))
    attempt_dir = out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = run_fixture(args.workload, docx_body, out_root / "fixture.docx")

    editors = args.editors or list(BROWSER_TARGETS.keys())
    paired_rows: list[dict] = []
    summary_editors: list[dict] = []
    refusal_rows: list[dict] = []

    for editor_id in editors:
        lane = BROWSER_TARGETS[editor_id].get("lane") or default_lane(editor_id)
        trial_pin = pin_label(editor_id)
        editor_version, harness_meta = browser_harness_editor_version(editor_id, trial_pin)
        target = BROWSER_TARGETS.get(editor_id)
        if target and target.get("enabled") is False:
            target = None
        if not target:
            reason = "no browser harness host configured for %s on warm_cold" % editor_id
            env = _env_for(
                editor_id=editor_id,
                editor_version=editor_version,
                fixture_sha256=sha,
                workload_row=workload_row,
                docx_size=docx_size,
                cache_state="process_cold_fs_warm",
            )
            for cid in ("C03", "C05", "C06", "C07", "C02"):
                boundary, layer = {
                    "C03": ("first_usable", "browser_visible"),
                    "C05": ("presented_frame", "browser_visible"),
                    "C06": ("input_to_next_paint", "browser_visible"),
                    "C07": ("input_to_next_paint", "browser_visible"),
                    "C02": ("model_ready_browser", "model"),
                }[cid]
                path = _write_not_run(
                    attempt_dir=attempt_dir,
                    criterion_id=cid,
                    layer=layer,
                    boundary=boundary,
                    editor_id=editor_id,
                    lane=lane,
                    env=env,
                    failure_reason=reason,
                )
                refusal_rows.append(
                    {
                        "criterion_id": cid,
                        "editor_id": editor_id,
                        "outcome": "not_run",
                        "failure_reason": reason,
                        "attempt_file": _attempt_ref(path),
                    }
                )
            continue

        proc = None
        try:
            proc = _start_server(editor_id, target)
            payload = _run_browser_probe(target=target, corpus_path=fixture_path, pairs=args.pairs)
        except Exception as exc:
            reason = "browser_probe: %s" % (exc,)
            env = _env_for(
                editor_id=editor_id,
                editor_version=editor_version,
                fixture_sha256=sha,
                workload_row=workload_row,
                docx_size=docx_size,
                cache_state="process_cold_fs_warm",
            )
            for raw_cid, (boundary, layer) in target.get("criteria", {}).items():
                cid = "C02" if raw_cid == "C02b" else raw_cid
                path = _write_not_run(
                    attempt_dir=attempt_dir,
                    criterion_id=cid,
                    layer=layer,
                    boundary=boundary,
                    editor_id=editor_id,
                    lane=lane,
                    env=env,
                    failure_reason=reason,
                )
                refusal_rows.append(
                    {
                        "criterion_id": cid,
                        "editor_id": editor_id,
                        "outcome": "not_run",
                        "failure_reason": reason,
                        "attempt_file": _attempt_ref(path),
                    }
                )
            if proc:
                _stop_server(proc)
            continue
        finally:
            if proc:
                _stop_server(proc)

        # run_cli invokes one pair per fresh server. Direct multi-pair probes
        # also retain pair 1 separately rather than pooling it with later loads.
        if len(payload['pairs']) > 1:
            first_pair = payload['pairs'][0]
            first_env = _env_for(editor_id=editor_id, editor_version=editor_version,
                fixture_sha256=sha, workload_row=workload_row, docx_size=docx_size,
                cache_state='process_cold_fs_warm')
            _write_measured_attempt(attempt_dir=attempt_dir, criterion_id='C03',
                layer='browser_visible', boundary='first_usable', editor_id=editor_id,
                lane=lane, env=first_env, samples_ms=[first_pair['cold']['first_usable_ms']],
                cache_state='process_cold_fs_warm', diagnostic={'server_cold':True,
                    'settle_ms':first_pair['cold'].get('settle_ms'),
                    'clock_skew':[first_pair['cold'].get('clock_skew')], 'pair':first_pair})
            payload['pairs'] = payload['pairs'][1:]

        probe_rows = [
            {
                "browser_launch_only_ms": row.get("browser_launch_only_ms"),
                "document_navigation_only_ms": row.get("document_navigation_only_ms"),
                "model_ready_browser_ms": row.get("model_ready_browser_ms"),
                "document_reload_same_context_ms": row.get("document_reload_same_context_ms"),
            }
            for row in payload["pairs"]
        ]
        probe_bundle = probe_medians(probe_rows)

        criteria_map = dict(target.get("criteria", {}))

        def _ready_signals_indistinguishable() -> bool:
            for pair in payload["pairs"]:
                cold = pair.get("cold") or {}
                fu = cold.get("first_usable_ms")
                mr = cold.get("model_ready_browser_ms")
                if fu is None or mr is None:
                    continue
                if float(fu) != float(mr):
                    return False
            return True

        single_ready_signal = _ready_signals_indistinguishable()
        c03_cold_attempt_ref = ""
        c02_skip_reason = (
            "browser harness exposes one ready signal (selector/JS hook); "
            "cannot separate model_ready_browser from first_usable"
        )

        if single_ready_signal and "C02b" in criteria_map:
            boundary, layer = criteria_map["C02b"]
            env_skip = _env_for(
                editor_id=editor_id,
                editor_version=editor_version,
                fixture_sha256=sha,
                workload_row=workload_row,
                docx_size=docx_size,
                cache_state="process_cold_fs_warm",
            )
            skip_path = _write_not_run(
                attempt_dir=attempt_dir,
                criterion_id="C02",
                layer=layer,
                boundary=boundary,
                editor_id=editor_id,
                lane=lane,
                env=env_skip,
                failure_reason=c02_skip_reason,
            )
            row = {
                "criterion_id": "C02",
                "editor_id": editor_id,
                "boundary": boundary,
                "outcome": "not_run",
                "failure_reason": c02_skip_reason,
                "attempt_file": _attempt_ref(skip_path),
                "publishable": False,
            }
            if harness_meta:
                row["harness_version"] = harness_meta
            refusal_rows.append(row)

        # C03 / C02b — cold only (first load in fresh browser per pair)
        cold_load_specs = []
        if "C03" in criteria_map:
            cold_load_specs.append(("C03", "first_usable_ms", "browser_visible", "first_usable"))
        if "C02b" in criteria_map and not single_ready_signal:
            cold_load_specs.append(("C02", "model_ready_browser_ms", "model", "model_ready_browser"))

        for cid, key, layer, boundary in cold_load_specs:
            cold_samples = [pair["cold"][key] for pair in payload["pairs"] if key in pair["cold"]]
            if not cold_samples:
                continue
            env_cold = _env_for(
                editor_id=editor_id,
                editor_version=editor_version,
                fixture_sha256=sha,
                workload_row=workload_row,
                docx_size=docx_size,
                cache_state="process_cold_fs_warm",
            )
            cold_path = _write_measured_attempt(
                attempt_dir=attempt_dir,
                criterion_id="C03" if cid == "C03" else "C02",
                layer=layer,
                boundary=boundary,
                editor_id=editor_id,
                lane=lane,
                env=env_cold,
                samples_ms=[float(s) for s in cold_samples],
                cache_state="process_cold_fs_warm",
                diagnostic={
                    "suite": "warm_cold",
                    "driver": payload.get("driver"),
                    "distinction": "browser_page_event",
                    "probes": probe_bundle,
                    "settle_ms": [p["cold"].get("settle_ms") for p in payload["pairs"]],
                    "clock_skew": [p["cold"].get("clock_skew") for p in payload["pairs"]],
                    "server_cold": payload["pairs"][0].get("server_cold", True),
                },
            )
            if json.loads(cold_path.read_text()).get('outcome') != 'measured':
                continue
            summary_row = {
                "criterion_id": "C03" if cid == "C03" else "C02",
                "editor_id": editor_id,
                "boundary": boundary,
                "outcome": "measured",
                "cache_state": "process_cold_fs_warm",
                "median_ms": median(cold_samples),
                "attempt_file": _attempt_ref(cold_path),
                "publishable": False,
            }
            if harness_meta:
                summary_row["harness_version"] = harness_meta
            if single_ready_signal and cid == "C03":
                summary_row["shared_ready_signal"] = {
                    "measured_boundary": "first_usable",
                    "skipped_criterion": "C02",
                    "reason": c02_skip_reason,
                }
            summary_editors.append(summary_row)
            if cid == "C03":
                c03_cold_attempt_ref = _attempt_ref(cold_path)

        reload_samples = [
            float(row["document_reload_same_context_ms"])
            for row in payload["pairs"]
            if row.get("document_reload_same_context_ms") is not None
        ]
        cold_first = [
            float(pair["cold"]["first_usable_ms"])
            for pair in payload["pairs"]
            if pair.get("cold", {}).get("first_usable_ms") is not None
        ]
        if reload_samples and cold_first and "C03" in criteria_map and c03_cold_attempt_ref:
            cause_load, breakdown = attribute_delta(
                median(cold_first), median(reload_samples), probe_bundle
            )
            warm_load_env = _env_for(editor_id=editor_id, editor_version=editor_version,
                fixture_sha256=sha, workload_row=workload_row, docx_size=docx_size,
                cache_state='warm_steady')
            warm_load_path = _write_measured_attempt(attempt_dir=attempt_dir,
                criterion_id='C03', layer='browser_visible', boundary='first_usable',
                editor_id=editor_id, lane=lane, env=warm_load_env,
                samples_ms=reload_samples, cache_state='warm_steady',
                diagnostic={'settle_ms':[p['warm'].get('settle_ms') for p in payload['pairs']],
                    'clock_skew':[p['warm'].get('clock_skew') for p in payload['pairs']]})
            if json.loads(warm_load_path.read_text()).get('outcome') != 'measured':
                continue
            paired_rows.append(
                _paired_summary_row(
                    criterion_id="C03",
                    editor_id=editor_id,
                    boundary="first_usable",
                    cold_median=median(cold_first),
                    warm_median=median(reload_samples),
                    cause=cause_load,
                    cold_path=c03_cold_attempt_ref,
                    warm_path=_attempt_ref(warm_load_path),
                    probes={**probe_bundle, **breakdown},
                )
            )

        if target.get("skip_edit"):
            for cid in ("C05", "C06", "C07", "C08", "C09", "C10"):
                boundary, layer = {
                    "C05": ("presented_frame", "browser_visible"),
                    "C06": ("input_to_next_paint", "browser_visible"),
                }.get(cid, ("presented_frame", "browser_visible"))
                env = _env_for(
                    editor_id=editor_id,
                    editor_version=editor_version,
                    fixture_sha256=sha,
                    workload_row=workload_row,
                    docx_size=docx_size,
                    cache_state="warm_steady",
                )
                path = _write_not_run(
                    attempt_dir=attempt_dir,
                    criterion_id=cid,
                    layer=layer,
                    boundary=boundary,
                    editor_id=editor_id,
                    lane=lane,
                    env=env,
                    failure_reason="adapter-not-implemented: no warm edit surface without verified selector",
                )
                refusal_rows.append(
                    {
                        "criterion_id": cid,
                        "editor_id": editor_id,
                        "outcome": "not_run",
                        "failure_reason": "adapter-not-implemented: no warm edit surface without verified selector",
                        "attempt_file": _attempt_ref(path),
                    }
                )
            continue

        if ("C05" in criteria_map or "C06" in criteria_map) and not target.get("skip_edit"):
            cold_edits = [
                pair["cold"]["single_edit_ms"]
                for pair in payload["pairs"]
                if pair.get("cold", {}).get("single_edit_ms") is not None
            ]
            warm_edits = [
                pair["warm"]["single_edit_ms"]
                for pair in payload["pairs"]
                if pair.get("warm", {}).get("single_edit_ms") is not None
            ]
            if len(cold_edits) < len(payload["pairs"]) or len(warm_edits) < len(payload["pairs"]):
                reason = "missing_input_latency"
                for cid in ("C05", "C06"):
                    if cid not in criteria_map:
                        continue
                    boundary, layer = {
                        "C05": ("presented_frame", "browser_visible"),
                        "C06": ("input_to_next_paint", "browser_visible"),
                    }[cid]
                    env = _env_for(
                        editor_id=editor_id,
                        editor_version=editor_version,
                        fixture_sha256=sha,
                        workload_row=workload_row,
                        docx_size=docx_size,
                        cache_state="warm_steady",
                    )
                    path = _write_input_refusal(
                        attempt_dir=attempt_dir,
                        criterion_id=cid,
                        layer=layer,
                        boundary=boundary,
                        editor_id=editor_id,
                        lane=lane,
                        env=env,
                        observations=[p[a] for p in payload["pairs"] for a in ("cold", "warm")],
                        failure_reason=reason,
                    )
                    refusal_rows.append(
                        {
                            "criterion_id": cid,
                            "editor_id": editor_id,
                            "outcome": "failed",
                            "failure_reason": json.loads(path.read_text())["failure_reason"],
                            "failure_reasons": json.loads(path.read_text()).get("failure_reasons", []),
                            "attempt_file": _attempt_ref(path),
                        }
                    )
                continue
            if warm_equals_cold(cold_edits, warm_edits):
                from perf.runner.browser_run import ACTIVE, CELL
                active = ACTIVE.get()
                if active is not None:
                    active.sample("saturation-%s-%s" % (CELL.get()["repetition"], editor_id), {
                        "editor_id": editor_id, "outcome": "failed",
                        "failure_reason": "warm_cold_identical", "cold_samples_ms": cold_edits,
                        "warm_samples_ms": warm_edits,
                    })
                refusal_rows.append({"editor_id": editor_id, "outcome": "failed",
                                     "failure_reason": "warm_cold_identical"})
                continue

            env_cold = _env_for(
                editor_id=editor_id,
                editor_version=editor_version,
                fixture_sha256=sha,
                workload_row=workload_row,
                docx_size=docx_size,
                cache_state="process_cold_fs_warm",
            )
            env_warm = _env_for(
                editor_id=editor_id,
                editor_version=editor_version,
                fixture_sha256=sha,
                workload_row=workload_row,
                docx_size=docx_size,
                cache_state="warm_steady",
            )

            identical_edits = warm_equals_cold(cold_edits, warm_edits)

            cold_path = _write_measured_attempt(
                attempt_dir=attempt_dir,
                criterion_id="C05",
                layer="browser_visible",
                boundary="presented_frame",
                editor_id=editor_id,
                lane=lane,
                env=env_cold,
                samples_ms=[float(s) for s in cold_edits],
                cache_state="process_cold_fs_warm",
                diagnostic={"suite": "warm_cold", "phase": "non_warm_edit",
                            "warm_equals_cold": identical_edits,
                            "mechanism": "cdp_screencast_changed_frame",
                            "clock_skew": [p["cold"].get("clock_skew") for p in payload["pairs"]],
                            "observations": [p["cold"] for p in payload["pairs"]]},
            )
            warm_path = _write_measured_attempt(
                attempt_dir=attempt_dir,
                criterion_id="C05",
                layer="browser_visible",
                boundary="presented_frame",
                editor_id=editor_id,
                lane=lane,
                env=env_warm,
                samples_ms=[float(s) for s in warm_edits],
                cache_state="warm_steady",
                diagnostic={"suite": "warm_cold", "phase": "warm_edit",
                            "warm_equals_cold": identical_edits,
                            "mechanism": "cdp_screencast_changed_frame",
                            "clock_skew": [p["warm"].get("clock_skew") for p in payload["pairs"]],
                            "observations": [p["warm"] for p in payload["pairs"]]},
            )

            if any(json.loads(path.read_text()).get('outcome') != 'measured'
                   for path in (cold_path, warm_path)):
                continue
            cause, breakdown = attribute_delta(median(cold_edits), median(warm_edits), probe_bundle)
            paired_rows.append(
                _paired_summary_row(
                    criterion_id="C05",
                    editor_id=editor_id,
                    boundary="presented_frame",
                    cold_median=median(cold_edits),
                    warm_median=median(warm_edits),
                    cause=cause,
                    cold_path=_attempt_ref(cold_path),
                    warm_path=_attempt_ref(warm_path),
                    probes={**probe_bundle, **breakdown},
                )
            )

            cold_burst = [
                pair["cold"].get(C06_PROBE_KEY)
                for pair in payload["pairs"]
                if pair.get("cold", {}).get(C06_PROBE_KEY) is not None
            ]
            warm_burst = [
                pair["warm"].get(C06_PROBE_KEY)
                for pair in payload["pairs"]
                if pair.get("warm", {}).get(C06_PROBE_KEY) is not None
            ]
            if (
                len(cold_burst) >= len(payload["pairs"])
                and len(warm_burst) >= len(payload["pairs"])
                and "C06" in criteria_map
            ):
                assert_same_probe_paired(C06_PROBE_KEY, C06_PROBE_KEY)
                identical_burst = warm_equals_cold(cold_burst, warm_burst)
                env_cold_burst = _env_for(
                    editor_id=editor_id,
                    editor_version=editor_version,
                    fixture_sha256=sha,
                    workload_row=workload_row,
                    docx_size=docx_size,
                    cache_state="process_cold_fs_warm",
                )
                env_warm_burst = _env_for(
                    editor_id=editor_id,
                    editor_version=editor_version,
                    fixture_sha256=sha,
                    workload_row=workload_row,
                    docx_size=docx_size,
                    cache_state="warm_steady",
                )
                c06_cold_path = _write_measured_attempt(
                    attempt_dir=attempt_dir,
                    criterion_id="C06",
                    layer="browser_visible",
                    boundary="input_to_next_paint",
                    editor_id=editor_id,
                    lane=lane,
                    env=env_cold_burst,
                    samples_ms=[float(s) for s in cold_burst],
                    cache_state="process_cold_fs_warm",
                    diagnostic={
                        "suite": "warm_cold",
                        "phase": "non_warm_burst",
                        "probe_key": C06_PROBE_KEY,
                        "warm_equals_cold": identical_burst,
                        "mechanism": "cdp_screencast_changed_frame",
                        "observations": [p["cold"].get("burst", []) for p in payload["pairs"]],
                    },
                )
                burst_path = _write_measured_attempt(
                    attempt_dir=attempt_dir,
                    criterion_id="C06",
                    layer="browser_visible",
                    boundary="input_to_next_paint",
                    editor_id=editor_id,
                    lane=lane,
                    env=env_warm_burst,
                    samples_ms=[float(s) for s in warm_burst],
                    cache_state="warm_steady",
                    diagnostic={
                        "suite": "warm_cold",
                        "phase": "warm_burst",
                        "probe_key": C06_PROBE_KEY,
                        "warm_equals_cold": identical_burst,
                        "mechanism": "cdp_screencast_changed_frame",
                        "observations": [p["warm"].get("burst", []) for p in payload["pairs"]],
                    },
                )
                if any(json.loads(path.read_text()).get('outcome') != 'measured'
                       for path in (c06_cold_path, burst_path)):
                    continue
                cause_burst, breakdown_burst = attribute_delta(
                    median(cold_burst), median(warm_burst), probe_bundle
                )
                paired_rows.append(
                    _paired_summary_row(
                        criterion_id="C06",
                        editor_id=editor_id,
                        boundary="input_to_next_paint",
                        cold_median=median(cold_burst),
                        warm_median=median(warm_burst),
                        cause=cause_burst,
                        cold_path=_attempt_ref(c06_cold_path),
                        warm_path=_attempt_ref(burst_path),
                        probes={**probe_bundle, **breakdown_burst},
                    )
                )
            elif "C06" in criteria_map:
                reason = "missing_input_latency"
                boundary, layer = ("input_to_next_paint", "browser_visible")
                env = _env_for(
                    editor_id=editor_id,
                    editor_version=editor_version,
                    fixture_sha256=sha,
                    workload_row=workload_row,
                    docx_size=docx_size,
                    cache_state="warm_steady",
                )
                path = _write_input_refusal(
                    attempt_dir=attempt_dir,
                    criterion_id="C06",
                    layer=layer,
                    boundary=boundary,
                    editor_id=editor_id,
                    lane=lane,
                    env=env,
                    observations=[o for p in payload["pairs"] for a in ("cold", "warm") for o in p[a].get("burst", [])],
                    failure_reason=reason,
                )
                refusal_rows.append(
                    {
                        "criterion_id": "C06",
                        "editor_id": editor_id,
                        "outcome": "failed",
                        "failure_reason": json.loads(path.read_text())["failure_reason"],
                        "failure_reasons": json.loads(path.read_text()).get("failure_reasons", []),
                        "attempt_file": _attempt_ref(path),
                    }
                )

        for cid in ("C07", "C08", "C09", "C10", "C22", "C23"):
            boundary, layer = {
                "C07": ("input_to_next_paint", "browser_visible"),
                "C22": ("input_to_next_paint", "browser_visible"),
            }.get(cid, ("input_to_next_paint", "browser_visible"))
            env = _env_for(
                editor_id=editor_id,
                editor_version=editor_version,
                fixture_sha256=sha,
                workload_row=workload_row,
                docx_size=docx_size,
                cache_state="warm_steady",
            )
            path = _write_not_run(
                attempt_dir=attempt_dir,
                criterion_id=cid,
                layer=layer,
                boundary=boundary,
                editor_id=editor_id,
                lane=lane,
                env=env,
                failure_reason="adapter-not-implemented: criterion %s not driven on warm_cold host yet" % cid,
            )
            refusal_rows.append(
                {
                    "criterion_id": cid,
                    "editor_id": editor_id,
                    "outcome": "not_run",
                    "failure_reason": "adapter-not-implemented: criterion %s not driven on warm_cold host yet" % cid,
                    "attempt_file": _attempt_ref(path),
                }
            )

    driver_checks: list[dict] = []
    if "plate" in editors:
        proc = None
        try:
            target = {**BROWSER_TARGETS["plate"], "driver": "puppeteer"}
            proc = _start_server("plate", target)
            puppeteer_payload = _run_browser_probe(
                target=target,
                corpus_path=fixture_path,
                pairs=1,
            )
            pair0 = puppeteer_payload["pairs"][0]
            driver_checks.append(
                {
                    "editor_id": "plate",
                    "driver": "puppeteer",
                    "c05_cold_ms": pair0["cold"].get("single_edit_ms"),
                    "c05_warm_ms": pair0["warm"].get("single_edit_ms"),
                }
            )
        except Exception as exc:
            driver_checks.append({"editor_id": "plate", "puppeteer_error": str(exc)})
        finally:
            if proc is not None:
                _stop_server(proc)

    validate_ready_attempts(json.loads(path.read_text()) for path in attempt_dir.glob("*.json"))

    summary = {
        "suite": "warm_cold",
        "execution_profile": execution_profile(EXECUTION_PROFILE),
        "host_class": host_class(),
        "workload_id": args.workload,
        "fixture_sha256": sha,
        "publishable": False,
        "pairs_per_cell": args.pairs,
        "paired": paired_rows,
        "editors": summary_editors + refusal_rows,
        "host": {
            "os": sys.platform,
            "arch": platform.machine(),
            "cpu_model": _host_cpu_model(),
            "ram_bytes": _ram_bytes(),
        },
        "driver_checks": driver_checks,
        "commands": [
            "PYTHONPATH=. python3 perf/runner/benchmark_warm_cold.py --pairs %d" % args.pairs,
            "PYTHONPATH=. python3 -m unittest discover -s perf/tests -q",
            "python3 -I build/test_perf_plan_coverage.py",
        ],
    }
    out_root.mkdir(parents=True, exist_ok=True)
    write_json(out_root / "summary.json", summary)
    print("Wrote %s" % (out_root / "summary.json",))
    return 0


def _host_cpu_model() -> str:
    """CPU brand string from ``perf.runner.host`` (``platform.processor()`` is "arm")."""
    return _contract_host()["cpu_model"]


def main() -> int:
    return run_cli(_main, 'benchmark_warm_cold', BROWSER_TARGETS, count_flag='--pairs', default_count=3, single=False)


if __name__ == "__main__":
    raise SystemExit(main())
