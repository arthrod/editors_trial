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
        for name in ("python3 build/word_verdicts.py --set broken", "python3 neurotic_docx_bench/run.py"):
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



def _no_proc(tmp):
    """Point every Linux evidence path at an empty temporary tree (#120)."""
    return [mock.patch.object(host, name, str(tmp / name.lower()))
            for name in ("PROC_SELF_CGROUP", "PROC1_CGROUP", "PROC1_ENVIRON", "DMI", "CPUINFO", "PROC_STAT",
                         "PROC_SELF_MOUNTINFO")]


class LinuxContainerHost(unittest.TestCase):
    """What a Hugging Face sandbox shows (#118, probe of 2026-11-09): an empty
    /sys/class/power_supply, a cgroup CPU quota of 16 on a 64-core host, a
    memory limit below the host's 517 GB, and the host's load average."""

    def setUp(self):
        import tempfile
        from pathlib import Path

        self.tmp = Path(tempfile.mkdtemp())
        self.supply = self.tmp / "power_supply"
        self.supply.mkdir()
        self.cgroup = self.tmp / "cgroup"
        self.cgroup.mkdir()
        self.patches = [
            mock.patch.object(host.sys, "platform", "linux"),
            mock.patch.object(host, "POWER_SUPPLY", str(self.supply)),
            mock.patch.object(host, "CGROUP", str(self.cgroup)),
            mock.patch.object(host, "CONTAINER_MARKERS", (str(self.tmp / "dockerenv"),)),
            *_no_proc(self.tmp),
            mock.patch.dict(host.os.environ, {}),  # the real environment may be a container's (#120)
        ]
        import shutil

        self.addCleanup(shutil.rmtree, self.tmp)
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        for key in ("KUBERNETES_SERVICE_HOST", "container"):
            host.os.environ.pop(key, None)
        # a v2 machine seen from its own cgroup namespace, as on the sandbox (#121)
        (self.tmp / "proc_self_cgroup").write_text("0::/\n")
        (self.cgroup / "cgroup.controllers").write_text("cpu memory\n")
        # bare-metal x86: CPU flags without "hypervisor"
        (self.tmp / "cpuinfo").write_text("processor\t: 0\nflags\t\t: fpu vme\n")

    def _supply(self, name, kind, online=None):
        d = self.supply / name
        d.mkdir()
        (d / "type").write_text(kind + "\n")
        if online is not None:
            (d / "online").write_text(online + "\n")

    def test_no_power_supply_at_all_is_mains_not_battery(self):
        self.assertEqual(host._power_source(), "ac")

    def test_a_laptop_on_battery_is_battery(self):
        self._supply("AC", "Mains", "0")
        self._supply("BAT0", "Battery")
        self.assertEqual(host._power_source(), "battery")

    def test_a_laptop_plugged_in_is_ac(self):
        self._supply("AC", "Mains", "1")
        self._supply("BAT0", "Battery")
        self.assertEqual(host._power_source(), "ac")

    def test_a_battery_alone_is_battery(self):
        self._supply("BAT0", "Battery")
        self.assertEqual(host._power_source(), "battery")

    def test_a_supply_whose_type_is_unreadable_is_unknown(self):
        (self.supply / "BAT0").mkdir()  # no type file: cannot tell a battery from mains (#119)
        self.assertIsNone(host._power_source())

    def test_unreadable_supply_directory_is_unknown(self):
        self.supply.rmdir()
        self.assertIsNone(host._power_source())

    def test_cgroup_v2_cpu_quota(self):
        (self.cgroup / "cpu.max").write_text("1600000 100000\n")
        self.assertEqual(host._cpu_quota(), 16.0)

    def test_unlimited_cgroup_has_no_quota(self):
        (self.cgroup / "cpu.max").write_text("max 100000\n")
        self.assertIsNone(host._cpu_quota())

    def test_no_cgroup_file_has_no_quota(self):
        self.assertIsNone(host._cpu_quota())

    def test_cgroup_v2_memory_limit(self):
        (self.cgroup / "memory.max").write_text("133143986176\n")
        self.assertEqual(host._memory_limit(), 133143986176)
        (self.cgroup / "memory.max").write_text("max\n")
        self.assertIsNone(host._memory_limit())

    def test_container_marker(self):
        self.assertFalse(host._in_container({}))
        self.assertTrue(host._in_container({"KUBERNETES_SERVICE_HOST": "10.0.0.1"}))
        (self.tmp / "dockerenv").write_text("")
        self.assertTrue(host._in_container({}))

    def test_record_carries_quota_limit_and_container(self):
        (self.cgroup / "cpu.max").write_text("1600000 100000\n")
        (self.cgroup / "memory.max").write_text("133143986176\n")
        with mock.patch.object(host, "_ram_bytes_probe", return_value=517267300 * 1024), mock.patch.object(
            host, "_cpu_model_probe", return_value="AMD EPYC 7R13 Processor"
        ), mock.patch.object(host, "_cores", return_value=(None, 64)), mock.patch.object(
            host, "_os_version", return_value="6.12.113"
        ), mock.patch.dict(host.os.environ, {"KUBERNETES_SERVICE_HOST": "10.0.0.1"}):
            record = host.host_record()
        # a container that sees no supply and no vendor cannot know its power (#120)
        self.assertEqual(record["power_source"], "unknown")
        self.assertEqual(record["power_supplies"], [])
        self.assertEqual(record["cpu_quota"], 16.0)
        self.assertEqual(record["memory_limit_bytes"], 133143986176)
        self.assertTrue(record["container"])
        self.assertEqual(record["cpu_cores_logical"], 64)


