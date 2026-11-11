"""Aggregate browser-lane trials into report E2 cells (#136)."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import hashlib
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


def build_identity(summary: dict | None, editor_id: str, rows: list[dict] | None = None) -> str | None:
    """Built-editor identity: summary ``hosts`` first, trial provenance as fallback (#149)."""
    host = ((summary or {}).get('hosts') or {}).get(editor_id) or {}
    if isinstance(host, dict):
        tree = host.get('tree_sha256')
        if isinstance(tree, str) and tree:
            return tree
    for row in rows or ():
        pin = editor_pin(row)
        if pin:
            return pin
    return None


def editor_pin(row):
    """The built-editor identity a trial must carry (#149).

    The runner stamps ``environment.editor_version`` with ``pin_label``
    (``perf/runner/speed_headless.py``) — the editor slug, not a pin — so
    only ``host_provenance.tree_sha256``, the hash of the built editor, and a
    genuinely pinned ``editor_version`` (not equal to the slug) identify the
    measured build. ``None`` means the trial records no identity.
    """
    provenance = row.get('host_provenance')
    if isinstance(provenance, dict):
        tree = provenance.get('tree_sha256')
        if isinstance(tree, str) and tree:
            return tree
    version = (row.get('environment') or {}).get('editor_version')
    if isinstance(version, str) and version and version != row.get('editor_id'):
        return version
    return None


def _shakedown_reason(row) -> str | None:
    """A shakedown mark anywhere in a run: never a publication run (#149).

    ``perf/runner/browser_run.py`` finishes a shakedown run with
    ``shakedown: True``, ``publishable: False`` and a
    ``publication_block_reason`` starting ``shakedown``; the same marks are
    honoured wherever they appear — summary or trial — regardless of the
    other fields around them.
    """
    if row.get('shakedown') is True:
        return 'shakedown: few repetitions to find bugs; never a publication run'
    reason = str(row.get('publication_block_reason') or '')
    if reason.startswith('shakedown'):
        return reason
    return None


def _run_shakedown(run_directory: Path) -> str | None:
    """The first shakedown mark on any trial of the run, if there is one."""
    for _, _, row in _iter_attempt_rows(run_directory):
        mark = _shakedown_reason(row)
        if mark:
            return mark
    return None


def _run_shakedown_job(job: Path) -> str | None:
    """The first shakedown mark under one job directory only."""
    cells_dir = job / 'cells'
    if not cells_dir.is_dir():
        return None
    for directory in sorted(cells_dir.glob('*/attempts')):
        for _path, row in _read_rows(directory):
            mark = _shakedown_reason(row)
            if mark:
                return mark
    return None


def _job_measured_launch_names(job: Path, editor_id: str) -> list[str]:
    """Launch cells that carry at least one trial JSON (not an empty attempts tree)."""
    names: list[str] = []
    cells_dir = job / 'cells'
    if not cells_dir.is_dir():
        return names
    suffix = '-' + editor_id
    for directory in sorted(cells_dir.glob('*/attempts')):
        if not any(directory.glob('*.json')):
            continue
        name = directory.parent.name
        if name.endswith(suffix):
            names.append(name)
    for directory in sorted(cells_dir.iterdir()):
        if not directory.is_dir() or directory.name in names:
            continue
        if directory.name.endswith(suffix) and (directory / 'resource.json').is_file():
            names.append(directory.name)
    return names


def _job_launch_names(job: Path, editor_id: str) -> list[str]:
    names = []
    cells_dir = job / 'cells'
    if not cells_dir.is_dir():
        return names
    for directory in sorted(cells_dir.glob('*/attempts')):
        name = directory.parent.name
        if name.endswith('-' + editor_id):
            names.append(name)
    suffix = '-' + editor_id
    for directory in sorted(cells_dir.iterdir()):
        if not directory.is_dir() or directory.name in names:
            continue
        if directory.name.endswith(suffix) and (directory / 'resource.json').is_file():
            names.append(directory.name)
    return names


def _job_run_fingerprint(job: Path, editor_id: str) -> tuple[frozenset[str], str]:
    """Launch set and content hash for one job; used to compare duplicate pulls."""
    launches = _job_launch_names(job, editor_id)
    launch_set = frozenset(launches)
    digests: list[str] = []
    for launch in sorted(launches):
        cell = job / 'cells' / launch
        parts: list[str] = []
        attempts = cell / 'attempts'
        if attempts.is_dir():
            for path in sorted(attempts.glob('*.json')):
                try:
                    parts.append(hashlib.sha256(path.read_bytes()).hexdigest())
                except OSError:
                    parts.append('unreadable')
        if (cell / 'resource.json').is_file():
            try:
                parts.append('resource:' + hashlib.sha256((cell / 'resource.json').read_bytes()).hexdigest())
            except OSError:
                parts.append('resource:unreadable')
        digests.append('%s=%s' % (launch, ','.join(parts) if parts else 'empty'))
    body = '%s:%s' % (','.join(sorted(launch_set)), ';'.join(digests))
    return launch_set, hashlib.sha256(body.encode()).hexdigest()


def _same_root_duplicate_whole_schedule(
    job_pairs: list[tuple[Path, Path]], editor_id: str
) -> bool:
    """Two whole jobs in one root that repeated the same full launch list (#154)."""
    roots = {run for run, _ in job_pairs}
    if len(roots) != 1:
        return False
    jobs = [job for _run, job in job_pairs]
    if any(_block_slice_key(_load_summary(job)) for job in jobs):
        return False
    sets = [frozenset(_job_launch_names(job, editor_id)) for job in jobs]
    if len(sets) < 2:
        return False
    full = sets[0]
    if len(full) < 30:
        return False
    return len({s for s in sets}) == 1


def _seed_block_gate(
    summaries: list[dict | None], job_pairs: list[tuple[Path, Path]], editor_id: str
) -> tuple[bool, str | None]:
    specs, orders = [], []
    block_jobs: list[tuple[dict, Path]] = []
    for (_root, job), summary in zip(job_pairs, summaries):
        if not summary:
            continue
        if isinstance(summary.get('order'), list) and not summary.get('order'):
            if any((other or {}).get('order') for other in summaries):
                return True, 'session job with empty order'
        block = summary.get('block')
        if isinstance(block, dict) and block.get('index'):
            specs.append(block)
            block_jobs.append((block, job))
        order = summary.get('order') or []
        if order:
            orders.append({(rep, ed) for rep, ed in order})
    if _same_root_duplicate_whole_schedule(job_pairs, editor_id):
        return True, 'overlapping launch schedules in one seed'
    jobs = [job for _root, job in job_pairs]
    if specs:
        jobs_with_block = {job for _block, job in block_jobs}
        whole_reruns = [job for job in jobs if job not in jobs_with_block and _job_launch_names(job, editor_id)]
        if whole_reruns:
            return True, 'whole re-run beside block campaign'
        ofs = {item['of'] for item in specs if item.get('of')}
        reps = {item['repetitions'] for item in specs if item.get('repetitions')}
        indices = [item['index'] for item in specs]
        if len(ofs) != 1 or len(reps) != 1:
            return True, 'inconsistent block layout across jobs of one seed'
        of_val, rep_val = ofs.pop(), reps.pop()
        if of_val * rep_val != 30:
            return True, 'block layout does not cover 30 repetitions'
        if len(set(indices)) != len(indices):
            return True, 'duplicate block index in one seed'
        out_of_range = sorted({index for index in indices if index < 1 or index > of_val})
        if out_of_range:
            return True, 'block index out of range %s' % ','.join(map(str, out_of_range))
        missing = sorted(set(range(1, of_val + 1)) - set(indices))
        if missing:
            return True, 'missing blocks %s' % ','.join(map(str, missing))
        for block, job in block_jobs:
            expected = block.get('repetitions') or 0
            found = len(_job_measured_launch_names(job, editor_id))
            if found < expected:
                return True, 'block %d has no launch files' % block.get('index')
    elif len(jobs) >= 2:
        sets = [frozenset(_job_launch_names(job, editor_id)) for job in jobs]
        full_schedules = [item for item in sets if len(item) >= 30]
        if len(full_schedules) >= 2 and len({item for item in full_schedules}) > 1:
            return True, 'inconsistent launch schedules in one seed'
    if len(orders) > 1:
        seen: set = set()
        overlap = False
        for reps in orders:
            if seen & reps:
                overlap = True
                break
            seen |= reps
        if overlap:
            qualify = _overlap_qualify_jobs(job_pairs, editor_id)
            if not qualify:
                return True, 'overlapping launch schedules in one seed'
    return False, None


def _block_slice_key(summary: dict | None) -> tuple[int, int] | None:
    block = (summary or {}).get('block') or {}
    if block.get('index') and block.get('of'):
        return int(block['of']), int(block['index'])
    return None


def _filter_job_pairs(
    job_pairs: list[tuple[Path, Path]], editor_id: str, *, qualify_keys: bool = True
) -> tuple[list[tuple[Path, Path]], bool, str | None]:
    """Drop a duplicate pull of one job; refuse a second run of the same launches."""
    seen_pairs: set[tuple[str, str]] = set()
    unique_pairs: list[tuple[Path, Path]] = []
    for run_directory, job in job_pairs:
        key = (str(run_directory), str(job))
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        unique_pairs.append((run_directory, job))
    job_pairs = unique_pairs
    launch_owner: dict[str, str] = {}
    bare_owner: dict[str, str] = {}
    block_owner: dict[tuple[int, int], str] = {}
    qualify = _overlap_qualify_jobs(job_pairs, editor_id) if qualify_keys else set()
    filtered: list[tuple[Path, Path]] = []
    blocked, block_reason = False, None
    skip_jobs: set[Path] = set()
    by_run_id: dict[str, list[tuple[Path, Path, tuple[frozenset[str], str]]]] = defaultdict(list)
    for run_directory, job in job_pairs:
        summary = _load_summary(job) or {}
        run_id = str(summary.get('run_id') or job.name)
        launches = _job_launch_names(job, editor_id)
        if launches:
            by_run_id[run_id].append((run_directory, job, _job_run_fingerprint(job, editor_id)))
    for run_id, copies in by_run_id.items():
        if len(copies) == 1:
            continue
        fingerprints = {fp for _root, _job, fp in copies}
        if len(fingerprints) > 1:
            blocked = True
            block_reason = 'duplicate run_id with conflicting copies'
        else:
            for _root, job, _fp in sorted(copies, key=lambda item: (str(item[0]), str(item[1])))[1:]:
                skip_jobs.add(job)
    if blocked:
        return [], True, block_reason
    for run_directory, job in job_pairs:
        if job in skip_jobs:
            continue
        summary = _load_summary(job) or {}
        run_id = str(summary.get('run_id') or job.name)
        launches = _job_launch_names(job, editor_id)
        if not launches:
            filtered.append((run_directory, job))
            continue
        keys = [_launch_key(run_directory, job, launch, qualify=qualify) for launch in launches]
        owners = {launch_owner[key] for key in keys if key in launch_owner}
        if owners == {run_id} and owners:
            continue
        bare_owners = {bare_owner[launch] for launch in launches if launch in bare_owner}
        if bare_owners - {run_id}:
            slice_key = _block_slice_key(summary)
            multi_root = len({run for run, _ in job_pairs}) > 1
            if slice_key and slice_key in block_owner and block_owner[slice_key] != run_id:
                blocked = True
                block_reason = 'launches measured twice: a block was re-run'
            elif not qualify:
                blocked = True
                block_reason = 'launches measured twice: a block was re-run'
            elif multi_root:
                blocked = True
                block_reason = 'launches measured twice: a block was re-run'
        filtered.append((run_directory, job))
        for launch in launches:
            bare_owner.setdefault(launch, run_id)
            launch_owner.setdefault(_launch_key(run_directory, job, launch, qualify=qualify), run_id)
        slice_key = _block_slice_key(summary)
        if slice_key:
            block_owner.setdefault(slice_key, run_id)
    return filtered, blocked, block_reason


def _trial_block(trial):
    code = refusal_code(trial)
    if code:
        return code
    if trial.get('publishable') is not True or _nested_unpublishable(trial.get('host_provenance')):
        return 'publishable_not_true'
    if trial.get('outcome') != 'measured':
        return 'crash'
    if editor_pin(trial) is None:
        return 'pin_not_recorded'
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
    mark = _shakedown_reason(summary)
    if mark:
        return True, mark
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
            if path.name.startswith('chrome-profile-'):
                continue  # a truncated trace record is diagnostic, never a trial
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


def _attempt_rows_of(run_directory: Path, jobs, *, qualify: set[Path] | None = None):
    for job in jobs:
        for directory in sorted((job / 'cells').glob('*/attempts')):
            for path, row in _read_rows(directory):
                # Measured attempts only, never a profiling subtree or a traced repetition.
                if _diagnostic_trial_path(path) or _diagnostic_trial_row(row):
                    continue
                yield _launch_key(run_directory, job, directory.parent.name, qualify=qualify), path, row


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
    if not jobs and (run_directory / 'runs').is_dir():
        for campaign in sorted((run_directory / 'runs').iterdir()):
            if campaign.is_dir():
                jobs.extend(_job_roots(campaign))
    return jobs


def _overlap_qualify_jobs(job_pairs: list[tuple[Path, Path]], editor_id: str) -> set[Path]:
    """Jobs whose launch names collide within the pool (campaign 2 one-editor jobs)."""
    owner: dict[str, Path] = {}
    qualify: set[Path] = set()
    for _root, job in job_pairs:
        for name in _job_launch_names(job, editor_id):
            if name in owner and owner[name] != job:
                qualify.add(job)
                qualify.add(owner[name])
            else:
                owner[name] = job
    return qualify


def _launch_key(run_directory: Path, job: Path, launch: str, *, qualify: set[Path] | None = None) -> str:
    """Per-seed names when disjoint; per-job when one-editor jobs reuse rep indices."""
    if qualify and job in qualify and job != Path(run_directory):
        return '%s/%s' % (job.name, launch)
    return launch


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


_FIGURE_FIELDS = frozenset({'stats', 'kept_ms', 'raw_samples_ms', 'sub_frame', 'frame_interval_ms'})


def public_cell_dict(cell: dict, *, published: bool = False) -> dict:
    """Facts payload for one seed group: figures only when the cell publishes."""
    if published:
        return dict(cell)
    return {key: value for key, value in cell.items() if key not in _FIGURE_FIELDS}


def build_run_cell(
    run_directory: Path, editor_id: str, criterion_id: str, *, scheduled: int = 30, measure: str = '', workload_id: str | None = None
) -> dict:
    job_pairs = [(run_directory, job) for job in _lane_jobs(run_directory, _job_roots(run_directory), editor_id, criterion_id)]
    return _build_cell_from_jobs(job_pairs, editor_id, criterion_id, scheduled=scheduled, measure=measure, workload_id=workload_id)


def _build_cell_from_jobs(
    job_pairs: list[tuple[Path, Path]],
    editor_id: str,
    criterion_id: str,
    *,
    scheduled: int = 30,
    measure: str = '',
    workload_id: str | None = None,
) -> dict:
    if not job_pairs:
        return {
            'editor_id': editor_id, 'criterion_id': criterion_id, 'measure': measure, 'workload_id': workload_id,
            'scheduled': 0, 'stats': None, 'blocked': False, 'block_reason': None, 'refusals': {},
        }
    job_pairs, rerun_blocked, rerun_reason = _filter_job_pairs(job_pairs, editor_id)
    jobs = [job for _, job in job_pairs]
    summaries = [_load_summary(job) for job in jobs]
    qualify = _overlap_qualify_jobs(job_pairs, editor_id)
    layout_blocked, layout_reason = _seed_block_gate(summaries, job_pairs, editor_id)
    orders = [summary for summary in summaries if (summary or {}).get('order')]
    scheduled = sum(_scheduled_for_editor(summary, editor_id, 0) for summary in orders) if orders else 0
    run_blocked, block_reason = next(
        ((True, reason) for summary in summaries for blocked, reason in [_run_blocks_publication(summary)] if blocked),
        (False, None),
    )
    if layout_blocked:
        run_blocked, block_reason = True, layout_reason
    elif rerun_blocked:
        run_blocked, block_reason = True, rerun_reason
    if not run_blocked:
        for _run_directory, job in job_pairs:
            mark = _run_shakedown_job(job)
            if mark:
                run_blocked, block_reason = True, mark
                break
    if run_blocked:
        return {
            'editor_id': editor_id,
            'criterion_id': criterion_id,
            'measure': measure,
            'workload_id': workload_id,
            'sample_unit': 'bytes' if criterion_id in ('C17', 'C19') else 'ms',
            'witnessed': False,
            'scheduled': scheduled,
            'kept_ms': [],
            'raw_samples_ms': [],
            'sub_frame': [],
            'refusals': {},
            'additional_refusals': {},
            'content_verified': False,
            'failed_launches': 0,
            'frame_interval_ms': None,
            'stats': None,
            'blocked': True,
            'block_reason': block_reason,
        }
    kept, raw, sub_frame, intervals = [], [], [], []
    refusals = Counter()
    sample_unit = 'bytes' if criterion_id in ('C17', 'C19') else 'ms'
    failed_launches = set()
    trials = defaultdict(list)
    refused_launches = {}
    additional = defaultdict(set)
    witnessed_cell = False
    verified_content = []
    for run_directory, job in job_pairs:
        for launch, path, trial in _attempt_rows_of(run_directory, [job], qualify=qualify):
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
    for run_directory, job in job_pairs:
        for path in (job / 'rejected-evidence').glob('*'):
            if path.is_dir() and path.name.endswith('-' + editor_id):
                key = _launch_key(run_directory, job, path.name, qualify=qualify)
                if key in refused_launches:
                    additional[key].add(refused_launches[key])
                refused_launches[key] = 'quarantined'
        for path, row in _read_rows(job / 'samples'):
            if (path.parent != job / 'samples'
                    or row.get('editor_id') != editor_id or row.get('accounting_scope') == 'diagnostic'
                    or not re.fullmatch(r'\d+-' + re.escape(editor_id), path.stem)
                    or row.get('outcome') in ('ok', 'measured')):
                continue
            key = _launch_key(run_directory, job, path.stem, qualify=qualify)
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


def _criterion_job_pairs(roots, editor_id: str, criterion_id: str) -> dict:
    groups: dict = {}
    for root in map(Path, roots):
        for job in _lane_jobs(root, _job_roots(root), editor_id, criterion_id):
            summary = _load_summary(job) or {}
            scheduled = _scheduled_for_editor(summary, editor_id, 0)
            if not scheduled and not _job_measures(root, job, editor_id, criterion_id):
                continue
            seed = summary.get('seed')
            groups.setdefault(seed, []).append((root, job))
    return groups


def _criterion_pins(job_pairs: list[tuple[Path, Path]], editor_id: str) -> set:
    pins: set = set()
    for run_directory, job in job_pairs:
        summary = _load_summary(job)
        pin = build_identity(summary, editor_id)
        if pin:
            pins.add(pin)
            continue
        for _launch, _path, row in _attempt_rows_of(run_directory, [job]):
            if row.get('editor_id') == editor_id:
                trial_pin = editor_pin(row)
                if trial_pin:
                    pins.add(trial_pin)
    return pins


def _criterion_block(seeds, groups) -> str | None:
    if not groups:
        return 'not in these runs'
    if len(groups) != 2 or None in seeds:
        return 'two seeds required'
    for name, group in zip(('first', 'second'), groups):
        if group['blocked']:
            reason = group.get('block_reason') or 'run blocked'
            return '%s seed: run blocked (%s)' % (name, reason)
    for name, group in zip(('first', 'second'), groups):
        stats = group.get('stats') or {}
        n_kept = stats.get('n', 0)
        if n_kept < MIN_PUBLISH_N:
            reasons = ', '.join('%s %d' % item for item in sorted((group.get('refusals') or {}).items()))
            return '%s seed: %d of %d launches kept%s' % (
                name, n_kept, group.get('scheduled', 0), ' (%s)' % reasons if reasons else '')
    return None


def read_criterion_cell(
    roots, editor_id: str, criterion_id: str, *, measure: str = '', workload_id: str | None = None
) -> dict:
    """Pool launches by seed across any number of campaign roots (#154)."""
    by_seed = _criterion_job_pairs(roots, editor_id, criterion_id)
    seeds = sorted(by_seed, key=lambda seed: (seed is None, seed))
    groups = [
        _build_cell_from_jobs(by_seed[seed], editor_id, criterion_id, measure=measure, workload_id=workload_id)
        for seed in seeds
    ]
    cell = {'published': False, 'reason': None, 'seeds': seeds, 'groups': groups, 'by_seed': by_seed}
    cell['reason'] = _criterion_cell_block(seeds, groups, by_seed, editor_id)
    if not cell['reason']:
        cell['published'] = True
    return cell


def _criterion_cell_block(seeds, groups, by_seed, editor_id: str) -> str | None:
    missing = _criterion_block(seeds, groups)
    if missing:
        return missing
    pins = []
    for name, seed in zip(('first', 'second'), seeds):
        pin = _criterion_pins(by_seed[seed], editor_id)
        if not pin:
            return 'the built editor is not recorded'
        if len(pin) > 1:
            return '%s seed: more than one editor build recorded' % name
        pins.append(pin)
    if pins[0] != pins[1]:
        return 'the two seeds measured different editor builds'
    return None


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
    return _cell_text({}, [first.path, second.path], editor_id, criterion_id, measure, workload_id)
