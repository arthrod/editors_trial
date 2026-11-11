#!/usr/bin/env python3
"""C24 — Rust/TS/WASM overhead, measured through each editor's own WASM module.

C24 is a ``wasm_boundary`` criterion: it may claim compile, instantiate, call,
copy and ``memory.grow`` across the host boundary, and nothing about typing
latency (``perf/README.md``). The repetition unit is ``in_process_iteration``
and the cache state is ``warm_steady``: one compile, then warm in-process
repetitions against the instance the editor page is already running.

What this runner does, per editor:

1. starts the editor's own browser host (``harness/ui`` host, untouched),
2. opens it in Playwright and waits for the editor's own ready signal,
3. reaches the *already initialized* WASM instance in that page — WordCraft
   publishes its exports on the Trunk boot event, Docxodus's managed bridge is
   reachable from the page's own module (``getWasmExports()``),
4. runs each operation warm, asserting the call returns the expected value
   before a sample is recorded (``perf/runner/wasm_host.mjs``),
5. writes one immutable attempt per operation and the support/refusal table.

An operation this runner cannot measure for an editor is recorded as
``unsupported`` with the exact reason (`CAPABILITIES`); an editor with no C24
adapter is recorded ``not_applicable`` (`REFUSALS`). Neither is a zero.

Usage (from the repo root, ``PYTHONPATH=.``):

    python3 perf/runner/wasm_boundary.py --list
    python3 perf/runner/wasm_boundary.py --editors wordcraft --samples 5
    python3 perf/runner/wasm_boundary.py --editors wordcraft docxodus
"""

from __future__ import annotations

import argparse
import hashlib
import json
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

from perf.adapters.capabilities import LANES, default_lane, pin_label  # noqa: E402
from perf.analysis.publication_gate import trial_publishable_flags  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402
from perf.fixtures.generate import build_workload, correctness_fixtures, docx_zip_bytes  # noqa: E402
from perf.fixtures.profiles import size_ladder  # noqa: E402
from perf.layers.wasm import assert_wasm_report, required_wasm_operations  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.load_timeouts import load_timeout_ms  # noqa: E402
from perf.runner.benchmark_ci_contract import (  # noqa: E402
    INTERPRETATION_CONDITIONS,
    _finalize_publishable,
    _host_base,
    _ram_bytes,
    _host as _contract_host,
    _trial_dict,
)
from perf.runner.harness_ui_versions import browser_harness_editor_version  # noqa: E402
from perf.schema import validate_environment, validate_sample_budget, validate_trial  # noqa: E402

UI = REPO / "harness" / "ui"
PROBE = REPO / "perf" / "runner" / "wasm_host.mjs"

OPERATIONS = list(required_wasm_operations())
CRITERION_ID = "C24"
LAYER = "wasm_boundary"
BOUNDARY = "wasm_call"
EXECUTION_PROFILE = "ci_contract"
CACHE_STATE = "warm_steady"
REPETITION_UNIT = "in_process_iteration"
WORKLOAD_ID = "micro-paragraphs"

DEFAULT_SAMPLES = 5
DEFAULT_COMPILE_SAMPLES = 3
MUTATION_SAMPLES = 3

STRING_FIXTURE = "C24 wasm boundary \u2713 \u6f22\u5b57 \u00e9"
F64_FIXTURE = [0.0, 1.0, -1.5, 3.25, 1e-9, 12345.6789, -2.5e300, 0.1]

