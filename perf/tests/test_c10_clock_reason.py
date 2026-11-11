"""C10 clock-check refusal reason (fixc10typ lane 1).

HF evidence (e2-docsplus, wordcraft, commit a5b1654): every C10 sample
refused with ``clock_skew_above_bound: the clock skew -0.7 ms is above the
bound of 2 ms`` while the same campaign's warm/cold lane recorded the real
failed check, ``anchor_lag_above_bound`` (frame lag ~105.7 ms over a ~100 ms
bound). The page offset of -0.7 ms sits inside the ±2 ms bound; the probe's
``!skew.acceptable`` branch discarded ``skew.reason`` and relabelled every
failed clock check ``clock_skew_above_bound``.

The repro feeds HF-shaped ``clockSkew`` records through the reason builder
the probe uses; before the fix the builder does not exist and the repro
process fails outright.
"""
import json
import os
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REPRO = REPO / 'perf' / 'tests' / 'c10_clock_reason_repro.mjs'


def _run_repro() -> dict:
    proc = subprocess.run(
        ['node', str(REPRO)], cwd=str(REPO), capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise AssertionError(
            'c10_clock_reason_repro.mjs failed (rc=%s)\nstdout:\n%s\nstderr:\n%s'
            % (proc.returncode, proc.stdout, proc.stderr))
    return json.loads(proc.stdout.strip())


class C10ClockReason(unittest.TestCase):
    def test_anchor_lag_failure_is_not_labelled_clock_skew(self):
        reason = _run_repro()['wordcraft_anchor_lag']
        self.assertTrue(reason.startswith('anchor_lag_above_bound:'), reason)
        self.assertIn('105.7', reason)
        self.assertNotIn('-0.7 ms is above the bound', reason)

    def test_true_page_offset_failure_keeps_clock_skew_token(self):
        reason = _run_repro()['page_offset']
        self.assertTrue(reason.startswith('clock_skew_above_bound:'), reason)
        self.assertIn('-3.2 ms', reason)

    def test_unknown_timestamp_kind_reports_kind(self):
        reason = _run_repro()['unknown_kind']
        self.assertTrue(reason.startswith('timestamp_kind_unknown:'), reason)


if __name__ == '__main__':
    unittest.main()
