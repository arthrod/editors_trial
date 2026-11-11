"""C10 attempt-writer integration, using the captured shared witness."""
import json
from perf.tests import test_witness
from perf.tests.test_schema import _env
from perf.runner import adversarial_c10_scroll as lane


def write(tmp_path, outcome='measured', reason=None):
    path = lane._write_outcome(attempt_dir=tmp_path, outcome=outcome, reason=reason,
        samples=[{'value': 5, 'record': {'witness': test_witness.WitnessValidatorTests.good_record()}}]
                if outcome == 'measured' else [],
        env=_env(), editor_id='plate', lane='browser_visible', diagnostic={}, seed=1)
    return json.loads(path.read_text())


def test_c10_writer_keeps_witness_interval(tmp_path):
    trial = write(tmp_path)
    assert trial['diagnostic'].get('frame_interval_ms') == 16.7, trial
    assert trial.get('sub_frame_samples') == [True], trial


def test_c10_writer_preserves_throttle_refusal(tmp_path):
    trial = write(tmp_path, 'failed', 'cpu_throttled: the sample was refused')
    assert trial.get('refusal_code') == 'cpu_throttled', trial
    assert trial['samples_ms'] == []


import pytest


@pytest.mark.parametrize('intervals', [[], [8.3, 16.7]])
def test_c10_does_not_measure_without_one_coherent_interval(tmp_path, intervals):
    samples = [{'value': 5, 'record': {'witness': {'clock_check': {'frame_interval_ms': value}}}}
               for value in intervals] or [{'value': 5}]
    path = lane._write_outcome(attempt_dir=tmp_path, outcome='measured', reason=None,
        samples=samples, env=_env(), editor_id='plate', lane='browser_visible', diagnostic={}, seed=1)
    trial = json.loads(path.read_text())
    assert trial['outcome'] != 'measured', trial
    assert trial['samples_ms'] == []
    assert trial['refusal_code'] == 'paint_witness_unavailable'
