"""Reviewer trees for #140; filesystem effects use upstream pyfakefs."""

import json
from pathlib import Path

import pytest
from build import perf_e2_tables as report
from perf.analysis import e2_cells as cells


@pytest.fixture
def runs(fs):
    roots = [Path('/runs/primary'), Path('/runs/repro')]
    for seed, root in enumerate(roots):
        root.mkdir(parents=True)
        (root / 'summary.json').write_text(
            json.dumps(
                dict(
                    run_id=root.name,
                    seed=seed,
                    execution_profile='dedicated_publish',
                    host_class='dedicated',
                    publishable=True,
                    host={},
                    rendering={},
                    order=[[i, 'plate'] for i in range(30)],
                )
            )
        )
        for rep in range(10):
            trial(root, rep)
    return roots


def trial(root, rep, criterion='C07', name=None, **extra):
    row = dict(
        editor_id='plate',
        criterion_id=criterion,
        outcome='measured',
        samples_ms=[20],
        publishable=True,
        refusal_code=None,
        sub_frame_samples=[False],
        diagnostic={'frame_interval_ms': 16.7},
        # Built-editor identity every real trial carries (#149).
        host_provenance={'host_build': 'production', 'publishable': True, 'tree_sha256': 'tree-a'},
    )
    row.update(extra)
    path = root / 'cells' / f'{rep:04d}-plate' / 'attempts' / (name or criterion + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row))


def sample(root, rep, reason, code="crash"):
    path = root / 'samples' / f'{rep:04d}-plate.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(dict(editor_id='plate', failure_reason=reason, outcome='failed', refusal_code=code)))


def cell(root, criterion='C07'):
    return cells.build_run_cell(root, 'plate', criterion)


@pytest.mark.parametrize(
    'reason,family',
    [
        ('HostBuildError: host_build: production build failed: plate exited 1; log: /tmp/build.log', 'host_build'),
        ('search_timeout: selector; host_build', 'host_build'),
        ('search_timeout: selector; cpu_throttled: quota', 'cpu_throttled'),
    ],
)
def test_run_family_veto_and_label(runs, reason, family):
    for rep in range(10):
        sample(runs[0], rep, reason, family)
    assert cell(runs[0])['stats'] is None
    assert cell(runs[0])['refusals'] == {family: 10}


@pytest.mark.parametrize('reverse', [False, True])
def test_conflicting_trials_independent_of_filename_order(runs, reverse):
    for rep in range(10):
        trial(
            runs[0],
            rep,
            name='A.json' if reverse else 'Z.json',
            outcome='not_run',
            failure_reason='host-error: page crashed',
            samples_ms=[],
        )
    assert cell(runs[0])['stats'] is None
    assert cell(runs[0])['refusals'] == {'conflicting_trials': 10}


@pytest.mark.parametrize(
    'reason,family',
    [
        ('host-error: page crashed', 'crash'),
        ('TimeoutExpired: Command node timed out', 'crash'),
        ('TargetClosedError: Target page closed', 'crash'),
        ('harness-error: page crashed', 'crash'),
        ('HostBuildError: host_build: failed; log: /tmp/build.log', 'host_build'),
    ],
)
def test_sample_without_trials_counted_for_every_criterion(runs, reason, family):
    for rep in range(10, 13):
        sample(runs[0], rep, reason, family)
    for criterion in ('C04', 'C07', 'C11'):
        assert cell(runs[0], criterion)['refusals'] == {family: 3}
    text = cells.publication_text(cell(runs[0]))
    assert '20.0 ms' in text
    assert '3 of 30 launches failed' in text
    assert family in text


@pytest.mark.parametrize(
    'extra,family',
    [
        ({'publishable': False}, 'publishable_not_true'),
        ({'publication_block_reason': 'production build failed: plate', 'refusal_code': 'host_build'}, 'host_build'),
        ({'host_build': 'build_failed', 'refusal_code': 'host_build'}, 'host_build'),
        (
            {
                'publishable': False,
                'publication_block_reason': 'production build failed: plate',
                'host_build': 'build_failed',
            },
            'publishable_not_true',
        ),
    ],
)
def test_trial_publication_blocks(runs, extra, family):
    for rep in range(10):
        trial(runs[0], rep, **extra)
    assert cell(runs[0])['stats'] is None
    assert cell(runs[0])['refusals'] == {family: 10}


