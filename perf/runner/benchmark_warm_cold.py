#!/usr/bin/env python3
"""Warm vs non-warm browser contrast on harness UI hosts (Playwright / Puppeteer)."""

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

from perf.adapters.capabilities import default_lane, pin_label  # noqa: E402
from perf.runner.harness_ui_versions import browser_harness_editor_version  # noqa: E402
from perf.analysis.publication_gate import trial_publishable_flags  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402
from perf.fixtures.generate import build_workload, correctness_fixtures, docx_zip_bytes  # noqa: E402
from perf.fixtures.profiles import assert_workload_allowed, feature_profile, size_ladder  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.benchmark_ci_contract import (  # noqa: E402
    INTERPRETATION_CONDITIONS,
    _finalize_publishable,
    _host_base,
    _ram_bytes,
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
from perf.schema import validate_environment, validate_trial  # noqa: E402

UI = REPO / "harness" / "ui"
PROBE = REPO / "perf" / "runner" / "warm_cold_browser.mjs"

PAIR_SAMPLES = 3
EXECUTION_PROFILE = "ci_broad"
HOST_CLASS = "ci_coarse"

# Editors with a harness/ui dev server target (Microsoft Word and CLI-only lanes omitted).
BROWSER_TARGETS: dict[str, dict] = {
    "plate": {
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
        },
    },
    "superdoc": {
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
        },
    },
    "genoffice": {
        "cwd": UI / "genoffice",
        "command": ["npm", "exec", "--", "vite", "--config", "vite.config.mjs", "--port", "5201", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5201/",
        "corpus_route": "/corpus.docx",
        "ready_selector": ".doc-page",
        "wait_after_ready": "8000",
        "edit_selector": ".doc-page",
        "driver": "playwright",
        "env": {"GENOFFICE_REPO": str(REPO / "repos" / "genoffice")},
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
        },
    },
    "canvas": {
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
}


def _apryse_key_present() -> bool:
    for name in ("APRYSE_LICENSE_KEY", "PDFTRON_LICENSE_KEY", "TRIAL_KEY"):
        if os.environ.get(name, "").strip():
            return True
    return False


