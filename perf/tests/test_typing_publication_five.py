"""Typing publication at 6 scheduled sessions and 5 kept (issue #163).

Arthur, 11 November: the typing lane schedules 6 sessions per kind per seed
and publishes a cell at 5 kept. A 12-session group is the previous campaign's
schedule and is not published. These numbers are the constants, not literals.
"""

import json
from functools import partial
from pathlib import Path

from build import perf_e2_tables as report


def _summary(run_id, seed, sessions):
    return {
        'run_id': run_id,
        'seed': seed,
        'execution_profile': 'dedicated_publish',
        'host_class': 'dedicated',
        'publishable': False,
        'host': {},
        'rendering': {},
        'order': [[i, 'plate'] for i in range(sessions)],
    }


def _session(kind, *, value, p90_ms=22):
    row = {
        'schema': 'perf.typing/2',
        'editor_id': 'plate',
        'criterion_id': 'TYPING',
        'session_kind': kind,
        'outcome': 'measured',
        'publishable': True,
        'refusal_code': None,
        'failure_reason': None,
        'publication_block_reason': None,
        'execution_profile': 'dedicated_publish',
        'host_class': 'dedicated',
        'isolation': 'fresh_process',
        'values_per_session': 1,
        'cadence_ms': 0,
        'budget_s': 3600,
        'correctness_oracle': 'dom_document_text',
        'fixture_sha256': 'full-file',
        'typed_text_sha256': 'full-stripped-text',
        'fixture_words': 12805,
        'words_typed': 12805,
        'session_wall_s': 300,
        'load_ms': 25,
        'load_refusal': None,
        'throughput_chars_s': value,
        'host_provenance': {
            'host_build': 'production',
            'publishable': True,
            'tree_sha256': 'tree-a',
        },
        'key_to_paint': {
            'outcome': 'measured',
            'n_scheduled': 2,
            'n_accepted': 2,
            'n_refused': 0,
            'median_ms': 20,
            'p90_ms': p90_ms,
            'samples': [{'ms': 20, 'sub_frame': False}, {'ms': p90_ms, 'sub_frame': False}],
        },
    }
    return row


def _write_pair(tmp_path, sessions, values, *, kind='throughput', p90s=None):
    roots = []
    for name, run_id, seed in (('primary', 'run-a', 1), ('repro', 'run-b', 2)):
        root = tmp_path / name
        root.mkdir()
        (root / 'summary.json').write_text(json.dumps(_summary(run_id, seed, sessions)))
        for index, value in enumerate(values):
            cell = root / 'cells' / f'{index:04d}-plate' / 'attempts'
            cell.mkdir(parents=True)
            p90 = 22 if not p90s else p90s[index]
            (cell / 'typing.json').write_text(json.dumps(_session(kind, value=value, p90_ms=p90)))
        roots.append(root)
    return roots


def test_typing_constants_are_six_sessions_and_five_kept():
    from perf.runner.browser_run import TYPING_PUBLICATION_MIN_KEPT, TYPING_PUBLICATION_SESSIONS

    assert TYPING_PUBLICATION_SESSIONS == 6
    assert TYPING_PUBLICATION_MIN_KEPT == 5


def test_six_scheduled_five_kept_publishes_median_and_range(tmp_path):
    roots = _write_pair(tmp_path, 6, [10, 20, 30, 40, 50])
    facts = {}
    text = report.typing_table(facts, roots, 'plate', 'throughput')
    assert facts['perf.e2.plate.TYPING.throughput.reproduced'] is True
    assert 'n = 5 of 6' in text
    assert 'wrong schedule' not in text
    assert '30 chars/s' in text
    assert 'range 10.0 to 50.0 chars/s' in text
    assert 'p90' not in text


def test_four_of_six_is_withheld_and_names_the_count(tmp_path):
    roots = _write_pair(tmp_path, 6, [123, 123, 123, 123])
    facts = {}
    text = report.typing_table(facts, roots, 'plate', 'throughput')
    assert facts['perf.e2.plate.TYPING.throughput.reproduced'] is False
    assert 'n = 4 of 6' in text
    assert 'wrong schedule' not in text
    assert '123 chars/s' not in text


