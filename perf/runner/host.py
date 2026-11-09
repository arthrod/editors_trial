"""Host record and quiet-machine check (editors_trial#101).

The host record is evidence. Every runner used to fall back to
a hardcoded 512 MiB when ``/proc/meminfo`` was missing, and to record
``platform.processor()``, which is ``"arm"`` on Apple silicon. A value this
module cannot read raises :class:`HostProbeError`; it is never invented.

``quiet_machine_check`` is AGENTS.md §3 made executable: the load average,
the busiest processes, and whether a Word or ``neurotic_docx_bench`` job is
running, with the verdict and the thresholds that produced it. The runner's
own process tree (anything under ``perf/runner/``) is not held against it.
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import sys


class HostProbeError(RuntimeError):
    """A host fact could not be read; the run must not invent it."""


# Thresholds for "quiet". A 1-minute load average above a third of the
# logical CPUs, or any one foreign process above 25% of a core, is not quiet.
LOAD_FRACTION = 1.0 / 3.0
PROCESS_CPU_PERCENT = 25.0
_HEAVY_JOBS = re.compile(r"Microsoft Word|neurotic_docx_bench", re.I)
_OWN_TREE = re.compile(r"perf/runner/")


def _run(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def _sysctl(name: str) -> str | None:
    return _run(["sysctl", "-n", name])


def _ram_bytes_probe() -> int | None:
    if sys.platform == "darwin":
        value = _sysctl("hw.memsize")
        return int(value) if value and value.isdigit() else None
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        return None
    return None


def _cpu_model_probe() -> str | None:
    if sys.platform == "darwin":
        return _sysctl("machdep.cpu.brand_string")
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            for line in handle:
                if line.lower().startswith(("model name", "hardware", "cpu model")):
                    return line.split(":", 1)[1].strip() or None
    except OSError:
        return None
    return None


def _cores() -> tuple[int | None, int | None]:
    if sys.platform == "darwin":
        phys, logical = _sysctl("hw.physicalcpu"), _sysctl("hw.logicalcpu")
        return (int(phys) if phys else None, int(logical) if logical else None)
    return (None, os.cpu_count())


def _logical_cpus() -> int:
    _, logical = _cores()
    if not logical:
        raise HostProbeError("logical CPU count unreadable")
    return logical


def _os_version() -> str | None:
    if sys.platform == "darwin":
        return _run(["sw_vers", "-productVersion"])
    return platform.release() or None


def _power_source() -> str | None:
    if sys.platform == "darwin":
        out = _run(["pmset", "-g", "batt"])
        if not out:
            return None
        if "AC Power" in out:
            return "ac"
        if "Battery Power" in out:
            return "battery"
        return None
    supply = "/sys/class/power_supply"
    try:
        for name in os.listdir(supply):
            with open(os.path.join(supply, name, "online"), encoding="utf-8") as handle:
                if handle.read().strip() == "1":
                    return "ac"
        return "battery"
    except OSError:
        return None


def host_record() -> dict:
    """Facts about the measuring host, read now. Raises if one is unreadable."""
    ram = _ram_bytes_probe()
    if not ram:
        raise HostProbeError("RAM size unreadable (no hw.memsize / MemTotal)")
    cpu = _cpu_model_probe()
    if not cpu:
        raise HostProbeError("CPU model unreadable (no machdep.cpu.brand_string / cpuinfo)")
    physical, logical = _cores()
    if not logical:
        raise HostProbeError("logical CPU count unreadable")
    os_version = _os_version()
    if not os_version:
        raise HostProbeError("OS version unreadable")
    power = _power_source()
    if not power:
        raise HostProbeError("power source unreadable")
    return {
        "os": sys.platform,
        "os_version": os_version,
        "arch": platform.machine(),
        "cpu_model": cpu,
        "cpu_cores_physical": physical,
        "cpu_cores_logical": logical,
        "ram_bytes": ram,
        "power_source": power,
        "python": platform.python_version(),
    }


def _load_average() -> tuple[float, float, float]:
    return os.getloadavg()


def _top_processes(limit: int = 12) -> list[tuple[float, str]]:
    """``(percent CPU, command)`` for the busiest processes, highest first."""
    out = _run(["ps", "-Ao", "pcpu=,command=", "-r"]) or ""
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        pct, _, command = line.partition(" ")
        try:
            rows.append((float(pct), command.strip()))
        except ValueError:
            continue
        if len(rows) >= limit:
            break
    return rows


def quiet_machine_check() -> dict:
    """AGENTS.md §3: is the machine quiet enough to time an editor?"""
    load = _load_average()
    ncpu = _logical_cpus()
    top = _top_processes()
    load_limit = round(ncpu * LOAD_FRACTION, 2)
    reasons: list[str] = []
    heavy = False
    if load[0] > load_limit:
        reasons.append("1-minute load average %.2f exceeds %.2f (a third of %d CPUs)" % (load[0], load_limit, ncpu))
    for pct, command in top:
        if _OWN_TREE.search(command):
            continue
        if _HEAVY_JOBS.search(command):
            heavy = True
            reasons.append("trial job running: %s" % command[:120])
        elif pct > PROCESS_CPU_PERCENT:
            reasons.append("%.1f%% CPU: %s" % (pct, command[:120]))
    return {
        "load_average": [round(v, 2) for v in load],
        "logical_cpus": ncpu,
        "top_cpu": ["%.1f %s" % (pct, command[:160]) for pct, command in top],
        "thresholds": {
            "load1_max": load_limit,
            "foreign_process_cpu_percent_max": PROCESS_CPU_PERCENT,
            "heavy_jobs": _HEAVY_JOBS.pattern,
        },
        "heavy_trial_job_seen": heavy,
        "quiet": not reasons,
        "reasons": reasons,
    }
