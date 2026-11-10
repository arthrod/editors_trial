"""Aggregate browser-lane trials into report E2 cells (#136)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import json

from perf.analysis.summarize import percentile
from perf.runner.speed_headless import MIN_PUBLISH_N

_REFUSAL_OUTCOMES = frozenset(
    {"failed", "refused", "not_applicable", "unsupported", "unverified", "not_run"}
)


def _iter_trials(run_directory: Path):
    for path in sorted(run_directory.rglob("*.json")):
        if path.name == "summary.json":
            continue
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(row, dict):
            continue
        if row.get("criterion_id") and row.get("editor_id"):
            yield row


def _frame_interval_ms(trials) -> float | None:
    for trial in trials:
        diagnostic = trial.get("diagnostic") or {}
        value = diagnostic.get("frame_interval_ms")
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def build_run_cell(run_directory: Path, editor_id: str, criterion_id: str, *, scheduled: int = 30) -> dict:
    trials = [row for row in _iter_trials(run_directory) if row.get("editor_id") == editor_id and row.get("criterion_id") == criterion_id]
    kept = []
    sub_frame = []
    refusals: Counter[str] = Counter()
    for trial in trials:
        outcome = trial.get("outcome")
        if outcome == "measured":
            samples = trial.get("samples_ms") or []
            flags = trial.get("sub_frame_samples") or trial.get("diagnostic", {}).get("sub_frame_samples") or []
            if flags and len(flags) != len(samples):
                flags = [False] * len(samples)
            for index, sample in enumerate(samples):
                if isinstance(sample, (int, float)):
                    kept.append(float(sample))
                    sub_frame.append(bool(flags[index]) if index < len(flags) else False)
            continue
        if outcome in _REFUSAL_OUTCOMES:
            reason = trial.get("failure_reason") or trial.get("publication_block_reason") or outcome
            refusals[str(reason).split(":", 1)[0]] += 1
    frame_interval = _frame_interval_ms(trials)
    stats = None
    if kept:
        stats = {
            "n": len(kept),
            "median": percentile(kept, 50),
            "p90": percentile(kept, 90),
        }
    return {
        "editor_id": editor_id,
        "criterion_id": criterion_id,
        "scheduled": scheduled,
        "kept_ms": kept,
        "sub_frame": sub_frame,
        "refusals": dict(refusals),
        "frame_interval_ms": frame_interval,
        "stats": stats,
    }


def _sub_frame_share(cell: dict) -> float | None:
    flags = cell.get("sub_frame") or []
    if not flags:
        return None
    return sum(1 for flag in flags if flag) / len(flags)


def _format_p90(cell: dict, p90: float, frame_interval: float) -> str:
    if p90 < frame_interval:
        return f"p90 < 1 frame ({frame_interval:g} ms)"
    return f"p90 {p90:.1f} ms"


def publication_text(cell: dict) -> str:
    stats = cell.get("stats")
    scheduled = cell.get("scheduled", 30)
    n_kept = stats["n"] if stats else 0
    if n_kept < MIN_PUBLISH_N:
        reasons = cell.get("refusals") or {}
        reason_text = "; ".join(f"{key}: {count}" for key, count in sorted(reasons.items())) or "none counted"
        return f"not enough samples (n = {n_kept} of {scheduled}; reasons {reason_text})"
    frame_interval = cell.get("frame_interval_ms") or 16.7
    median = stats["median"]
    p90 = stats["p90"]
    share = _sub_frame_share(cell)
    share_text = f"; {share * 100:.0f}% sub-frame samples" if share is not None else ""
    if median < frame_interval:
        return f"< 1 frame ({frame_interval:g} ms){share_text}; {_format_p90(cell, p90, frame_interval)}"
    return f"{median:.1f} ms{share_text}; {_format_p90(cell, p90, frame_interval)}"


def publish_dual_runs(primary: Path, reproduction: Path, editor_id: str, criterion_id: str, *, scheduled: int = 30) -> str:
    primary_cell = build_run_cell(primary, editor_id, criterion_id, scheduled=scheduled)
    reproduction_cell = build_run_cell(reproduction, editor_id, criterion_id, scheduled=scheduled)
    primary_text = publication_text(primary_cell)
    reproduction_text = publication_text(reproduction_cell)
    if "not enough samples" in primary_text or "not enough samples" in reproduction_text:
        failing = reproduction_text if "not enough" in reproduction_text else primary_text
        return failing
    return primary_text
