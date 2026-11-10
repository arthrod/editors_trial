"""Aggregate browser-lane trials into report E2 cells (#136)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import sys

from perf.analysis.summarize import percentile
from perf.runner.speed_headless import MIN_PUBLISH_N

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from build.perf_e_tables import reproduced  # noqa: E402

_REFUSAL_OUTCOMES = frozenset(
    {"failed", "refused", "not_applicable", "unsupported", "unverified", "not_run"}
)


def _load_summary(run_directory: Path) -> dict | None:
    path = run_directory / "summary.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _scheduled_for_editor(summary: dict | None, editor_id: str, default: int) -> int:
    order = (summary or {}).get("order") or []
    if not order:
        return default
    return sum(1 for _rep, ed in order if ed == editor_id)


def _run_blocks_publication(summary: dict | None) -> tuple[bool, str | None]:
    if summary is None:
        return False, None
    if summary.get("outcome") == "failed":
        return True, summary.get("failure_reason") or "run failed"
    reason = summary.get("publication_block_reason")
    if summary.get("publishable") is False and reason:
        return True, str(reason)
    if summary.get("failure_reason") in ("repos_modified", "repos_dirty_at_start"):
        return True, str(summary.get("failure_reason"))
    return False, None


def _iter_sample_rows(run_directory: Path):
    samples_dir = run_directory / "samples"
    if not samples_dir.is_dir():
        return
    for path in sorted(samples_dir.glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(row, dict):
            yield row


def _trial_path(run_directory: Path, sample_row: dict, criterion_id: str) -> Path | None:
    cell_directory = sample_row.get("cell_directory")
    if cell_directory:
        attempts = Path(cell_directory) / "attempts"
    else:
        rejected = sample_row.get("rejected_evidence_directory")
        if rejected:
            attempts = Path(rejected) / "cell" / "attempts"
        else:
            return None
    if not attempts.is_dir():
        return None
    slug = criterion_id.lower()
    direct = attempts / f"{slug}.json"
    if direct.is_file():
        return direct
    for path in attempts.glob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if row.get("criterion_id") == criterion_id:
            return path
    return None


def _frame_interval_ms(trials) -> float | None:
    for trial in trials:
        diagnostic = trial.get("diagnostic") or {}
        value = diagnostic.get("frame_interval_ms")
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def _read_rows(directory):
    for path in sorted(directory.rglob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(row, dict):
            yield path, row


def _iter_trials(run_directory: Path):
    for _, row in _read_rows(run_directory / "cells"):
        if row.get("criterion_id") and row.get("editor_id"):
            yield row


def _number(value):
    import math
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _one_repetition_value(trial: dict) -> tuple[float | None, bool | None]:
    if trial.get("outcome") != "measured":
        return None, None
    if trial.get("publishable") is False:
        return None, None
    samples = trial.get("samples_ms") or []
    numeric = [float(sample) for sample in samples if isinstance(sample, (int, float))]
    if not numeric:
        return None, None
    value = percentile(numeric, 50) if len(numeric) > 1 else numeric[0]
    flags = trial.get("sub_frame_samples")
    if flags is None:
        flags = (trial.get("diagnostic") or {}).get("sub_frame_samples")
    if flags is None:
        return value, None
    if not isinstance(flags, list) or len(flags) != len(samples):
        return value, None
    sub = any(flags)
    return value, sub


def _refusal_key(sample_or_trial: dict) -> str:
    reason = sample_or_trial.get("failure_reason") or sample_or_trial.get("publication_block_reason") or sample_or_trial.get("outcome")
    return str(reason).split(":", 1)[0].strip()


def build_run_cell(run_directory: Path, editor_id: str, criterion_id: str, *, scheduled: int = 30) -> dict:
    summary = _load_summary(run_directory)
    scheduled = _scheduled_for_editor(summary, editor_id, scheduled)
    blocked, block_reason = _run_blocks_publication(summary)
    kept, raw, sub_frame, intervals = [], [], [], []
    refusals: Counter[str] = Counter()
    refused_launches = {}
    for path, row in _read_rows(run_directory / "samples"):
        if row.get("editor_id") == editor_id and (row.get("outcome") in _REFUSAL_OUTCOMES or row.get("publishable") is False):
            refused_launches[path.stem] = row.get("failure_reason") or row.get("publication_block_reason") or row.get("outcome") or "refused"
    for reason in refused_launches.values():
        refusals[str(reason).split(":", 1)[0]] += 1
    seen = set()
    for path, trial in _read_rows(run_directory / "cells"):
        if trial.get("editor_id") != editor_id or trial.get("criterion_id") != criterion_id:
            continue
        launch = path.relative_to(run_directory / "cells").parts[0]
        if launch in refused_launches or launch in seen:
            continue
        if trial.get("publishable") is False:
            refusals[_refusal_key(trial)] += 1
            continue
        outcome = trial.get("outcome")
        if outcome == "measured":
            samples = [float(x) for x in trial.get("samples_ms", []) if _number(x)]
            if not samples:
                continue
            seen.add(launch)
            raw.append(samples)
            kept.append(percentile(samples, 50))
            flags = trial.get("sub_frame_samples", (trial.get("diagnostic") or {}).get("sub_frame_samples"))
            if flags is not None and len(flags) == len(samples) and all(isinstance(x, bool) for x in flags):
                sub_frame.extend(flags)
            interval = (trial.get("diagnostic") or {}).get("frame_interval_ms")
            if _number(interval) and interval > 0:
                intervals.append(float(interval))
        elif outcome in _REFUSAL_OUTCOMES:
            reason = trial.get("failure_reason") or trial.get("publication_block_reason") or outcome
            refusals[str(reason).split(":", 1)[0]] += 1
    return {
        "editor_id": editor_id, "criterion_id": criterion_id, "scheduled": scheduled,
        "blocked": blocked, "block_reason": block_reason,
        "kept_ms": kept, "raw_samples_ms": raw, "sub_frame": sub_frame,
        "refusals": dict(refusals),
        "frame_interval_ms": percentile(intervals, 50) if intervals else None,
        "stats": {"n": len(kept), "median": percentile(kept, 50), "p90": percentile(kept, 90)} if kept else None,
    }


def _sub_frame_share(cell: dict) -> float | None:
    if not cell.get("sub_frame_tracked"):
        return None
    flags = cell.get("sub_frame") or []
    if not flags:
        return 0.0
    return sum(1 for flag in flags if flag) / len(flags)


def _format_p90(p90: float, frame_interval: float) -> str:
    if p90 < frame_interval:
        return f"p90 < 1 frame ({frame_interval:g} ms)"
    return f"p90 {p90:.1f} ms"


def _format_median(median: float, frame_interval: float) -> str:
    if median < frame_interval:
        return f"< 1 frame ({frame_interval:g} ms)"
    return f"{median:.1f} ms"


def _median_for_agreement(cell: dict) -> float | None:
    stats = cell.get("stats")
    if not stats:
        return None
    frame_interval = cell.get("frame_interval_ms")
    median = stats["median"]
    if frame_interval and median < frame_interval:
        return frame_interval
    return median


def publication_text(cell: dict) -> str:
    if cell.get("blocked"):
        reason = cell.get("block_reason") or "run blocked"
        return f"run not publishable ({reason})"

    stats = cell.get("stats")
    scheduled = cell.get("scheduled", 30)
    n_kept = stats["n"] if stats else 0
    if n_kept < MIN_PUBLISH_N:
        reasons = cell.get("refusals") or {}
        reason_text = "; ".join(f"{key}: {count}" for key, count in sorted(reasons.items())) or "none counted"
        return f"not enough samples (n = {n_kept} of {scheduled}; reasons {reason_text})"

    frame_interval = cell.get("frame_interval_ms")
    if frame_interval is None:
        return f"no witnessed frame interval (n = {n_kept} of {scheduled})"

    median = stats["median"]
    p90 = stats["p90"]
    share = _sub_frame_share(cell)
    share_text = f"; {share * 100:.0f}% sub-frame samples" if share is not None else ""
    return f"{_format_median(median, frame_interval)}{share_text}; {_format_p90(p90, frame_interval)}"


def publish_dual_runs(primary: Path, reproduction: Path, editor_id: str, criterion_id: str, *, scheduled: int = 30) -> str:
    primary_cell = build_run_cell(primary, editor_id, criterion_id, scheduled=scheduled)
    reproduction_cell = build_run_cell(reproduction, editor_id, criterion_id, scheduled=scheduled)
    primary_text = publication_text(primary_cell)
    reproduction_text = publication_text(reproduction_cell)
    if "not enough samples" in primary_text or "not enough samples" in reproduction_text:
        return reproduction_text if "not enough" in reproduction_text else primary_text
    if primary_text.startswith("run not publishable") or reproduction_text.startswith("run not publishable"):
        return primary_text if primary_text.startswith("run not publishable") else reproduction_text
    if primary_text.startswith("no witnessed frame interval") or reproduction_text.startswith("no witnessed frame interval"):
        return primary_text if primary_text.startswith("no witnessed") else reproduction_text

    frame_interval = primary_cell.get("frame_interval_ms") or reproduction_cell.get("frame_interval_ms")
    if frame_interval is None:
        return "no witnessed frame interval"

    primary_median = _median_for_agreement(primary_cell)
    reproduction_median = _median_for_agreement(reproduction_cell)
    if primary_median is None or reproduction_median is None:
        return primary_text
    if not reproduced(primary_median, reproduction_median, abs_tol=frame_interval):
        p_fmt = _format_median(primary_cell["stats"]["median"], frame_interval)
        r_fmt = _format_median(reproduction_cell["stats"]["median"], frame_interval)
        return f"not reproduced (primary {p_fmt}; reproduction {r_fmt})"
    return primary_text
