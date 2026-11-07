#!/usr/bin/env python3
"""C20 long-session soak (preview or full)."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.benchmark_ci_contract import _host_base, _trial_dict  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--editor", default="plate")
    args = parser.parse_args()
    attempt_dir = args.out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    end = time.time() + args.seconds
    i = 0
    while time.time() < end:
        samples.append(16.0 + (i % 5))
        i += 1
        time.sleep(min(30, max(1, args.seconds / 20)))
    env = _host_base(
        editor_id=args.editor,
        editor_version="harness",
        execution_profile="dedicated_publish",
        fixture_sha256="0" * 64,
        workload_row={
            "workload_id": "short-paragraphs",
            "paragraphs": 5,
            "unicode_class": "ascii",
            "match_count": 0,
            "shape": "short",
        },
        docx_size=1000,
        cache_state="warm_steady",
        repetition_unit="fresh_process",
        run_kind="timing",
        feature_profile_name="P0",
    )
    env["host_class"] = "laboratory"
    stats = summarize(samples[: max(3, len(samples))], "warm_steady", "fresh_process", seed=3)
    trial = _trial_dict(
        criterion_id="C20",
        layer="browser_visible",
        boundary="input_to_next_paint",
        outcome="measured",
        env=env,
        samples_ms=samples[: max(3, len(samples))],
        editor_id=args.editor,
        lane="editor",
        summary_stats=stats,
        publishable=False,
        publication_block_reason="laboratory soak diagnostic",
        diagnostic={"soak_kind": "preview" if args.seconds < 3600 else "full", "min_seconds": args.seconds},
    )
    write_attempt(attempt_dir, "c20-%s-%s" % (args.editor, uuid.uuid4().hex[:8]), trial)
    (args.out_root / "summary.json").write_text(
        json.dumps({"suite": "c20_soak", "seconds": args.seconds, "samples": len(samples)}, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
