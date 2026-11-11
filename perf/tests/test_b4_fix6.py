"""B4 fix round 6: F2 suite phase-boundary isolation; m5 malformed observation in refusal recorder."""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from perf.runner.criteria_input_io import write_trials_from_payload
from perf.tests.test_b4_fix import _payload, fixture_identity
from perf.tests.test_input_criteria import _catalog

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def phases():
    proc = subprocess.run(
        ['node', str(REPO / 'perf/tests/b4_fix6_repro.mjs')],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return json.loads(proc.stdout)


def _page_lost(entry):
    assert entry is not None
    assert entry['outcome'] == 'failed'
    assert entry['reason'] and entry['reason'].startswith('page_lost:')


def test_suite_returns_on_every_death_phase(phases):
    for death_at, row in phases.items():
        assert row['thrown'] is None, death_at
        assert row['returned'] is True, death_at


def test_c04_mid_keeps_c04_page_lost_and_fills_rest(phases):
    row = phases['c04_mid']
    _page_lost(row['C04'])
    for cid in ('C07', 'C09', 'C08'):
        _page_lost(row[cid])


def test_after_c04_measured_survives(phases):
    row = phases['after_c04']
    assert row['C04']['outcome'] == 'measured'
    assert row['C04']['samples'] == [123.4]
    for cid in ('C07', 'C09', 'C08'):
        _page_lost(row[cid])


def test_c07_mid_keeps_c04_measured(phases):
    row = phases['c07_mid']
    assert row['C04']['outcome'] == 'measured'
    _page_lost(row['C07'])
    for cid in ('C09', 'C08'):
        _page_lost(row[cid])


def test_c09_mid_keeps_prior_criteria(phases):
    row = phases['c09_mid']
    assert row['C04']['outcome'] == 'measured'
    assert row['C07']['observations'] == 3
    _page_lost(row['C09'])
    _page_lost(row['C08'])


def test_c08_refresh_keeps_complete_c09(phases):
    row = phases['c08_refresh']
    assert row['C04']['outcome'] == 'measured'
    assert row['C07']['observations'] == 3
    assert row['C09']['fixture_reset'] is not None
    assert row['C09']['fixture_reset'].get('restored') is True
    assert row['C09']['observations'] >= 1
    _page_lost(row['C08'])


def test_c08_mid_keeps_prior_complete_entries(phases):
    row = phases['c08_mid']
    assert row['C04']['outcome'] == 'measured'
    assert row['C07']['observations'] == 3
    assert row['C09'] is not None
    assert not (row['C09'].get('reason') or '').startswith('page_lost:')
    _page_lost(row['C08'])


def test_malformed_observation_recorded_in_refusal_not_raised():
    """Refused write plus malformed observations must not escape write_trials_from_payload."""
    row = _catalog()['C08']
    c08 = {
        'criterion_id': 'C08',
        'layer': row['layer'],
        'boundary': row['boundary'],
        'evidence': row['evidence'],
        'outcome': 'failed',
        'samples_ms': [16.0],
        'failure_reason': 'paint_witness_refused: clock',
        'assertion': {'name': 'x', 'passed': False, 'scope': 's', 'checks': {}, 'failures': []},
        'trial_hints': {'cache_state': 'warm_steady', 'repetition_unit': 'in_process_iteration'},
        'observations': [None],
        'notes': [],
    }
    payload = _payload({'C08': c08})
    row, sha, size = fixture_identity()
    with tempfile.TemporaryDirectory() as tmp:
        written = write_trials_from_payload(
            payload,
            tmp,
            editor_version='fake',
            fixture_sha256=sha,
            workload_row=row,
            docx_size=size,
        )
    assert written['C08']['written'] is False
    reason = written['C08']['failure_reason'] or ''
    assert 'malformed_observation' in reason