@pytest.mark.parametrize(
    'samples,flags,frame',
    [([10, 12, 14], [True] * 3, 8.3), ([8] * 3, [False] * 3, 16.7), ([12], [True], 8.3), ([8], [False], 16.7)],
)
def test_recorded_median_flag_mismatch_refuses(runs, samples, flags, frame):
    for rep in range(10):
        trial(runs[0], rep, samples_ms=samples, sub_frame_samples=flags, diagnostic={'frame_interval_ms': frame})
    assert cell(runs[0])['stats'] is None
    assert cell(runs[0])['refusals'] == {'sub_frame_flag_mismatch': 10}


@pytest.mark.parametrize(
    'reason',
    [
        'host-error: page crashed',
        'TargetClosedError: Target page closed',
        'TimeoutExpired: Command node timed out',
        'harness-error: page crashed',
    ],
)
def test_crash_sibling_preserves_measurement_and_its_reason(runs, reason):
    for root in runs:
        for rep in range(10):
            trial(root, rep, 'C11', outcome='not_run', failure_reason=reason)
            sample(root, rep, reason)
    facts = report.facts_from_runs(*runs)
    assert facts['perf.e2.plate.C07.reproduced'] is True
    assert '10' in facts['perf.e2.table.C11'] and 'none counted' not in facts['perf.e2.table.C11']


def test_failure_counts_survive_reproduction_and_mismatch(runs):
    for rep in range(10, 13):
        sample(runs[1], rep, 'host-error: page crashed')
    for value in (20, 999):
        for rep in range(10):
            trial(runs[1], rep, samples_ms=[value])
        text = cells.publish_dual_runs(*runs, 'plate', 'C07')
        assert 'second' in text and '3 of 30 launches failed' in text
        assert text in report.facts_from_runs(*runs)['perf.e2.table.C07']


def test_blocked_reproduction_is_not_short_sample_claim(runs):
    root = runs[1]
    summary = json.loads((root / 'summary.json').read_text())
    summary.update(publishable=False, publication_block_reason='repos_modified')
    (root / 'summary.json').write_text(json.dumps(summary))
    for path in (root / 'cells').rglob('*.json'):
        if '0000-plate' not in str(path):
            path.unlink()
    text = cells.publish_dual_runs(*runs, 'plate', 'C07')
    assert 'blocked' in text and 'repos_modified' in text
    assert 'not enough samples' not in text


def test_mixed_tracking_withholds_share(runs):
    for rep in range(5):
        trial(runs[0], rep, sub_frame_samples=None)
    assert '% sub-frame' not in cells.publication_text(cell(runs[0]))


def test_each_failure_family_retained(runs):
    trial(runs[0], 10, outcome='failed', failure_reason='search_timeout: selector', refusal_code='search_timeout')
    trial(runs[0], 11, outcome='failed', failure_reason='paint_witness_unavailable: CDP', refusal_code='paint_witness_unavailable')
    text = cells.publication_text(cell(runs[0]))
    assert 'search_timeout' in text and 'paint_witness_unavailable' in text


@pytest.mark.parametrize(
    'extra',
    [
        {'outcome': 'refused', 'failure_reason': 'paint_witness_unavailable'},
        {'publishable': False, 'publication_block_reason': 'host_build: failed'},
    ],
)
def test_refused_companion_conflicts(runs, extra):
    trial(runs[0], 0, name='companion.json', **extra)
    assert cell(runs[0])['stats']['n'] == 9
    assert cell(runs[0])['refusals'] == {'conflicting_trials': 1}


@pytest.mark.parametrize(
    'samples,flags,frame,share',
    [
        ([10, 12, 14], [False] * 3, 8.3, '0%'),
        ([30, 8, 20], [False, True, False], 16.7, '0%'),
        ([8] * 3, [True] * 3, 16.7, '100%'),
    ],
)
def test_matching_median_flags_publish(runs, samples, flags, frame, share):
    for rep in range(10):
        trial(runs[0], rep, samples_ms=samples, sub_frame_samples=flags, diagnostic={'frame_interval_ms': frame})
    assert share + ' sub-frame launches' in cells.publication_text(cell(runs[0]))
