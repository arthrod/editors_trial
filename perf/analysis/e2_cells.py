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
_RUN_REFUSALS = frozenset({'cpu_throttled', 'cpu_accounting_unavailable', 'host_build'})


def refusal_family(reason):
    """Label the segment that decides a refusal, including wrapped exceptions."""
    families = [
        re.sub(r'^\w+(Error|Exception|Expired|Exit): ', '', part.strip()).split(':', 1)[0]
        for part in str(reason).split('; ')
    ]
    return next((family for family in families if family in _RUN_REFUSALS), families[0])


def _trial_block(trial):
    reason = trial.get('publication_block_reason')
    if reason:
        return refusal_family(reason)
    if trial.get('host_build') == 'build_failed':
        return 'host_build'
    if trial.get('publishable') is False:
        return refusal_family(trial.get('failure_reason') or 'publishable_false')
    if trial.get('outcome') != 'measured':
        return refusal_family(trial.get('failure_reason') or trial.get('outcome') or 'unmeasured')
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


def _read_rows(directory):
    for path in sorted(directory.rglob('*.json')):
        try:
            row = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(row, dict):
            yield path, row


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


def build_run_cell(run_directory: Path, editor_id: str, criterion_id: str, *, scheduled: int = 30) -> dict:
    summary = _load_summary(run_directory)
    scheduled = _scheduled_for_editor(summary, editor_id, scheduled)
    run_blocked, block_reason = _run_blocks_publication(summary)
    kept, raw, sub_frame, intervals = [], [], [], []
    refusals: Counter[str] = Counter()
    failed_launches = set()
    trials = defaultdict(list)
    editor_launches = set()
    for path, trial in _read_rows(run_directory / 'cells'):
        if trial.get('editor_id') != editor_id or not trial.get('criterion_id'):
            continue
        launch = path.relative_to(run_directory / 'cells').parts[0]
        editor_launches.add(launch)
        if trial['criterion_id'] == criterion_id:
            trials[launch].append(trial)
    refused_launches = {
        path.name: 'quarantined'
        for path in (run_directory / 'rejected-evidence').glob('*')
        if path.is_dir() and path.name.endswith('-' + editor_id)
    }
    for path, row in _read_rows(run_directory / 'samples'):
        if row.get('editor_id') != editor_id:
            continue
        reason = row.get('failure_reason') or row.get('publication_block_reason')
        family = refusal_family(reason) if reason else None
        if family in _RUN_REFUSALS:
            refused_launches[path.stem] = family
        elif row.get('rejected_evidence_directory'):
            refused_launches[path.stem] = 'quarantined'
        elif reason and path.stem not in editor_launches:
            refused_launches.setdefault(path.stem, family)
    for launch, reason in refused_launches.items():
        refusals[reason] += 1
        failed_launches.add(launch)
    for launch, rows in trials.items():
        if launch in refused_launches:
            continue
        candidates, blocked = [], []
        for trial in rows:
            reason = _trial_block(trial)
            if reason:
                blocked.append(reason)
                continue
            samples = [float(x) for x in trial.get('samples_ms', []) if _number(x)]
            if not samples:
                continue
            median = percentile(samples, 50)
            flags = trial.get('sub_frame_samples', (trial.get('diagnostic') or {}).get('sub_frame_samples'))
            interval = (trial.get('diagnostic') or {}).get('frame_interval_ms')
            interval = float(interval) if _number(interval) and interval > 0 else None
            flag = None
            if (
                isinstance(flags, list)
                and len(flags) == len(samples)
                and all(isinstance(x, bool) for x in flags)
                and interval
            ):
                ordered = sorted(zip(samples, flags))
                # Even-sized sets have an interpolated median. Validate both
                # central recorded samples against their own witnessed interval.
                central = ordered[(len(ordered) - 1) // 2 : len(ordered) // 2 + 1]
                if any(recorded != (value < interval) for value, recorded in central):
                    blocked.append('sub_frame_flag_mismatch')
                    continue
                flag = median < interval
            candidates.append((samples, median, interval, flag))
        if blocked:
            failed_launches.add(launch)
            if candidates:
                refusals['conflicting_trials'] += 1
            else:
                refusals.update(set(blocked))
            continue
        if not candidates:
            continue
        samples, median, interval, flag = candidates[0]
        raw.append(samples)
        kept.append(median)
        if interval:
            intervals.append(interval)
        if flag is not None:
            sub_frame.append(flag)
    return {
        'editor_id': editor_id,
        'criterion_id': criterion_id,
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
    primary: Path, reproduction: Path, editor_id: str, criterion_id: str, *, scheduled: int = 30
) -> str:
    """Compatibility entry point; all publication gates live in the report path.

    ``scheduled`` remains accepted for callers, but the run summaries are the
    authoritative schedule. Missing/corrupt summaries raise before publication.
    """
    from build.perf_e2_tables import load_run, check_comparable, _cell_text

    first, second = load_run(primary), load_run(reproduction)
    check_comparable(first, second)
    return _cell_text({}, first.path, second.path, editor_id, criterion_id)
