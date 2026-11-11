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
    if summary.get("publishable") is False and reason and reason != 'summary is not a trial; trials carry publishability':
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
    measure = str(trial.get('measure') or diagnostic.get('size_rung') or diagnostic.get('measurement') or '')
    phase = trial.get('measurement_phase') if trial.get('criterion_id') == 'C17' else None
    return ':'.join(filter(None, (measure, str(phase or ''))))


def trial_workload(trial):
    return str(trial.get('workload_id') or (trial.get('environment') or {}).get('workload_id')
               or (trial.get('diagnostic') or {}).get('workload_id') or '')


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


def _diagnostic_trial_path(path: Path) -> bool:
    """Chrome-profile traces and traced re-invocations live under these subtrees."""
    return 'profile-invoke' in path.parts or 'profile' in path.parts


def _diagnostic_trial_row(row: dict) -> bool:
    return row.get('outcome') == 'profiled' or row.get('accounting_scope') == 'diagnostic'


def _iter_attempt_rows(run_directory: Path):
    yield from _attempt_rows_of(run_directory, _job_roots(run_directory))


def _attempt_rows_of(run_directory: Path, jobs):
    for job in jobs:
        for directory in sorted((job / 'cells').glob('*/attempts')):
            for path, row in _read_rows(directory):
                # Measured attempts only, never a profiling subtree or a traced repetition.
                if _diagnostic_trial_path(path) or _diagnostic_trial_row(row):
                    continue
                yield _launch_key(run_directory, job, directory.parent.name), path, row


def _job_measures(run_directory: Path, job: Path, editor_id: str, criterion_id: str) -> bool:
    return any(
        row.get('editor_id') == editor_id and row.get('criterion_id') == criterion_id
        for _, _, row in _attempt_rows_of(run_directory, [job])
    )


def _lane_jobs(run_directory: Path, jobs, editor_id: str, criterion_id: str):
    """Only the runner lane that measures this criterion contributes
    launches: a campaign run directory holds jobs of many runners, and a
    warm/cold refusal must not veto an input-lane cell."""
    if len(jobs) < 2:
        return jobs
    lanes = {
        job.parent.name
        for job in jobs
        if _job_measures(run_directory, job, editor_id, criterion_id)
    }
    return [job for job in jobs if not lanes or job.parent.name in lanes]


def _job_roots(run_directory: Path) -> list[Path]:
    """The job directories of a run directory.

    A run directory is one job (``cells/`` beside ``summary.json``) or a
    campaign run whose jobs sit under ``<runner>/<job>/``: campaign 2 runs
    one editor per job, so one cell's launches can be spread over several
    job directories.
    """
    run_directory = Path(run_directory)
    parts = ('cells', 'samples', 'rejected-evidence', 'summary.json')
    if any((run_directory / part).exists() for part in parts):
        return [run_directory]
    jobs = [
        job
        for job in sorted(run_directory.glob('*/*'))
        if job.is_dir() and any((job / part).exists() for part in parts)
    ]
    return jobs or [run_directory]


def _launch_key(run_directory: Path, job: Path, launch: str) -> str:
    """Launch identity is per job: a resumed one-editor job numbers its
    launches from 0000 again, so two jobs must never collide on a name."""
    return launch if job == Path(run_directory) else '%s/%s' % (job.name, launch)