# Editors whose WASM surface this runner can reach, with one spec per operation.
# `technique` names a fixed routine in perf/runner/wasm_host.mjs; nothing here is
# a free-form script, and every routine asserts a correct return value.
EDITORS: dict[str, dict] = {
    "wordcraft": {
        "lane": "wasm_ui",
        "cwd": UI / "wordcraft-host",
        "command": ["node", "server.mjs"],
        "url": "http://127.0.0.1:5219/",
        "ready_selector": '#wc-ready[data-state="rendered"]',
        "ready_js": "window.__WORDCRAFT_READY__ === true",
        "ready_timeout_ms": 180000,
        "corpus_route": "/corpus.docx",
        "surface": "exports",
        "require_export": "__wbindgen_malloc",
        "module_url_regex": "_bg\\.wasm(\\?|$)",
        "surface_note": (
            "Rust/wasm-bindgen cdylib: the page's Trunk boot event carries the live exports "
            "(window.wasmBindings is the JS glue; detail.wasm is the instance exports). "
            "__wbindgen_malloc/__wbindgen_realloc/__wbindgen_free and memory are the exact "
            "primitives the app's glue uses for every string and array it passes in or out."
        ),
        "ops": {
            "compile_and_instantiate": {
                "technique": "compile_instantiate",
                "warmup": 1,
            },
            "empty_call": {
                "technique": "export_call_void",
                "basis": "amortized_per_call",
                "export": "__wbindgen_exn_store",
                "args": [0],
                "note": "the export the glue calls before every exception-bearing import; one i32 in, no return",
            },
            "scalar_call": {
                "technique": "malloc_scalar",
                "basis": "amortized_per_call",
                "malloc": "__wbindgen_malloc",
                "free": "__wbindgen_free",
                "size": 64,
                "align": 8,
                "note": "i32 (size, align) -> i32 pointer, freed outside the timed call",
            },
            "string_conversion": {
                "technique": "string_alloc_roundtrip",
                "basis": "amortized_per_call",
                "malloc": "__wbindgen_malloc",
                "free": "__wbindgen_free",
                "text": STRING_FIXTURE,
                "note": "UTF-8 string -> malloc -> linear memory -> decode -> free (the wasm-bindgen &str path)",
            },
            "typed_array_transfer": {
                "technique": "f64_roundtrip",
                "basis": "amortized_per_call",
                "malloc": "__wbindgen_malloc",
                "free": "__wbindgen_free",
                "values": F64_FIXTURE,
                "note": "Float64Array -> 64 bytes of linear memory -> Float64Array, compared with Object.is",
            },
            "batched_call": {
                "technique": "batch_malloc",
                "basis": "per_batch",
                "malloc": "__wbindgen_malloc",
                "free": "__wbindgen_free",
                "size": 64,
                "align": 8,
                "note": "malloc+write+read+free cycles; one sample is the whole batch, batch size calibrated and recorded",
            },
            "memory_grow": {
                "technique": "memory_grow",
                "basis": "single_call",
                "calls": 1,
                "pages": 1,
                "warmup": 0,
                "samples": MUTATION_SAMPLES,
                "note": "memory.grow(1) on the live instance; returns the previous page count",
            },
        },
    },
    "docxodus": {
        "lane": "wasm_editor",
        "cwd": UI / "docxodus",
        "command": ["pnpm", "exec", "vite", "--port", "5210", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5210/",
        "ready_selector": "#status",
        "ready_js": (
            "window.__docxodus && window.__docxodus.rendered"
        ),
        "ready_timeout_ms": 240000,
        "corpus_route": "/corpus.docx",
        "surface": "bridge",
        "bridge_url_regex": "docxodus/dist/(index|core)\\.js",
        "module_url_regex": "dotnet\\.native\\.wasm(\\.br)?(\\?|$)",
        "surface_note": (
            ".NET (browser-wasm 10.0.14) runtime: the page's own module is re-imported by URL, "
            "so getWasmExports() returns the *already initialized* bridge (DocumentConverter, "
            "DocxSessionBridge, DocxDiffBridge, HistoryBridge) — no second runtime, no repo edit. "
            "compile_and_instantiate re-instantiates dotnet.native.wasm with the import object "
            "dotnet.js handed it."
        ),
        "ops": {
            "compile_and_instantiate": {
                "technique": "compile_instantiate",
                "warmup": 1,
            },
            "empty_call": {
                "technique": "bridge_nullary",
                "basis": "amortized_per_call",
                "call": "DocumentComparer.Warmup",
                "expect": "ok",
                "note": "nullary [JSExport]; after the first call it returns the cached \"ok\" (ComparisonEngine.EnsureWarm)",
            },
            "string_conversion": {
                "technique": "bridge_json",
                "basis": "amortized_per_call",
                "call": "DocumentConverter.GetVersion",
                "require_keys": ["Library", "DotnetVersion", "Platform"],
                "expect_library": "Docxodus WASM",
                "note": "managed JSON string built in .NET and marshalled to JS each call, parsed and checked",
            },
            "batched_call": {
                "technique": "bridge_batch",
                "basis": "per_batch",
                "call": "DocumentConverter.GetVersion",
                "note": "boundary crossings per sample; one sample is the whole batch, batch size calibrated and recorded",
            },
        },
    },
}

# Operations an adapter cannot express, with the exact reason. `null` in the
# wasm report (perf/layers/wasm.py capabilities) — never a fabricated sample.
CAPABILITIES: dict[str, dict[str, str]] = {
    "wordcraft": {},
    "docxodus": {
        "scalar_call": (
            "docxodus's bridge has no numeric-in/numeric-out entry point: every [JSExport] in "
            "repos/docxodus/wasm/DocxodusWasm takes byte[]/string/int handles and returns string, "
            "byte[] or void; the closest scalar return is DocxSessionBridge.Exists(handle, anchorId) "
            "-> bool, which needs an opened document session and takes a string, so it measures a "
            "document lookup rather than a scalar call. Recorded unavailable instead of mislabelled."
        ),
        "typed_array_transfer": (
            "the only byte[] (Uint8Array) argument path is a whole document operation "
            "(GeneratePackageManifest / ConvertDocxToHtml / ConvertWmlToMarkdown), whose parse "
            "dominates the copy; isolating the transfer would need a private export added to "
            "repos/docxodus, which is out of bounds."
        ),
        "memory_grow": (
            "the .NET runtime's linear memory is owned by dotnet.js; the product exposes no growth "
            "path, and growing it from the page would measure a path the editor never takes."
        ),
    },
}

# Why every other editor in the harness has no C24 measurement here.
REGISTRY_NOT_APPLICABLE = "perf/adapters/capabilities.py records this lane's wasm feature as not_applicable"
NO_ADAPTER = (
    "no C24 adapter in this runner: C24 is implemented for the two hosts the task scopes — "
    "wordcraft (wasm_ui) and docxodus (wasm_editor); no probe was written for this lane"
)
REFUSALS: dict[str, str] = {
    "plate": REGISTRY_NOT_APPLICABLE,
    "canvas": REGISTRY_NOT_APPLICABLE,
    "office-open": REGISTRY_NOT_APPLICABLE,
    "apryse": (
        "WebViewer's wasm sits behind the licensed SDK bundle; harness/apryse has no viewer assets "
        "on this host (no APRYSE/PDFTRON key in the environment) and the harness records Apryse "
        "not_run, so the module URL never loads"
    ),
    "superdoc": NO_ADAPTER,
    "folio": NO_ADAPTER,
    "genoffice": NO_ADAPTER,
    "eigenpal": NO_ADAPTER,
    "docen": NO_ADAPTER,
    "fidus": NO_ADAPTER,
    "docsplus": NO_ADAPTER,
    "libreoffice": (
        "LibreOffice is a native soffice process, not a WASM module; C24's wasm_call boundary does "
        "not exist on this lane"
    ),
}


# --------------------------------------------------------------------------- #
# probe payload validation (imported by perf/tests/test_wasm_boundary.py)
# --------------------------------------------------------------------------- #


def capabilities_for(editor_id: str) -> dict[str, bool]:
    refused = CAPABILITIES.get(editor_id, {})
    return {name: name not in refused for name in OPERATIONS}


def assert_probe_payload(payload: dict, editor_id: str, expected_samples: dict[str, int]) -> dict:
    """Validate the probe's raw payload; return ``{operation: samples}``.

    Raises instead of recording when a measured operation has no samples, a
    non-numeric sample, a failing correctness assertion, the wrong repetition
    count, or a sample list copied from another operation.
    """
    if payload.get("schema") != "c24-wasm-host/1":
        raise ValueError("probe schema %r" % (payload.get("schema"),))
    if payload.get("editor_id") != editor_id:
        raise ValueError("probe editor_id %r != %r" % (payload.get("editor_id"), editor_id))
    capabilities = capabilities_for(editor_id)
    ops = payload.get("ops") or {}
    report: dict[str, list[float]] = {}
    seen: dict[tuple[float, ...], str] = {}
    for name in OPERATIONS:
        if not capabilities[name]:
            if name in ops:
                raise ValueError("%s was refused for %s but the probe returned %r" % (name, editor_id, ops[name]))
            report[name] = None
            continue
        entry = ops.get(name)
        if entry is None:
            raise ValueError("%s/%s: operation missing from the probe payload" % (editor_id, name))
        if entry.get("error"):
            raise ValueError("%s/%s: probe reported %s" % (editor_id, name, entry["error"]))
        correctness = entry.get("correctness") or {}
        if correctness.get("ok") is not True:
            raise ValueError(
                "%s/%s: correctness assertion failed (expected %r, observed %r)"
                % (editor_id, name, correctness.get("expected"), correctness.get("observed"))
            )
        samples = entry.get("samples_ms")
        if not isinstance(samples, list) or not samples:
            raise ValueError("%s/%s: no samples recorded" % (editor_id, name))
        for sample in samples:
            if isinstance(sample, bool) or not isinstance(sample, (int, float)):
                raise ValueError("%s/%s: non-numeric sample %r" % (editor_id, name, sample))
            if sample != sample or sample in (float("inf"), float("-inf")) or sample < 0:
                raise ValueError("%s/%s: sample not finite non-negative" % (editor_id, name))
        want = expected_samples.get(name)
        if want is not None and len(samples) != want:
            raise ValueError(
                "%s/%s: expected %d samples, probe returned %d" % (editor_id, name, want, len(samples))
            )
        # Duplicated evidence — the same call recorded twice under two names — is
        # the fabrication this guard exists for. Two cheap operations may honestly
        # share a sample list on a quantised clock; they cannot also share the
        # technique and the observed return value.
        key = (
            tuple(round(float(s), 6) for s in samples),
            json.dumps(correctness.get("observed"), sort_keys=True, default=str),
        )
        if key in seen:
            raise ValueError(
                "%s/%s: identical samples and identical observed value as %s — copied samples are not a measurement"
                % (editor_id, name, seen[key])
            )
        seen[key] = name
        report[name] = [float(s) for s in samples]
    assert_wasm_report(report, capabilities)
    return report


def support_table() -> list[dict]:
    rows = []
    for editor_id in LANES:
        if editor_id in EDITORS:
            refused = CAPABILITIES.get(editor_id, {})
            rows.append(
                {
                    "editor_id": editor_id,
                    "lane": EDITORS[editor_id]["lane"],
                    "state": "supported" if len(refused) < len(OPERATIONS) else "refused",
                    "measured_operations": [n for n in OPERATIONS if n not in refused],
                    "refused_operations": {n: refused[n] for n in OPERATIONS if n in refused},
                    "reason": None,
                }
            )
        else:
            rows.append(
                {
                    "editor_id": editor_id,
                    "lane": default_lane(editor_id),
                    "state": "refused",
                    "measured_operations": [],
                    "refused_operations": {n: REFUSALS.get(editor_id, NO_ADAPTER) for n in OPERATIONS},
                    "reason": REFUSALS.get(editor_id, NO_ADAPTER),
                }
            )
    return rows


# --------------------------------------------------------------------------- #
# harness plumbing
# --------------------------------------------------------------------------- #


def _attempt_ref(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return path.name


def _attempt_name(editor_id: str, operation: str) -> str:
    return "c24-%s-%s-%s" % (editor_id.lower(), operation.replace("_", "-"), uuid.uuid4().hex[:10])


def _spec_for(editor_id: str, corpus_path: Path, samples: int, compile_samples: int) -> dict:
    editor = EDITORS[editor_id]
    ops = []
    for name in OPERATIONS:
        raw = editor["ops"].get(name)
        if raw is None:
            continue
        op = dict(raw)
        op["name"] = name
        if name == "compile_and_instantiate":
            op["samples"] = compile_samples
        else:
            op.setdefault("samples", MUTATION_SAMPLES if name == "memory_grow" else samples)
        ops.append(op)
    return {
        "schema": "c24-wasm-host-spec/1",
        "editor_id": editor_id,
        "url": editor["url"],
        "ready_selector": editor.get("ready_selector"),
        "ready_js": editor.get("ready_js"),
        "ready_timeout_ms": editor.get("ready_timeout_ms"),
        # Lax layer (owner 2026-11-11): navigation waits are minutes, not
        # 120 s; recorded in the spec so the probe output discloses it.
        "nav_timeout_ms": load_timeout_ms(WORKLOAD_ID),
        "corpus_path": str(corpus_path),
        "corpus_route": editor.get("corpus_route"),
        "surface": editor["surface"],
        "require_export": editor.get("require_export"),
        "module_url_regex": editor.get("module_url_regex"),
        "bridge_url_regex": editor.get("bridge_url_regex"),
        "warmup": 3,
        "samples": samples,
        "compile_samples": compile_samples,
        "ops": ops,
    }


def _start_server(editor_id: str, target: dict) -> subprocess.Popen:
    cwd = target["cwd"]
    if not cwd.is_dir():
        raise FileNotFoundError("missing harness host %s" % (cwd,))
    env = dict(os.environ)
    env.setdefault("NODE_OPTIONS", "--no-deprecation")
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


def _stop_server(proc: subprocess.Popen) -> None:
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


def _run_probe(spec_path: Path) -> dict:
    node = shutil.which("node") or "node"
    proc = subprocess.run(
        [node, str(PROBE), "--spec", str(spec_path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if proc.returncode != 0:
        raise RuntimeError("wasm_host failed: %s" % ((proc.stderr or proc.stdout or "")[-2000:],))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("wasm_host returned non-JSON output: %s" % (proc.stdout[:500],)) from exc


def _env_for(
    *,
    editor_id: str,
    editor_version: str,
    fixture_sha256: str,
    docx_size: int,
) -> dict:
    workload_row = next(w for w in size_ladder() if w["workload_id"] == WORKLOAD_ID)
    env = _host_base(
        editor_id=editor_id,
        editor_version=editor_version,
        execution_profile=EXECUTION_PROFILE,
        fixture_sha256=fixture_sha256,
        workload_row=workload_row,
        docx_size=docx_size,
        cache_state=CACHE_STATE,
        repetition_unit=REPETITION_UNIT,
        run_kind="timing",
        feature_profile_name="P0",
    )
    env["interpretation_conditions"] = list(INTERPRETATION_CONDITIONS)
    return env


def _write_measured(
    attempt_dir: Path,
    *,
    operation: str,
    editor_id: str,
    lane: str,
    editor_version: str,
    env: dict,
    samples: list[float],
    entry: dict,
    module: dict | None,
    live_surface: dict | None,
    surface_note: str,
    calls_per_sample: int,
    clock: dict | None = None,
) -> Path:
    validate_sample_budget(env, len(samples))
    stats = summarize(samples, CACHE_STATE, REPETITION_UNIT, seed=0)
    pub, reason = trial_publishable_flags(env, LAYER, stats["n"])
    pub, reason = _finalize_publishable(pub, reason, env)
    trial = _trial_dict(
        criterion_id=CRITERION_ID,
        layer=LAYER,
        boundary=BOUNDARY,
        outcome="measured",
        env=env,
        samples_ms=samples,
        editor_id=editor_id,
        lane=lane,
        summary_stats=stats,
        publishable=pub,
        publication_block_reason=reason,
        diagnostic={
            "suite": "wasm_boundary",
            "operation": operation,
            "technique": entry.get("technique"),
            "surface": entry.get("surface"),
            "surface_note": surface_note,
            "calls_per_sample": calls_per_sample,
            "sample_basis": entry.get("sample_basis"),
            "correctness": entry.get("correctness"),
            "module": module,
            "live_surface": live_surface,
            "clock": clock,
            "editor_version": editor_version,
            "probe": "perf/runner/wasm_host.mjs",
        },
    )
    validate_trial(trial)
    return write_attempt(attempt_dir, _attempt_name(editor_id, operation), trial)


def _write_non_measured(
    attempt_dir: Path,
    *,
    operation: str,
    editor_id: str,
    lane: str,
    env: dict,
    outcome: str,
    reason: str,
    module: dict | None = None,
    live_surface: dict | None = None,
) -> Path:
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("a non-measured C24 cell needs a failure_reason")
    trial = _trial_dict(
        criterion_id=CRITERION_ID,
        layer=LAYER,
        boundary=BOUNDARY,
        outcome=outcome,
        env=env,
        samples_ms=[],
        failure_reason=reason,
        editor_id=editor_id,
        lane=lane,
        diagnostic={
            "suite": "wasm_boundary",
            "operation": operation,
            "module": module,
            "live_surface": live_surface,
            "probe": "perf/runner/wasm_host.mjs",
        },
    )
    validate_environment(env)
    validate_trial(trial)
    return write_attempt(attempt_dir, _attempt_name(editor_id, operation), trial)


def main() -> int:
    parser = argparse.ArgumentParser(description="C24 WASM boundary runner")
    parser.add_argument("--editors", nargs="*", default=None, help="editor ids (default: the adapted ones)")
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES, help="warm repetitions per operation")
    parser.add_argument("--compile-samples", type=int, default=DEFAULT_COMPILE_SAMPLES,
                        help="compile+instantiate repetitions (each compiles the whole module)")
    parser.add_argument("--out-root", type=Path, default=None)
    parser.add_argument("--list", action="store_true", help="print the support/refusal table and exit")
    args = parser.parse_args()

    if args.list:
        for row in support_table():
            if row["state"] == "supported":
                detail = "measured: %s" % (", ".join(row["measured_operations"]),)
                refused = row["refused_operations"]
                if refused:
                    detail += " | refused: %s" % (", ".join(refused),)
            else:
                detail = row["reason"]
            print("%-12s %-12s %-9s %s" % (row["editor_id"], row["lane"], row["state"], detail))
        return 0

    editors = args.editors or list(EDITORS)
    unknown = [e for e in editors if e not in LANES]
    if unknown:
        parser.error("unknown editor(s): %s" % (", ".join(unknown),))

    workload_row = next(w for w in size_ladder() if w["workload_id"] == WORKLOAD_ID)
    built = build_workload(workload_row)
    cfs = correctness_fixtures()
    docx_body = docx_zip_bytes(built["body"] + b"\n" + cfs["unicode"])
    sha = hashlib.sha256(docx_body).hexdigest()
    docx_size = len(docx_body)

    run_day = date.today().isoformat().replace("-", "_")
    out_root = args.out_root or (REPO / "perf" / "out" / ("wasm_boundary_%s" % run_day))
    attempt_dir = out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = out_root / ("%s.docx" % WORKLOAD_ID)
    if not fixture_path.is_file():
        fixture_path.write_bytes(docx_body)

    summary_rows: list[dict] = []
    clock: dict | None = None
    for editor_id in editors:
        lane = EDITORS[editor_id]["lane"] if editor_id in EDITORS else default_lane(editor_id)
        trial_pin = pin_label(editor_id)
        editor_version, harness_meta = browser_harness_editor_version(editor_id, trial_pin)
        env = _env_for(
            editor_id=editor_id,
            editor_version=editor_version,
            fixture_sha256=sha,
            docx_size=docx_size,
        )

        if editor_id not in EDITORS:
            reason = REFUSALS.get(editor_id, NO_ADAPTER)
            for operation in OPERATIONS:
                path = _write_non_measured(
                    attempt_dir,
                    operation=operation,
                    editor_id=editor_id,
                    lane=lane,
                    env=env,
                    outcome="not_applicable",
                    reason=reason,
                )
                summary_rows.append(
                    {
                        "editor_id": editor_id,
                        "operation": operation,
                        "outcome": "not_applicable",
                        "failure_reason": reason,
                        "attempt_file": _attempt_ref(path),
                    }
                )
            continue

        spec = _spec_for(editor_id, fixture_path, args.samples, args.compile_samples)
        spec_path = out_root / ("spec-%s.json" % editor_id)
        spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

        proc = None
        payload = None
        failure = None
        try:
            proc = _start_server(editor_id, EDITORS[editor_id])
            payload = _run_probe(spec_path)
        except Exception as exc:  # noqa: BLE001 - recorded verbatim, never a sample
            failure = "wasm_host: %s" % (exc,)
        finally:
            if proc:
                _stop_server(proc)

        if failure is None and payload and payload.get("failure"):
            failure = "wasm_host page: %s" % (payload["failure"],)
        if failure is None and payload:
            clock = payload.get("clock")

        if failure is not None:
            for operation in OPERATIONS:
                if operation in CAPABILITIES.get(editor_id, {}):
                    path = _write_non_measured(
                        attempt_dir,
                        operation=operation,
                        editor_id=editor_id,
                        lane=lane,
                        env=env,
                        outcome="unsupported",
                        reason=CAPABILITIES[editor_id][operation],
                    )
                    summary_rows.append(
                        {
                            "editor_id": editor_id,
                            "operation": operation,
                            "outcome": "unsupported",
                            "failure_reason": CAPABILITIES[editor_id][operation],
                            "attempt_file": _attempt_ref(path),
                        }
                    )
                    continue
                path = _write_non_measured(
                    attempt_dir,
                    operation=operation,
                    editor_id=editor_id,
                    lane=lane,
                    env=env,
                    outcome="failed",
                    reason=failure,
                )
                summary_rows.append(
                    {
                        "editor_id": editor_id,
                        "operation": operation,
                        "outcome": "failed",
                        "failure_reason": failure,
                        "attempt_file": _attempt_ref(path),
                    }
                )
            continue

        expected = {}
        for op in spec["ops"]:
            expected[op["name"]] = int(op["samples"])
        try:
            report = assert_probe_payload(payload, editor_id, expected)
        except ValueError as exc:
            for operation in OPERATIONS:
                path = _write_non_measured(
                    attempt_dir,
                    operation=operation,
                    editor_id=editor_id,
                    lane=lane,
                    env=env,
                    outcome="failed",
                    reason="probe payload rejected: %s" % (exc,),
                    module=payload.get("module"),
                    live_surface=payload.get("live_surface"),
                )
                summary_rows.append(
                    {
                        "editor_id": editor_id,
                        "operation": operation,
                        "outcome": "failed",
                        "failure_reason": "probe payload rejected: %s" % (exc,),
                        "attempt_file": _attempt_ref(path),
                    }
                )
            continue

        for operation in OPERATIONS:
            if operation in CAPABILITIES.get(editor_id, {}):
                reason = CAPABILITIES[editor_id][operation]
                path = _write_non_measured(
                    attempt_dir,
                    operation=operation,
                    editor_id=editor_id,
                    lane=lane,
                    env=env,
                    outcome="unsupported",
                    reason=reason,
                    module=payload.get("module"),
                    live_surface=payload.get("live_surface"),
                )
                summary_rows.append(
                    {
                        "editor_id": editor_id,
                        "operation": operation,
                        "outcome": "unsupported",
                        "failure_reason": reason,
                        "attempt_file": _attempt_ref(path),
                    }
                )
                continue
            entry = payload["ops"][operation]
            samples = report[operation]
            quantum = (clock or {}).get("quantum_ms")
            path = _write_measured(
                attempt_dir,
                operation=operation,
                editor_id=editor_id,
                lane=lane,
                editor_version=editor_version,
                env=env,
                samples=samples,
                entry=entry,
                module=payload.get("module"),
                live_surface=payload.get("live_surface"),
                surface_note=EDITORS[editor_id]["surface_note"],
                calls_per_sample=int(entry.get("calls_per_sample") or 1),
                clock=clock,
            )
            summary_rows.append(
                {
                    "editor_id": editor_id,
                    "operation": operation,
                    "outcome": "measured",
                    "samples_ms": samples,
                    "median_ms": summarize(samples, CACHE_STATE, REPETITION_UNIT, seed=0)["median"],
                    "calls_per_sample": int(entry.get("calls_per_sample") or 1),
                    "sample_basis": entry.get("sample_basis"),
                    "correctness": entry.get("correctness"),
                    "below_clock_quantum": bool(
                        quantum
                        and str(entry.get("sample_basis")) == "single_call"
                        and summarize(samples, CACHE_STATE, REPETITION_UNIT, seed=0)["median"] <= quantum
                    ),
                    "attempt_file": _attempt_ref(path),
                    "harness_version": harness_meta,
                }
            )

    summary = {
        "suite": "wasm_boundary",
        "criterion_id": CRITERION_ID,
        "layer": LAYER,
        "boundary": BOUNDARY,
        "execution_profile": EXECUTION_PROFILE,
        "host_class": "ci_coarse",
        "repetition_unit": REPETITION_UNIT,
        "cache_state": CACHE_STATE,
        "workload_id": WORKLOAD_ID,
        "fixture_sha256": sha,
        "clock": clock,
        "publishable": False,
        "publication_block_reason": "ci_coarse host_class blocks headline publication",
        "samples_requested": args.samples,
        "compile_samples_requested": args.compile_samples,
        "results": summary_rows,
        "support_table": support_table(),
        "host": {
            "os": sys.platform,
            "arch": platform.machine(),
            "cpu_model": _host_cpu_model(),
            "ram_bytes": _ram_bytes(),
        },
        "commands": [
            "PYTHONPATH=. python3 perf/runner/wasm_boundary.py --editors %s" % (" ".join(editors),),
            "PYTHONPATH=. python3 -m unittest perf.tests.test_wasm_boundary -q",
        ],
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("Wrote %s" % (out_root / "summary.json",))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def _host_cpu_model() -> str:
    """CPU brand string from ``perf.runner.host`` (``platform.processor()`` is "arm")."""
    return _contract_host()["cpu_model"]
