#!/usr/bin/env python3
"""C24 WASM boundary trials for docxodus (prebuilt dotnet.native.wasm)."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.analysis.summarize import summarize  # noqa: E402
from perf.analysis.publication_gate import trial_publishable_flags  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.benchmark_ci_contract import (  # noqa: E402
    _attempt_ref,
    _finalize_publishable,
    _host_base,
    _trial_dict,
)
from perf.fixtures.profiles import size_ladder  # noqa: E402
from perf.schema import sample_budget_for_profile, validate_trial  # noqa: E402

PROBE = REPO / "perf" / "runner" / "wasm_docxodus_probe.mjs"
WASM = REPO / "harness/ui/docxodus/node_modules/docxodus/dist/wasm/_framework/dotnet.native.wasm"
COLD_ITERATIONS = 3


def _wasm_meta(wasm_path: Path) -> dict:
    data = wasm_path.read_bytes()
    try:
        artifact = str(wasm_path.relative_to(REPO))
    except ValueError:
        artifact = str(wasm_path)
    return {
        "wasm_artifact": artifact,
        "wasm_byte_size": len(data),
        "wasm_sha256": hashlib.sha256(data).hexdigest(),
        "engine": "node",
    }


def _run_probe(node: str, *extra: str, timeout: int = 180) -> dict:
    proc = subprocess.run(
        [node, str(PROBE), *extra],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO / "harness/ui/docxodus"),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "probe failed")
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("probe returned empty stdout")
    return json.loads(lines[-1])


def _cold_init_samples(node: str, n: int) -> list[float]:
    out: list[float] = []
    for _ in range(n):
        payload = _run_probe(node, "--mode", "cold_init")
        out.extend(float(x) for x in payload["samples_ms"])
    return out


def _base_env(execution_profile: str, host_class: str) -> dict:
    env = _host_base(
        editor_id="docxodus",
        editor_version="15.0.0",
        execution_profile=execution_profile,
        fixture_sha256="0" * 64,
        workload_row=next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs"),
        docx_size=0,
        cache_state="process_cold_fs_warm",
        repetition_unit="in_process_iteration",
        run_kind="timing",
        feature_profile_name="P0",
    )
    env["host_class"] = host_class
    return env


def _write_summary(out_root: Path, rows: list[dict], wasm_meta: dict, publishable: bool) -> None:
    summary = {
        "suite": "c24_wasm",
        "measured_at": "2026-11-07",
        "publishable": publishable,
        "engine": wasm_meta.get("engine", "node"),
        "wasm_artifact": wasm_meta["wasm_artifact"],
        "wasm_byte_size": wasm_meta["wasm_byte_size"],
        "wasm_sha256": wasm_meta["wasm_sha256"],
        "operations": rows,
    }
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--execution-profile", default="ci_broad")
    parser.add_argument("--host-class", default="ci_coarse")
    args = parser.parse_args()
    attempt_dir = args.out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict] = []

    if not WASM.is_file():
        env = _base_env(args.execution_profile, args.host_class)
        trial = _trial_dict(
            criterion_id="C24",
            layer="wasm_boundary",
            boundary="wasm_call",
            outcome="not_run",
            env=env,
            samples_ms=[],
            failure_reason="wasm_boundary: missing prebuilt dotnet.native.wasm at %s" % WASM,
            editor_id="docxodus",
            lane="editor",
        )
        write_attempt(attempt_dir, "c24-docxodus-missing", trial)
        _write_summary(
            args.out_root,
            [
                {
                    "operation": "compile_and_instantiate",
                    "outcome": "not_run",
                    "failure_reason": trial["failure_reason"],
                }
            ],
            {"wasm_artifact": str(WASM), "wasm_byte_size": 0, "wasm_sha256": "", "engine": "node"},
            publishable=False,
        )
        return 0

    wasm_meta = _wasm_meta(WASM)
    node = shutil.which("node") or "node"
    budget = sample_budget_for_profile(args.execution_profile, "in_process_iteration")
    cold_n = max(COLD_ITERATIONS, min(budget, COLD_ITERATIONS))

    try:
        cold_samples = _cold_init_samples(node, cold_n)
    except RuntimeError as err:
        env = _base_env(args.execution_profile, args.host_class)
        trial = _trial_dict(
            criterion_id="C24",
            layer="wasm_boundary",
            boundary="compile_and_instantiate",
            outcome="not_run",
            env=env,
            samples_ms=[],
            failure_reason="wasm_boundary: %s" % err,
            editor_id="docxodus",
            lane="editor",
            diagnostic=wasm_meta,
        )
        write_attempt(attempt_dir, "c24-docxodus-init-fail", trial)
        _write_summary(
            args.out_root,
            [
                {
                    "operation": "compile_and_instantiate",
                    "outcome": "not_run",
                    "failure_reason": str(err),
                }
            ],
            wasm_meta,
            publishable=False,
        )
        return 0

    def record(op: str, samples_ms: list[float]) -> None:
        env = _base_env(args.execution_profile, args.host_class)
        stats = summarize(samples_ms, env["cache_state"], env["repetition_unit"], seed=1)
        pub, reason = trial_publishable_flags(env, "wasm_boundary", stats["n"])
        pub, reason = _finalize_publishable(pub, reason, env)
        diag = {**wasm_meta, "operation": op}
        trial = _trial_dict(
            criterion_id="C24",
            layer="wasm_boundary",
            boundary=op,
            outcome="measured",
            env=env,
            samples_ms=samples_ms,
            editor_id="docxodus",
            lane="editor",
            summary_stats=stats,
            publishable=False,
            publication_block_reason=reason or "ci_coarse host_class blocks headline publication",
            diagnostic=diag,
        )
        validate_trial(trial)
        path = write_attempt(attempt_dir, "c24-docxodus-%s-%s" % (op, uuid.uuid4().hex[:8]), trial)
        summary_rows.append(
            {
                "operation": op,
                "outcome": "measured",
                "samples_ms": samples_ms,
                "median_ms": stats["median"],
                "n": stats["n"],
                "attempt_file": _attempt_ref(path),
                "publishable": False,
            }
        )

    record("compile_and_instantiate", cold_samples)

    warm_payload = _run_probe(node, "--iterations", str(max(COLD_ITERATIONS, min(budget, 20))))
    for op, samples in warm_payload["samples_ms"].items():
        samples_ms = [float(x) for x in samples]
        if len(samples_ms) < COLD_ITERATIONS:
            raise SystemExit("%s returned %d samples; need >= %d" % (op, len(samples_ms), COLD_ITERATIONS))
        record(op, samples_ms)

    _write_summary(args.out_root, summary_rows, wasm_meta, publishable=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
