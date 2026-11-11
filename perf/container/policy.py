"""Validation and command planning for the HF-only container workflow."""
import re
import json
from pathlib import Path

EDITORS = ('plate eigenpal-docx-editor folio genoffice superdoc canvas-editor '
           'canvas-editor-plugin wordcraft docxodus docen office-open office-open-upstream '
           'docs-plus fiduswriter fiduswriter-document-ts fiduswriter-cli-ts '
           'fiduswriter-pandoc-plugin-ts').split()
INSTALLS = {
    'plate': ['pnpm', 'install', '--no-frozen-lockfile', '--ignore-scripts'],
    'eigenpal-docx-editor': ['bun', 'install'], 'folio': ['bun', 'install'],
    'genoffice': ['npm', 'install', '--no-audit', '--no-fund'],
    'canvas-editor': ['pnpm', 'install', '--no-frozen-lockfile'],
    'canvas-editor-plugin': ['pnpm', 'install', '--no-frozen-lockfile'],
    'docen': ['pnpm', 'install', '--frozen-lockfile', '--ignore-scripts'],
}
RUNNERS = ('benchmark_warm_cold', 'benchmark_document', 'benchmark_input', 'adversarial_c10_scroll', 'benchmark_typing')
NPM = (
    ('superdoc_sdk', 'harness/superdoc-sdk', '@superdoc/sdk'),
    ('docxodus', 'harness/ui/docxodus', 'docxodus'),
    ('docxodus', 'harness/ui/docxodus', '@docxodus/export'),
    ('apryse', 'harness/apryse', '@pdftron/webviewer'),
)


def git_pins(facts, required=EDITORS):
    result = []
    for name in required:
        pin, slug = facts.get(f'ver.{name}.commit'), facts.get(f'ver.{name}.slug')
        if not isinstance(pin, str) or not re.fullmatch(r'[0-9a-f]{7,40}', pin):
            raise ValueError(f'missing or invalid commit: {name}')
        if not isinstance(slug, str) or not re.fullmatch(r'[\w-]+/[\w.-]+', slug):
            raise ValueError(f'missing or invalid slug: {name}')
        result.append((name, slug, pin))
    return result


def verify_commit(pin, full):
    if not re.fullmatch(r'[0-9a-f]{40}', full) or not full.startswith(pin):
        raise ValueError(f'commit mismatch: {pin} / {full}')
    return full


def verify_version(expected, actual):
    if not expected or expected != actual:
        raise ValueError(f'version mismatch: {expected} / {actual}')
    return actual


def npm_pins(facts):
    result = []
    for key, directory, package in NPM:
        version = facts.get('ver.npm.' + key)
        if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[\w.-]+)?', version):
            raise ValueError(f'missing or invalid npm pin: {key}')
        result.append((directory, package, version))
    return result


def publication_jobs(editors, seed, seed2, host_class, blocks=None):
    """Every job of a campaign. ``blocks=N`` is the publication layout (interleaved blocks)."""
    if not editors or seed == seed2 or host_class != 'shared_guarded':
        raise ValueError('publication requires editors, distinct seeds and shared_guarded')
    if blocks is not None:
        return _block_jobs(list(editors), (seed, seed2), host_class, blocks)
    jobs = []
    for value in (seed, seed2):
        for runner in (*RUNNERS, 'benchmark_memory', 'benchmark_resources'):
            base = ['--execution-profile', 'dedicated_publish', '--host-class', host_class,
                    '--chrome-profile', '--seed', str(value)]
            if runner == 'benchmark_typing':
                from perf.runner.browser_run import TYPING_PUBLICATION_SESSIONS
                jobs.extend((runner, base + ['--repetitions', str(TYPING_PUBLICATION_SESSIONS),
                    '--cadence-ms', '0', '--budget-s', '3600', '--session-kind', kind, '--editors', editor])
                    for editor in editors for kind in ('throughput', 'latency'))
                continue
            from perf.fixtures.docx_workload import PROSE_LADDER, CORPUS_ROW
            # One editor per job (Arthur, 2026-11-11): every job is independent
            # and can run on any Space; the planner spreads them.
            for row in [*PROSE_LADDER, CORPUS_ROW]:
                args = base + ['--workload', row['workload_id']]
                for editor in editors:
                    if runner == 'adversarial_c10_scroll':
                        jobs.append((runner, args + ['--editor', editor]))
                    elif runner == 'benchmark_document':
                        jobs.append((runner, args + ['--editors', editor, '--criteria', 'C11', 'C12', 'C15']))
                    else:
                        jobs.append((runner, args + ['--editors', editor]))
            if runner == 'benchmark_document':
                # C14 traverses the entire ladder itself, once per seed and editor.
                jobs.extend((runner, base + ['--editors', editor, '--criteria', 'C14']) for editor in editors)
    return jobs


