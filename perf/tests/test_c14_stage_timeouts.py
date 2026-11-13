"""A C14 sample that times out says where (Arthur, 2026-11-13).

Plate's 250,000-word cells said only "did not finish within 330s". A C14
sample now logs each stage as it starts and ends: navigation, the editor's
ready signal, the document surface, the witness, and the whole-text read.
A timeout inside the probe names the stage that failed and the stages that
finished, with their times. When our own watchdog kills the probe, the
refusal reads the stage log the probe left on stderr.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from unittest import mock

import perf.runner.benchmark_document as bd
from perf.tests import test_b3_document as b3


class ProbeNamesTheStage(unittest.TestCase):
    setUpClass = classmethod(b3.FakeHostMeasurers.setUpClass.__func__)
    tearDownClass = classmethod(b3.FakeHostMeasurers.tearDownClass.__func__)

    def _run(self, host: str, extra: list) -> tuple[dict, str]:
        cmd = [b3._node(), str(b3.PROBE), "--mode", "scale", "--url", "%s/%s" % (self.base_url, host),
               "--corpus", str(self.corpus), "--doc-selector", ".doc-paragraph", "--page-model",
               "continuous_flow", *extra]
        proc = subprocess.run(cmd, cwd=str(b3.REPO), capture_output=True, text=True, timeout=120)
        return json.loads(proc.stdout), proc.stderr

    def test_a_ready_signal_that_never_comes_names_the_ready_stage(self):
        payload, stderr = self._run("b3_long_fixture_at_end.html",
                                    ["--timeout-ms", "2000", "--ready-js", "false"])
        self.assertEqual(payload["status"], "probe_error")
        self.assertIn("stage ready failed after", payload["reason"])
        self.assertIn("done: navigation", payload["reason"])
        self.assertEqual([s["stage"] for s in payload["stages"]], ["navigation"])
        self.assertIn("[c14-stage] ready start", stderr)

    def test_a_finished_sample_records_every_stage(self):
        payload, stderr = self._run("c14_canvas_copy.html", ["--timeout-ms", "20000", "--editor", "wordcraft"])
        names = [s["stage"] for s in payload["load_stages"]]
        self.assertEqual(names[:3], ["navigation", "ready", "surface"])
        self.assertEqual(names[-1], "c14_text_read")
        self.assertTrue(all(isinstance(s["ms"], int) and s["ms"] >= 0 for s in payload["load_stages"]))
        self.assertIn("[c14-stage] c14_text_read done", stderr)


class WatchdogNamesTheStage(unittest.TestCase):
    """Our own kill: the probe never answers, so the stage comes from its stderr."""

    STALLED = (
        "process.stderr.write('[c14-stage] navigation start\\n');"
        "process.stderr.write('[c14-stage] navigation done 812 ms\\n');"
        "process.stderr.write('[c14-stage] ready start\\n');"
        "setTimeout(() => {}, 60000);"
    )

    def test_the_refusal_names_the_stage_the_probe_was_in(self):
        cmd = [b3._node() or "node", "-e", self.STALLED]
        with mock.patch.object(bd, "_subprocess_timeout_s", lambda cmd: 3.0):
            with self.assertRaises(bd.ProbeRefusal) as caught:
                bd._run_probe(cmd, editor_id="plate")
        reason = caught.exception.reason
        self.assertIn("did not finish within 3s", reason)
        self.assertIn("stopped in stage ready", reason)
        self.assertIn("navigation 812 ms", reason)
        self.assertEqual(caught.exception.refusal_code, "harness_error")

    def test_a_probe_with_no_stage_log_keeps_the_old_reason(self):
        cmd = [sys.executable, "-c", "import time; time.sleep(60)"]
        with mock.patch.object(bd, "_subprocess_timeout_s", lambda cmd: 2.0):
            with self.assertRaises(bd.ProbeRefusal) as caught:
                bd._run_probe(cmd, editor_id="plate")
        self.assertEqual(caught.exception.reason, "probe error for plate: editor did not finish within 2s")


if __name__ == "__main__":
    unittest.main()
