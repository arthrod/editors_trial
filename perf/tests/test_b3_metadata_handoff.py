"""Writer integration: retain observed intervals and launch publication semantics."""
from perf.tests import test_witness
from perf.tests.test_schema import _env
from perf.runner import benchmark_document as lane


def write(tmp_path):
    return lane._write_measured(
        attempt_dir=tmp_path, criterion_id='C11', editor_id='plate', lane='browser',
        env=_env(), samples=[5],
        diagnostic={'samples': [{'content_verified': True,
                     'witness': test_witness.WitnessValidatorTests.good_record()}]})[1]


def test_document_writer_records_observed_interval_and_subframe(tmp_path):
    trial = write(tmp_path)
    assert trial['diagnostic'].get('frame_interval_ms') == 16.7, trial
    assert trial.get('sub_frame_samples') == [True], trial


def test_document_fresh_process_is_not_a_distribution_refusal(tmp_path):
    trial = write(tmp_path)
    assert 'I10' not in (trial.get('publication_block_reason') or ''), trial


def test_find_writer_uses_its_own_interval_observations(tmp_path):
    trial = lane._write_measured(attempt_dir=tmp_path, criterion_id='C15',
        editor_id='plate', lane='browser', env=_env(), samples=[5],
        diagnostic={'samples': [{'frame_interval_ms': 8.3}]})[1]
    assert trial['diagnostic'].get('frame_interval_ms') == 8.3, trial
    assert trial.get('sub_frame_samples') == [True]


import json
import pytest


@pytest.mark.parametrize('reason,code', [
    ('witness refused: no_frame', 'paint_witness_unavailable'),
    ('document_content_mismatch', 'unverified'),
    ('cpu_throttled: sample rejected', 'cpu_throttled'),
    ('host-error: startup unavailable', 'host_build'),
    ('clock skew exceeds the 2 ms bound (clock_skew_ms=3)', 'paint_witness_unavailable'),
    ('no compositor frame captured at or after the observed y-shift', 'paint_witness_unavailable'),
    ('no presented frame at or after the document surface; FCP is not a C11 sample', 'paint_witness_unavailable'),
    ('no document surface; FCP is not a C11 sample', 'unverified'),
    ('presented frame precedes the anchor reflow (frame=1 shift=20 input=0)', 'paint_witness_unavailable'),
    ('negative presented_frame_ms', 'paint_witness_unavailable'),
    ('compositor frame timestamp precedes the DOM usability mark; clock mismatch', 'paint_witness_unavailable'),
    ('no DOM usability mark (page/block element never appeared with text)', 'unverified'),
    ('text-shift assertion failed: anchor block did not move down', 'unverified'),
    ("C12 window includes the probe's own forced layout", 'unverified'),
    ('first_match: find widget acknowledged neither a first match nor completion', 'unverified'),
    ('probe produced no JSON for plate (exit 1): failure', 'crash'),
    ('unexpected internal exception', 'crash'),
])
def test_document_refusals_keep_their_classification(tmp_path, reason, code):
    path = lane._write_refusal(attempt_dir=tmp_path, criterion_id='C11',
        editor_id='plate', lane='browser', env=_env(), outcome='failed', failure_reason=reason)
    trial = json.loads(path.read_text())
    assert trial['refusal_code'] == code
    assert trial['failure_reason'] == reason
    assert trial['samples_ms'] == []


@pytest.mark.parametrize('intervals', [[], [8.3, 16.7]])
def test_document_does_not_measure_without_one_coherent_interval(tmp_path, intervals):
    trial = lane._write_measured(attempt_dir=tmp_path, criterion_id='C15',
        editor_id='plate', lane='browser', env=_env(), samples=[5] * max(1, len(intervals)),
        diagnostic={'samples': [{'frame_interval_ms': value} for value in intervals]})[1]
    assert trial['outcome'] != 'measured', trial
    assert trial['samples_ms'] == []
    assert trial['refusal_code'] == 'paint_witness_unavailable'
