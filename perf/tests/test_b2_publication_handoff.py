"""Writer integration: launch-level sample counts are aggregated by B7."""
import json
from perf.tests.test_schema import _env
from perf.runner import benchmark_warm_cold as lane


def test_one_fresh_process_sample_is_not_a_distribution_refusal(tmp_path):
    path = lane._write_measured_attempt(
        attempt_dir=tmp_path, criterion_id='C03', layer='browser_visible',
        boundary='first_usable', editor_id='plate', lane='browser',
        env=_env(), samples_ms=[25], cache_state='process_cold_fs_warm',
        diagnostic={'clock_skew': [{'acceptable': True, 'skew_ms': 0, 'bound_ms': 5, 'frame_interval_ms': 8.3}]})
    trial = json.loads(path.read_text())
    assert 'I10' not in (trial.get('publication_block_reason') or ''), trial
    assert trial['publishable'] is True, trial


import pytest


@pytest.mark.parametrize('reason,code', [
    ('clock_skew_above_bound', 'paint_witness_unavailable'),
    ('frame_interval_unavailable', 'paint_witness_unavailable'),
    ('expected_edit_not_confirmed', 'unverified'),
    ('cpu_throttled', 'cpu_throttled'),
    ('not_document_scoped', 'paint_witness_unavailable'),
    ('no_pixel_evidence', 'paint_witness_unavailable'),
    ('not_a_witness_record', 'malformed_samples'),
    ('record_not_a_mapping', 'malformed_samples'),
    ('browser_probe: process failed', 'crash'),
])
def test_b2_refusal_is_structured_without_an_active_run(tmp_path, reason, code):
    path = lane._persist_attempt(tmp_path, 'C05', 'plate', {
        'criterion_id': 'C05', 'editor_id': 'plate', 'layer': 'browser_visible',
        'boundary': 'presented_frame', 'environment': _env(), 'outcome': 'failed',
        'failure_reason': reason, 'samples_ms': [], 'latency_ms': None, 'claims': []})
    trial = json.loads(path.read_text())
    assert trial.get('refusal_code') == code, trial
    assert trial['failure_reason'] == reason