@unittest.skipUnless(sys.platform == "darwin", "macOS probe")
class MacIsNotAContainer(unittest.TestCase):
    def test_mac_record_has_no_quota(self):
        record = host.host_record()
        self.assertIsNone(record["cpu_quota"])
        self.assertIsNone(record["memory_limit_bytes"])
        self.assertFalse(record["container"])


class QuietCheckAncestors(unittest.TestCase):
    """#119 (grok new 1): ancestors are excluded from the CPU rule, not from the
    heavy-job rule. A Word driver that launched the runner is still a Word job."""

    def _check(self, parent_cmd, parent_pct):
        import os

        me, parent = os.getpid(), 4242
        rows = [(1, 0, 0.0, "init"), (parent, 1, parent_pct, parent_cmd), (me, parent, 0.0, "python3 runner")]
        with mock.patch.object(host, "_load_average", return_value=(0.5, 0.5, 0.5)), mock.patch.object(
            host, "_processes", return_value=rows
        ), mock.patch.object(host, "_logical_cpus", return_value=12), mock.patch.object(host.os, "getppid", return_value=parent):
            return host.quiet_machine_check()

    def test_a_word_driver_that_launched_the_runner_is_a_job(self):
        q = self._check("python3 build/word_verdicts.py --set broken", 90.0)
        self.assertFalse(q["quiet"])
        self.assertTrue(q["heavy_trial_job_seen"])

    def test_the_launching_shell_is_still_not_counted(self):
        self.assertTrue(self._check("zsh -c bash launch-e.sh", 90.0)["quiet"])


