#!/usr/bin/env python3
"""Run performance attempts for criteria C01–C24.

Writes immutable trial JSON under ``perf/out/<profile>_<date>/attempts/`` and
``summary.json``. Uses harness-emitted ``PERF model_ready_ms=`` for C02 load
timing, ``PERF save_ms=`` for C16 serialization where the harness emits it
(LibreOffice has no such probe: C16 is ``not_run``), and Linux
``getrusage(RUSAGE_CHILDREN)`` child CPU milliseconds for C21 (real probe,
subprocess tree is mostly the direct child on these drivers).

``--execution-profile`` selects ``ci_contract`` (default) or ``ci_broad``;
workload must fall under that profile's cap (``build/test_perf_plan_coverage.py``).

Usage (from repo root)::

    PYTHONPATH=. python3 perf/runner/benchmark_ci_contract.py
    PYTHONPATH=. python3 perf/runner/benchmark_ci_contract.py --dry-run
    PYTHONPATH=. python3 perf/runner/benchmark_ci_contract.py --execution-profile ci_broad
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO))

from perf.adapters.capabilities import default_lane, editor_pins, pin_label  # noqa: E402
from perf.analysis.interpretation import evaluate_measured_trial  # noqa: E402
from perf.analysis.publication_gate import trial_publishable_flags  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402
from perf.analysis.summary_integrity import assert_ci_contract_summary_valid  # noqa: E402
from perf.fixtures.generate import build_workload, correctness_fixtures, docx_zip_bytes  # noqa: E402
from perf.fixtures.profiles import assert_workload_allowed, feature_profile, size_ladder  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.docx_plaintext import docx_body_text  # noqa: E402
from perf.runner.load_timing import parse_perf_lines  # noqa: E402
from perf.runner.order import editor_order  # noqa: E402
from perf.runner.schedule import plan_attempts  # noqa: E402
from perf.scenarios.catalog import scenarios  # noqa: E402
from perf.schema import sample_budget_for_profile, validate_environment, validate_sample_budget, validate_trial  # noqa: E402

EDITORS = [
    "plate",
    "docxodus",
    "apryse",
    "superdoc",
    "folio",
    "genoffice",
    "eigenpal",
    "office-open",
    "docen",
    "wordcraft",
    "fidus",
    "canvas",
    "docsplus",
    "libreoffice",
]

INTERPRETATION_CONDITIONS = ["I%02d" % n for n in range(1, 13)]


def _attempt_ref(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return path.name


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


def _host_base(
    *,
    editor_id: str,
    editor_version: str,
    execution_profile: str,
    fixture_sha256: str,
    workload_row: dict,
    docx_size: int,
    cache_state: str,
    repetition_unit: str,
    run_kind: str,
    feature_profile_name: str,
) -> dict:
    feats = feature_profile(feature_profile_name)
    disabled = list(feats.get("disabled_features") or [])
    return {
        "host_class": "ci_coarse",
        "execution_profile": execution_profile,
        "cpu_model": platform.processor() or "unknown",
        "os": sys.platform,
        "arch": platform.machine(),
        "ram_bytes": _ram_bytes(),
        "power_source": "unknown",
        "editor_id": editor_id,
        "editor_version": editor_version,
        "fixture_sha256": fixture_sha256,
        "cache_state": cache_state,
        "feature_profile": feature_profile_name,
        "workload_id": workload_row["workload_id"],
        "fixture_byte_size": docx_size,
        "fixture_paragraph_count": int(workload_row["paragraphs"]),
        "paragraph_shape": str(workload_row.get("shape") or "unknown"),
        "unicode_class": str(workload_row["unicode_class"]),
        "match_count": int(workload_row["match_count"]),
        "repetition_unit": repetition_unit,
        "run_kind": run_kind,
        "headless": True,
        "display_refresh_hz": None,
        "interpretation_conditions": list(INTERPRETATION_CONDITIONS),
        "feature_fallback": disabled,
    }


def _measure_cmd(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict | None = None,
) -> tuple[float, str, str, float]:
    r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    child_cpu_ms = ((r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)) * 1000.0
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "")[-2000:]
        raise RuntimeError("command failed (rc=%s): %s" % (result.returncode, tail))
    return elapsed_ms, result.stdout or "", result.stderr or "", child_cpu_ms


def _run_plate(indocx: Path, outdocx: Path) -> tuple[float, str, str]:
    cmd = [
        "bun",
        "--preload",
        "./aliases.ts",
        "roundtrip.ts",
        str(indocx),
        str(outdocx),
    ]
    return _measure_cmd(cmd, cwd=REPO / "harness" / "plate")


def _run_folio(indocx: Path, outdocx: Path) -> tuple[float, str, str]:
    cmd = ["bun", str(REPO / "harness" / "folio.ts"), str(indocx), str(outdocx), "model"]
    return _measure_cmd(cmd, cwd=REPO / "repos" / "folio")


def _run_superdoc(indocx: Path, outdocx: Path) -> tuple[float, str, str]:
    cmd = ["node", str(REPO / "harness" / "superdoc.mjs"), str(indocx), str(outdocx)]
    return _measure_cmd(cmd, cwd=REPO)


def _run_office_open(indocx: Path, outdocx: Path) -> tuple[float, str, str]:
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


def _run_eigenpal_store(indocx: Path, outdocx: Path) -> tuple[float, str, str]:
    cmd = ["bun", str(REPO / "harness" / "eigenpal.ts"), str(indocx), str(outdocx), "store"]
    return _measure_cmd(cmd, cwd=REPO / "repos" / "eigenpal-docx-editor")


def _run_docen(indocx: Path, outdocx: Path) -> tuple[float, str, str]:
    tsx = REPO / "repos" / "docen" / "node_modules" / ".bin" / "tsx"
    cmd = [str(tsx), str(REPO / "harness" / "docen" / "roundtrip.mts"), str(indocx), str(outdocx)]
    return _measure_cmd(cmd, cwd=REPO / "repos" / "docen")


def _run_genoffice(indocx: Path, outdocx: Path) -> tuple[float, str, str, float]:
    env = os.environ.copy()
    env["NODE_OPTIONS"] = "--import %s --import %s" % (
        REPO / "harness" / "css-stub.mjs",
        REPO / "repos" / "genoffice" / "node_modules" / "tsx" / "dist" / "loader.mjs",
    )
    env["NODE_PATH"] = str(REPO / "repos" / "genoffice" / "node_modules")
    cmd = [
        "node",
        str(REPO / "harness" / "genoffice.cts"),
        str(indocx),
        str(outdocx),
    ]
    return _measure_cmd(cmd, cwd=REPO / "repos" / "genoffice", env=env)


def _run_fidus(indocx: Path, outdocx: Path) -> tuple[float, str, str]:
    env = os.environ.copy()
    env["IN_DOCX"] = str(indocx)
    env["OUT_DOCX"] = str(outdocx)
    env["TEMPLATE"] = "generated"
    env["NODE_PATH"] = str(REPO / "repos" / "fiduswriter-document-ts" / "node_modules")
    tsx = REPO / "repos" / "fiduswriter-document-ts" / "node_modules" / ".bin" / "tsx"
    cmd = [
        str(tsx),
        "--no-cache",
        str(REPO / "harness" / "fidus" / "roundtrip.mts"),
    ]
    return _measure_cmd(cmd, cwd=REPO / "repos" / "fiduswriter-document-ts", env=env)


def _run_docsplus(indocx: Path, outdocx: Path) -> tuple[float, str, str]:
    cmd = ["bun", str(REPO / "harness" / "docsplus" / "roundtrip.ts"), str(indocx), str(outdocx)]
    return _measure_cmd(cmd, cwd=REPO / "harness" / "docsplus" / "repo-copy")


def _run_canvas(indocx: Path, outdocx: Path, perf_mark: Path | None = None) -> tuple[float, str, str]:
    env = os.environ.copy()
    env["VITEST_DOCX_INPUT"] = str(indocx)
    env["VITEST_DOCX_OUTPUT"] = str(outdocx)
    if perf_mark is not None:
        env["PERF_MARK_PATH"] = str(perf_mark)
    env["NODE_PATH"] = str(REPO / "repos" / "canvas-editor" / "node_modules")
    cmd = [
        str(REPO / "repos" / "canvas-editor" / "node_modules" / ".bin" / "vitest"),
        "run",
        "--root",
        str(REPO / "harness" / "canvas"),
    ]
    return _measure_cmd(cmd, cwd=REPO / "repos" / "canvas-editor", env=env)


def _run_wordcraft(indocx: Path, outdocx: Path) -> tuple[float, str, str]:
    bin_path = REPO / "harness" / "wordcraft" / "target" / "release" / "wc-harness"
    if not bin_path.is_file():
        raise RuntimeError(
            "wordcraft binary missing; run `cargo build --release` in harness/wordcraft"
        )
    cmd = [str(bin_path), str(indocx), str(outdocx)]
    return _measure_cmd(cmd, cwd=REPO / "harness" / "wordcraft")


LIBREOFFICE_C16_NOT_RUN_REASON = (
    "libreoffice: headless soffice conversion has no save-boundary probe emitting "
    "PERF save_ms= (serialization timing not separately measurable here)"
)


def _run_libreoffice(indocx: Path, outdocx: Path) -> tuple[float, str, str, float]:
    """Headless conversion wall time; do not label as ``model_ready`` (no editor model)."""
    outdir = outdocx.parent
    outdir.mkdir(parents=True, exist_ok=True)
    stem = indocx.stem
    r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
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
    r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    child_cpu_ms = ((r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)) * 1000.0
    if result.returncode != 0:
        raise RuntimeError("soffice failed: %s" % (result.stderr or result.stdout,))
    produced = outdir / ("%s.docx" % stem)
    if not produced.is_file():
        raise RuntimeError("libreoffice did not produce output")
    produced.replace(outdocx)
    combined_out = result.stdout or ""
    return elapsed_ms, combined_out, result.stderr or "", child_cpu_ms


def _run_docxodus(indocx: Path, outdocx: Path) -> tuple[float, str, str]:
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
    "libreoffice": _run_libreoffice,
    "docxodus": _run_docxodus,
}


def _harness_run(editor_id: str, indocx: Path, outdocx: Path, perf_mark: Path | None = None) -> tuple[float, str, str, float]:
    fn = _RUNNERS[editor_id]
    if editor_id == "canvas":
        return _run_canvas(indocx, outdocx, perf_mark=perf_mark)
    return fn(indocx, outdocx)


def _perf_sample_from_output(
    key: str, stderr: str, stdout: str, perf_mark: Path | None = None
) -> float:
    perf = parse_perf_lines(stderr, stdout)
    if perf_mark is not None and perf_mark.is_file():
        extra = perf_mark.read_text(encoding="utf-8", errors="replace")
        perf.update(parse_perf_lines(extra, ""))
    val = perf.get(key)
    if val is None:
        raise RuntimeError("harness did not emit PERF %s=" % key)
    return round(float(val), 6)


def _collect_samples(
    *,
    key: str,
    editor_id: str,
    docx_body: bytes,
    tmp_path: Path,
    workload_id: str,
    attempt_count: int,
    metric_from_wall: bool = False,
) -> tuple[list[float], list[float], list[float], Path | None]:
    """Return (metric_samples, wall_samples_ms, child_cpu_samples_ms, last_outdocx).

    When ``metric_from_wall`` is true, each metric sample is the subprocess wall
    time (used for LibreOffice C02 conversion wall: same numeric series as
    ``subprocess_wall_ms_median``, not a fabricated ``PERF`` line).
    """
    metric_samples: list[float] = []
    wall_samples: list[float] = []
    cpu_samples: list[float] = []
    last_out: Path | None = None
    for _ in range(attempt_count):
        indocx = tmp_path / ("load-%s-%s.docx" % (workload_id, uuid.uuid4().hex[:8]))
        outdocx = tmp_path / ("save-%s-%s.docx" % (workload_id, uuid.uuid4().hex[:8]))
        indocx.write_bytes(docx_body)
        perf_path = tmp_path / ("perf_marks-%s.txt" % uuid.uuid4().hex[:8])
        if perf_path.is_file():
            perf_path.unlink()
        wall_ms, out, err, child_cpu = _harness_run(editor_id, indocx, outdocx, perf_mark=perf_path)
        if metric_from_wall:
            metric_samples.append(round(wall_ms, 6))
        else:
            metric_samples.append(_perf_sample_from_output(key, err, out, perf_mark=perf_path))
        wall_samples.append(round(wall_ms, 6))
        cpu_samples.append(round(child_cpu, 6))
        last_out = outdocx
    return metric_samples, wall_samples, cpu_samples, last_out


def _collect_child_cpu_only(
    *,
    editor_id: str,
    docx_body: bytes,
    tmp_path: Path,
    workload_id: str,
    attempt_count: int,
) -> tuple[list[float], list[float], Path | None]:
    """Linux: delta ``RUSAGE_CHILDREN`` around each fresh harness run."""
    wall_samples: list[float] = []
    cpu_samples: list[float] = []
    last_out: Path | None = None
    for _ in range(attempt_count):
        indocx = tmp_path / ("load-%s-%s.docx" % (workload_id, uuid.uuid4().hex[:8]))
        outdocx = tmp_path / ("save-%s-%s.docx" % (workload_id, uuid.uuid4().hex[:8]))
        indocx.write_bytes(docx_body)
        perf_path = tmp_path / ("perf_marks-%s.txt" % uuid.uuid4().hex[:8])
        if perf_path.is_file():
            perf_path.unlink()
        wall_ms, _out, _err, child_cpu = _harness_run(editor_id, indocx, outdocx, perf_mark=perf_path)
        wall_samples.append(round(wall_ms, 6))
        cpu_samples.append(round(child_cpu, 6))
        last_out = outdocx
    return cpu_samples, wall_samples, last_out


def c24_boundary_decision(editor_id: str, execution_profile: str) -> tuple[str, str | None, dict | None]:
    """
    C24 WASM boundary: docxodus uses the Node probe when a prebuilt artifact exists.
    """
    if editor_id == "apryse":
        return "unverified", None, None
    wasm = (
        Path(__file__).resolve().parents[2]
        / "harness/ui/docxodus/node_modules/docxodus/dist/wasm/_framework/dotnet.native.wasm"
    )
    if editor_id == "docxodus" and wasm.is_file():
        return "measured", None, {"wasm_artifact": str(wasm)}
    return (
        "not_run",
        "wasm_boundary: no host/WASM boundary harness on %s (design C24)" % execution_profile,
        None,
    )


def _finalize_publishable(pub: bool, reason: str | None, env: dict) -> tuple[bool, str | None]:
    if env.get("host_class") in ("ci_coarse", "laboratory"):
        if pub:
            reason = reason or "%s host_class blocks headline publication" % env.get("host_class")
        pub = False
    if pub is False and (not reason or not str(reason).strip()):
        reason = "publishable blocked"
    return pub, reason


def _trial_dict(
    *,
    criterion_id: str,
    layer: str,
    boundary: str,
    outcome: str,
    env: dict,
    samples_ms: list[float],
    failure_reason: str | None = None,
    editor_id: str | None = None,
    lane: str | None = None,
    summary_stats: dict | None = None,
    publishable: bool | None = None,
    publication_block_reason: str | None = None,
    diagnostic: dict | None = None,
) -> dict:
    trial = {
        "schema_version": 1,
        "criterion_id": criterion_id,
        "layer": layer,
        "outcome": outcome,
        "boundary": boundary,
        "claims": [],
        "samples_ms": samples_ms,
        "latency_ms": None,
        "environment": env,
    }
    if editor_id is not None:
        trial["editor_id"] = editor_id
    if lane is not None:
        trial["lane"] = lane
    if failure_reason is not None:
        trial["failure_reason"] = failure_reason
    if summary_stats is not None:
        trial["summary_stats"] = summary_stats
    if publishable is not None:
        trial["publishable"] = publishable
    if publication_block_reason is not None:
        trial["publication_block_reason"] = publication_block_reason
    if diagnostic is not None:
        trial["diagnostic"] = diagnostic
    validate_trial(trial)
    return trial


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workload",
        default="micro-paragraphs",
        help="Workload id from the size ladder (must be allowed for --execution-profile)",
    )
    parser.add_argument(
        "--execution-profile",
        default="ci_contract",
        choices=("ci_contract", "ci_broad"),
        help="Schedules browser_visible on ci_broad; sets sample budget (default ci_contract)",
    )
    parser.add_argument("--out-root", type=Path, default=None, help="Override perf/out/... root")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write scheduler outcomes only (not_run / skipped measure); fast CI check",
    )
    args = parser.parse_args()

    editor_pins()
    execution_profile = args.execution_profile
    workload_row = next(w for w in size_ladder() if w["workload_id"] == args.workload)
    assert_workload_allowed(execution_profile, args.workload)
    built = build_workload(workload_row)
    cfs = correctness_fixtures()
    augmented_body = (
        built["body"]
        + b"\n"
        + cfs["unicode"]
        + cfs["emoji"]
        + cfs["bidi"]
        + cfs["ime_committed"]
    )
    docx_body = docx_zip_bytes(augmented_body)
    sha = hashlib.sha256(docx_body).hexdigest()
    docx_size = len(docx_body)

    run_day = date.today().isoformat()
    out_root = args.out_root or (
        REPO / "perf" / "out" / ("%s_%s" % (execution_profile, run_day.replace("-", "_")))
    )
    attempt_dir = out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)

    catalog = {row["id"]: row for row in scenarios()}
    summary_rows = []
    seed = 42
    ordered = editor_order(list(EDITORS), seed=seed)

    for sc_id in ["C%02d" % i for i in range(1, 25)]:
        scenario = catalog[sc_id]
        layer = scenario["layer"]
        boundary = scenario["boundary"]
        for editor_id in ordered:
            lane = default_lane(editor_id)
            editor_version = pin_label(editor_id)
            rep_unit = scenario["repetition_unit"]
            run_kind = scenario["run_kind"]
            cache_state = "process_cold_fs_warm"
            if sc_id == "C24":
                rep_unit = "in_process_iteration"
            env = _host_base(
                editor_id=editor_id,
                editor_version=editor_version,
                execution_profile=execution_profile,
                fixture_sha256=sha,
                workload_row=workload_row,
                docx_size=docx_size,
                cache_state=cache_state,
                repetition_unit=rep_unit,
                run_kind=run_kind,
                feature_profile_name="P0",
            )
            decision = plan_attempts(scenario, env, editor_id, lane)
            if not decision["run"]:
                trial = _trial_dict(
                    criterion_id=sc_id,
                    layer=layer,
                    boundary=boundary,
                    outcome="not_run",
                    env=env,
                    samples_ms=[],
                    failure_reason="execution_profile: %s" % (decision["failure_reason"],),
                    editor_id=editor_id,
                    lane=lane,
                )
                validate_environment(env)
                path = write_attempt(attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial)
                summary_rows.append(
                    {
                        "criterion_id": sc_id,
                        "editor_id": editor_id,
                        "outcome": "not_run",
                        "failure_reason": trial["failure_reason"],
                        "attempt_file": _attempt_ref(path),
                        "publishable": False,
                    }
                )
                continue

            validate_environment(env)

            budget = sample_budget_for_profile(execution_profile, env["repetition_unit"])

            if sc_id == "C02":
                if editor_id == "apryse":
                    trial = _trial_dict(
                        criterion_id=sc_id,
                        layer=layer,
                        boundary=boundary,
                        outcome="not_run",
                        env=env,
                        samples_ms=[],
                        failure_reason=(
                            "apryse: proprietary WebViewer round-trip harness not run on this Linux CI host"
                        ),
                        editor_id=editor_id,
                        lane=lane,
                    )
                    path = write_attempt(
                        attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial
                    )
                    summary_rows.append(
                        {
                            "criterion_id": sc_id,
                            "editor_id": editor_id,
                            "outcome": "not_run",
                            "failure_reason": trial["failure_reason"],
                            "attempt_file": _attempt_ref(path),
                            "publishable": False,
                        }
                    )
                    continue
                if editor_id == "libreoffice":
                    if args.dry_run:
                        trial = _trial_dict(
                            criterion_id=sc_id,
                            layer=layer,
                            boundary=boundary,
                            outcome="not_run",
                            env=env,
                            samples_ms=[],
                            failure_reason="dry-run",
                            editor_id=editor_id,
                            lane=lane,
                        )
                        path = write_attempt(
                            attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial
                        )
                        summary_rows.append(
                            {
                                "criterion_id": sc_id,
                                "editor_id": editor_id,
                                "outcome": "not_run",
                                "failure_reason": "dry-run",
                                "attempt_file": _attempt_ref(path),
                                "publishable": False,
                            }
                        )
                        continue
                    validate_sample_budget(env, budget)
                    with tempfile.TemporaryDirectory(prefix="perf_c02_libreoffice_") as tmp:
                        tmp_path = Path(tmp)
                        try:
                            samples, wall_list, _cpu_list, last_outdocx = _collect_samples(
                                key="save_ms",
                                editor_id=editor_id,
                                docx_body=docx_body,
                                tmp_path=tmp_path,
                                workload_id=args.workload,
                                attempt_count=budget,
                                metric_from_wall=True,
                            )
                        except Exception as exc:
                            fail = _trial_dict(
                                criterion_id=sc_id,
                                layer=layer,
                                boundary=boundary,
                                outcome="failed",
                                env=env,
                                samples_ms=[],
                                failure_reason="harness-error: %s" % exc,
                                editor_id=editor_id,
                                lane=lane,
                            )
                            path = write_attempt(
                                attempt_dir,
                                "%s-%s-fail-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:8]),
                                fail,
                            )
                            summary_rows.append(
                                {
                                    "criterion_id": sc_id,
                                    "editor_id": editor_id,
                                    "outcome": "failed",
                                    "error": str(exc),
                                    "attempt_file": _attempt_ref(path),
                                    "publishable": False,
                                }
                            )
                            continue
                        c02_scenario = catalog["C02"]
                        stats = summarize(samples, env["cache_state"], env["repetition_unit"], seed=seed)
                        pub, reason = trial_publishable_flags(env, layer, len(samples))
                        diag_note = (
                            "load_timing_ms is headless CLI conversion (not model_ready); boundary labeled conversion_wall"
                        )
                        try:
                            doc_text = docx_body_text(last_outdocx) if last_outdocx and last_outdocx.is_file() else None
                        except OSError:
                            doc_text = None
                        interp_ok, interp_reason = evaluate_measured_trial(
                            c02_scenario,
                            env,
                            doc_output_text=doc_text,
                            summary_stats=stats,
                        )
                        if not interp_ok:
                            pub = False
                            reason = "%s; %s" % (diag_note, interp_reason)
                        elif pub:
                            pub = False
                            reason = (
                                "%s; ci_coarse cannot publish model latency; libreoffice C02 uses conversion wall only"
                                % (diag_note,)
                            )
                        pub, reason = _finalize_publishable(pub, reason, env)
                        trial = _trial_dict(
                            criterion_id=sc_id,
                            layer=layer,
                            boundary="conversion_wall",
                            outcome="measured",
                            env=env,
                            samples_ms=samples,
                            editor_id=editor_id,
                            lane=lane,
                            summary_stats=stats,
                            publishable=pub,
                            publication_block_reason=reason,
                            diagnostic={"note": diag_note},
                        )
                        path = write_attempt(
                            attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial
                        )
                        wall_med = summarize(wall_list, env["cache_state"], env["repetition_unit"], seed=seed)[
                            "median"
                        ]
                        summary_rows.append(
                            {
                                "criterion_id": sc_id,
                                "editor_id": editor_id,
                                "outcome": "measured",
                                "boundary": "conversion_wall",
                                "median_ms": stats["median"],
                                "load_timing_ms": stats["median"],
                                "subprocess_wall_ms_median": wall_med,
                                "attempt_file": _attempt_ref(path),
                                "publishable": pub,
                            }
                        )
                    continue
                if args.dry_run:
                    trial = _trial_dict(
                        criterion_id=sc_id,
                        layer=layer,
                        boundary=boundary,
                        outcome="not_run",
                        env=env,
                        samples_ms=[],
                        failure_reason="dry-run",
                        editor_id=editor_id,
                        lane=lane,
                    )
                    path = write_attempt(
                        attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial
                    )
                    summary_rows.append(
                        {
                            "criterion_id": sc_id,
                            "editor_id": editor_id,
                            "outcome": "not_run",
                            "failure_reason": "dry-run",
                            "attempt_file": _attempt_ref(path),
                            "publishable": False,
                        }
                    )
                    continue
                validate_sample_budget(env, budget)
                with tempfile.TemporaryDirectory(prefix="perf_c02_") as tmp:
                    tmp_path = Path(tmp)
                    try:
                        samples, wall_list, _cpu_list, last_outdocx = _collect_samples(
                            key="model_ready_ms",
                            editor_id=editor_id,
                            docx_body=docx_body,
                            tmp_path=tmp_path,
                            workload_id=args.workload,
                            attempt_count=budget,
                        )
                    except Exception as exc:
                        fail = _trial_dict(
                            criterion_id=sc_id,
                            layer=layer,
                            boundary=boundary,
                            outcome="failed",
                            env=env,
                            samples_ms=[],
                            failure_reason="harness-error: %s" % exc,
                            editor_id=editor_id,
                            lane=lane,
                        )
                        path = write_attempt(
                            attempt_dir, "%s-%s-fail-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:8]), fail
                        )
                        summary_rows.append(
                            {
                                "criterion_id": sc_id,
                                "editor_id": editor_id,
                                "outcome": "failed",
                                "error": str(exc),
                                "attempt_file": _attempt_ref(path),
                                "publishable": False,
                            }
                        )
                        continue
                    wall_med = summarize(wall_list, env["cache_state"], env["repetition_unit"], seed=seed)["median"]
                    try:
                        doc_text = docx_body_text(last_outdocx) if last_outdocx and last_outdocx.is_file() else None
                    except OSError:
                        doc_text = None
                    stats = summarize(samples, env["cache_state"], env["repetition_unit"], seed=seed)
                    pub, reason = trial_publishable_flags(env, layer, len(samples))
                    interp_ok, interp_reason = evaluate_measured_trial(
                        scenario,
                        env,
                        doc_output_text=doc_text,
                        summary_stats=stats,
                    )
                    if not interp_ok:
                        pub = False
                        reason = interp_reason
                    pub, reason = _finalize_publishable(pub, reason, env)
                    trial = _trial_dict(
                        criterion_id=sc_id,
                        layer=layer,
                        boundary=boundary,
                        outcome="measured",
                        env=env,
                        samples_ms=samples,
                        editor_id=editor_id,
                        lane=lane,
                        summary_stats=stats,
                        publishable=pub,
                        publication_block_reason=reason,
                    )
                    path = write_attempt(attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial)
                    summary_rows.append(
                        {
                            "criterion_id": sc_id,
                            "editor_id": editor_id,
                            "outcome": "measured",
                            "median_ms": stats["median"],
                            "model_ready_ms": samples[0] if len(samples) == 1 else None,
                            "subprocess_wall_ms_median": wall_med,
                            "attempt_file": _attempt_ref(path),
                            "publishable": pub,
                        }
                    )
                continue

            if sc_id == "C16":
                if editor_id == "apryse":
                    trial = _trial_dict(
                        criterion_id=sc_id,
                        layer=layer,
                        boundary=boundary,
                        outcome="not_run",
                        env=env,
                        samples_ms=[],
                        failure_reason=(
                            "apryse: proprietary WebViewer round-trip harness not run on this Linux CI host"
                        ),
                        editor_id=editor_id,
                        lane=lane,
                    )
                    path = write_attempt(
                        attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial
                    )
                    summary_rows.append(
                        {
                            "criterion_id": sc_id,
                            "editor_id": editor_id,
                            "outcome": "not_run",
                            "failure_reason": trial["failure_reason"],
                            "attempt_file": _attempt_ref(path),
                            "publishable": False,
                        }
                    )
                    continue
                if editor_id == "libreoffice":
                    trial = _trial_dict(
                        criterion_id=sc_id,
                        layer=layer,
                        boundary=boundary,
                        outcome="not_run",
                        env=env,
                        samples_ms=[],
                        failure_reason=LIBREOFFICE_C16_NOT_RUN_REASON,
                        editor_id=editor_id,
                        lane=lane,
                    )
                    path = write_attempt(
                        attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial
                    )
                    summary_rows.append(
                        {
                            "criterion_id": sc_id,
                            "editor_id": editor_id,
                            "outcome": "not_run",
                            "failure_reason": trial["failure_reason"],
                            "attempt_file": _attempt_ref(path),
                            "publishable": False,
                        }
                    )
                    continue
                if args.dry_run:
                    trial = _trial_dict(
                        criterion_id=sc_id,
                        layer=layer,
                        boundary=boundary,
                        outcome="not_run",
                        env=env,
                        samples_ms=[],
                        failure_reason="dry-run",
                        editor_id=editor_id,
                        lane=lane,
                    )
                    path = write_attempt(
                        attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial
                    )
                    summary_rows.append(
                        {
                            "criterion_id": sc_id,
                            "editor_id": editor_id,
                            "outcome": "not_run",
                            "failure_reason": "dry-run",
                            "attempt_file": _attempt_ref(path),
                            "publishable": False,
                        }
                    )
                    continue
                validate_sample_budget(env, budget)
                with tempfile.TemporaryDirectory(prefix="perf_c16_") as tmp:
                    tmp_path = Path(tmp)
                    try:
                        samples, wall_list, _cpu, _last = _collect_samples(
                            key="save_ms",
                            editor_id=editor_id,
                            docx_body=docx_body,
                            tmp_path=tmp_path,
                            workload_id=args.workload,
                            attempt_count=budget,
                        )
                    except Exception as exc:
                        fail = _trial_dict(
                            criterion_id=sc_id,
                            layer=layer,
                            boundary=boundary,
                            outcome="failed",
                            env=env,
                            samples_ms=[],
                            failure_reason="harness-error: %s" % exc,
                            editor_id=editor_id,
                            lane=lane,
                        )
                        path = write_attempt(
                            attempt_dir,
                            "%s-%s-fail-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:8]),
                            fail,
                        )
                        summary_rows.append(
                            {
                                "criterion_id": sc_id,
                                "editor_id": editor_id,
                                "outcome": "failed",
                                "error": str(exc),
                                "attempt_file": _attempt_ref(path),
                                "publishable": False,
                            }
                        )
                        continue
                    stats = summarize(samples, env["cache_state"], env["repetition_unit"], seed=seed)
                    pub, reason = trial_publishable_flags(env, layer, len(samples))
                    if pub:
                        pub = False
                        reason = "ci_coarse cannot publish model timing as headline distribution (serialization complete)"
                    pub, reason = _finalize_publishable(pub, reason, env)
                    trial = _trial_dict(
                        criterion_id=sc_id,
                        layer=layer,
                        boundary=boundary,
                        outcome="measured",
                        env=env,
                        samples_ms=samples,
                        editor_id=editor_id,
                        lane=lane,
                        summary_stats=stats,
                        publishable=pub,
                        publication_block_reason=reason,
                    )
                    path = write_attempt(attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial)
                    wall_med = summarize(wall_list, env["cache_state"], env["repetition_unit"], seed=seed)["median"]
                    summary_rows.append(
                        {
                            "criterion_id": sc_id,
                            "editor_id": editor_id,
                            "outcome": "measured",
                            "median_ms": stats["median"],
                            "save_ms": stats["median"],
                            "subprocess_wall_ms_median": wall_med,
                            "attempt_file": _attempt_ref(path),
                            "publishable": pub,
                        }
                    )
                continue

            if sc_id == "C21":
                if editor_id == "apryse":
                    trial = _trial_dict(
                        criterion_id=sc_id,
                        layer=layer,
                        boundary=boundary,
                        outcome="not_run",
                        env=env,
                        samples_ms=[],
                        failure_reason=(
                            "apryse: proprietary WebViewer round-trip harness not run on this Linux CI host"
                        ),
                        editor_id=editor_id,
                        lane=lane,
                    )
                    path = write_attempt(
                        attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial
                    )
                    summary_rows.append(
                        {
                            "criterion_id": sc_id,
                            "editor_id": editor_id,
                            "outcome": "not_run",
                            "failure_reason": trial["failure_reason"],
                            "attempt_file": _attempt_ref(path),
                            "publishable": False,
                        }
                    )
                    continue
                if args.dry_run:
                    trial = _trial_dict(
                        criterion_id=sc_id,
                        layer=layer,
                        boundary=boundary,
                        outcome="not_run",
                        env=env,
                        samples_ms=[],
                        failure_reason="dry-run",
                        editor_id=editor_id,
                        lane=lane,
                    )
                    path = write_attempt(
                        attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial
                    )
                    summary_rows.append(
                        {
                            "criterion_id": sc_id,
                            "editor_id": editor_id,
                            "outcome": "not_run",
                            "failure_reason": "dry-run",
                            "attempt_file": _attempt_ref(path),
                            "publishable": False,
                        }
                    )
                    continue
                validate_sample_budget(env, budget)
                with tempfile.TemporaryDirectory(prefix="perf_c21_") as tmp:
                    tmp_path = Path(tmp)
                    try:
                        cpu_samples, wall_list, _lasto = _collect_child_cpu_only(
                            editor_id=editor_id,
                            docx_body=docx_body,
                            tmp_path=tmp_path,
                            workload_id=args.workload,
                            attempt_count=budget,
                        )
                    except Exception as exc:
                        fail = _trial_dict(
                            criterion_id=sc_id,
                            layer=layer,
                            boundary=boundary,
                            outcome="failed",
                            env=env,
                            samples_ms=[],
                            failure_reason="harness-error: %s" % exc,
                            editor_id=editor_id,
                            lane=lane,
                        )
                        path = write_attempt(
                            attempt_dir,
                            "%s-%s-fail-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:8]),
                            fail,
                        )
                        summary_rows.append(
                            {
                                "criterion_id": sc_id,
                                "editor_id": editor_id,
                                "outcome": "failed",
                                "error": str(exc),
                                "attempt_file": _attempt_ref(path),
                                "publishable": False,
                            }
                        )
                        continue
                    stats = summarize(cpu_samples, env["cache_state"], env["repetition_unit"], seed=seed)
                    pub, reason = trial_publishable_flags(env, layer, len(cpu_samples))
                    if pub:
                        pub = False
                        reason = (
                            "ci_coarse cannot publish native CPU probe; "
                            "sample is getrusage(RUSAGE_CHILDREN) delta per subprocess run"
                        )
                    pub, reason = _finalize_publishable(pub, reason, env)
                    diag = {
                        "probe": "linux_getrusage_rusage_children_per_subprocess_ms",
                        "note": "measures direct child CPU of the harness driver process, not full editor tree",
                    }
                    trial = _trial_dict(
                        criterion_id=sc_id,
                        layer=layer,
                        boundary=boundary,
                        outcome="measured",
                        env=env,
                        samples_ms=cpu_samples,
                        editor_id=editor_id,
                        lane=lane,
                        summary_stats=stats,
                        publishable=pub,
                        publication_block_reason=reason,
                        diagnostic=diag,
                    )
                    path = write_attempt(attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial)
                    wall_med = summarize(wall_list, env["cache_state"], env["repetition_unit"], seed=seed)["median"]
                    summary_rows.append(
                        {
                            "criterion_id": sc_id,
                            "editor_id": editor_id,
                            "outcome": "measured",
                            "median_ms": stats["median"],
                            "child_cpu_ms_median": stats["median"],
                            "subprocess_wall_ms_median": wall_med,
                            "attempt_file": _attempt_ref(path),
                            "publishable": pub,
                        }
                    )
                continue

            if sc_id == "C24":
                outcome_c24, fail_c24, _diag = c24_boundary_decision(editor_id, execution_profile)
                if outcome_c24 == "unverified":
                    trial = _trial_dict(
                        criterion_id=sc_id,
                        layer=layer,
                        boundary=boundary,
                        outcome="unverified",
                        env=env,
                        samples_ms=[],
                        editor_id=editor_id,
                        lane=lane,
                    )
                else:
                    trial = _trial_dict(
                        criterion_id=sc_id,
                        layer=layer,
                        boundary=boundary,
                        outcome="not_run",
                        env=env,
                        samples_ms=[],
                        failure_reason=fail_c24 or "wasm_boundary",
                        editor_id=editor_id,
                        lane=lane,
                    )
                path = write_attempt(attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial)
                summary_rows.append(
                    {
                        "criterion_id": sc_id,
                        "editor_id": editor_id,
                        "outcome": trial["outcome"],
                        "failure_reason": trial.get("failure_reason"),
                        "attempt_file": _attempt_ref(path),
                        "publishable": False,
                    }
                )
                continue

            trial = _trial_dict(
                criterion_id=sc_id,
                layer=layer,
                boundary=boundary,
                outcome="not_run",
                env=env,
                samples_ms=[],
                failure_reason="adapter-not-implemented: criterion %s on %s" % (sc_id, execution_profile),
                editor_id=editor_id,
                lane=lane,
            )
            path = write_attempt(attempt_dir, "%s-%s-%s" % (sc_id.lower(), editor_id, uuid.uuid4().hex[:10]), trial)
            summary_rows.append(
                {
                    "criterion_id": sc_id,
                    "editor_id": editor_id,
                    "outcome": "not_run",
                    "failure_reason": trial["failure_reason"],
                    "attempt_file": _attempt_ref(path),
                    "publishable": False,
                }
            )

    payload = {
        "execution_profile": execution_profile,
        "host_class": "ci_coarse",
        "workload_id": args.workload,
        "fixture_sha256": sha,
        "dry_run": args.dry_run,
        "criteria": list(catalog.keys()),
        "editors": summary_rows,
    }
    assert_ci_contract_summary_valid(payload)
    summary_path = out_root / "summary.json"
    summary_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
