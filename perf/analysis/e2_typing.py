"""Read B9 session sets without publishing latency-session resource diagnostics."""

from collections import Counter, defaultdict
from pathlib import Path
import math

from perf.analysis import e2_cells as cells

DEFERRED = 'inspect all witness and resource refusals; publication requires complete session set'


def _valid_number(value):
    return cells._number(value) and value >= 0


def session_refusal(row, kind):
    if row.get('failure_reason'):
        return row['failure_reason']
    if cells.refusal_code(row):
        return cells.refusal_code(row)
    if row.get('publication_block_reason') not in (None, DEFERRED):
        return row['publication_block_reason']
    if row.get('publishable') is not True and row.get('publication_block_reason') != DEFERRED:
        return 'publishable_not_true'
    if row.get('outcome') != 'measured':
        return 'not_measured'
    if row.get('correctness_oracle') not in ('dom_document_text', 'model_document_text'):
        # Only a document text oracle can prove what was typed. A session on
        # a flag (or missing) oracle is unverified evidence — it is recorded
        # with its flag and key count but never counts as kept, and an old
        # row that called itself measured is refused on sight.
        return 'document_text_not_readable'
    if cells.editor_pin(row) is None:
        # A session that records no built-editor identity cannot pair with
        # another run's sessions (#149).
        return 'pin_not_recorded'
    if (
        row.get('schema') != 'perf.typing/2'
        or row.get('session_kind') != kind
        or row.get('execution_profile') != 'dedicated_publish'
        or row.get('host_class') not in ('dedicated', 'shared_guarded')
        or cells._nested_unpublishable(row.get('host_provenance'))
        or row.get('isolation') != 'fresh_process'
        or row.get('values_per_session') != 1
        or row.get('cadence_ms') != 0
        or row.get('budget_s') != 3600
        or not row.get('fixture_sha256')
        or not row.get('typed_text_sha256')
        or row.get('fixture_words') != 12805
        or row.get('words_typed') != 12805
    ):
        return 'session_contract'
    if not _valid_number(row.get('session_wall_s')):
        return 'session_contract'
    if row['session_wall_s'] > 3600:
        return 'budget_exceeded'
    if kind == 'throughput':
        return None if _valid_number(row.get('throughput_chars_s')) else 'malformed_throughput'
    latency = row.get('key_to_paint') or {}
    scheduled, accepted, refused = (latency.get(k) for k in ('n_scheduled', 'n_accepted', 'n_refused'))
    if (
        not all(type(n) is int and n >= 0 for n in (scheduled, accepted, refused))
        or not scheduled
        or accepted + refused != scheduled
        or accepted < max(math.ceil(scheduled * 0.5), min(100, scheduled))
        or latency.get('outcome') != 'measured'
        or latency.get('refusal_code')
        or not all(_valid_number(latency.get(k)) for k in ('median_ms', 'p90_ms'))
        or not _valid_number(row.get('load_ms'))
        or row.get('load_refusal')
    ):
        return 'witness_unavailable'
    return None


def resource_values(value, prefix=''):
    """Named phase/endpoint values; process identities and raw series are not metrics."""
    if isinstance(value, dict) and 'marker' not in value:
        for key, child in sorted(value.items()):
            if key not in ('processes', 'static_server', 'pid', 'ppid', 'start_time', 'series', 'cmdline'):
                yield from resource_values(child, prefix + ('.' if prefix else '') + key)
    elif not isinstance(value, list):
        yield prefix, value


def read_sessions(root: Path, editor: str, kind: str):
    jobs = cells._lane_jobs(root, cells._job_roots(root), editor, 'TYPING')
    job_pairs = [(root, job) for job in jobs]
    return _sessions_from_jobs(job_pairs, editor, kind)


def _sessions_from_jobs(job_pairs: list[tuple[Path, Path]], editor: str, kind: str) -> dict:
    job_pairs, rerun_blocked, rerun_reason = cells._filter_job_pairs(job_pairs, editor)
    jobs = [job for _root, job in job_pairs]
    summaries = [cells._load_summary(job) or {} for job in jobs]
    orders = [summary for summary in summaries if summary.get('order')]
    scheduled = sum(cells._scheduled_for_editor(summary, editor, 0) for summary in orders) if orders else 0
    qualify = cells._overlap_qualify_jobs(job_pairs, editor)
    layout_blocked, layout_reason = cells._seed_block_gate(summaries, job_pairs, editor)
    grouped = defaultdict(list)
    vetoes = {}
    for root, job in job_pairs:
        for launch, path, row in cells._attempt_rows_of(root, [job], qualify=qualify):
            if row.get('refusal_code') == 'unreadable_trial' and launch.endswith('-' + editor):
                vetoes[launch] = 'unreadable_trial'
            if row.get('editor_id') == editor and row.get('criterion_id') == 'TYPING' and row.get('session_kind') == kind:
                grouped[launch].append(row)
        for path, row in cells._read_rows(job / 'samples'):
            if path.parent == job / 'samples' and row.get('editor_id') == editor:
                code = cells.refusal_code(row)
                if code in cells._RUN_REFUSALS:
                    vetoes[cells._launch_key(root, job, path.stem, qualify=qualify)] = code
        for path in (job / 'rejected-evidence').glob('*'):
            if path.is_dir() and path.name.endswith('-' + editor):
                vetoes[cells._launch_key(root, job, path.name, qualify=qualify)] = 'quarantined'
    kept, progress = [], []
    refusals = Counter()
    for launch in sorted(set(grouped) | set(vetoes)):
        rows = grouped.get(launch, [])
        reason = vetoes.get(launch) or ('conflicting_trials' if len(rows) != 1 else session_refusal(rows[0], kind))
        if reason:
            refusals[reason] += 1
            progress.extend(row['progress'] for row in rows if row.get('progress'))
        else:
            kept.append(rows[0])
    blocked, reason = next(
        ((True, why) for summary in summaries for blocked, why in [cells._run_blocks_publication(summary)] if blocked),
        (False, None),
    )
    if layout_blocked:
        blocked, reason = True, layout_reason
    elif rerun_blocked:
        blocked, reason = True, rerun_reason
    if not blocked:
        for _root, job in job_pairs:
            mark = cells._run_shakedown_job(job)
            if mark:
                blocked, reason = True, mark
                break
    policy = [
        summary
        for summary in summaries
        if summary.get('failure_reason')
        or summary.get('execution_profile') != 'dedicated_publish'
        or summary.get('host_class') not in ('dedicated', 'shared_guarded')
    ]
    if policy:
        blocked = True
        reason = next((summary.get('failure_reason') for summary in policy if summary.get('failure_reason')), None) or 'run policy'
    seeds = {summary.get('seed') for summary in summaries if summary.get('seed') is not None}
    pins = set()
    for summary in summaries:
        pin = cells.build_identity(summary, editor)
        if pin:
            pins.add(pin)
    for row in kept:
        pin = cells.editor_pin(row)
        if pin:
            pins.add(pin)
    build_pin = next(iter(pins)) if len(pins) == 1 else None
    return dict(
        scheduled=scheduled,
        kept=kept,
        refusals=dict(refusals),
        progress=progress,
        blocked=blocked,
        block_reason=reason,
        build_pin=build_pin,
        seed=seeds.pop() if len(seeds) == 1 else None,
    )
