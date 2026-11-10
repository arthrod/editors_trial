#!/usr/bin/env python3
"""One-off adversarial C10 (viewport scroll) for browser harness hosts."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2].resolve()
sys.path.insert(0, str(REPO))

from perf.fixtures.generate import build_workload, correctness_fixtures, docx_zip_bytes  # noqa: E402
from perf.fixtures.profiles import size_ladder  # noqa: E402
from perf.runner.browser_run import run_cli, fixture_path as run_fixture, write_json, record_process
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402
from perf.runner.benchmark_ci_contract import INTERPRETATION_CONDITIONS, _host_base, _trial_dict  # noqa: E402
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS, _start_server, _stop_server  # noqa: E402
from perf.schema import validate_trial  # noqa: E402

SCROLL_PROBE = REPO / "perf" / "runner" / "adversarial_c10_scroll.mjs"


def _scroll_samples(*, target: dict, corpus_path: Path, pairs: int) -> list[float]:
    import shutil

    from perf.runner.browser_hosts import select_fixture
    select_fixture(target, corpus_path)
    node = shutil.which("node") or "node"
    cmd = [
        node,
        str(SCROLL_PROBE),
        "--url",
        target["url"],
        "--corpus",
        str(corpus_path.resolve()),
        "--corpus-route",
        target["corpus_route"],
        "--ready-selector",
        target.get("ready_selector", ""),
        "--pairs",
        str(pairs),
    ]
    if target.get("sample_route"):
        cmd.extend(["--sample-route", target["sample_route"]])
    if target.get("ready_js"):
        cmd.extend(["--ready-js", target["ready_js"]])
    if target.get("ready_text"):
        cmd.extend(["--ready-text", target["ready_text"]])
    if target.get("wait_after_ready"):
        cmd.extend(["--wait-after-ready", str(target["wait_after_ready"])])
    proc = subprocess.run(
        cmd,
        cwd=str(REPO / "harness" / "ui"),
        capture_output=True,
        text=True,
        timeout=600,
    )
    record_process(proc)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "scroll probe failed")
    payload = json.loads(proc.stdout)
    return [float(x) for x in payload["scroll_frame_ms"]]


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--editor", default="plate")
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=3)
    args = parser.parse_args()

    target = dict(BROWSER_TARGETS[args.editor])
    workload_row = next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs")
    built = build_workload(workload_row)
    docx_body = docx_zip_bytes(built["body"] + b"\n" + correctness_fixtures()["unicode"])
    sha = hashlib.sha256(docx_body).hexdigest()
    out_root = args.out_root
    attempt_dir = out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = run_fixture(workload_row["workload_id"], docx_body, out_root / "fixture.docx")

    from perf.adapters.capabilities import default_lane, pin_label  # noqa: E402

    editor_id = args.editor
    proc = _start_server(editor_id, target)
    try:
        samples = _scroll_samples(target=target, corpus_path=fixture_path, pairs=args.pairs)
    finally:
        _stop_server(proc)

    env = _host_base(
        editor_id=editor_id,
        editor_version=pin_label(editor_id),
        execution_profile="ci_broad",
        fixture_sha256=sha,
        workload_row=workload_row,
        docx_size=len(docx_body),
        cache_state="warm_steady",
        repetition_unit="fresh_process",
        run_kind="timing",
        feature_profile_name="P0",
    )
    env["interpretation_conditions"] = list(INTERPRETATION_CONDITIONS)
    stats = summarize(samples, "warm_steady", "fresh_process", seed=0)
    trial = _trial_dict(
        criterion_id="C10",
        layer="browser_visible",
        boundary="frame_time",
        outcome="measured",
        env=env,
        samples_ms=samples,
        editor_id=editor_id,
        lane=BROWSER_TARGETS[editor_id].get("lane") or default_lane(editor_id),
        summary_stats=stats,
        publishable=False,
        publication_block_reason="adversarial scroll probe; ci_coarse",
        diagnostic={"suite": "adversarial", "probe": "scroll_container_frac_0.5"},
    )
    validate_trial(trial)
    path = write_attempt(
        attempt_dir,
        "c10-%s-%s" % (editor_id, uuid.uuid4().hex[:10]),
        trial,
    )
    summary_path = out_root / "summary_c10.json"
    row = {
        "criterion_id": "C10",
        "editor_id": editor_id,
        "outcome": "measured",
        "median_ms": stats["median"],
        "samples_ms": samples,
        "attempt_file": str(path.resolve()),
        "publishable": False,
    }
    write_json(summary_path, row)
    print("Wrote %s (median %.1f ms)" % (path, stats["median"]))
    return 0


def main() -> int:
    return run_cli(_main, 'adversarial_c10_scroll', BROWSER_TARGETS, count_flag='--pairs', default_count=3, single=True)


if __name__ == "__main__":
    raise SystemExit(main())