def _iter_trials(run_directory: Path):
    for _, _, row in _iter_attempt_rows(run_directory):
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
    run_directory: Path, editor_id: str, criterion_id: str, *, scheduled: int = 30, measure: str = '', workload_id: str | None = None
) -> dict:
    jobs = _lane_jobs(run_directory, _job_roots(run_directory), editor_id, criterion_id)
    summaries = [_load_summary(job) for job in jobs]
    orders = [summary for summary in summaries if (summary or {}).get('order')]
    scheduled = sum(_scheduled_for_editor(summary, editor_id, 0) for summary in orders) if orders else scheduled
    run_blocked, block_reason = next(
        ((True, reason) for summary in summaries for blocked, reason in [_run_blocks_publication(summary)] if blocked),
        (False, None),
    )
    kept, raw, sub_frame, intervals = [], [], [], []
    refusals = Counter()
    sample_unit = 'bytes' if criterion_id in ('C17', 'C19') else 'ms'
    failed_launches = set()
    trials = defaultdict(list)
    refused_launches = {}
    additional = defaultdict(set)
    witnessed_cell = False
    verified_content = []
    for launch, path, trial in _attempt_rows_of(run_directory, jobs):
        if trial.get('refusal_code') == 'unreadable_trial' and launch.endswith('-' + editor_id):
            if launch in refused_launches:
                additional[launch].add(refused_launches[launch])
            refused_launches[launch] = 'unreadable_trial'
        if trial.get('editor_id') != editor_id or not trial.get('criterion_id'):
            continue
        if workload_id is not None and trial_workload(trial) != workload_id:
            continue
        code = refusal_code(trial)
        if code in _RUN_REFUSALS:
            if refused_launches.get(launch) == 'unreadable_trial':
                additional[launch].add(code)
            else:
                if launch in refused_launches:
                    additional[launch].add(refused_launches[launch])
                refused_launches[launch] = code
        if trial['criterion_id'] == criterion_id and trial_measure(trial) == measure:
            trials[launch].append(trial)
    for job in jobs:
        for path in (job / 'rejected-evidence').glob('*'):
            if path.is_dir() and path.name.endswith('-' + editor_id):
                key = _launch_key(run_directory, job, path.name)
                if key in refused_launches:
                    additional[key].add(refused_launches[key])
                refused_launches[key] = 'quarantined'
        for path, row in _read_rows(job / 'samples'):
            if (path.parent != job / 'samples'
                    or row.get('editor_id') != editor_id or row.get('accounting_scope') == 'diagnostic'
                    or not re.fullmatch(r'\d+-' + re.escape(editor_id), path.stem)
                    or row.get('outcome') in ('ok', 'measured')):
                continue
            key = _launch_key(run_directory, job, path.stem)
            code = refusal_code(row)
            if code and refused_launches.get(key) in ('quarantined', 'unreadable_trial'):
                additional[key].add(code)
            elif code in _RUN_REFUSALS:
                refused_launches[key] = code
            elif code and key not in trials:
                refused_launches.setdefault(key, code)
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
        # Frame-witness flags exist only where the writer witnesses paints
        # (browser_visible layer); model-layer clocks like C04 and byte counts
        # publish without them. An absent layer keeps the strict contract.
        witnessed = sample_unit != 'bytes' and trial.get('layer', 'browser_visible') == 'browser_visible'
        if not reason and (
            not isinstance(samples, list)
            or not samples
            or not all(_number(x) for x in samples)
            or (sample_unit == 'bytes' and (trial.get('sample_unit') != 'bytes' or not all(type(x) is int and x >= 0 for x in samples)))
            or (witnessed and (not isinstance(flags, list)
                or len(flags) != len(samples) or not all(type(x) is bool for x in flags)))
        ):
            reason = 'malformed_samples'
        if not reason and witnessed and (
            interval is None or any(flag != (sample < interval) for sample, flag in zip(samples, flags))
        ):
            reason = 'sub_frame_flag_mismatch'
        if not reason and criterion_id == 'C14':
            # A C14 sample is one clock: a compositor-frame time or the no-damage
            # DOM mark. A trial that pools both (or disagrees with the measure it
            # is filed under) is refused, never published as one number.
            per_sample = {
                row.get('measure')
                for row in (diagnostic.get('samples') or [])
                if isinstance(row, dict) and row.get('measure') is not None
            }
            if len(per_sample) > 1 or (per_sample and measure and per_sample != {measure}):
                reason = 'mixed_c14_measures'
        if reason:
            failed_launches.add(launch)
            refusals[reason] += 1
            continue
        median = percentile(samples, 50)
        verified_content.append(trial.get('content_verified') is True)
        raw.append(samples)
        kept.append(median)
        witnessed_cell = witnessed_cell or witnessed
        if witnessed:
            intervals.append(interval)
            sub_frame.append(median < interval)
    return {
        'editor_id': editor_id,
        'criterion_id': criterion_id,
        'measure': measure,
        'workload_id': workload_id,
        'sample_unit': sample_unit,
        'witnessed': witnessed_cell,
        'scheduled': scheduled,
        'kept_ms': kept,
        'raw_samples_ms': raw,
        'sub_frame': sub_frame,
        'refusals': dict(refusals),
        'additional_refusals': dict(Counter(code for launch, codes in additional.items() for code in codes if code != refused_launches.get(launch))),
        'content_verified': bool(verified_content) and all(verified_content),
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
    extra = cell.get('additional_refusals') or {}
    also = '; also ' + '; '.join(f'{k}: {v}' for k, v in sorted(extra.items())) if extra else ''
    return f'{count} of {cell.get("scheduled", 30)} launches failed: {counts}{also}'


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
        additional = cell.get('additional_refusals') or {}
        extra = '; also ' + '; '.join(f'{k}: {v}' for k, v in sorted(additional.items())) if additional else ''
        return f'not enough samples (n = {n_kept} of {scheduled}; reasons {reason_text}{extra})'
    failures = failure_text(cell)
    failure_suffix = f'; n = {n_kept} of {scheduled}' + (f'; {failures}' if failures else '')
    if cell.get('criterion_id') == 'C11' and cell.get('content_verified') is not True:
        failure_suffix += ' — content not verified'
    if cell.get('sample_unit') == 'bytes':
        return f"{stats['median']:.1f} bytes; p90 {stats['p90']:.1f} bytes{failure_suffix}"
    frame_interval = cell.get('frame_interval_ms')
    if frame_interval is None:
        if cell.get('witnessed', True):
            return f'no witnessed frame interval (n = {n_kept} of {scheduled})'
        # Not a frame-witnessed clock: no interval to bucket or check against.
        return f"{stats['median']:.1f} ms; p90 {stats['p90']:.1f} ms{failure_suffix}"
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
    primary: Path, reproduction: Path, editor_id: str, criterion_id: str, *, scheduled: int = 30, measure: str = '', workload_id: str | None = None
) -> str:
    """Compatibility entry point; all publication gates live in the report path.

    ``scheduled`` remains accepted for callers, but the run summaries are the
    authoritative schedule. Missing/corrupt summaries raise before publication.
    """
    from build.perf_e2_tables import load_run, check_comparable, _cell_text

    first, second = load_run(primary), load_run(reproduction)
    check_comparable(first, second)
    return _cell_text({}, first.path, second.path, editor_id, criterion_id, measure, workload_id)
