"""B6 accounting integration tests: real trial files and B1's outcome walkers."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from perf.container import policy, run
from perf.runner.browser_run import failure_reasons, has_failure, non_failure_outcomes


def cell(root, name, trials):
    directory = root / 'cells' / name
    attempts = directory / 'attempts'
    attempts.mkdir(parents=True)
    skipped, reasons = [], []
    for index, trial in enumerate(trials):
        value = {
            'editor_id': 'plate',
            'environment': {'execution_profile': 'dedicated_publish', 'host_class': 'shared_guarded'},
            **trial,
        }
        path = attempts / f'{index}.json'
        path.write_text(json.dumps(value))
        skipped.extend({'file': str(path), **row} for row in non_failure_outcomes(value))
        reasons.extend(failure_reasons(value))
    # Summaries repeat outcomes but are not additional trial files.
    (directory / 'summary.json').write_text(json.dumps({'criteria': trials}))
    return {
        'outcome': 'failed' if has_failure(trials) else 'ok',
        'accounting_scope': 'sample',
        'editor_id': 'plate',
        'cell_directory': str(directory),
        'non_failure_outcomes': skipped,
        'failure_reason': '; '.join(reasons) or None,
    }


def trial(cid, outcome='measured', reason=None):
    return {
        'criterion_id': cid,
        'outcome': outcome,
        'samples_ms': [42.0, 44.0] if outcome == 'measured' else [],
        'failure_reason': reason,
    }


def warm():
    return [trial('C03')] + [
        trial(cid, 'not_run', f'adapter-not-implemented: {cid}') for cid in ('C07', 'C08', 'C09', 'C10', 'C22', 'C23')
    ]


def summary(samples):
    return {'rendering': {'renderer': 'SwiftShader'}, 'samples': samples}


def test_mixed_criteria_and_quarantine(tmp_path):
    rows = [
        cell(tmp_path, '0000-plate', warm()),
        cell(tmp_path, '0001-plate', [trial('C14'), trial('C14', 'not_run', 'rung refused'), trial('C15')]),
        cell(
            tmp_path,
            '0002-plate',
            [trial('C05'), trial('C06', 'unsupported', 'no surface'), trial('C18', 'failed', 'probe crashed')],
        ),
    ]
    rejected = cell(tmp_path, '0003-plate', [trial('C03')])
    destination = tmp_path / 'rejected-evidence' / '0003-plate'
    destination.parent.mkdir()
    Path(rejected['cell_directory']).rename(destination)
    rows += [
        {
            'editor_id': 'plate',
            'outcome': 'failed',
            'failure_reason': 'cpu_throttled',
            'rejected_evidence_directory': str(destination),
        },
        {'outcome': 'failed', 'failure_reason': 'clock', 'accounting_scope': 'diagnostic'},
    ]
    counts = policy.cell_counts(summary(rows))
    assert counts['measured'] == 4
    assert counts['cells_total'] == 4
    assert counts['trials_total'] == 13
    assert counts['by_editor_criterion']['plate']['C03']['measured'] == 1
    assert counts['by_editor_criterion']['plate']['C14']['not_run_by_reason'] == {'rung refused': 1}
    assert counts['by_editor_criterion']['plate']['C06']['refused_by_reason'] == {'no surface': 1}
    assert counts['by_editor_criterion']['plate']['C18']['failed_by_reason'] == {'probe crashed': 1}
    assert counts['run_refused_by_reason'] == {'cpu_throttled': 1}
    assert sum(counts['not_run_by_reason'].values()) == 7
    assert policy.verify_run(summary(rows))


def test_ok_without_trial_is_not_measurement():
    with pytest.raises(ValueError, match='nothing_measured'):
        policy.verify_run(summary([{'outcome': 'ok'}]))


def test_only_skipped_trials_refused(tmp_path):
    row = cell(tmp_path, '0000-plate', warm()[1:])
    assert policy.cell_counts(summary([row]))['measured'] == 0
    with pytest.raises(ValueError, match='nothing_measured'):
        policy.verify_run(summary([row]))


def test_publication_counts_real_siblings_both_seeds(tmp_path, monkeypatch):
    def process(command, **kwargs):
        if command[2] == 'perf.container.check_host':
            return SimpleNamespace(returncode=0)
        name = command[2].rsplit('.', 1)[-1]
        directory = tmp_path / name / command[command.index('--run-id') + 1]
        row = cell(directory, '0000-plate', warm())
        (directory / 'summary.json').write_text(json.dumps(summary([row])))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run.subprocess, 'run', process)
    monkeypatch.setattr(
        run.sys,
        'argv',
        [
            'run',
            '--publish',
            '--host-class',
            'shared_guarded',
            '--seed',
            '1',
            '--seed2',
            '2',
            '--out-root',
            str(tmp_path),
        ],
    )
    monkeypatch.chdir(tmp_path)
    error = None
    try:
        run.main()
    except RuntimeError as exc:
        error = str(exc)
    report = json.loads((tmp_path / 'out/e2-publication.json').read_text())
    assert all(row['measured'] == 1 for row in report['runs']), error
    assert {row['seed'] for row in report['runs']} == {1, 2}
    assert all(
        row['by_editor_criterion']['plate']['C07']['not_run_by_reason'] == {'adapter-not-implemented: C07': 1}
        for row in report['runs']
    )
    assert error is None


def test_outer_not_run_reason_and_editor_separation():
    # Pure aggregation: no disk, clock, network or process dependencies.
    data = summary([
        {'editor_id': 'plate', 'outcome': 'ok', 'cell_directory': '/fake/plate'},
        {'editor_id': 'folio', 'outcome': 'ok', 'cell_directory': '/fake/folio'},
        {'editor_id': 'docen', 'outcome': 'not_run', 'reason': 'no host'},
    ])

    def trials(row):
        return [trial('C03')] if row['outcome'] == 'ok' else []

    counts = policy.cell_counts(data, trial_reader=trials)
    assert counts['by_editor_criterion']['plate']['C03']['measured'] == 1
    assert counts['by_editor_criterion']['folio']['C03']['measured'] == 1
    assert counts['run_not_run_by_reason'] == {'no host': 1}
    assert counts['not_run_by_reason'] == {}


def assert_trial_partition(counts):
    from collections import Counter

    groups = [g for criteria in counts['by_editor_criterion'].values() for g in criteria.values()]
    assert counts['measured'] == sum(g['measured'] for g in groups)
    total = counts['measured']
    for key in ('failed_by_reason', 'refused_by_reason', 'not_run_by_reason'):
        expected = Counter()
        for group in groups:
            expected.update(group[key])
        assert counts[key] == dict(expected)
        total += sum(expected.values())
    assert total == counts['trials_total']


@pytest.mark.parametrize('failures', [
    [('C11', 'probe crashed'), ('C12', 'host-error: boom')],
    [('C18', 'probe crashed')],
    [('C10', 'cpu_throttled: the sample was refused')],
    [('C05', 'cpu_throttled')],
])
def test_live_failed_attempts_count_once(failures):
    attempts = [trial('C03')] + [trial(cid, 'failed', reason) for cid, reason in failures]
    row = {'editor_id': 'plate', 'cell_directory': '/fake/live', 'outcome': 'failed',
           'failure_reason': '; '.join(reason for _, reason in failures)}
    reader = lambda row: attempts
    counts = policy.cell_counts(summary([row]), trial_reader=reader)
    assert counts['measured'] == 1
    assert counts['trials_total'] == len(attempts)
    assert counts['failed_by_reason'] == {reason: 1 for _, reason in failures if reason != 'cpu_throttled'}
    assert counts['refused_by_reason'] == ({'cpu_throttled': 1} if failures[0][1] == 'cpu_throttled' else {})
    for key in ('failed_by_reason', 'refused_by_reason', 'not_run_by_reason'):
        assert counts['run_' + key] == {}
    assert_trial_partition(counts)
    assert policy.verify_run(summary([row]), trial_reader=reader)


@pytest.mark.parametrize('row,reason', [
    ({'cell_directory': '/fake/live', 'rejected_evidence_directory': '/fake/rejected'}, 'cpu_throttled'),
    ({}, 'crashed before directory'),
    ({'cell_directory': '/fake/empty'}, 'crashed before attempt'),
])
def test_run_only_outcomes_are_not_trial_aggregates(row, reason):
    calls = []
    def reader(value):
        calls.append(value)
        return []
    row = dict(row, outcome='failed', failure_reason=reason)
    counts = policy.cell_counts(summary([row]), trial_reader=reader)
    key = 'refused_by_reason' if reason == 'cpu_throttled' else 'failed_by_reason'
    assert counts['run_' + key] == {reason: 1}
    assert counts[key] == {}
    assert len(calls) == (1 if row.get('cell_directory') and not row.get('rejected_evidence_directory') else 0)
    assert_trial_partition(counts)
