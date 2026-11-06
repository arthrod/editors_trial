#!/usr/bin/env python3
"""Run headless `ci_contract` performance samples (model round-trip wall time).

Writes immutable attempt JSON under ``perf/out/ci_contract_<date>/attempts/`` and a
``summary.json`` with aggregated timings. Does not use Word or Apryse/Chromium.
Apryse is skipped entirely. Docxodus (WASM init + round-trip) is optional via
``--with-docxodus`` because it is slow on low-resource hosts.

Usage (from repo root)::

    PYTHONPATH=. python3 perf/runner/benchmark_ci_contract.py
    PYTHONPATH=. python3 perf/runner/benchmark_ci_contract.py --with-docxodus
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO))

from perf.adapters.capabilities import PINS  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402
from perf.fixtures.generate import build_workload, docx_zip_bytes  # noqa: E402
from perf.fixtures.profiles import size_ladder  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.schema import validate_environment, validate_trial  # noqa: E402

CRITERION_ID = "C02"
BOUNDARY = "model_ready"
LAYER = "model"


def _editor_versions() -> dict[str, str]:
    return dict(PINS)


def _host_env(
    fixture_sha256: str,
    workload_id: str,
    editor_id: str,
    editor_version: str,
) -> dict:
    return {
        "host_class": "ci_coarse",
        "execution_profile": "ci_contract",
        "cpu_model": platform.processor() or "unknown",
        "os": sys.platform,
        "arch": platform.machine(),
        "ram_bytes": _ram_bytes(),
        "power_source": "unknown",
        "editor_id": editor_id,
        "editor_version": editor_version,
        "fixture_sha256": fixture_sha256,
        "cache_state": "process_cold_fs_warm",
        "feature_profile": "P0",
        "workload_id": workload_id,
        "repetition_unit": "fresh_process",
        "run_kind": "timing",
        "headless": True,
        "display_refresh_hz": None,
    }


def _ram_bytes() -> int:
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    return int(parts[1]) * 1024
    except OSError:
        pass
    return 512 * 1024 * 1024


def _measure_cmd(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> float:
    start = time.perf_counter()
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "")[-2000:]
        raise RuntimeError("command failed (rc=%s): %s" % (result.returncode, tail))
    return elapsed_ms


def _trial_record(
    env: dict,
    samples_ms: list[float],
    attempt_root: Path,
) -> Path:
    trial = {
        "schema_version": 1,
        "criterion_id": CRITERION_ID,
        "layer": LAYER,
        "outcome": "measured",
        "boundary": BOUNDARY,
        "claims": [],
        "samples_ms": samples_ms,
        "latency_ms": None,
        "environment": env,
    }
    validate_trial(trial)
    attempt_id = "c02-%s-%s" % (env["editor_id"], uuid.uuid4().hex[:12])
    return write_attempt(attempt_root, attempt_id, trial)


def _run_plate(indocx: Path, outdocx: Path) -> float:
    cmd = [
        "bun",
        "--preload",
        "./aliases.ts",
        "roundtrip.ts",
        str(indocx),
        str(outdocx),
    ]
    return _measure_cmd(cmd, cwd=REPO / "harness" / "plate")


def _run_folio(indocx: Path, outdocx: Path) -> float:
    cmd = ["bun", str(REPO / "harness" / "folio.ts"), str(indocx), str(outdocx), "model"]
    return _measure_cmd(cmd, cwd=REPO / "repos" / "folio")


def _run_superdoc(indocx: Path, outdocx: Path) -> float:
    cmd = ["node", str(REPO / "harness" / "superdoc.mjs"), str(indocx), str(outdocx)]
    return _measure_cmd(cmd, cwd=REPO)


def _run_office_open(indocx: Path, outdocx: Path) -> float:
    tsx = REPO / "repos" / "office-open" / "node_modules" / ".bin" / "tsx"
    cmd = [
        str(tsx),
        "--tsconfig",
        str(REPO / "repos" / "office-open" / "packages" / "docx" / "tsconfig.json"),
        str(REPO / "harness" / "officeopen" / "roundtrip.mts"),
        str(indocx),
        str(outdocx),
    ]
    return _measure_cmd(cmd, cwd=REPO / "repos" / "office-open")


def _run_eigenpal_store(indocx: Path, outdocx: Path) -> float:
    cmd = ["bun", str(REPO / "harness" / "eigenpal.ts"), str(indocx), str(outdocx), "store"]
    return _measure_cmd(cmd, cwd=REPO / "repos" / "eigenpal-docx-editor")


def _run_docen(indocx: Path, outdocx: Path) -> float:
    tsx = REPO / "repos" / "docen" / "node_modules" / ".bin" / "tsx"
    cmd = [str(tsx), str(REPO / "harness" / "docen" / "roundtrip.mts"), str(indocx), str(outdocx)]
    return _measure_cmd(cmd, cwd=REPO / "repos" / "docen")


def _run_genoffice(indocx: Path, outdocx: Path) -> float:
    env = os.environ.copy()
    env["NODE_OPTIONS"] = "--import %s --import %s" % (
        REPO / "harness" / "css-stub.mjs",
        REPO / "repos" / "genoffice" / "node_modules" / "tsx" / "dist" / "loader.mjs",
    )
    cmd = [
        "node",
        str(REPO / "harness" / "genoffice.cts"),
        str(indocx),
        str(outdocx),
    ]
    return _measure_cmd(cmd, cwd=REPO, env=env)


def _run_fidus(indocx: Path, outdocx: Path) -> float:
    env = os.environ.copy()
    env["IN_DOCX"] = str(indocx)
    env["OUT_DOCX"] = str(outdocx)
    env["TEMPLATE"] = "generated"
    tsx = REPO / "repos" / "fiduswriter-document-ts" / "node_modules" / ".bin" / "tsx"
    cmd = [
        str(tsx),
        "--no-cache",
        str(REPO / "harness" / "fidus" / "roundtrip.mts"),
    ]
    return _measure_cmd(cmd, cwd=REPO / "repos" / "fiduswriter-document-ts", env=env)


def _run_docsplus(indocx: Path, outdocx: Path) -> float:
    cmd = ["bun", str(REPO / "harness" / "docsplus" / "roundtrip.ts"), str(indocx), str(outdocx)]
    return _measure_cmd(cmd, cwd=REPO / "harness" / "docsplus" / "repo-copy")


def _run_canvas(indocx: Path, outdocx: Path) -> float:
    env = os.environ.copy()
    env["VITEST_DOCX_INPUT"] = str(indocx)
    env["VITEST_DOCX_OUTPUT"] = str(outdocx)
    cmd = [
        str(REPO / "repos" / "canvas-editor" / "node_modules" / ".bin" / "vitest"),
        "run",
        "--root",
        str(REPO / "harness" / "canvas"),
    ]
    return _measure_cmd(cmd, cwd=REPO / "repos" / "canvas-editor", env=env)


def _run_wordcraft(indocx: Path, outdocx: Path) -> float:
    bin_path = REPO / "harness" / "wordcraft" / "target" / "release" / "wc-harness"
    if not bin_path.is_file():
        raise RuntimeError("wordcraft binary missing; run `cargo build --release` in harness/wordcraft")
    cmd = [str(bin_path), str(indocx), str(outdocx)]
    return _measure_cmd(cmd, cwd=REPO / "harness" / "wordcraft")


def _run_libreoffice_timed(indocx: Path, outdocx: Path) -> float:
    """Return wall time for one headless conversion (includes rename to out path)."""
    outdir = outdocx.parent
    outdir.mkdir(parents=True, exist_ok=True)
    stem = indocx.stem
    start = time.perf_counter()
    cmd = [
        "soffice",
        "--headless",
        "--norestore",
        "--convert-to",
        "docx",
        "--outdir",
        str(outdir),
        str(indocx),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError("soffice failed: %s" % (result.stderr or result.stdout,))
    produced = outdir / ("%s.docx" % stem)
    if not produced.is_file():
        raise RuntimeError("libreoffice did not produce output")
    produced.replace(outdocx)
    return (time.perf_counter() - start) * 1000.0


def _run_docxodus(indocx: Path, outdocx: Path) -> float:
    cmd = ["node", str(REPO / "harness" / "ui" / "docxodus" / "roundtrip.mjs"), str(indocx), str(outdocx)]
    return _measure_cmd(cmd, cwd=REPO / "harness" / "ui" / "docxodus")


_RUNNERS = {
    "plate": _run_plate,
    "folio": _run_folio,
    "superdoc": _run_superdoc,
    "office-open": _run_office_open,
    "eigenpal": _run_eigenpal_store,
    "docen": _run_docen,
    "genoffice": _run_genoffice,
    "fidus": _run_fidus,
    "docsplus": _run_docsplus,
    "canvas": _run_canvas,
    "wordcraft": _run_wordcraft,
    "libreoffice": _run_libreoffice_timed,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workload",
        default="micro-paragraphs",
        help="Workload id from the size ladder (ci_contract allows micro-* only)",
    )
    parser.add_argument(
        "--with-docxodus",
        action="store_true",
        help="Also measure docxodus (WASM); slow on small hosts",
    )
    parser.add_argument("--out-root", type=Path, default=None, help="Override perf/out/... root")
    args = parser.parse_args()

    workload_row = next(w for w in size_ladder() if w["workload_id"] == args.workload)
    built = build_workload(workload_row)
    docx_body = docx_zip_bytes(built["body"])
    sha = hashlib.sha256(docx_body).hexdigest()

    run_day = date.today().isoformat()
    out_root = args.out_root or (REPO / "perf" / "out" / ("ci_contract_%s" % run_day.replace("-", "_")))
    attempt_dir = out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)

    versions = _editor_versions()

    summary_rows = []
    skipped = [
        {
            "editor_id": "apryse",
            "reason": "skipped_by_policy",
            "detail": "Apryse lane requires proprietary WebViewer/Chromium; excluded on this Linux VM",
        }
    ]

    for editor_id, fn in _RUNNERS.items():
        with tempfile.TemporaryDirectory(prefix="perf_ci_contract_") as tmp:
            tmp_path = Path(tmp)
            indocx = tmp_path / ("load-%s.docx" % args.workload)
            outdocx = tmp_path / ("save-%s.docx" % args.workload)
            indocx.write_bytes(docx_body)
            env = _host_env(sha, args.workload, editor_id, versions[editor_id])
            validate_environment(env)
            try:
                if editor_id == "libreoffice":
                    ms = _run_libreoffice_timed(indocx, outdocx)
                else:
                    ms = fn(indocx, outdocx)
            except Exception as exc:
                fail = {
                    "schema_version": 1,
                    "criterion_id": CRITERION_ID,
                    "layer": LAYER,
                    "outcome": "failed",
                    "boundary": BOUNDARY,
                    "claims": [],
                    "samples_ms": [],
                    "latency_ms": None,
                    "failure_reason": "harness-error: %s" % exc,
                    "environment": env,
                }
                validate_trial(fail)
                write_attempt(
                    attempt_dir,
                    "c02-%s-fail-%s" % (editor_id, uuid.uuid4().hex[:8]),
                    fail,
                )
                summary_rows.append(
                    {
                        "editor_id": editor_id,
                        "editor_version": versions[editor_id],
                        "outcome": "failed",
                        "error": str(exc),
                    }
                )
                continue

            samples = [round(ms, 6)]
            path = _trial_record(env, samples, attempt_dir)
            stats = summarize(samples, env["cache_state"], env["repetition_unit"], seed=42)
            summary_rows.append(
                {
                    "editor_id": editor_id,
                    "editor_version": versions[editor_id],
                    "outcome": "measured",
                    "median_ms": stats["median"],
                    "min_ms": stats["minimum"],
                    "max_ms": stats["maximum"],
                    "n": stats["n"],
                    "attempt_file": str(path.relative_to(REPO)),
                }
            )

    if args.with_docxodus:
        with tempfile.TemporaryDirectory(prefix="perf_docxodus_") as tmp:
            tmp_path = Path(tmp)
            indocx = tmp_path / "in.docx"
            outdocx = tmp_path / "out.docx"
            indocx.write_bytes(docx_body)
            env = _host_env(sha, args.workload, "docxodus", versions["docxodus"])
            validate_environment(env)
            try:
                ms = _run_docxodus(indocx, outdocx)
            except Exception as exc:
                summary_rows.append(
                    {"editor_id": "docxodus", "outcome": "failed", "error": str(exc)}
                )
            else:
                path = _trial_record(env, [round(ms, 6)], attempt_dir)
                stats = summarize([ms], env["cache_state"], env["repetition_unit"], seed=42)
                summary_rows.append(
                    {
                        "editor_id": "docxodus",
                        "editor_version": versions["docxodus"],
                        "outcome": "measured",
                        "median_ms": stats["median"],
                        "attempt_file": str(path.relative_to(REPO)),
                    }
                )

    payload = {
        "criterion_id": CRITERION_ID,
        "boundary": BOUNDARY,
        "layer": LAYER,
        "execution_profile": "ci_contract",
        "workload_id": args.workload,
        "fixture_sha256": sha,
        "generated_fixture_note": "synthetic OOXML from perf/fixtures/generate.docx_zip_bytes",
        "editors": summary_rows,
        "skipped": skipped,
    }
    summary_path = out_root / "summary.json"
    summary_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
