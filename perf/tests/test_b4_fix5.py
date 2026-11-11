"""B4 fix round 5: F1 cleanup I/O, meta refresh, reset wait, malformed observations."""

import json
import subprocess
from pathlib import Path

import pytest

from perf.runner.criteria_input_io import _witness_evidence_from_entry
from perf.tests.test_b4_fix4 import entry, observation

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def probes():
    proc = subprocess.run(
        ['node', str(REPO / 'perf/tests/b4_fix5_repro.mjs')],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return json.loads(proc.stdout)


def test_refused_c09_survives_page_loss_in_finally(probes):
    a10 = probes['a10']
    assert a10['thrown'] is None
    assert a10['kept_reason']
    assert a10['kept_refusal']
    assert a10['fixture_reset'] is not None
    assert a10['fixture_reset'].get('error')


def test_measured_c09_survives_page_loss_in_finally(probes):
    a11 = probes['a11']
    assert a11['thrown'] is None
    assert a11['outcome'] == 'measured'
    assert a11['samples'] == [40]
    assert a11['fixture_reset'] is not None
    assert a11['fixture_reset'].get('error')


def test_c09_only_skips_long_fixture_wait(probes):
    # The long restore wait polls the document ~100 times; when C09 runs
    # without C08 the restore is a single read. Wall-clock duration is a bad
    # proxy here because the double's cdp emits no screencast frames and the
    # witness burns its fixed baseline waits — measure the poll count instead.
    assert probes['m2_skip_wait']['reads_after_reload'] <= 2
    assert probes['m2_skip_wait']['fixture_reset']['restored'] is False


def test_meta_editable_refreshed_after_c09_reset(probes):
    assert probes['m1_meta_refresh']['c09_reset']['restored'] is True
    assert probes['m1_meta_refresh']['payload_text_length'] == 20


def test_refused_entry_malformed_observation_not_silent():
    refused = dict(outcome='failed', failure_reason='refused', observations=[None, observation()])
    with pytest.raises(ValueError, match='observation'):
        _witness_evidence_from_entry(refused)
