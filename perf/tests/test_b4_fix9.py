"""B4 fix round 9: CDP session close → page_lost; manifest discovers executable awaits."""

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROBE_DIR = Path(__file__).resolve().parent / 'probes' / 'b4_fix9'
RUNNER = REPO / 'perf/runner/criteria_input.mjs'
PHASE_ANCHOR = '  try {\n    // @suite-phase input_tap\n'

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
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _manifest_report() -> dict:
    proc = subprocess.run(
        ['node', str(REPO / 'perf/tests/b4_suite_phase_manifest.mjs')],
        capture_output=True,
        text=True,
        timeout=30,
    )
    report = json.loads(proc.stdout)
    assert proc.returncode == (0 if report.get('ok') else 1), (proc.stdout, proc.stderr)
    return report


ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')


def _plain(text: str) -> str:
    """util.inspect colors (FORCE_COLOR=1 ignores NO_COLOR) must not defeat the parser."""
    return ANSI_RE.sub('', text)


def test_real_cdp_detach_is_page_lost():
    proc = _run_node(PROBE_DIR / 'detach.mjs', '--crash-only', timeout=120)
    assert proc.returncode == 0, proc.stderr
    matches = re.findall(
        r"reason:\s*['\"]((page_lost|harness_error)[^'\"]*)['\"]",
        _plain(proc.stdout + proc.stderr),
    )
    reasons = [m[0] for m in matches]
    assert reasons, proc.stdout
    assert all(r.startswith('page_lost:') for r in reasons), reasons


def test_phase_manifest_rejects_untagged_await_in_mutant():
    backup = RUNNER.read_text(encoding='utf8')
    try:
        # One await with no phase tag, placed where the suite's first phase starts.
        assert backup.count(PHASE_ANCHOR) == 1
        RUNNER.write_text(backup.replace(
            PHASE_ANCHOR, '  try {\n    await Promise.resolve("UNTAGGED NEW BOUNDARY");\n    // @suite-phase input_tap\n'),
            encoding='utf8')
        proc = subprocess.run(
            ['node', str(REPO / 'perf/tests/b4_suite_phase_manifest.mjs')],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode != 0, proc.stdout
        report = json.loads(proc.stdout)
        assert not report['ok']
        assert report.get('untagged_awaits'), report
    finally:
        RUNNER.write_text(backup, encoding='utf8')


def test_phase_boundary_manifest_discovers_executable_awaits():
    report = _manifest_report()
    assert report['ok'], report
    covered = set(report['exported']) | NESTED_INJECTION_PHASES
    assert REPRO_DEATH_KEYS <= covered
    assert set(report['discovered']) == set(report['exported'])
