#!/usr/bin/env python3
"""C20 stability soak: real headless samples appended to samples.jsonl."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.fixtures.generate import build_workload, correctness_fixtures, docx_zip_bytes  # noqa: E402
from perf.fixtures.profiles import size_ladder  # noqa: E402
from perf.runner.benchmark_ci_contract import _run_plate  # noqa: E402

DEFAULT_OUT = REPO / "perf" / "out" / "c20_soak_2026_11_07"
OPERATION = "c02_plate_headless_roundtrip"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fixture_docx() -> tuple[Path, tempfile.TemporaryDirectory]:
    row = next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs")
    built = build_workload(row)
    body = built["body"] + b"\n" + correctness_fixtures()["unicode"]
    docx_bytes = docx_zip_bytes(body)
    tmp = tempfile.TemporaryDirectory(prefix="c20-soak-")
    base = Path(tmp.name)
    indocx = base / "micro-paragraphs.docx"
    indocx.write_bytes(docx_bytes)
    return indocx, tmp


def _one_sample(indocx: Path) -> float:
    outdocx = indocx.parent / ("out-%s.docx" % uuid.uuid4().hex[:8])
    elapsed_ms, *_rest = _run_plate(indocx, outdocx)
    return float(elapsed_ms)


def _append_sample(
    samples_path: Path,
    *,
    elapsed_ms: float,
    operation: str,
    started_at: float,
) -> None:
    line = {
        "timestamp": _iso_now(),
        "elapsed_ms": round(elapsed_ms, 3),
        "operation": operation,
        "wall_elapsed_ms": round((time.perf_counter() - started_at) * 1000.0, 3),
    }
    with samples_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, separators=(",", ":")) + "\n")
        fh.flush()


def run_soak(
    *,
    seconds: int,
    out_root: Path,
    write_preview: bool,
    preview_name: str,
) -> dict:
    out_root.mkdir(parents=True, exist_ok=True)
    samples_path = out_root / "samples.jsonl"
    status_path = out_root / "status.json"
    if not status_path.is_file():
        status_path.write_text(
            json.dumps(
                {
                    "started_at": _iso_now(),
                    "planned_seconds": 3600,
                    "publishable": False,
                    "editor": "plate",
                    "lane": "headless_docx",
                    "cache_state": "warm_steady",
                    "operation": OPERATION,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    indocx, tmp = _fixture_docx()
    soak_start = time.perf_counter()
    end = soak_start + seconds
    elapsed_samples: list[float] = []

    try:
        while time.perf_counter() < end:
            try:
                ms = _one_sample(indocx)
            except Exception as exc:
                err_path = out_root / "last_error.txt"
                err_path.write_text(str(exc) + "\n", encoding="utf-8")
                raise
            elapsed_samples.append(ms)
            _append_sample(samples_path, elapsed_ms=ms, operation=OPERATION, started_at=soak_start)
    finally:
        tmp.cleanup()

    summary = {
        "seconds_requested": seconds,
        "sample_count": len(elapsed_samples),
        "median_ms": statistics.median(elapsed_samples) if elapsed_samples else None,
        "operation": OPERATION,
        "finished_at": _iso_now(),
    }
    if write_preview:
        (out_root / preview_name).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write-preview", action="store_true")
    parser.add_argument("--preview-name", default="preview_60s.json")
    args = parser.parse_args()
    summary = run_soak(
        seconds=args.seconds,
        out_root=args.out_root,
        write_preview=args.write_preview,
        preview_name=args.preview_name,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
