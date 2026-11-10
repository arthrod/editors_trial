"""Aggregate browser-lane trials into report E2 cells (#136)."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import json
import sys
import re

from perf.analysis.summarize import percentile
from perf.runner.speed_headless import MIN_PUBLISH_N

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from build.perf_e_tables import reproduced  # noqa: E402

_REFUSAL_OUTCOMES = frozenset(
    {"failed", "refused", "not_applicable", "unsupported", "unverified", "not_run"}
)
from perf.runner.refusals import RUN_REFUSALS as _RUN_REFUSALS, refusal_code


def _trial_block(trial):
    code = refusal_code(trial)
    if code:
        return code
    if trial.get('publishable') is not True or _nested_unpublishable(trial.get('host_provenance')):
        return 'publishable_not_true'
    if trial.get('outcome') != 'measured':
        return 'crash'
    return None


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
def _nested_unpublishable(value):
    if isinstance(value, dict):
        return value.get('publishable') is False or any(_nested_unpublishable(v) for v in value.values())
    if isinstance(value, list):
        return any(_nested_unpublishable(v) for v in value)
    return False


def trial_measure(trial):
    diagnostic = trial.get('diagnostic') or {}
    return str(trial.get('measure') or diagnostic.get('size_rung') or diagnostic.get('measurement') or '')


def _read_rows(directory):
    for path in sorted(directory.rglob('*.json')):
        try:
            row = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            yield path, {'refusal_code': 'unreadable_trial'}
            continue
        if isinstance(row, dict):
            yield path, row
        else:
            yield path, {'refusal_code': 'unreadable_trial'}


def _iter_trials(run_directory: Path):
    for _, row in _read_rows(run_directory / 'cells'):
        if row.get('criterion_id') and row.get('editor_id'):
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


def build_run_cell(
    run_directory: Path, editor_id: str, criterion_id: str, *, scheduled: int = 30, measure: str = ''
) -> dict:
    summary = _load_summary(run_directory)
    scheduled = _scheduled_for_editor(summary, editor_id, scheduled)
    run_blocked, block_reason = _run_blocks_publication(summary)
    kept, raw, sub_frame, intervals = [], [], [], []
    refusals = Counter()
    failed_launches = set()
    trials = defaultdict(list)
    refused_launches = {}
    for path, trial in _read_rows(run_directory / 'cells'):
        launch = path.relative_to(run_directory / 'cells').parts[0]
        if trial.get('refusal_code') == 'unreadable_trial' and launch.endswith('-' + editor_id):
            refused_launches[launch] = 'unreadable_trial'
        if trial.get('editor_id') != editor_id or not trial.get('criterion_id'):
            continue
        code = refusal_code(trial)
        if code in _RUN_REFUSALS:
            refused_launches[launch] = code
        if trial['criterion_id'] == criterion_id and trial_measure(trial) == measure:
            trials[launch].append(trial)
    for path in (run_directory / 'rejected-evidence').glob('*'):
        if path.is_dir() and path.name.endswith('-' + editor_id):
            refused_launches[path.name] = 'quarantined'
    for path, row in _read_rows(run_directory / 'samples'):
        if row.get('editor_id') != editor_id:
            continue
        code = refusal_code(row)
        if code in _RUN_REFUSALS and refused_launches.get(path.stem) != 'unreadable_trial':
            refused_launches[path.stem] = code
        elif code and path.stem not in trials:
            refused_launches.setdefault(path.stem, code)
    for launch, code in refused_launches.items():
        refusals[code] += 1
        failed_launches.add(launch)
    for launch, rows in trials.items():
        if launch in refused_launches:
            continue
        reason = 'conflicting_trials' if len(rows) != 1 else _trial_block(rows[0])
        trial = rows[0]
        samples = trial.get('samples_ms')
        diagnostic = trial.get('diagnostic') or {}
        flags = trial.get('sub_frame_samples', diagnostic.get('sub_frame_samples'))
        interval = diagnostic.get('frame_interval_ms')
        interval = float(interval) if _number(interval) and interval > 0 else None
        if not reason and (
            not isinstance(samples, list)
            or not samples
            or not all(_number(x) for x in samples)
            or not isinstance(flags, list)
            or len(flags) != len(samples)
            or not all(type(x) is bool for x in flags)
        ):
            reason = 'malformed_samples'
        if not reason and (
            interval is None or any(flag != (sample < interval) for sample, flag in zip(samples, flags))
        ):
            reason = 'sub_frame_flag_mismatch'
        if reason:
            failed_launches.add(launch)
            refusals[reason] += 1
            continue
        median = percentile(samples, 50)
        raw.append(samples)
        kept.append(median)
        intervals.append(interval)
        sub_frame.append(median < interval)
    return {
        'editor_id': editor_id,
        'criterion_id': criterion_id,
        'measure': measure,
        'scheduled': scheduled,
        'kept_ms': kept,
        'raw_samples_ms': raw,
        'sub_frame': sub_frame,
        'refusals': dict(refusals),
        'failed_launches': len(failed_launches),
        'frame_interval_ms': percentile(intervals, 50) if intervals else None,
        'stats': {'n': len(kept), 'median': percentile(kept, 50), 'p90': percentile(kept, 90)} if kept else None,
        'blocked': run_blocked, 'block_reason': block_reason,
    }


def _sub_frame_share(cell: dict) -> float | None:
    flags = cell.get('sub_frame') or []
    if not flags or len(flags) != len(cell.get('kept_ms', [])):
        return None
    return sum(1 for flag in flags if flag) / len(flags)


def _format_p90(cell: dict, p90: float, frame_interval: float) -> str:
    if p90 < frame_interval:
        return f'p90 < 1 frame ({frame_interval:g} ms)'
    return f'p90 {p90:.1f} ms'


def failure_text(cell: dict) -> str:
    reasons = cell.get('refusals') or {}
    if not reasons:
        return ''
    counts = '; '.join(f'{key}: {count}' for key, count in sorted(reasons.items()))
    count = cell.get('failed_launches', sum(reasons.values()))
    return f'{count} of {cell.get("scheduled", 30)} launches failed: {counts}'


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

    stats = cell.get('stats')
    scheduled = cell.get('scheduled', 30)
    n_kept = stats['n'] if stats else 0
    if n_kept < MIN_PUBLISH_N:
        reasons = cell.get('refusals') or {}
        reason_text = '; '.join(f'{key}: {count}' for key, count in sorted(reasons.items())) or 'none counted'
        return f'not enough samples (n = {n_kept} of {scheduled}; reasons {reason_text})'
    failures = failure_text(cell)
    failure_suffix = f'; {failures}' if failures else ''
    frame_interval = cell.get('frame_interval_ms')
    if frame_interval is None:
        return f'no witnessed frame interval (n = {n_kept} of {scheduled})'
    median = stats['median']
    p90 = stats['p90']
    share = _sub_frame_share(cell)
    share_text = f'; {share * 100:.0f}% sub-frame launches' if share is not None else ''
    if median < frame_interval:
        return (
            f'< 1 frame ({frame_interval:g} ms){share_text}; {_format_p90(cell, p90, frame_interval)}{failure_suffix}'
        )
    return f'{median:.1f} ms{share_text}; {_format_p90(cell, p90, frame_interval)}{failure_suffix}'


def publish_dual_runs(
    primary: Path, reproduction: Path, editor_id: str, criterion_id: str, *, scheduled: int = 30, measure: str = ''
) -> str:
    """Compatibility entry point; all publication gates live in the report path.

    ``scheduled`` remains accepted for callers, but the run summaries are the
    authoritative schedule. Missing/corrupt summaries raise before publication.
    """
    from build.perf_e2_tables import load_run, check_comparable, _cell_text

    first, second = load_run(primary), load_run(reproduction)
    check_comparable(first, second)
    return _cell_text({}, first.path, second.path, editor_id, criterion_id, measure)
