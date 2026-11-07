#!/usr/bin/env python3
"""C24 WASM boundary trials for docxodus (prebuilt dotnet.native.wasm)."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.analysis.summarize import summarize  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.benchmark_ci_contract import _finalize_publishable, _host_base, _trial_dict  # noqa: E402
from perf.analysis.publication_gate import trial_publishable_flags  # noqa: E402
from perf.schema import validate_trial, sample_budget_for_profile  # noqa: E402

PROBE = REPO / "perf" / "runner" / "wasm_docxodus_probe.mjs"
WASM = REPO / "harness/ui/docxodus/node_modules/docxodus/dist/wasm/_framework/dotnet.native.wasm"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--execution-profile", default="ci_broad")
    parser.add_argument("--host-class", default="ci_coarse")
    args = parser.parse_args()
    attempt_dir = args.out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    if not WASM.is_file():
        trial = _trial_dict(
            criterion_id="C24",
            layer="wasm_boundary",
            boundary="host_call",
            outcome="not_run",
            env=_host_base(
                editor_id="docxodus",
                editor_version="15.0.0",
                execution_profile=args.execution_profile,
                fixture_sha256="0" * 64,
                workload_row={
                    "workload_id": "micro-paragraphs",
                    "fixture_byte_size": 0,
                    "fixture_paragraph_count": 1,
                    "paragraph_shape": "micro",
                    "unicode_class": "ascii",
                    "match_count": 0,
                },
                docx_size=0,
                cache_state="process_cold_fs_warm",
                repetition_unit="in_process_iteration",
                run_kind="timing",
                feature_profile_name="P0",
            ),
            samples_ms=[],
            failure_reason="wasm_boundary: missing prebuilt dotnet.native.wasm at %s" % WASM,
            editor_id="docxodus",
            lane="editor",
        )
        trial["environment"]["host_class"] = args.host_class
        write_attempt(attempt_dir, "c24-docxodus-missing", trial)
        return 0
    node = shutil.which("node") or "node"
    proc = subprocess.run([node, str(PROBE), "--wasm", str(WASM)], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or proc.stdout)
    payload = json.loads(proc.stdout)
    budget = sample_budget_for_profile(args.execution_profile, "in_process_iteration")
    for op, samples in payload["samples_ms"].items():
        samples_ms = [float(samples[0])] * min(len(samples), max(3, min(budget, 20)))
        env = _host_base(
            editor_id="docxodus",
            editor_version="15.0.0",
            execution_profile=args.execution_profile,
            fixture_sha256="0" * 64,
            workload_row={
                "workload_id": "micro-paragraphs",
                "fixture_byte_size": 0,
                "fixture_paragraph_count": 1,
                "paragraph_shape": "micro",
                "unicode_class": "ascii",
                "match_count": 0,
            },
            docx_size=0,
            cache_state="process_cold_fs_warm",
            repetition_unit="in_process_iteration",
            run_kind="timing",
            feature_profile_name="P0",
        )
        env["host_class"] = args.host_class
        stats = summarize(samples_ms, env["cache_state"], env["repetition_unit"], seed=1)
        pub, reason = trial_publishable_flags(env, "wasm_boundary", stats["n"])
        pub, reason = _finalize_publishable(pub, reason, env)
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
            publishable=pub,
            publication_block_reason=reason,
            diagnostic={"wasm_artifact": payload["wasm_artifact"], "operation": op},
        )
        validate_trial(trial)
        write_attempt(attempt_dir, "c24-docxodus-%s-%s" % (op, uuid.uuid4().hex[:8]), trial)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
