"""#211: C17's ``ready`` memory is kept only where the document was checked as loaded.

The memory probe samples the browser tree once the editor's ready signal is
raised. For editors whose ready check is ``opening_only`` or ``not_run`` the
harness did not enforce that the whole document was mounted
(``content_length_enforced: false``): SuperDoc at 250,000 words read 667 MB at
ready and 1,426 MB after the edit burst. Such a sample is not the memory of the
loaded document, so the reader does not keep it. The cached row is never
mutated; the other phases and C19 are left alone.
"""
from copy import deepcopy

from perf.analysis import e2_cells


def _row(phase='ready', enforced=False, check='opening_only', criterion='C17'):
    return {
        'criterion_id': criterion,
        'editor_id': 'superdoc',
        'outcome': 'measured',
        'refusal_code': None,
        'publishable': True,
        'measurement_phase': phase,
        'sample_unit': 'bytes',
        'samples_ms': [666779648],
        'latency_ms': None,
        'diagnostic': {'content_length_check': check, 'content_length_enforced': enforced},
    }


def test_a_ready_sample_whose_document_check_was_not_enforced_is_not_kept():
    row = _row()
    before = deepcopy(row)
    fixed = e2_cells.c17_ready_unverified(row)
    assert row == before
    assert fixed['outcome'] == 'refused'
    assert fixed['refusal_code'] == 'unverified'
    assert fixed['failure_reason'] == 'document_not_verified_loaded'
    assert fixed['samples_ms'] == []
    assert e2_cells._trial_block(fixed) == 'unverified'
    assert fixed['ready_unverified'] == {'issue': 211, 'was_bytes': 666779648, 'content_length_check': 'opening_only'}


def test_an_enforced_ready_sample_is_kept():
    row = _row(enforced=True, check='applied')
    assert e2_cells.c17_ready_unverified(row) is row


def test_a_record_that_does_not_say_is_left_alone():
    row = _row()
    row['diagnostic'] = {}
    assert e2_cells.c17_ready_unverified(row) is row


def test_the_later_phases_and_other_criteria_are_left_alone():
    for phase in ('after_edit_burst', 'quiescent'):
        row = _row(phase=phase)
        assert e2_cells.c17_ready_unverified(row) is row
    row = _row(criterion='C19')
    assert e2_cells.c17_ready_unverified(row) is row


def test_a_refused_ready_row_keeps_its_own_reason():
    row = _row()
    row.update(outcome='failed', refusal_code='editor_timeout', samples_ms=[])
    assert e2_cells.c17_ready_unverified(row) is row
