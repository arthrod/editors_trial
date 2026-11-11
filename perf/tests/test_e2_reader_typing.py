"""B9 publication separates instrumented sessions from throughput resources."""

import json
import pytest
from perf.tests import test_e2_report_fix3 as fixtures
from perf.tests.test_e2_report_fix3 import trial
from build import perf_e2_tables as report

runs = fixtures.runs

DEFERRED = 'inspect all witness and resource refusals; publication requires complete session set'


def typing_pair(runs, kind='throughput', count=12, **updates):
    for root in runs:
        s = json.loads((root / 'summary.json').read_text())
        s.update(
            order=[[i, 'plate'] for i in range(12)], runner='benchmark_typing', session_kind=kind, publishable=False
        )
        (root / 'summary.json').write_text(json.dumps(s))
        for i in range(count):
            row = dict(
                schema='perf.typing/2',
                session_kind=kind,
                correctness_oracle='dom_document_text',
                isolation='fresh_process',
                values_per_session=1,
                cadence_ms=0,
                budget_s=3600,
                session_wall_s=300,
                fixture_sha256='full-file',
                typed_text_sha256='full-stripped-text',
                fixture_words=12805,
                words_typed=12805,
                execution_profile='dedicated_publish',
                host_class='dedicated',
                publishable=False,
                publication_block_reason=DEFERRED,
                throughput_chars_s=123,
                load_ms=25,
                load_refusal=None,
                key_to_paint={
                    'outcome': 'measured',
                    'n_scheduled': 2,
                    'n_accepted': 2,
                    'n_refused': 0,
                    'median_ms': 20,
                    'p90_ms': 22,
                    'samples': [{'ms': 20, 'sub_frame': False}, {'ms': 22, 'sub_frame': False}],
                },
                resources={
                    'phases': {
                        'typing': {
                            'cpu_ms': 0,
                            'rss_bytes': 1234,
                            'io_read_bytes': {'marker': 'not_available_on_platform', 'reason': 'single_sample_phase'},
                        }
                    }
                },
                resource_endpoints={'end': {'cpu_ms': 'not_applicable_endpoint'}},
                instrumented={'throughput_chars_s': 999999, 'resources': {'rss_bytes': 987654321}},
            )
            row.update(updates)
            trial(root, i, 'TYPING', **row)


def render(runs, kind):
    assert callable(getattr(report, 'typing_table', None)), 'B9 reader absent'
    return report.typing_table({}, list(runs), 'plate', kind)


def test_throughput_resources_and_markers(runs):
    typing_pair(runs)
    text = render(runs, 'throughput')
    assert '123' in text and 'chars/s' in text and 'n = 12 of 12' in text
    assert '1.2 KiB' in text and '0 ms' in text and 'single_sample_phase' in text
    assert 'not applicable at this endpoint' in text
    assert '999999' not in text and 'load_ms' not in text


def test_latency_excludes_instrumented_figures(runs):
    typing_pair(runs, 'latency')
    text = render(runs, 'latency')
    assert 'load_ms' in text and 'key_to_paint' in text and 'accepted 24' in text and 'refused 0' in text
    assert 'instrumented' in text and '999999' not in text and '987654321' not in text and 'chars/s' not in text


@pytest.mark.parametrize(
    'updates,reason',
    [
        (
            {'failure_reason': 'budget_exceeded', 'progress': {'characters_typed': 77, 'elapsed_s': 3601}},
            'budget_exceeded',
        ),
        ({'cadence_ms': 5}, 'session_contract'),
        ({'session_wall_s': 3601}, 'budget_exceeded'),
        ({'host_class': 'ci_coarse'}, 'session_contract'),
        ({'fixture_words': 20, 'words_typed': 20}, 'session_contract'),
        ({'publishable': False, 'publication_block_reason': 'unsafe'}, 'unsafe'),
    ],
)
def test_typing_gates_do_not_publish_bad_sessions(runs, updates, reason):
    typing_pair(runs, **updates)
    text = render(runs, 'throughput')
    assert reason in text and '123 chars/s' not in text
    if reason == 'budget_exceeded' and 'progress' in updates:
        assert '77' in text


def test_nine_sessions_do_not_publish(runs):
    typing_pair(runs, count=9)
    assert 'not enough sessions' in render(runs, 'throughput')


