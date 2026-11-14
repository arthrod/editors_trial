"""#205: the reader drops the load's long tasks from C04 records made before the fix.

C04 asks whether deferred work followed ready. Its long-task observer used
``buffered: true``, which replays the long tasks recorded during load, and
stamped each with its delivery time: 2 ms after ready. A long task lasts at
least 50 ms, so one delivered less than 50 ms after ready began before ready;
it is load work, not deferred work. When nothing else was observed, the
attempt is ``not_applicable`` (``no_deferred_work``), the harness's own rule.
When a later activity exists, the sample already ends at it and is unchanged.
The cached row is never mutated; a record from the fixed harness
(``long_tasks_before_ready`` in the observation) is left alone.
"""
from copy import deepcopy

from perf.analysis import e2_cells

READY = 5089.3


def _row(activities, sample=None, **observation_extra):
    if sample is None:
        sample = round(max(a['t'] for a in activities) - READY, 3)
    observation = {
        'ready_page_ms': READY,
        'quiescent': True,
        'quiet_at_page_ms': READY + sample,
        'elapsed_from_ready_ms': sample,
        'activity_count': len(activities),
        'long_tasks': sum(1 for a in activities if a['kind'] == 'longtask'),
        'activities': activities,
        'quiescence_event': 'last_activity_before_quiet_window',
        **observation_extra,
    }
    return {
        'criterion_id': 'C04',
        'editor_id': 'docen',
        'outcome': 'measured',
        'refusal_code': None,
        'publishable': True,
        'samples_ms': [sample],
        'latency_ms': sample,
        'diagnostic': {
            'assertion': {'name': 'deferred_work_settles', 'passed': True, 'failures': []},
            'notes': ['One sample per page load.'],
            'observations': [observation],
        },
    }


def _replayed(n=3, at=2.0):
    return [{'kind': 'longtask', 't': READY + at, 'detail': {'duration': 120}} for _ in range(n)]


def test_an_attempt_resting_only_on_replayed_load_tasks_is_not_applicable():
    row = _row(_replayed())
    fixed = e2_cells.c04_replay_corrected(row)
    assert fixed['outcome'] == 'not_applicable'
    assert fixed['refusal_code'] == 'not_applicable'
    assert fixed['failure_reason'] == 'no_deferred_work'
    assert fixed['samples_ms'] == []
    assert fixed['latency_ms'] is None
    assert e2_cells._trial_block(fixed) == 'not_applicable'
    note = fixed['replay_reclassified']
    assert note['issue'] == 205
    assert note['was_ms'] == 2.0
    assert note['replayed_long_tasks'] == 3
    observation = fixed['diagnostic']['observations'][0]
    assert observation['elapsed_from_ready_ms'] is None
    assert fixed['diagnostic']['assertion']['failures'] == ['no_deferred_work']


def test_the_cached_row_is_not_mutated():
    row = _row(_replayed())
    before = deepcopy(row)
    e2_cells.c04_replay_corrected(row)
    assert row == before


def test_a_later_long_task_keeps_the_sample():
    """WordCraft: the replayed load tasks at 2 ms, then its own task 422 ms after ready."""
    later = {'kind': 'longtask', 't': READY + 422.5, 'detail': {'duration': 110}}
    row = _row(_replayed() + [later])
    assert e2_cells.c04_replay_corrected(row) is row


def test_a_mutation_soon_after_ready_is_deferred_work():
    """Mutations are never replayed: only a long task proves it started before ready."""
    row = _row(_replayed() + [{'kind': 'mutation', 't': READY + 4.0, 'detail': {'count': 1}}])
    assert e2_cells.c04_replay_corrected(row) is row


def test_a_long_task_delivered_50_ms_or_more_after_ready_may_be_deferred():
    row = _row(_replayed(at=50.0))
    assert e2_cells.c04_replay_corrected(row) is row


def test_a_record_from_the_fixed_harness_is_left_alone():
    row = _row(_replayed(), long_tasks_before_ready=3)
    assert e2_cells.c04_replay_corrected(row) is row


def test_a_truncated_activity_list_is_left_alone():
    """The page keeps 400 activities; past that the list may miss the last one."""
    row = _row(_replayed())
    row['diagnostic']['observations'][0]['activity_count'] = 401
    assert e2_cells.c04_replay_corrected(row) is row


def test_other_criteria_and_unmeasured_rows_are_left_alone():
    row = _row(_replayed())
    other = dict(row, criterion_id='C07')
    assert e2_cells.c04_replay_corrected(other) is other
    refused = dict(row, outcome='unverified')
    assert e2_cells.c04_replay_corrected(refused) is refused


def test_the_reader_applies_it_to_every_attempt():
    import inspect
    assert 'c04_replay_corrected(row)' in inspect.getsource(e2_cells._attempt_rows_of)


def test_a_c04_cell_with_no_deferred_work_in_any_load_says_so():
    cell = {'criterion_id': 'C04', 'stats': None, 'scheduled': 10, 'refusals': {'not_applicable': 10}}
    assert e2_cells.publication_text(cell) == 'no deferred work after ready (10 of 10 loads)'


def test_a_c04_cell_with_other_refusals_keeps_the_count_text():
    cell = {'criterion_id': 'C04', 'stats': None, 'scheduled': 10,
            'refusals': {'not_applicable': 6, 'crash': 4}}
    assert e2_cells.publication_text(cell).startswith('not enough samples (n = 0 of 10')
