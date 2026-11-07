#!/usr/bin/env python3
"""Drive C07–C12, C22–C23 browser interaction probes for harness UIs."""

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

from perf.adapters.capabilities import default_lane  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402
from perf.fixtures.generate import build_workload, correctness_fixtures, docx_zip_bytes  # noqa: E402
from perf.fixtures.profiles import size_ladder  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.benchmark_ci_contract import (  # noqa: E402
    INTERPRETATION_CONDITIONS,
    _finalize_publishable,
    _host_base,
    _trial_dict,
)
from perf.runner.benchmark_warm_cold import (  # noqa: E402
    BROWSER_TARGETS,
    _start_server,
    _stop_server,
)
from perf.runner.harness_ui_versions import browser_harness_editor_version  # noqa: E402
from perf.analysis.publication_gate import trial_publishable_flags  # noqa: E402
from perf.adapters.capabilities import pin_label  # noqa: E402
from perf.schema import validate_trial  # noqa: E402

INTERACTIONS = REPO / "perf" / "runner" / "browser_interactions.mjs"
CANVAS = REPO / "perf" / "runner" / "canvas_interactions.mjs"
C10_SCROLL = REPO / "perf" / "runner" / "adversarial_c10_scroll.mjs"


def _env(editor_id, editor_version, sha, workload_row, docx_size, execution_profile, host_class):
    env = _host_base(
        editor_id=editor_id,
        editor_version=editor_version,
        execution_profile=execution_profile,
        fixture_sha256=sha,
        workload_row=workload_row,
        docx_size=docx_size,
        cache_state="warm_steady",
        repetition_unit="fresh_process",
        run_kind="timing",
        feature_profile_name="P0",
    )
    env["host_class"] = host_class
    env["headless"] = True
    env["display_refresh_hz"] = None
    env["interpretation_conditions"] = list(INTERPRETATION_CONDITIONS)
    return env


def _run_mjs(script: Path, args: list[str]) -> dict:
    node = shutil.which("node") or "node"
    proc = subprocess.run(
        [node, str(script), *args],
        cwd=str(REPO / "harness" / "ui"),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "mjs probe failed")
    return json.loads(proc.stdout)


def _write_measured(attempt_dir, cid, boundary, layer, editor_id, lane, env, samples, diagnostic=None):
    stats = summarize(samples, env["cache_state"], env["repetition_unit"], seed=0)
    pub, reason = trial_publishable_flags(env, layer, stats["n"])
    pub, reason = _finalize_publishable(pub, reason, env)
    trial = _trial_dict(
        criterion_id=cid,
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
        diagnostic=diagnostic,
    )
    validate_trial(trial)
    return write_attempt(attempt_dir, "%s-%s-%s" % (cid.lower(), editor_id, uuid.uuid4().hex[:10]), trial)


def _write_not_run(attempt_dir, cid, boundary, layer, editor_id, lane, env, failure_reason, diagnostic=None):
    trial = _trial_dict(
        criterion_id=cid,
        layer=layer,
        boundary=boundary,
        outcome="not_run",
        env=env,
        samples_ms=[],
        failure_reason=failure_reason,
        editor_id=editor_id,
        lane=lane,
        diagnostic=diagnostic,
    )
    return write_attempt(attempt_dir, "%s-%s-%s" % (cid.lower(), editor_id, uuid.uuid4().hex[:10]), trial)