def test_twelve_scheduled_is_the_wrong_schedule(tmp_path):
    roots = _write_pair(tmp_path, 12, [7777] * 12)
    facts = {}
    text = report.typing_table(facts, roots, 'plate', 'throughput')
    assert facts['perf.e2.plate.TYPING.throughput.reproduced'] is False
    assert 'wrong schedule' in text
    assert '7777' not in text


def test_latency_keeps_within_session_key_to_paint_p90(tmp_path):
    """p90 inside one session is over keys. Five to nine sessions print median and range."""
    p90s = [22, 22, 22, 22, 28]
    roots = _write_pair(tmp_path, 6, [100] * 5, kind='latency', p90s=p90s)
    text = report.typing_table({}, roots, 'plate', 'latency')
    assert 'key_to_paint.p90_ms' in text
    assert '22 ms' in text
    assert 'range 22.0 to 28.0 ms' in text


def test_early_stop_when_five_kept_are_unreachable(tmp_path):
    """A 6-session cell stops once two failures make 5 kept unreachable."""
    import sys
    from perf.runner.browser_run import BrowserRun, run_cli, write_json

    executed = 0
    old = sys.argv

    def cell():
        nonlocal executed
        executed += 1
        write_json(
            Path(sys.argv[sys.argv.index('--out-root') + 1]) / 'attempts/typing.json',
            {
                'criterion_id': 'TYPING',
                'session_kind': 'throughput',
                'outcome': 'refused',
                'correctness_oracle': 'dom_document_text',
                'refusal_code': 'correctness_failure',
                'throughput_chars_s': None,
                'failure_reason': 'budget_exceeded',
            },
        )
        return 0

    try:
        sys.argv = [
            'test',
            '--out-root', str(tmp_path),
            '--run-id', 'early-five',
            '--editors', 'plate',
            '--execution-profile', 'dedicated_publish',
            '--host-class', 'dedicated',
            '--session-kind', 'throughput',
        ]
        run_cli(
            cell,
            'benchmark_typing',
            {'plate': {}},
            run_factory=partial(
                BrowserRun,
                snapshot=lambda: {},
                accounting_reader=lambda: {'available': False, 'reason': 'synthetic unavailable'},
            ),
            facts=(lambda: {}, lambda: {}),
        )
    finally:
        sys.argv = old

    result = json.loads((tmp_path / 'benchmark_typing/early-five/summary.json').read_text())
    skipped = [
        json.loads(path.read_text())
        for path in (tmp_path / 'benchmark_typing/early-five').glob('cells/*/attempts/typing.json')
        if json.loads(path.read_text()).get('outcome') == 'not_run'
    ]
    assert len(result['order']) == 6
    assert executed == 2
    assert len(skipped) == 4
    assert {row.get('failure_reason') for row in skipped} == {'typing_sessions_unreachable'}
    assert result.get('failure_reason') == 'insufficient_typing_sessions'


def test_typing_sample_plan_sits_next_to_the_lane_sample_plan(tmp_path):
    from perf.runner import lax_bounds
    from perf.runner.browser_run import TYPING_PUBLICATION_MIN_KEPT, TYPING_PUBLICATION_SESSIONS

    paragraph = lax_bounds.typing_sample_paragraph()
    template = (
        Path(__file__).resolve().parents[2]
        / 'templates/reports/Report E2 - Speed in the Browser (2026).md'
    ).read_text()
    sample_at = template.index('{{perf.e2.sample_plan}}')
    typing_at = template.index('{{perf.e2.typing_sample_plan}}')
    assert 0 < typing_at - sample_at < 200
    assert '12 sessions' not in template
    assert 'at least 10 kept' not in template
    assert f'{TYPING_PUBLICATION_SESSIONS} sessions per kind per seed' in paragraph
    assert f'at least {TYPING_PUBLICATION_MIN_KEPT}' in paragraph
    assert 'median and the range' in paragraph
    assert report.unset_facts()['perf.e2.typing_sample_plan'] == paragraph
    roots = _write_pair(tmp_path, 6, [10, 20, 30, 40, 50])
    assert report.facts_from_roots(roots)['perf.e2.typing_sample_plan'] == paragraph


def test_typing_plan_minutes_scaled_from_the_twelve_session_calibration():
    """Campaign 1 calibrated benchmark_typing at 360 minutes for 12 sessions."""
    from perf.container import plan

    assert plan._TYPING == 180
    assert plan.estimate('benchmark_typing', []) == 180
