"""Host record and quiet-machine check (arthrod/editors_trial#101).

The host record is evidence: a value the probe could not read is an error,
never a default. The quiet check is the AGENTS.md §3 rule made executable.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from unittest import mock

from perf.runner import host


def _sysctl(name: str) -> str:
    return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, check=True).stdout.strip()


@unittest.skipUnless(sys.platform == "darwin", "macOS probe")
class MacHostRecord(unittest.TestCase):
    def setUp(self):
        self.record = host.host_record()

    def test_ram_is_the_real_ram(self):
        self.assertEqual(self.record["ram_bytes"], int(_sysctl("hw.memsize")))

    def test_cpu_model_is_the_brand_string(self):
        self.assertEqual(self.record["cpu_model"], _sysctl("machdep.cpu.brand_string"))
        self.assertNotEqual(self.record["cpu_model"], "arm")

    def test_cores_and_os_version(self):
        self.assertEqual(self.record["cpu_cores_logical"], int(_sysctl("hw.logicalcpu")))
        self.assertEqual(self.record["cpu_cores_physical"], int(_sysctl("hw.physicalcpu")))
        product = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True).stdout.strip()
        self.assertEqual(self.record["os_version"], product)
        self.assertEqual(self.record["os"], "darwin")

    def test_power_source_is_read(self):
        self.assertIn(self.record["power_source"], ("ac", "battery"))


class NoInventedValues(unittest.TestCase):
    def test_unreadable_ram_raises(self):
        with mock.patch.object(host, "_ram_bytes_probe", return_value=None):
            with self.assertRaises(host.HostProbeError):
                host.host_record()

    def test_unreadable_cpu_raises(self):
        with mock.patch.object(host, "_cpu_model_probe", return_value=None):
            with self.assertRaises(host.HostProbeError):
                host.host_record()

    def test_no_hardcoded_512_mib_anywhere_in_runners(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "runner"
        offenders = [p.name for p in root.glob("*.py") if "512 * 1024 * 1024" in p.read_text(encoding="utf-8")]
        self.assertEqual(offenders, [])


class QuietCheck(unittest.TestCase):
    def _check(self, load1, top, ncpu=12, own=()):
        """``top`` rows are foreign processes; ``own`` rows are children of this process."""
        import os

        me = os.getpid()
        rows = [(me, 1, 0.0, "python3 test")]
        rows += [(10_000 + k, 1, pct, cmd) for k, (pct, cmd) in enumerate(top)]
        rows += [(20_000 + k, me, pct, cmd) for k, (pct, cmd) in enumerate(own)]
        with mock.patch.object(host, "_load_average", return_value=(load1, load1, load1)), mock.patch.object(
            host, "_processes", return_value=rows
        ), mock.patch.object(host, "_logical_cpus", return_value=ncpu):
            return host.quiet_machine_check()

    def test_idle_machine_is_quiet(self):
        result = self._check(1.2, [(3.0, "/usr/sbin/cfprefsd")])
        self.assertTrue(result["quiet"])
        self.assertEqual(result["reasons"], [])

    def test_high_load_is_not_quiet(self):
        result = self._check(9.0, [(3.0, "x")])
        self.assertFalse(result["quiet"])
        self.assertTrue(any("load" in r for r in result["reasons"]))

    def test_a_cpu_hog_is_not_quiet(self):
        result = self._check(1.0, [(98.0, "/usr/bin/yes")])
        self.assertFalse(result["quiet"])
        self.assertTrue(any("yes" in r for r in result["reasons"]))

    def test_word_or_bench_job_is_not_quiet(self):
        for name in ("/Applications/Microsoft Word.app/Contents/MacOS/Microsoft Word", "python3 neurotic_docx_bench/run.py"):
            result = self._check(1.0, [(1.0, name)])
            self.assertFalse(result["quiet"], name)
            self.assertTrue(result["heavy_trial_job_seen"])

    def test_own_process_tree_is_excluded(self):
        result = self._check(1.0, [], ncpu=12, own=[(99.0, "node harness/plate/roundtrip.ts")])
        self.assertTrue(result["quiet"])

    def test_another_sessions_runner_is_not_excluded(self):
        result = self._check(1.0, [(99.0, "python3 perf/runner/speed_headless.py")], ncpu=12)
        self.assertFalse(result["quiet"])

    def test_record_keeps_the_evidence(self):
        result = self._check(2.0, [(40.0, "/usr/libexec/syspolicyd")])
        for key in ("load_average", "logical_cpus", "top_cpu", "thresholds", "quiet", "reasons", "heavy_trial_job_seen"):
            self.assertIn(key, result)
        self.assertEqual(result["top_cpu"][0], "40.0 /usr/libexec/syspolicyd")


if __name__ == "__main__":
    unittest.main()
