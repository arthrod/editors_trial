"""B4 fix round 8: page-loss state vs message; health-probe deadline; discovered phase manifest."""

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROBE_DIR = Path(__file__).resolve().parent / 'probes' / 'b4_fix8'
RUNNER = REPO / 'perf/runner/criteria_input.mjs'

NESTED_INJECTION_PHASES = {'alive_c04', 'alive_boundary', 'partial_c07', 'after_c08'}
REPRO_DEATH_KEYS = {
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
    'c04_mid',
    'after_c04',
    'c07_mid',
    'c09_mid',
    'c08_refresh',
    'c08_mid',
    'classify_criterion',
    'classify_suite',
    'classify_health_probe',
}


def _run_node(script: Path, *args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    cmd = ['node', str(script), str(REPO), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)


@pytest.fixture(scope='module')
def fix8_repro():
    proc = subprocess.run(
        ['node', str(REPO / 'perf/tests/b4_fix8_repro.mjs')],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return json.loads(proc.stdout)


ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')


def _plain(text: str) -> str:
    """util.inspect colors (FORCE_COLOR=1 ignores NO_COLOR) must not defeat the parser."""
    return ANSI_RE.sub('', text)


def test_real_renderer_crash_is_page_lost():
    proc = _run_node(PROBE_DIR / 'browser-probes.mjs', '--crash-only')
    assert proc.returncode == 0
    matches = re.findall(
        r"reason:\s*['\"]((page_lost|harness_error)[^'\"]*)['\"]",
        _plain(proc.stdout + proc.stderr),
    )
    matches = [m[0] for m in matches]
    assert matches, proc.stdout
    assert all(r.startswith('page_lost:') for r in matches), matches


def test_live_page_probe_failure_is_harness_error_not_page_lost():
    proc = _run_node(PROBE_DIR / 'probe-error.mjs')
    data = json.loads(proc.stdout)
    row = data['alive_boundary']
    assert row['state']['dead'] is False
    assert row['C04']['outcome'] == 'measured'
    for cid in ('C07', 'C09', 'C08'):
        reason = row[cid]['reason'] or ''
        assert reason.startswith('harness_error:'), reason
        assert 'health_probe:' in reason


def test_keyword_probe_success_stays_harness_error():
    proc = _run_node(PROBE_DIR / 'keyword-short.mjs')
    data = json.loads(proc.stdout)
    row = data['alive_boundary']
    assert row['state']['dead'] is False
    reason = row['C07']['reason'] or ''
    assert reason.startswith('harness_error:')
    assert 'health_probe:' not in reason


def test_fake_crash_without_closed_is_page_lost(fix8_repro):
    row = fix8_repro['crash_alive']
    assert row['state']['crashed'] is True
    assert row['state']['dead'] is False
    assert row['C07']['reason'].startswith('page_lost:')


def test_phase_boundary_manifest_discovers_awaits():
    proc = subprocess.run(
        ['node', str(REPO / 'perf/tests/b4_suite_phase_manifest.mjs')],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    report = json.loads(proc.stdout)
    assert report['ok'], report
    covered = set(report['exported']) | NESTED_INJECTION_PHASES
    assert REPRO_DEATH_KEYS <= covered