def _mjs_base_args(target: dict, corpus: Path) -> list[str]:
    args = [
        "--url",
        target["url"],
        "--corpus",
        str(corpus.resolve()),
        "--corpus-route",
        target["corpus_route"],
        "--ready-selector",
        target.get("ready_selector", ""),
        "--edit-selector",
        target.get("edit_selector", '[contenteditable="true"]'),
    ]
    if target.get("sample_route"):
        args.extend(["--sample-route", target["sample_route"]])
    if target.get("ready_js"):
        args.extend(["--ready-js", target["ready_js"]])
    if target.get("ready_text"):
        args.extend(["--ready-text", target["ready_text"]])
    if target.get("wait_after_ready"):
        args.extend(["--wait-after-ready", str(target["wait_after_ready"])])
    return args


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument("--editors", nargs="*", default=None)
    parser.add_argument("--execution-profile", default="ci_broad")
    parser.add_argument("--host-class", default="ci_coarse")
    args = parser.parse_args()

    workload_row = next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs")
    built = build_workload(workload_row)
    docx_body = docx_zip_bytes(built["body"] + b"\n" + correctness_fixtures()["unicode"])
    sha = hashlib.sha256(docx_body).hexdigest()
    attempt_dir = args.out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    corpus = args.out_root / "micro-paragraphs.docx"
    if not corpus.is_file():
        corpus.write_bytes(docx_body)

    editors = args.editors or list(BROWSER_TARGETS.keys())
    rows: list[dict] = []

    for editor_id in editors:
        target = BROWSER_TARGETS.get(editor_id)
        if not target:
            continue
        lane = default_lane(editor_id)
        editor_version, _ = browser_harness_editor_version(editor_id, pin_label(editor_id))
        env = _env(editor_id, editor_version, sha, workload_row, len(docx_body), args.execution_profile, args.host_class)
        proc = _start_server(editor_id, target)
        base = _mjs_base_args(target, corpus)
        try:
            for cid, mjs_criterion in (
                ("C07", "c07"),
                ("C08", "c08"),
                ("C09", "c09"),
                ("C10", "c10"),
                ("C12", "c12"),
                ("C22", "c22"),
                ("C23", "c23"),
            ):
                boundary = "input_to_next_paint"
                layer = "browser_visible"
                try:
                    if editor_id == "canvas" and cid in ("C07", "C10"):
                        payload = _run_mjs(
                            CANVAS,
                            base
                            + ["--criterion", cid.lower(), "--pairs", str(args.pairs)],
                        )
                    elif cid == "C10":
                        node = shutil.which("node") or "node"
                        scroll = subprocess.run(
                            [node, str(C10_SCROLL), *base, "--pairs", str(args.pairs)],
                            cwd=str(REPO / "harness" / "ui"),
                            capture_output=True,
                            text=True,
                            timeout=600,
                        )
                        if scroll.returncode != 0:
                            raise RuntimeError(scroll.stderr or scroll.stdout)
                        payload = {
                            "outcome": "measured",
                            "samples_ms": json.loads(scroll.stdout)["scroll_frame_ms"],
                        }
                    elif cid == "C12" and editor_id == "canvas":
                        continue
                    else:
                        if cid == "C10":
                            continue
                        payload = _run_mjs(
                            INTERACTIONS,
                            base
                            + ["--criterion", mjs_criterion, "--pairs", str(args.pairs)],
                        )
                    if payload.get("outcome") == "not_applicable":
                        path = _write_not_run(
                            attempt_dir,
                            cid,
                            boundary,
                            layer,
                            editor_id,
                            lane,
                            env,
                            payload.get("reason") or "not_applicable",
                        )
                        rows.append({"criterion_id": cid, "editor_id": editor_id, "outcome": "not_applicable"})
                    elif payload.get("outcome") == "measured" or payload.get("samples_ms"):
                        samples = [float(x) for x in payload["samples_ms"][: args.pairs * 2]]
                        path = _write_measured(
                            attempt_dir,
                            cid,
                            boundary,
                            layer,
                            editor_id,
                            lane,
                            env,
                            samples,
                            diagnostic={"suite": "browser_interactions"},
                        )
                        rows.append(
                            {
                                "criterion_id": cid,
                                "editor_id": editor_id,
                                "outcome": "measured",
                                "attempt_file": str(path.relative_to(REPO)),
                            }
                        )
                except Exception as exc:
                    path = _write_not_run(
                        attempt_dir,
                        cid,
                        boundary,
                        layer,
                        editor_id,
                        lane,
                        env,
                        "browser_probe: %s" % exc,
                    )
                    rows.append(
                        {
                            "criterion_id": cid,
                            "editor_id": editor_id,
                            "outcome": "failed",
                            "failure_reason": str(exc),
                            "attempt_file": str(path.relative_to(REPO)),
                        }
                    )
        finally:
            _stop_server(proc)

    summary = {
        "suite": "browser_interactions",
        "execution_profile": args.execution_profile,
        "host_class": args.host_class,
        "editors": rows,
    }
    args.out_root.mkdir(parents=True, exist_ok=True)
    (args.out_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