def _attempt_ref(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return path.name


def _start_server(editor_id: str, target: dict) -> subprocess.Popen:
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


def _run_browser_probe(
    *,
    target: dict,
    corpus_path: Path,
    pairs: int,
) -> dict:
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
    proc = subprocess.run(
        cmd,
        cwd=str(UI),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "probe failed")
    return json.loads(proc.stdout)


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
    stats = summarize(samples_ms, cache_state, env["repetition_unit"], seed=0)
    pub, reason = trial_publishable_flags(env, layer, stats["n"])
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
    validate_trial(trial)
    return write_attempt(
        attempt_dir,
        "%s-%s-%s" % (criterion_id.lower(), editor_id, uuid.uuid4().hex[:10]),
        trial,
    )


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
    return write_attempt(
        attempt_dir,
        "%s-%s-%s" % (criterion_id.lower(), editor_id, uuid.uuid4().hex[:10]),
        trial,
    )


def _env_for(
    *,
    editor_id: str,
    editor_version: str,
    fixture_sha256: str,
    workload_row: dict,
    docx_size: int,
    cache_state: str,
    execution_profile: str | None = None,
    host_class: str | None = None,
) -> dict:
    env = _host_base(
        editor_id=editor_id,
        editor_version=editor_version,
        execution_profile=execution_profile or EXECUTION_PROFILE,
        fixture_sha256=fixture_sha256,
        workload_row=workload_row,
        docx_size=docx_size,
        cache_state=cache_state,
        repetition_unit="fresh_process",
        run_kind="timing",
        feature_profile_name="P0",
    )
    env["interpretation_conditions"] = list(INTERPRETATION_CONDITIONS)
    env["host_class"] = host_class or HOST_CLASS
    env["headless"] = True
    env["display_refresh_hz"] = None
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", default="micro-paragraphs")
    parser.add_argument("--out-root", type=Path, default=None)
    parser.add_argument("--pairs", type=int, default=PAIR_SAMPLES)
    parser.add_argument("--editors", nargs="*", default=None)
    parser.add_argument("--execution-profile", default=EXECUTION_PROFILE)
    parser.add_argument("--host-class", default=HOST_CLASS)
    args = parser.parse_args()
    global EXECUTION_PROFILE, HOST_CLASS
    EXECUTION_PROFILE = args.execution_profile
    HOST_CLASS = args.host_class

    workload_row = next(w for w in size_ladder() if w["workload_id"] == args.workload)
    assert_workload_allowed(EXECUTION_PROFILE, args.workload)
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
    fixture_path = out_root / "micro-paragraphs.docx"
    if not fixture_path.is_file():
        fixture_path.write_bytes(docx_body)

    editors = args.editors or list(BROWSER_TARGETS.keys())
    paired_rows: list[dict] = []
    summary_editors: list[dict] = []
    not_run_rows: list[dict] = []

    for editor_id in editors:
        lane = default_lane(editor_id)
        trial_pin = pin_label(editor_id)
        editor_version, harness_meta = browser_harness_editor_version(editor_id, trial_pin)
        if editor_id == "apryse" and not _apryse_key_present():
            reason = "apryse: trial key not present in environment"
            for cid, (boundary, layer) in {
                "C03": ("first_usable", "browser_visible"),
                "C05": ("presented_frame", "browser_visible"),
            }.items():
                env = _env_for(
                    editor_id=editor_id,
                    editor_version=editor_version,
                    fixture_sha256=sha,
                    workload_row=workload_row,
                    docx_size=docx_size,
                    cache_state="process_cold_fs_warm",
                )
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
                not_run_rows.append(
                    {
                        "criterion_id": cid,
                        "editor_id": editor_id,
                        "outcome": "not_run",
                        "failure_reason": reason,
                        "attempt_file": _attempt_ref(path),
                    }
                )
            continue

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
                not_run_rows.append(
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
                not_run_rows.append(
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
            not_run_rows.append(row)

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
                },
            )
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
        if reload_samples and cold_first and "C03" in criteria_map:
            cause_load, breakdown = attribute_delta(
                median(cold_first), median(reload_samples), probe_bundle
            )
            paired_rows.append(
                _paired_summary_row(
                    criterion_id="C03",
                    editor_id=editor_id,
                    boundary="first_usable",
                    cold_median=median(cold_first),
                    warm_median=median(reload_samples),
                    cause=cause_load,
                    cold_path=c03_cold_attempt_ref,
                    warm_path=c03_cold_attempt_ref,
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
                not_run_rows.append(
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
            if len(cold_edits) < args.pairs or len(warm_edits) < args.pairs:
                reason = "adapter-not-implemented: edit probe returned no timings"
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
                    not_run_rows.append(
                        {
                            "criterion_id": cid,
                            "editor_id": editor_id,
                            "outcome": "not_run",
                            "failure_reason": reason,
                            "attempt_file": _attempt_ref(path),
                        }
                    )
                continue
            assert_warm_cold_distinct(cold_edits, warm_edits)

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
                diagnostic={"suite": "warm_cold", "phase": "non_warm_edit"},
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
                diagnostic={"suite": "warm_cold", "phase": "warm_edit"},
            )

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
                len(cold_burst) >= args.pairs
                and len(warm_burst) >= args.pairs
                and "C06" in criteria_map
            ):
                assert_same_probe_paired(C06_PROBE_KEY, C06_PROBE_KEY)
                assert_warm_cold_distinct(cold_burst, warm_burst)
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
                    },
                )
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
                reason = "adapter-not-implemented: sustained_typing burst probe incomplete"
                boundary, layer = ("input_to_next_paint", "browser_visible")
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
                    criterion_id="C06",
                    layer=layer,
                    boundary=boundary,
                    editor_id=editor_id,
                    lane=lane,
                    env=env,
                    failure_reason=reason,
                )
                not_run_rows.append(
                    {
                        "criterion_id": "C06",
                        "editor_id": editor_id,
                        "outcome": "not_run",
                        "failure_reason": reason,
                        "attempt_file": _attempt_ref(path),
                    }
                )

    driver_checks: list[dict] = []
    if "plate" in editors:
        try:
            target = BROWSER_TARGETS["plate"]
            proc = _start_server("plate", {**target, "driver": "puppeteer"})
            puppeteer_payload = _run_browser_probe(
                target={**target, "driver": "puppeteer"},
                corpus_path=fixture_path,
                pairs=1,
            )
            _stop_server(proc)
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

    from perf.runner.cause_attribution import assert_no_duplicate_c02_c03_in_dir  # noqa: E402

    assert_no_duplicate_c02_c03_in_dir(attempt_dir)

    summary = {
        "suite": "warm_cold",
        "execution_profile": EXECUTION_PROFILE,
        "host_class": HOST_CLASS,
        "workload_id": args.workload,
        "fixture_sha256": sha,
        "publishable": False,
        "pairs_per_cell": args.pairs,
        "paired": paired_rows,
        "editors": summary_editors + not_run_rows,
        "host": {
            "os": sys.platform,
            "arch": platform.machine(),
            "cpu_model": platform.processor() or "unknown",
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
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("Wrote %s" % (out_root / "summary.json",))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
