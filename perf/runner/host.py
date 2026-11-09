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


def power_source() -> str:
    """``ac``, ``battery`` or ``unknown``: cheap enough to read before every sample."""
    return _power_source() or "unknown"


def _processes() -> list[tuple[int, int, float, str]] | None:
    """``(pid, ppid, percent CPU, command)`` for every process; None if ``ps`` fails."""
    out = _run(["ps", "-Ao", "pid=,ppid=,pcpu=,command="])
    if not out:
        return None
    rows = []
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 3:
            continue
        try:
            rows.append((int(parts[0]), int(parts[1]), float(parts[2]), parts[3].strip() if len(parts) > 3 else ""))
        except ValueError:
            continue
    return rows or None


def _own_tree(rows: list[tuple[int, int, float, str]]) -> set[int]:
    """This process and every descendant of it (the runner, its lanes, ``ps``)."""
    children: dict[int, list[int]] = {}
    for pid, ppid, _, _ in rows:
        children.setdefault(ppid, []).append(pid)
    own, todo = set(), [os.getpid()]
    while todo:
        pid = todo.pop()
        if pid in own:
            continue
        own.add(pid)
        todo.extend(children.get(pid, ()))
    return own


def quiet_machine_check() -> dict:
    """AGENTS.md §3: is the machine quiet enough to time an editor?

    Fails closed: no process list means not quiet. Only this process's own
    tree is excluded (by PID, never by name, so another session's runner
    counts), and a Word or bench job counts however idle it is.
    """
    load = _load_average()
    ncpu = _logical_cpus()
    rows = _processes()
    load_limit = round(ncpu * LOAD_FRACTION, 2)
    reasons: list[str] = []
    heavy = False
    if load[0] > load_limit:
        reasons.append("1-minute load average %.2f exceeds %.2f (a third of %d CPUs)" % (load[0], load_limit, ncpu))
    if rows is None:
        reasons.append("process list unavailable (ps failed): cannot tell what else runs")
        rows = []
    own = _own_tree(rows)
    foreign = sorted((r for r in rows if r[0] not in own), key=lambda r: -r[2])
    for _, _, pct, command in foreign:
        if _HEAVY_JOBS.search(command):
            heavy = True
            reasons.append("trial job running: %s" % command[:120])
        elif pct > PROCESS_CPU_PERCENT:
            reasons.append("%.1f%% CPU: %s" % (pct, command[:120]))
    top = [(pct, command) for _, _, pct, command in foreign[:12]]
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
