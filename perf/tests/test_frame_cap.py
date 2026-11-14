"""#202: the recorder's 1,200-frame cap must not freeze a frame cursor.

Docen's C11 at 500,000 words (job 164) was refused as ``anchor_missing`` with
``frames_total`` at 1,200: ``recorder.frames.length`` never grows past the cap, so
a scan from ``before = recorder.frames.length`` never saw the probe frame.
Frames now carry a sequence number that never repeats, and scans cursor on it.
"""
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REPRO = REPO / 'perf' / 'tests' / 'frame_cap_repro.mjs'


def _run():
    proc = subprocess.run(['node', str(REPRO)], cwd=str(REPO), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_frame_sequence_numbers_never_repeat_past_the_cap():
    out = _run()
    assert out['kept'] == 1200
    assert out['last_seq'] == 1299 and out['first_seq'] == 100
    assert out['seqs_increasing'] is True


def test_a_sequence_cursor_sees_frames_after_the_cap():
    out = _run()
    assert out['new_after_cap'] == 5
    assert out['all_retained'] == 1200


def test_the_clock_anchor_is_found_after_1200_frames():
    assert _run()['anchor_found'] is True


def test_a_frame_decoded_after_it_was_dropped_is_not_cached():
    """GLM review of #202: the cap evicts a frame's cached bitmap when it drops the frame; a decode
    that lands after the drop must not cache, or the bitmap stays for the whole session."""
    out = _run()
    assert out['dropped_decode_returned'] is True
    assert out['dropped_decode_cached'] is False
    assert out['live_decode_cached'] is True
