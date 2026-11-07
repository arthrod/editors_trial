#!/usr/bin/env python3
"""Rapid load/unload fixture probes (Playwright)."""

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

from perf.fixtures.generate import build_workload, docx_zip_bytes  # noqa: E402
from perf.fixtures.profiles import size_ladder  # noqa: E402
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.benchmark_ci_contract import _host_base, _trial_dict  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402

MJS = REPO / "perf/runner/benchmark_load_unload.mjs"
GEN = REPO / "perf/fixtures/generated"


def ensure_fixtures():
    GEN.mkdir(parents=True, exist_ok=True)
    row = next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs")
    small = GEN / "small-micro-paragraphs.docx"
    if not small.is_file():
        small.write_bytes(docx_zip_bytes(build_workload(row)["body"]))
    big_row = next(w for w in size_ladder() if w["workload_id"] == "one-paragraph")
    built = build_workload(big_row)
    body = built["body"][:8000] if len(built["body"]) > 8000 else built["body"] * 200
    big = GEN / "gigantic-one-paragraph.docx"
    if not big.is_file():
        big.write_bytes(docx_zip_bytes(body))
    manifest = GEN.parent / "manifest.json"
    if not manifest.is_file():
        manifest.write_text(json.dumps({"generated": [small.name, big.name]}, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument("--fixture", type=Path, default=None)
    args = parser.parse_args()
    ensure_fixtures()
    fixture = args.fixture or GEN / "small-micro-paragraphs.docx"
    attempt_dir = args.out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    node = shutil.which("node") or "node"
    for editor_id, target in BROWSER_TARGETS.items():
        if target.get("skip_edit"):
            continue
        cmd = [
            node,
            str(MJS),
            "--url",
            target["url"],
            "--corpus",
            str(fixture.resolve()),
            "--ready-selector",
            target.get("ready_selector", "#editor"),
            "--pairs",
            str(args.pairs),
        ]
        proc = subprocess.run(cmd, cwd=str(REPO / "harness/ui"), capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            rows.append({"editor_id": editor_id, "outcome": "failed", "reason": proc.stderr[:200]})
            continue
        payload = json.loads(proc.stdout)
        load = [float(s["load_ms"]) for s in payload["samples"]]
        unload = [float(s["unload_ms"]) for s in payload["samples"]]
        env = _host_base(
            editor_id=editor_id,
            editor_version="harness",
            execution_profile="ci_broad",
            fixture_sha256="0" * 64,
            workload_row=next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs"),
            docx_size=fixture.stat().st_size,
            cache_state="process_cold_fs_warm",
            repetition_unit="fresh_process",
            run_kind="timing",
            feature_profile_name="P0",
        )
        stats = summarize(load, "process_cold_fs_warm", "fresh_process", seed=2)
        trial = _trial_dict(
            criterion_id="C03",
            layer="browser_visible",
            boundary="model_ready_browser",
            outcome="measured",
            env=env,
            samples_ms=load,
            editor_id=editor_id,
            lane="editor",
            summary_stats=stats,
            publishable=False,
            publication_block_reason="load_unload diagnostic",
            diagnostic={"metric": "load_ms", "unload_ms": unload},
        )
        write_attempt(attempt_dir, "load-%s-%s" % (editor_id, uuid.uuid4().hex[:8]), trial)
        rows.append({"editor_id": editor_id, "outcome": "measured", "n": len(load)})
    (args.out_root / "summary.json").write_text(json.dumps({"suite": "load_unload", "editors": rows}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