class LinuxEvidence(unittest.TestCase):
    """#120 (codex review of #118/#119): limits from the process's own cgroup,
    power only from evidence, containers beyond two marker files, and the
    machine's own name (DMI) and steal counters in the record. Every path is a
    fixture, so this runs on any OS."""

    def setUp(self):
        import shutil
        import tempfile
        from pathlib import Path

        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "cgroup").mkdir()
        (self.tmp / "power_supply").mkdir()
        (self.tmp / "dmi").mkdir()
        patches = [
            mock.patch.object(host.sys, "platform", "linux"),
            mock.patch.object(host, "POWER_SUPPLY", str(self.tmp / "power_supply")),
            mock.patch.object(host, "CGROUP", str(self.tmp / "cgroup")),
            mock.patch.object(host, "CONTAINER_MARKERS", (str(self.tmp / "dockerenv"),)),
            *_no_proc(self.tmp),
            mock.patch.dict(host.os.environ, {}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        for key in ("KUBERNETES_SERVICE_HOST", "container"):
            host.os.environ.pop(key, None)

    def _write(self, rel, text):
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    # 4
    def test_nested_v2_cgroup_limits_are_the_effective_ones(self):
        self._write("proc_self_cgroup", "0::/job\n")
        self._write("cgroup/cpu.max", "max 100000\n")
        self._write("cgroup/memory.max", "max\n")
        self._write("cgroup/job/cpu.max", "200000 100000\n")
        self._write("cgroup/job/memory.max", "2147483648\n")
        self.assertEqual(host._cpu_quota(), 2.0)
        self.assertEqual(host._memory_limit(), 2 * 2**30)

    def test_the_tightest_limit_on_the_path_wins(self):
        self._write("proc_self_cgroup", "0::/a/b\n")
        self._write("cgroup/a/cpu.max", "400000 100000\n")
        self._write("cgroup/a/b/cpu.max", "800000 100000\n")
        self._write("cgroup/a/memory.max", "1073741824\n")
        self._write("cgroup/a/b/memory.max", "max\n")
        self.assertEqual(host._cpu_quota(), 4.0)
        self.assertEqual(host._memory_limit(), 2**30)

    def test_a_namespaced_cgroup_reads_its_own_root(self):
        # the sandbox: /proc/self/cgroup says 0::/ and /sys/fs/cgroup is the container's own
        self._write("proc_self_cgroup", "0::/\n")
        self._write("cgroup/cpu.max", "3200000 100000\n")
        self.assertEqual(host._cpu_quota(), 32.0)

    def test_a_path_not_mounted_here_falls_back_to_the_root(self):
        self._write("proc_self_cgroup", "0::/docker/abc\n")
        self._write("cgroup/cpu.max", "100000 100000\n")
        self.assertEqual(host._cpu_quota(), 1.0)

    def test_v1_controllers_resolve_their_own_paths(self):
        self._write("proc_self_cgroup", "4:cpu,cpuacct:/job\n3:memory:/job\n")
        self._write("cgroup/cpu,cpuacct/job/cpu.cfs_quota_us", "300000\n")
        self._write("cgroup/cpu,cpuacct/job/cpu.cfs_period_us", "100000\n")
        self._write("cgroup/memory/job/memory.limit_in_bytes", "1073741824\n")
        self.assertEqual(host._cpu_quota(), 3.0)
        self.assertEqual(host._memory_limit(), 2**30)

    def test_a_hybrid_hierarchy_reads_the_v1_controllers(self):
        # systemd's unified 0:: line next to v1 controllers is not a v2 machine
        self._write("proc_self_cgroup", "4:cpu,cpuacct:/job\n3:memory:/job\n0::/job\n")
        self._write("cgroup/cpu,cpuacct/job/cpu.cfs_quota_us", "300000\n")
        self._write("cgroup/cpu,cpuacct/job/cpu.cfs_period_us", "100000\n")
        self.assertEqual(host._cpu_quota(), 3.0)

    # 7
    def test_container_evidence_beyond_marker_files(self):
        self.assertFalse(host._in_container({}))
        self.assertTrue(host._in_container({"container": "lxc"}))
        self._write("proc1_environ", "PATH=/bin\0container=podman\0")
        self.assertTrue(host._in_container({}))

    def test_container_runtime_in_pid1_cgroup(self):
        self._write("proc1_cgroup", "0::/kubepods/burstable/pod1/abc\n")
        self.assertTrue(host._in_container({}))

    def test_a_plain_root_cgroup_is_not_a_container(self):
        self._write("proc1_cgroup", "0::/init.scope\n")
        self._write("proc_self_cgroup", "0::/user.slice/session-1.scope\n")
        self.assertFalse(host._in_container({}))

    # 6
    def test_a_container_without_supply_or_vendor_has_unknown_power(self):
        host.os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        self.assertEqual(host._power_source(), "unknown")
        self.assertEqual(host.power_source(), "unknown")

    def test_a_cloud_vendor_is_evidence_of_mains(self):
        host.os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        self._write("dmi/sys_vendor", "Amazon EC2\n")
        self.assertEqual(host._power_source(), "ac")

    def test_a_vm_without_supply_or_cloud_vendor_is_unknown(self):
        # Hyper-V or a desktop hypervisor on a laptop looks like this
        self._write("cpuinfo", "flags\t: fpu vme hypervisor\n")
        self._write("dmi/sys_vendor", "Microsoft Corporation\n")
        self.assertEqual(host._power_source(), "unknown")

    def test_bare_metal_without_supply_is_mains(self):
        self._write("cpuinfo", "flags\t: fpu vme\n")
        self.assertEqual(host._power_source(), "ac")

    def test_a_container_on_a_notebook_chassis_is_unknown(self):
        host.os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        self._write("dmi/chassis_type", "10\n")
        self.assertEqual(host._power_source(), "unknown")

    def test_a_battery_still_wins_in_a_container(self):
        host.os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        self._write("dmi/sys_vendor", "Amazon EC2\n")
        self._write("power_supply/BAT0/type", "Battery\n")
        self.assertEqual(host._power_source(), "battery")

    # the record carries the evidence
    def test_record_names_the_machine(self):
        self._write("dmi/sys_vendor", "Amazon EC2\n")
        self._write("dmi/product_name", "r6a.8xlarge\n")
        self._write("cpuinfo", "processor\t: 0\nflags\t\t: fpu hypervisor\n")
        host.os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        with mock.patch.object(host, "_ram_bytes_probe", return_value=264744833024), mock.patch.object(
            host, "_cpu_model_probe", return_value="AMD EPYC 7R13 Processor"
        ), mock.patch.object(host, "_cores", return_value=(None, 32)), mock.patch.object(
            host, "_os_version", return_value="6.12.113"
        ):
            record = host.host_record()
        self.assertEqual(record["machine_vendor"], "Amazon EC2")
        self.assertEqual(record["machine_product"], "r6a.8xlarge")
        self.assertIs(record["hypervisor"], True)
        self.assertEqual(record["power_source"], "ac")
        self.assertTrue(record["container"])

    # glm-5.3 review (#121)
    def test_undecodable_bytes_do_not_kill_the_probe(self):
        (self.tmp / "proc1_environ").write_bytes(b"PATH=/bin\0FOO=\x80\xff\0")
        self._write("cpuinfo", "flags\t: fpu\n")
        self.assertFalse(host._in_container({}))
        self.assertEqual(host._power_source(), "ac")

    def test_a_server_chassis_is_evidence_of_mains(self):
        host.os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        self._write("cpuinfo", "flags\t: fpu\n")  # bare metal: a guest's chassis is not evidence (#122)
        for chassis in ("17", "23", "28", "29"):
            with self.subTest(chassis=chassis):
                self._write("dmi/chassis_type", chassis + "\n")
                self.assertEqual(host._power(), ("ac", "server chassis"))
        for chassis in ("3", "8", "9", "10", "1"):
            with self.subTest(chassis=chassis):
                self._write("dmi/chassis_type", chassis + "\n")
                self.assertEqual(host._power(), ("unknown", None))

    def test_the_power_evidence_is_named(self):
        self._write("cpuinfo", "flags\t: fpu\n")
        self.assertEqual(host._power(), ("ac", "no battery on bare metal"))
        self._write("power_supply/AC/type", "Mains\n")
        self._write("power_supply/AC/online", "1\n")
        self.assertEqual(host._power(), ("ac", "supply"))
        host.os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        import shutil
        shutil.rmtree(self.tmp / "power_supply")
        (self.tmp / "power_supply").mkdir()
        self._write("dmi/sys_vendor", "Amazon EC2\n")
        self.assertEqual(host._power(), ("ac", "cloud vendor"))

    def test_record_carries_power_evidence_and_chassis(self):
        self._write("dmi/sys_vendor", "Amazon EC2\n")
        self._write("dmi/chassis_type", "1\n")
        self._write("cpuinfo", "flags\t: fpu hypervisor\n")
        host.os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        with mock.patch.object(host, "_ram_bytes_probe", return_value=2**34), mock.patch.object(
            host, "_cpu_model_probe", return_value="AMD EPYC 7R13 Processor"
        ), mock.patch.object(host, "_cores", return_value=(None, 32)), mock.patch.object(
            host, "_os_version", return_value="6.12.113"
        ):
            record = host.host_record()
        self.assertEqual(record["power_evidence"], "cloud vendor")
        self.assertEqual(record["machine_chassis"], "1")

    def test_v1_lines_win_over_a_unified_mount(self):
        self._write("cgroup/cgroup.controllers", "io pids\n")  # cpu is bound to v1, so v2 cannot offer it
        self._write("proc_self_cgroup", "4:cpu,cpuacct:/job\n0::/job\n")
        self._write("cgroup/cpu,cpuacct/job/cpu.cfs_quota_us", "300000\n")
        self._write("cgroup/cpu,cpuacct/job/cpu.cfs_period_us", "100000\n")
        self.assertEqual(host._cpu_quota(), 3.0)

    def test_blank_lines_do_not_turn_v2_into_v1(self):
        # between two entries, where stripping the file's ends cannot remove it (#122)
        self._write("proc_self_cgroup", "1:name=systemd:/x\n\n0::/x\n")
        self._write("cgroup/x/cpu.max", "200000 100000\n")
        self.assertEqual(host._cpu_quota(), 2.0)

    def test_a_named_v1_hierarchy_does_not_hide_the_unified_line(self):
        self._write("proc_self_cgroup", "1:name=systemd:/x\n0::/x\n")
        self._write("cgroup/x/cpu.max", "100000 100000\n")
        self.assertEqual(host._cpu_quota(), 1.0)

    def test_no_flags_line_means_the_hypervisor_is_unknown(self):
        self._write("cpuinfo", "processor\t: 0\nFeatures\t: fp asimd evtstrm\n")  # aarch64
        self.assertIsNone(host._hypervisor())
        self.assertEqual(host._power_source(), "unknown")  # not proof of bare metal
        self._write("cpuinfo", "flags\t: fpu vme\n")
        self.assertIs(host._hypervisor(), False)
        (self.tmp / "cpuinfo").unlink()
        self.assertIsNone(host._hypervisor())

    # codex review of #121 (#122)
    def _mounts(self, *lines):
        self._write("proc_self_mountinfo", "".join(line + "\n" for line in lines))

    def test_an_offline_supply_is_not_ac(self):
        self._write("cpuinfo", "flags\t: fpu\n")
        self._write("power_supply/dock/type", "Mains\n")
        self._write("power_supply/dock/online", "0\n")
        # bare metal sees its own battery: none visible is mains, whatever a dock says (#123)
        self.assertEqual(host._power(), ("ac", "no battery on bare metal"))
        host.os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        self.assertEqual(host._power(), ("unknown", None))
        self._write("dmi/sys_vendor", "Amazon EC2\n")
        self.assertEqual(host._power(), ("ac", "cloud vendor"))

    def test_a_guests_chassis_is_not_evidence(self):
        self._write("cpuinfo", "flags\t: fpu hypervisor\n")
        self._write("dmi/chassis_type", "23\n")
        self.assertEqual(host._power(), ("unknown", None))
        self._write("cpuinfo", "processor\t: 0\nFeatures\t: fp asimd\n")  # no flags: not known to be bare metal
        self.assertEqual(host._power(), ("unknown", None))

    def test_a_server_chassis_counts_for_a_container_on_bare_metal(self):
        host.os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        self._write("cpuinfo", "flags\t: fpu vme\n")
        self._write("dmi/chassis_type", "23\n")
        self.assertEqual(host._power(), ("ac", "server chassis"))

    def test_a_v1_subtree_mount_maps_through_its_root(self):
        mnt = self.tmp / "cgroup" / "cpu,cpuacct"
        self._mounts("30 25 0:26 /tenant %s rw,nosuid - cgroup cgroup rw,cpu,cpuacct" % mnt)
        self._write("proc_self_cgroup", "4:cpu,cpuacct:/tenant/job\n0::/job\n")
        self._write("cgroup/cpu,cpuacct/job/cpu.cfs_quota_us", "100000\n")
        self._write("cgroup/cpu,cpuacct/job/cpu.cfs_period_us", "100000\n")
        self._write("cgroup/cpu,cpuacct/tenant/job/cpu.cfs_quota_us", "800000\n")  # another group's
        self._write("cgroup/cpu,cpuacct/tenant/job/cpu.cfs_period_us", "100000\n")
        self.assertEqual(host._cpu_quota(), 1.0)

    def test_mount_names_come_from_mountinfo(self):
        mnt = self.tmp / "cgroup" / "cpuacct,cpu"
        self._mounts("30 25 0:26 / %s rw - cgroup cgroup rw,cpuacct,cpu" % mnt)
        self._write("proc_self_cgroup", "4:cpu,cpuacct:/job\n0::/job\n")
        self._write("cgroup/cpuacct,cpu/job/cpu.cfs_quota_us", "100000\n")
        self._write("cgroup/cpuacct,cpu/job/cpu.cfs_period_us", "100000\n")
        self.assertEqual(host._cpu_quota(), 1.0)

    def test_a_unified_mount_elsewhere(self):
        uni = self.tmp / "cgroup" / "unified"
        self._mounts("31 25 0:27 / %s rw - cgroup2 cgroup2 rw" % uni,
                     "32 25 0:28 / %s rw - cgroup cgroup rw,name=systemd" % (self.tmp / "cgroup" / "systemd"))
        self._write("proc_self_cgroup", "1:name=systemd:/x\n0::/x\n")
        self._write("cgroup/unified/x/cpu.max", "100000 100000\n")
        self.assertEqual(host._cpu_quota(), 1.0)

    def test_the_sandbox_mountinfo(self):
        # 2026-11-09 probe: one cgroup2 mount at the namespace root
        self._mounts("4037 3983 0:27 / %s ro,nosuid,nodev,noexec,relatime - cgroup2 cgroup rw,seclabel" % (self.tmp / "cgroup"))
        self._write("proc_self_cgroup", "0::/\n")
        self._write("cgroup/cpu.max", "3200000 100000\n")
        self._write("cgroup/memory.max", "274999996416\n")
        self.assertEqual(host._cpu_quota(), 32.0)
        self.assertEqual(host._memory_limit(), 274999996416)

    # MiniMax review of #122 (#123)
    def test_a_mains_supply_without_an_online_file_on_bare_metal_is_ac(self):
        self._write("cpuinfo", "flags\t: fpu\n")
        self._write("power_supply/AC/type", "Mains\n")
        self.assertEqual(host._power(), ("ac", "no battery on bare metal"))

    def test_a_discharging_battery_is_battery_even_with_an_adapter_online(self):
        self._write("power_supply/AC/type", "Mains\n")
        self._write("power_supply/AC/online", "1\n")
        self._write("power_supply/BAT0/type", "Battery\n")
        self._write("power_supply/BAT0/status", "Discharging\n")
        self.assertEqual(host._power(), ("battery", None))
        self._write("power_supply/BAT0/status", "Charging\n")
        self.assertEqual(host._power(), ("ac", "supply"))

    def test_aarch64_with_a_server_chassis_stays_unknown(self):
        # declined in #123: without x86 flags a guest and bare metal look alike here
        self._write("cpuinfo", "processor\t: 0\nFeatures\t: fp asimd\n")
        self._write("dmi/chassis_type", "23\n")
        self.assertEqual(host._power(), ("unknown", None))

    def test_a_cloud_container_does_not_read_cpuinfo(self):
        host.os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        self._write("dmi/sys_vendor", "Amazon EC2\n")
        with mock.patch.object(host, "_hypervisor", side_effect=AssertionError("cpuinfo read before a sample")):
            self.assertEqual(host._power(), ("ac", "cloud vendor"))

    def test_the_serving_mount_wins_not_the_first(self):
        other, main = self.tmp / "cgroup" / "other", self.tmp / "cgroup"
        self._mounts("31 25 0:27 /other %s ro - cgroup2 cgroup rw" % other,
                     "32 25 0:28 / %s ro - cgroup2 cgroup rw" % main)
        self._write("proc_self_cgroup", "0::/job\n")
        self._write("cgroup/job/cpu.max", "200000 100000\n")
        self._write("cgroup/job/memory.max", "2147483648\n")
        self.assertEqual(host._cpu_quota(), 2.0)
        self.assertEqual(host._memory_limit(), 2**31)

    def test_a_v1_hierarchy_mounted_twice(self):
        self._mounts("31 25 0:26 /other %s ro - cgroup cgroup rw,cpu,cpuacct" % (self.tmp / "cgroup" / "other"),
                     "32 25 0:27 / %s rw - cgroup cgroup rw,cpu,cpuacct" % (self.tmp / "cgroup" / "cpu,cpuacct"))
        self._write("proc_self_cgroup", "4:cpu,cpuacct:/job\n")
        self._write("cgroup/cpu,cpuacct/job/cpu.cfs_quota_us", "200000\n")
        self._write("cgroup/cpu,cpuacct/job/cpu.cfs_period_us", "100000\n")
        self.assertEqual(host._cpu_quota(), 2.0)

    def test_a_membership_equal_to_the_mount_root(self):
        mnt = self.tmp / "cgroup" / "cpu,cpuacct"
        self._mounts("30 25 0:26 /tenant %s rw - cgroup cgroup rw,cpu,cpuacct" % mnt)
        self._write("proc_self_cgroup", "4:cpu,cpuacct:/tenant\n")
        self._write("cgroup/cpu,cpuacct/cpu.cfs_quota_us", "300000\n")
        self._write("cgroup/cpu,cpuacct/cpu.cfs_period_us", "100000\n")
        self.assertEqual(host._cpu_quota(), 3.0)

    def test_dot_dot_never_leaves_the_mount(self):
        self.assertEqual(host._walk("/a/b", "/c"), ["/c"])
        self._mounts("4037 3983 0:27 / %s ro - cgroup2 cgroup rw" % (self.tmp / "cgroup"))
        self._write("proc_self_cgroup", "0::/../../etc\n")
        self.assertEqual(host._cgroup_dirs("cpu"), [str(self.tmp / "cgroup")])

    def test_a_malformed_escape_does_not_kill_the_probe(self):
        self.assertEqual(host._unescape("/a\\777b"), "/a\\777b")
        self.assertEqual(host._unescape("/a\\040b"), "/a b")

    def test_cpu_ticks(self):
        self._write("proc_stat", "cpu  65967 15 45687 1725841 16505 0 2300 61 0 0\ncpu0 1 2 3 4 5 6 7 8 0 0\n")
        self.assertEqual(host._cpu_ticks(), {"steal": 61, "total": 65967 + 15 + 45687 + 1725841 + 16505 + 0 + 2300 + 61})
        (self.tmp / "proc_stat").write_text("garbage\n")
        self.assertIsNone(host._cpu_ticks())

    def test_quiet_check_records_the_ticks(self):
        self._write("proc_stat", "cpu  1 0 1 10 0 0 0 3 0 0\n")
        with mock.patch.object(host, "_load_average", return_value=(0.1, 0.1, 0.1)), mock.patch.object(
            host, "_processes", return_value=[(host.os.getpid(), 1, 0.0, "python3")]
        ), mock.patch.object(host, "_logical_cpus", return_value=32):
            q = host.quiet_machine_check()
        self.assertEqual(q["cpu_ticks"], {"steal": 3, "total": 15})


@unittest.skipUnless(sys.platform == "darwin", "macOS probe")
class MacHasNoLinuxEvidence(unittest.TestCase):
    def test_mac_record_and_check(self):
        record = host.host_record()
        self.assertIsNone(record["machine_vendor"])
        self.assertIsNone(record["machine_product"])
        self.assertIsNone(record["hypervisor"])
        self.assertIsNone(host._cpu_ticks())


if __name__ == "__main__":
    unittest.main()


def test_a_defunct_process_is_not_a_running_job(monkeypatch):
    """A zombie holds no CPU; ps reports its lifetime average (campaign 2, 2026-11-11)."""
    from perf.runner import host as host_module

    listing = "\n".join([
        "    1     0  0.0 /tmp/init-process",
        "  812     1 33.8 [chrome] <defunct>",
        "  900     1  0.1 sshd",
    ])
    monkeypatch.setattr(host_module, "_run", lambda command: listing)
    rows = host_module._processes()
    assert [row[0] for row in rows] == [1, 900]