def test_two_seeds_required(runs):
    typing_pair(runs)
    s = json.loads((runs[1] / 'summary.json').read_text())
    s['seed'] = 0
    (runs[1] / 'summary.json').write_text(json.dumps(s))
    assert 'distinct seeds' in render(runs, 'throughput')


def test_latency_acceptance_gate(runs):
    typing_pair(
        runs,
        'latency',
        key_to_paint={
            'outcome': 'measured',
            'n_scheduled': 100,
            'n_accepted': 1,
            'n_refused': 99,
            'median_ms': 20,
            'p90_ms': 20,
        },
    )
    assert 'witness_unavailable' in render(runs, 'latency')


def test_generated_typing_table(runs):
    typing_pair(runs)
    facts = report.facts_from_runs(*runs)
    assert 'perf.e2.table.TYPING' in facts
    assert 'chars/s' in facts['perf.e2.table.TYPING']


@pytest.mark.parametrize(
    'updates,reason',
    [
        ({'outcome': 'refused'}, 'not_measured'),
        ({'refusal_code': 'crash'}, 'crash'),
        ({'publishable': False, 'publication_block_reason': None}, 'publishable_not_true'),
        ({'session_wall_s': None}, 'session_contract'),
        ({'throughput_chars_s': None}, 'malformed_throughput'),
    ],
)
def test_remaining_session_refusals(runs, updates, reason):
    typing_pair(runs, **updates)
    assert reason in render(runs, 'throughput')


def test_typing_quarantine_veto(runs):
    typing_pair(runs)
    for i in range(3):
        (runs[0] / f'rejected-evidence/{i:04d}-plate').mkdir(parents=True)
    assert 'quarantined' in render(runs, 'throughput')


def test_typing_duplicates_and_unreadable_attempts(runs):
    typing_pair(runs)
    root = runs[0]
    for i in range(3):
        p = root / f'cells/{i:04d}-plate/attempts'
        (p / 'duplicate.json').write_text((p / 'TYPING.json').read_text())
    assert 'conflicting_trials' in render(runs, 'throughput')
    (root / 'cells/0004-plate/attempts/bad.json').write_text('{')
    assert 'unreadable_trial' in render(runs, 'throughput')


def test_typing_sample_accounting_veto(runs):
    from perf.tests.test_e2_report_fix3 import sample

    typing_pair(runs)
    for i in range(3):
        sample(runs[0], i, 'cpu_throttled', 'cpu_throttled')
    assert 'cpu_throttled' in render(runs, 'throughput')


def test_typing_reproduction_versions_must_match(runs):
    typing_pair(runs)
    s = json.loads((runs[1] / 'summary.json').read_text())
    s['rendering'] = {'browser_version': 'other'}
    (runs[1] / 'summary.json').write_text(json.dumps(s))
    text = render(runs, 'throughput')
    assert 'other Playwright or Chromium' in text and '123 chars/s' not in text


def test_typing_reproduction_requires_same_editor_build_tree(runs):
    # Typing session rows carry no environment.editor_version; the built
    # editor tree in host_provenance is the pin a reproduction must share.
    typing_pair(runs)
    for root, tree in zip(runs, ('tree-a', 'tree-b')):
        for i in range(12):
            path = root / f'cells/{i:04d}-plate/attempts/TYPING.json'
            row = json.loads(path.read_text())
            row['host_provenance'] = {'host_build': 'production', 'publishable': True, 'tree_sha256': tree}
            path.write_text(json.dumps(row))
    text = render(runs, 'throughput')
    assert 'different editor builds' in text or 'other editor pins' in text
    assert '123 chars/s' not in text


def test_typing_reproduction_allows_matching_editor_build_tree(runs):
    typing_pair(runs)
    for root in runs:
        for i in range(12):
            path = root / f'cells/{i:04d}-plate/attempts/TYPING.json'
            row = json.loads(path.read_text())
            row['host_provenance'] = {'host_build': 'production', 'publishable': True, 'tree_sha256': 'tree-a'}
            path.write_text(json.dumps(row))
    assert 'chars/s' in render(runs, 'throughput')


def test_latency_instrumented_values_never_enter_public_facts(runs):
    typing_pair(runs, 'latency')
    facts = {}
    report.typing_table(facts, list(runs), 'plate', 'latency')
    serialized = json.dumps(facts)
    assert '999999' not in serialized and '987654321' not in serialized
    assert 'throughput_chars_s' not in serialized and 'resources' not in serialized
