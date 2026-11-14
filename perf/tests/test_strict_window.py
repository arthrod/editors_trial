"""#203: a classifying frame witness counts only frames inside its window.

C14 asks whether document damage followed load within 500 ms of a settled
frame. The scan loop's deadline was wall-clock from the loop's start, after
setup calls into a busy page returned, so every frame recorded meanwhile was
accepted: GenOffice at 500,000 words read 4.9 minutes from a 0.66% change
160 s after the window opened. ``strictWindow`` bounds the frame's page time
by ``afterPageMs + windowMs`` plus the clock conversion's upper error bound.
Lanes that wait for the paint of their own input keep their first changed frame.
"""
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REPRO = REPO / 'perf' / 'tests' / 'strict_window_repro.mjs'
_CACHE = {}


def _run():
    if 'out' not in _CACHE:
        proc = subprocess.run(['node', str(REPRO)], cwd=str(REPO), capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, proc.stderr
        _CACHE['out'] = json.loads(proc.stdout)
    return _CACHE['out']


def test_a_frame_recorded_while_the_page_was_busy_past_the_window_is_not_damage():
    late = _run()['late_strict']
    assert late['outcome'] == 'no_frame'
    assert late['strict_window'] is True
    assert late['frames_beyond_window'] == 1
    assert late['window_end_after_ms'] == 750


def test_a_wait_budget_witness_keeps_its_first_changed_frame():
    loose = _run()['late_loose']
    assert loose['outcome'] == 'witnessed'
    assert loose['frame_after_ms'] == 1000
    assert loose['strict_window'] is False


def test_a_frame_inside_the_window_is_damage():
    inside = _run()['inside_strict']
    assert inside['outcome'] == 'witnessed'
    assert inside['frame_after_ms'] == 300
    assert inside['frames_beyond_window'] == 0


def test_a_frame_inside_the_clock_error_past_500_ms_still_counts():
    slack = _run()['slack_strict']
    assert slack['outcome'] == 'witnessed'
    assert slack['frame_after_ms'] == 650


# -- the validator: the window fields are optional, typed, and a strict window binds --------------

def _record(**window):
    from perf.tests.witness_records import publishable_witness_record
    record = publishable_witness_record(frame_page_ms=100.0, after_page_ms=80.0)
    record.update(window)
    return record


def _validate(record):
    from perf.runner.witness import validate_witness
    return validate_witness(record)


def test_a_record_with_the_window_fields_validates():
    record = _record(strict_window=False, window_end_page_ms=None, window_slack_ms=None,
                     frames_beyond_window=0, scan_started_after_ms=3.5)
    assert _validate(record)['ok'], _validate(record)


def test_a_strict_record_inside_its_window_validates():
    record = _record(strict_window=True, window_end_page_ms=830.0, window_slack_ms=250,
                     frames_beyond_window=0, scan_started_after_ms=3.5)
    assert _validate(record)['ok'], _validate(record)


def test_a_strict_record_whose_frame_is_past_its_window_is_refused():
    record = _record(strict_window=True, window_end_page_ms=90.0, window_slack_ms=250,
                     frames_beyond_window=0, scan_started_after_ms=3.5)
    result = _validate(record)
    assert not result['ok']
    assert 'is past its strict window' in json.dumps(result)


def test_the_window_fields_are_typed():
    assert not _validate(_record(strict_window='yes'))['ok']
    assert not _validate(_record(frames_beyond_window=-1))['ok']
    assert not _validate(_record(window_end_page_ms=float('nan')))['ok']


def test_c14s_natural_witness_is_strict_and_only_it():
    """The classifying witness (C14 natural) is strict; the wait-budget witnesses
    (C11's presented frame, C12's reflow, the input lanes) keep their first frame."""
    import re
    src = (REPO / 'perf' / 'runner' / 'document_probe.mjs').read_text()
    natural = re.search(r"natural = await witnessFrame\(ctx\.page, ctx\.cdp, \{(.*?)\n      \}\);", src, re.S)
    assert natural and 'strictWindow: true' in natural.group(1)
    assert src.count('strictWindow: true') == 1
    for name in ('criteria_input.mjs', 'warm_cold_browser.mjs', 'typing_session.mjs', 'adversarial_c10_scroll.mjs'):
        assert 'strictWindow' not in (REPO / 'perf' / 'runner' / name).read_text(), name


def test_strict_without_an_arm_time_is_not_recorded_as_strict():
    """GLM review of #203: strict_window true with a null window end is a record the validator refuses."""
    rec = _run()['strict_no_arm']
    assert rec['strict_window'] is False
    assert rec['window_end_page_ms'] is None
