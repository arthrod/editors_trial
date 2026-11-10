"""Pure input-trial classification; keep refusals distinct from probe crashes."""
import pytest
from perf.runner.criteria_input_io import trial_from_entry
from perf.tests.test_schema import _env


@pytest.mark.parametrize('reason,code', [
    ('first_text_line: no_painted_frame', 'paint_witness_unavailable'),
    ('correctness: typed_character_or_position', 'unverified'),
    ('cpu_throttled', 'cpu_throttled'),
    ('malformed_observation', 'malformed_samples'),
    ('no_keydown_observed_for_undo', 'unverified'),
    ('typed_character_not_observable_in_document_text', 'unverified'),
    ('no_click_point_resolved', 'unverified'),
    ('quiescence_not_reached_within_3000ms', 'unverified'),
    ('fixture_reset_failed', 'unverified'),
    ('harness_error: TypeError: unexpected exception', 'crash'),
    ('page_lost: Target closed', 'crash'),
    ('unexpected probe exception', 'crash'),
])
def test_input_refusal_keeps_its_category(reason, code):
    trial = trial_from_entry('C08', {'layer':'browser_visible', 'boundary':'presented_frame',
        'outcome':'failed', 'samples_ms':[], 'failure_reason':reason}, _env())
    assert trial.get('refusal_code') == code, trial
    assert trial['failure_reason'] == reason
    assert trial['samples_ms'] == []


def test_fresh_process_multiple_samples_keep_the_guard_and_code():
    trial = trial_from_entry('C08', {'layer':'browser_visible', 'boundary':'presented_frame',
        'outcome':'measured', 'samples_ms':[1, 2]}, _env())
    assert trial['outcome'] == 'failed'
    assert trial['failure_reason'] == 'fresh_process_multi_sample'
    assert trial.get('refusal_code') == 'malformed_samples'
