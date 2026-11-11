"""Round 4 regressions: pure writer checks and Node host-interface integration probes."""

import json
import subprocess
from pathlib import Path

import pytest

from perf.tests.witness_records import publishable_witness_record
from perf.runner.criteria_input_io import (
    _assert_retained_sample_witness_deltas,
    _witness_evidence_from_entry,
)

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def probes():
    proc = subprocess.run(
        ['node', str(REPO / 'perf/tests/b4_fix4_repro.mjs')], capture_output=True, text=True, check=True, timeout=60
    )
    return json.loads(proc.stdout)


def test_truncated_paste_keeps_refused_record(probes):
    obs = probes['c08_refused']['observations'][0]
    assert obs.get('witness', {}).get('clock_check', {}).get('notes', [])[-1] == 'whole-record'
    assert obs.get('witness_refusal') == 'clock_check_not_acceptable'
    assert obs.get('witness_errors')


def test_missing_undo_input_stops_at_original(probes):
    assert probes['c09_missing_input']['body'] == 'ORIGINAL'
    assert probes['c09_missing_input']['undos'] == 1


def test_missing_undo_input_keeps_witness(probes):
    obs = probes['c09_missing_input']['observations'][0] if probes['c09_missing_input']['observations'] else {}
    assert obs.get('witness_refusal') == 'clock_check_not_acceptable'
    assert obs.get('witness_errors')


def test_noop_undo_resets_fixture(probes):
    assert probes['cleanup']['reason'] == 'correctness: undo_did_not_restore_document_text'
    assert probes['cleanup']['body'] == 'ORIGINAL'
    assert probes['cleanup']['fixture_reset']['restored'] is True


def test_missing_paste_input_keeps_witness(probes):
    obs = probes['missing_paste']['observations'][0]
    assert obs.get('witness_refusal') == 'clock_check_not_acceptable'
    assert obs.get('witness_errors')


def test_cleanup_failure_does_not_throw(probes):
    assert probes['cleanup_failure'].get('thrown') is None
    assert 'ok' in probes['cleanup_failure']


def observation(identity='good', anchor=100.0, frame=140.0, sample=40.0):
    return dict(
        observation_id=identity,
        input_ms=anchor,
        frame_ms=frame,
        sample_ms=sample,
        witness=publishable_witness_record(frame, 100.0),
    )


def entry(observations, identity='good', sample=40.0):
    return dict(outcome='measured', samples_ms=[sample], sample_observation_ids=[identity], observations=observations)


def test_writer_returns_failed_witness():
    good = observation()
    bad = observation('bad')
    bad['witness']['clock_check'].update(acceptable=False, reason='anchor_lag_above_bound')
    bad['witness']['clock_skew_acceptable'] = False
    bad['witness_errors'] = ['sentinel-refusal']
    result = _witness_evidence_from_entry(entry([good, bad]))
    assert result['witness']['clock_check']['acceptable'] is False
    assert 'sentinel-refusal' in result['witness_errors']
    assert result['witness_verdict']['refused'] is True
    assert result['witness_verdict']['reason'] == 'clock_check_not_acceptable'


def test_different_anchor_refused():
    with pytest.raises(ValueError, match='anchor'):
        _assert_retained_sample_witness_deltas('C08', entry([observation(anchor=0.0, sample=140.0)], sample=140.0))


@pytest.mark.parametrize('reverse', [False, True])
def test_identity_is_independent_of_observation_order(reverse):
    observations = [observation('wrong', frame=150.0), observation()]
    if reverse:
        observations.reverse()
    error = None
    try:
        _assert_retained_sample_witness_deltas('C08', entry(observations))
    except ValueError as exc:
        error = str(exc)
    assert error is None, f'the selected good observation must be accepted: {error}'
    with pytest.raises(ValueError, match='witness latency'):
        _assert_retained_sample_witness_deltas('C08', entry(observations, identity='wrong'))


def test_missing_identity_refused():
    value = entry([observation()])
    del value['sample_observation_ids']
    with pytest.raises(ValueError, match='identity'):
        _assert_retained_sample_witness_deltas('C08', value)


def test_refused_summary_preserves_writer_evidence():
    from perf.runner import benchmark_input

    summarize = getattr(benchmark_input, 'criterion_summary', None)
    assert callable(summarize), 'summary must preserve the writer refusal evidence'
    row = dict(
        written=False,
        path=None,
        failure_reason='refused',
        witness={'sentinel': True},
        witness_errors=['sentinel-error'],
        observations=[{'witness_verdict': {'refused': True}}],
    )
    summary = summarize(row, {})
    assert summary['witness'] == row['witness']
    assert summary['witness_errors'] == row['witness_errors']
    assert summary['observations'] == row['observations']
    assert summary['attempt_file'] is None


def test_missing_click_retains_record_and_verdict(probes):
    obs = probes['missing_click']['observations'][0]
    assert obs.get('witness', {}).get('clock_check', {}).get('notes', [])[-1] == 'whole-record'
    assert obs.get('witness_verdict', {}).get('refused') is True
    assert obs['witness_verdict']['reason'] == 'clock_check_not_acceptable'


def test_producer_carries_retained_identity(probes):
    result = probes['positive_undo']
    assert result['outcome'] == 'measured'
    assert result.get('sample_observation_ids') == [result['observations'][0].get('observation_id')]
    assert result['observations'][0].get('observation_id')


def test_public_boundary_rejects_different_anchor():
    from perf.runner.criteria_input_io import assert_payload_shape
    from perf.tests.test_input_criteria import _entry, _payload

    value = _entry(cid='C08', **entry([observation(anchor=0.0, sample=140.0)], sample=140.0))
    with pytest.raises(ValueError, match='anchor'):
        assert_payload_shape(_payload({'C08': value}))


def test_failed_reset_does_not_add_unrequested_criterion(probes):
    result = probes['failed_reset_suite']
    assert result['criteria']['C09']['fixture_reset']['restored'] is False
    assert set(result['criteria']) == {'C09'}


def test_malformed_observation_refused():
    with pytest.raises(ValueError):
        _assert_retained_sample_witness_deltas('C08', entry([None, observation()]))