def _block_jobs(editors, seeds, host_class, blocks):
    """Interleaved blocks (Arthur, 2026-11-11).

    Each job measures every editor, a few repetitions each, in the seeded
    interleaved order, so the editors of a cell share one machine and one
    hour. The N blocks of a seed are slices of its single schedule. Typing
    keeps one editor per job: a session is an hour of one editor.
    Traces are taken in the first block of each seed only.
    """
    from perf.fixtures.docx_workload import PROSE_LADDER, CORPUS_ROW
    from perf.runner.browser_run import PUBLICATION_REPETITIONS, TYPING_PUBLICATION_SESSIONS
    if blocks < 1 or PUBLICATION_REPETITIONS % blocks:
        raise ValueError(f'blocks must divide {PUBLICATION_REPETITIONS}')
    each = str(PUBLICATION_REPETITIONS // blocks)
    jobs = []
    for value in seeds:
        head = ['--execution-profile', 'dedicated_publish', '--host-class', host_class]
        for runner in (*RUNNERS, 'benchmark_memory', 'benchmark_resources'):
            if runner == 'benchmark_typing':
                jobs.extend((runner, head + ['--chrome-profile', '--seed', str(value),
                    '--repetitions', str(TYPING_PUBLICATION_SESSIONS), '--cadence-ms', '0', '--budget-s', '3600',
                    '--session-kind', kind, '--editors', editor])
                    for editor in editors for kind in ('throughput', 'latency'))
                continue
            tails = [['--workload', row['workload_id'], '--editors', *editors,
                      *(['--criteria', 'C11', 'C12', 'C15'] if runner == 'benchmark_document' else [])]
                     for row in [*PROSE_LADDER, CORPUS_ROW]]
            if runner == 'benchmark_document':
                tails.append(['--editors', *editors, '--criteria', 'C14'])
            for tail in tails:
                for index in range(1, blocks + 1):
                    jobs.append((runner, head + (['--chrome-profile'] if index == 1 else [])
                                 + ['--seed', str(value), *tail, '--block', f'{index}/{blocks}',
                                    SHAKEDOWN_COUNT_FLAG[runner], each]))
    return jobs


def harness_install(files):
    """Use the harness lock's owner; npm wins when legacy pnpm locks coexist."""
    if 'package-lock.json' in files:
        return ['npm', 'ci']
    if 'pnpm-lock.yaml' in files:
        return ['pnpm', 'install', '--frozen-lockfile']
    if {'bun.lock', 'bun.lockb'}.intersection(files):
        return ['bun', 'install', '--frozen-lockfile']
    raise ValueError('missing_lockfile: harness dependency graph is unpinned')


def read_trials(row):
    """Read canonical attempts only; lane summaries duplicate these outcomes."""
    directory = row.get('cell_directory')
    if not directory:
        return []
    trials, measured = [], False
    for path in sorted((Path(directory) / 'attempts').glob('*.json')):
        sidecar = path.name.startswith('chrome-profile-')
        try:
            trial = json.loads(path.read_text())
        except ValueError:
            if sidecar:
                continue  # a truncated trace record is not a trial
            raise
        trials.append(trial)
        measured = measured or not (sidecar or trial.get('outcome') == 'profiled'
                                    or trial.get('accounting_scope') == 'diagnostic')
    if measured:
        return trials
    # The resources lane writes one record per launch, not attempt files.
    record_path = Path(directory) / 'resource.json'
    if record_path.is_file():
        record = json.loads(record_path.read_text())
        if record.get('record_kind') == 'browser_resources' and record.get('outcome'):
            return trials + [{
                'criterion_id': 'B8',
                'editor_id': record.get('editor_id'),
                'outcome': record['outcome'],
                'failure_reason': record.get('refusal_code') or record.get('failure_reason'),
            }]
    return trials


def outcome_counts():
    return dict(measured=0, refused_by_reason={}, failed_by_reason={}, not_run_by_reason={})


def count_outcome(counts, row):
    outcome = row.get('outcome')
    if outcome == 'measured':
        counts['measured'] += 1
        return
    reason = row.get('failure_reason') or row.get('reason') or outcome or 'unknown'
    if outcome == 'not_run':
        key = 'not_run_by_reason'
    elif outcome in ('refused', 'unsupported', 'not_applicable', 'unverified') or reason == 'cpu_throttled':
        key = 'refused_by_reason'
    else:
        key = 'failed_by_reason'
    bucket = counts[key]
    bucket[reason] = bucket.get(reason, 0) + 1


def cell_counts(data, *, trial_reader=None):
    """Count trial files by editor/criterion, separately retaining outer outcomes.

    The injectable reader keeps aggregation testable without disk. Outer ok is
    process completion, never measurement evidence. A failed cell can still
    contain measured criteria; quarantined cells cannot.
    """
    trial_reader = trial_reader or read_trials
    counts = dict(
        cells_total=0,
        trials_total=0,
        **outcome_counts(),
        by_editor_criterion={},
        run_refused_by_reason={},
        run_failed_by_reason={},
        run_not_run_by_reason={},
    )
    for row in data.get('samples', []):
        if row.get('accounting_scope') == 'diagnostic':
            continue
        counts['cells_total'] += 1
        trials = [] if row.get('rejected_evidence_directory') or not row.get('cell_directory') else list(trial_reader(row))
        if not trials and row.get('outcome') not in ('ok', 'measured'):
            outer = outcome_counts()
            count_outcome(outer, row)
            for key in ('refused_by_reason', 'failed_by_reason', 'not_run_by_reason'):
                for reason, number in outer[key].items():
                    counts['run_' + key][reason] = counts['run_' + key].get(reason, 0) + number
        for trial in trials:
            if not isinstance(trial, dict) or not trial.get('criterion_id') or not trial.get('outcome'):
                raise ValueError('invalid_trial: criterion_id and outcome required')
            if trial.get('outcome') == 'profiled' or trial.get('accounting_scope') == 'diagnostic':
                continue
            editor = trial.get('editor_id') or row.get('editor_id')
            if not editor:
                raise ValueError('invalid_trial: editor_id required')
            criterion = trial['criterion_id']
            group = counts['by_editor_criterion'].setdefault(editor, {}).setdefault(criterion, outcome_counts())
            counts['trials_total'] += 1
            count_outcome(group, trial)
            count_outcome(counts, trial)
    groups = [group for criteria in counts['by_editor_criterion'].values() for group in criteria.values()]
    assert counts['measured'] == sum(group['measured'] for group in groups)
    total = counts['measured']
    for key in ('refused_by_reason', 'failed_by_reason', 'not_run_by_reason'):
        aggregate = {}
        for group in groups:
            for reason, number in group[key].items():
                aggregate[reason] = aggregate.get(reason, 0) + number
        assert counts[key] == aggregate, f'{key} differs from criterion totals'
        total += sum(aggregate.values())
    assert total == counts['trials_total'], 'each attempt must count exactly once'
    return counts


def verify_run(data, *, trial_reader=None):
    import os
    shakedown = os.environ.get('PERF_SHAKEDOWN') == '1'
    if data.get('runner') == 'benchmark_typing' and data.get('execution_profile') == 'dedicated_publish':
        from perf.runner.browser_run import TYPING_PUBLICATION_MIN_KEPT
        kept = data.get('typing_sessions_kept') or {}
        kind = data.get('session_kind')
        if (
            not shakedown
            and kind in ('throughput', 'latency')
            and kept
            and any(
                not isinstance(group, dict) or type(group.get(kind)) is not int
                or group[kind] < TYPING_PUBLICATION_MIN_KEPT for group in kept.values()
            )
        ):
            raise ValueError('insufficient_typing_sessions')
    if not (data.get('rendering') or {}).get('renderer'):
        raise ValueError('missing_renderer')
    counts = cell_counts(data, trial_reader=trial_reader)
    if not counts['measured']:
        if not (shakedown and counts['cells_total'] > 0):
            raise ValueError('nothing_measured')
    return data


def verify_profiles(records, execution_profile, host_class):
    """Inspect lane-owned metadata, including nested attempt environments."""
    expected = {'execution_profile': execution_profile, 'host_class': host_class}
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in expected and item != expected[key]:
                    raise ValueError(f'profile_mismatch: {key}={item!r}, expected {expected[key]!r}')
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(records)


def job_editors(options):
    """The editors a publication job measures (``--editor X`` or ``--editors X ...``)."""
    for flag in ('--editor', '--editors'):
        if flag in options:
            start = options.index(flag) + 1
            names = []
            for token in options[start:]:
                if token.startswith('--'):
                    break
                names.append(token)
            if names:
                return names
    raise ValueError('job names no editor')


def job_editor(options):
    """The one editor of a one-editor job."""
    names = job_editors(options)
    if len(names) != 1:
        raise ValueError(f'job must name exactly one editor: {names}')
    return names[0]


def job_key(name, options):
    """A job's cell identity without its seed: the two seeds of a cell share it."""
    at = options.index('--seed')
    return (name, tuple(options[:at] + options[at + 2:]))


SHAKEDOWN_COUNT_FLAG = {'benchmark_warm_cold': '--pairs', 'benchmark_document': '--samples',
                        'benchmark_memory': '--pairs', 'adversarial_c10_scroll': '--pairs',
                        'benchmark_input': '--repetitions', 'benchmark_resources': '--repetitions'}


def shakedown_options(name, options, count):
    """A publication job cut to ``count`` repetitions (typing: one 900 s session)."""
    if name == 'benchmark_typing':
        out = list(options)
        out[out.index('--repetitions') + 1] = '1'
        out[out.index('--budget-s') + 1] = '900'
        return out
    return [*options, SHAKEDOWN_COUNT_FLAG[name], str(count)]
