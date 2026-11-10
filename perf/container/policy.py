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
}
RUNNERS = ('benchmark_warm_cold', 'benchmark_document', 'benchmark_input', 'adversarial_c10_scroll')
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


def publication_jobs(editors, seed, seed2, host_class):
    if not editors or seed == seed2 or host_class != 'shared_guarded':
        raise ValueError('publication requires editors, distinct seeds and shared_guarded')
    jobs = []
    for value in (seed, seed2):
        for runner in RUNNERS:
            base = ['--execution-profile', 'dedicated_publish', '--host-class', host_class, '--seed', str(value)]
            # C10 has a singular CLI; run_cli still interleaves its 30 repetitions.
            if runner == 'adversarial_c10_scroll':
                jobs.extend((runner, base + ['--editor', editor]) for editor in editors)
            else:
                jobs.append((runner, base + ['--editors', *editors]))
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
    return [json.loads(path.read_text()) for path in sorted((Path(directory) / 'attempts').glob('*.json'))]


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
    if not (data.get('rendering') or {}).get('renderer'):
        raise ValueError('missing_renderer')
    if not cell_counts(data, trial_reader=trial_reader)['measured']:
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
