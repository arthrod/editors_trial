"""B4 fix round 7: frame-interval witness setup isolation; harness_error vs page_lost; remaining suite phases."""

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

PHASE_BOUNDARIES = [
    ('input_tap', 'install input tap'),
    ('ready_ms', 'ready page clock'),
    ('c04_mid', 'C04 quiescence (fix6)'),
    ('after_c04', 'initial resolve click points (fix6)'),
    ('initial_read_state', 'initial editable read'),
    ('frame_interval', 'paint witness frame interval'),
    ('alive_c04', 'C04 criterion harness fault (live page)'),
    ('alive_boundary', 'post-C04 resolve click points (live page)'),
    ('c07_mid', 'C07 mid-criterion (fix6)'),
    ('partial_c07', 'C07 partial observation discard'),
    ('c09_mid', 'C09 mid-criterion (fix6)'),
    ('c08_refresh', 'C08 fixture resolve (fix6)'),
    ('c08_refresh_read', 'C08 fixture editable read'),
    ('c08_mid', 'C08 mid-criterion (fix6)'),
    ('stop_send', 'stopRecorder transport'),
    ('after_c08', 'stopRecorder listener teardown'),
]


@pytest.fixture(scope='module')
def fix7():
    proc = subprocess.run(
        ['node', str(REPO / 'perf/tests/b4_fix7_repro.mjs')],
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    return json.loads(proc.stdout)


@pytest.fixture(scope='module')
def phases6():
    proc = subprocess.run(
        ['node', str(REPO / 'perf/tests/b4_fix6_repro.mjs')],
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    return json.loads(proc.stdout)


def _harness_error(entry):
    assert entry is not None
    assert entry['outcome'] == 'failed'
    assert entry['reason'] and entry['reason'].startswith('harness_error:')


def _page_lost(entry):
    assert entry is not None
    assert entry['outcome'] == 'failed'
    assert entry['reason'] and entry['reason'].startswith('page_lost:')


def test_fix7_suite_returns_on_every_new_phase(fix7):
    for death_at in (
        'frame_interval',
        'alive_boundary',
        'alive_c04',
        'partial_c07',
        'stop_send',
        'after_c08',
        'input_tap',
        'ready_ms',
        'initial_read_state',
        'c08_refresh_read',
    ):
        row = fix7[death_at]
        assert row['thrown'] is None, death_at
        assert row['returned'] is True, death_at


def test_frame_interval_keeps_c04_and_stops_recorder(fix7):
    row = fix7['frame_interval']
    assert row['C04']['outcome'] == 'measured'
    assert row['C04']['samples'] == [123.4]
    assert row['state']['offCalls'] == 1
    for cid in ('C07', 'C09', 'C08'):
        reason = row[cid]['reason'] or ''
        assert reason.startswith('paint_witness_unavailable:')


def test_alive_boundary_harness_error_not_page_lost(fix7):
    row = fix7['alive_boundary']
    assert row['state']['dead'] is False
    assert row['C04']['outcome'] == 'measured'
    _harness_error(row['C07'])
    _harness_error(row['C09'])
    _harness_error(row['C08'])


def test_alive_c04_harness_error_suite_continues(fix7):
    row = fix7['alive_c04']
    assert row['state']['dead'] is False
    _harness_error(row['C04'])
    assert row['C07']['observations'] == 3


def test_partial_c07_drops_partial_measurement(fix7):
    row = fix7['partial_c07']
    assert row['C04']['outcome'] == 'measured'
    _page_lost(row['C07'])
    assert row['C07']['samples'] == []
    assert row['C07']['observations'] == 0


def test_stop_send_and_after_c08_recorder_cleanup(fix7):
    for key in ('stop_send', 'after_c08'):
        row = fix7[key]
        assert row['state']['stopCalls'] == 1
        assert row['state']['offCalls'] == 1
        assert row['C04']['outcome'] == 'measured'
        assert row['C07']['observations'] == 3


def test_after_c08_completed_entries_not_relabelled_page_lost(fix7):
    row = fix7['after_c08']
    assert row['C09'] is not None
    assert not (row['C09'].get('reason') or '').startswith('page_lost:')


def test_early_phase_deaths_return_and_fill(fix7):
    for death_at in ('input_tap', 'ready_ms'):
        row = fix7[death_at]
        _page_lost(row['C04'])
        for cid in ('C07', 'C09', 'C08'):
            _page_lost(row[cid])


def test_initial_read_state_keeps_measured_c04(fix7):
    row = fix7['initial_read_state']
    assert row['C04']['outcome'] == 'measured'
    for cid in ('C07', 'C09', 'C08'):
        _page_lost(row[cid])


def test_c08_refresh_read_keeps_complete_prior_entries(fix7):
    row = fix7['c08_refresh_read']
    assert row['C04']['outcome'] == 'measured'
    assert row['C07']['observations'] == 3
    assert row['C09']['fixture_reset'] is not None
    _page_lost(row['C08'])


def test_phase_boundary_table_covers_fix6_regressions(phases6):
    for death_at in ('c04_mid', 'after_c04', 'c07_mid', 'c09_mid', 'c08_refresh', 'c08_mid'):
        row = phases6[death_at]
        assert row['thrown'] is None, death_at
        assert row['returned'] is True, death_at


def test_phase_boundary_manifest_is_complete():
    proc = subprocess.run(
        ['node', str(REPO / 'perf/tests/b4_suite_phase_manifest.mjs')],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    report = json.loads(proc.stdout)
    assert report['ok'], report
    nested = {'alive_c04', 'alive_boundary', 'partial_c07', 'after_c08'}
    table_keys = {k for k, _ in PHASE_BOUNDARIES}
    assert table_keys <= set(report['exported']) | nested
