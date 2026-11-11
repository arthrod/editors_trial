"""Host record and quiet-machine check (editors_trial#101).

The host record is evidence. Every runner used to fall back to
a hardcoded 512 MiB when ``/proc/meminfo`` was missing, and to record
``platform.processor()``, which is ``"arm"`` on Apple silicon. A value this
module cannot read raises :class:`HostProbeError`; it is never invented.

``quiet_machine_check`` is AGENTS.md §3 made executable: the load average,
the busiest processes, and whether a trial script is driving Word or a
``neurotic_docx_bench`` job is running, with the verdict and the thresholds
that produced it. The runner's own process tree (its descendants and its
ancestors, by PID, never by name) is not held against it.
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
# Another Word *job* (AGENTS.md section 3): a trial script driving Word, an
# osascript addressing it, or the bench batch. Word merely left open is not a
# job; a busy Word fails the per-process CPU rule like anything else.
_HEAVY_JOBS = re.compile(
    r"neurotic_docx_bench|build/word_\w+\.py|verify_publication|verify_deliverables|osascript.*Microsoft Word", re.I
)


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


POWER_SUPPLY = "/sys/class/power_supply"
CGROUP = "/sys/fs/cgroup"
CONTAINER_MARKERS = ("/.dockerenv", "/run/.containerenv")
PROC_SELF_CGROUP = "/proc/self/cgroup"
PROC_SELF_MOUNTINFO = "/proc/self/mountinfo"
PROC1_CGROUP = "/proc/1/cgroup"
PROC1_ENVIRON = "/proc/1/environ"
DMI = "/sys/class/dmi/id"
CPUINFO = "/proc/cpuinfo"
PROC_STAT = "/proc/stat"
# DMI vendors that only rent servers: their machines have no battery. Not
# "Microsoft Corporation" or "QEMU": Hyper-V and desktop hypervisors on a laptop
# report those too (#120).
CLOUD_VENDORS = ("Amazon EC2", "Google", "DigitalOcean", "Hetzner", "Scaleway", "Alibaba Cloud")
# SMBIOS chassis types that only servers have: main server chassis, rack
# mount, blade, blade enclosure (#121). A vendor name (Dell, HPE) is not one:
# it also sells laptops.
SERVER_CHASSIS = ("17", "23", "28", "29")
_RUNTIME = re.compile(r"(docker|kubepods|containerd|libpod|lxc|crio)")


def _read(path: str) -> str | None:
    try:
        # proc files hold arbitrary bytes (an environment): never let one kill the probe (#121)
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read().strip()
    except OSError:
        return None


def _power_supplies() -> list[tuple[str, str | None, str | None, str | None]] | None:
    """``(name, type, online, status)`` for each Linux power supply; None if unreadable."""
    try:
        names = sorted(os.listdir(POWER_SUPPLY))
    except OSError:
        return None
    return [(n, *(_read(os.path.join(POWER_SUPPLY, n, f)) for f in ("type", "online", "status"))) for n in names]


def _dmi(name: str) -> str | None:
    return _read(os.path.join(DMI, name)) or None


def _hypervisor() -> bool | None:
    """The x86 CPU flags say whether this kernel runs under a hypervisor. With
    no flags line (aarch64, or no cpuinfo) nobody said: None, not False (#121)."""
    flags = [line for line in (_read(CPUINFO) or "").splitlines() if line.startswith("flags")]
    if not flags:
        return None
    return any("hypervisor" in line.split(":", 1)[-1].split() for line in flags)


def _cpu_ticks() -> dict | None:
    """``/proc/stat``'s steal and total CPU ticks so far (guest time is already
    inside user time); None off Linux or when unreadable (#120)."""
    if sys.platform == "darwin":
        return None
    first = (_read(PROC_STAT) or "").splitlines()[:1]
    fields = first[0].split() if first else []
    if len(fields) < 9 or fields[0] != "cpu" or not all(f.isdigit() for f in fields[1:9]):
        return None
    ticks = [int(f) for f in fields[1:9]]
    return {"steal": ticks[7], "total": sum(ticks)}


def _power() -> tuple[str | None, str | None]:
    """``(power, evidence)``: power is ``ac``, ``battery``, ``unknown`` (readable,
    but nothing proves either) or None when the probe itself failed; evidence
    names what proved ``ac`` (#121)."""
    if sys.platform == "darwin":
        out = _run(["pmset", "-g", "batt"])
        if not out:
            return None, None
        if "AC Power" in out:
            return "ac", "supply"
        if "Battery Power" in out:
            return "battery", None
        return None, None
    supplies = _power_supplies()
    if supplies is None:
        return None, None
    if any(kind is None for _, kind, _, _ in supplies):
        return None, None  # a supply we cannot type could be a battery: unknown, not mains (#119)
    if any(kind == "Battery" and status == "Discharging" for _, kind, _, status in supplies):
        return "battery", None  # an adapter that cannot keep up does not make it mains (#123)
    if any(kind in ("Mains", "USB") and online == "1" for _, kind, online, _ in supplies):
        return "ac", "supply"  # only an online supply is evidence (#122)
    if any(kind == "Battery" for _, kind, _, _ in supplies):
        return "battery", None
    # No online supply and no battery visible. A container or a guest sees
    # nothing of its host's supplies: only a server-only cloud vendor, or a
    # server chassis on known bare metal (a guest's firmware can say anything),
    # is evidence of mains (#120, #121, #122). The vendor is read first, so a
    # cloud container does not read /proc/cpuinfo before every sample (#123).
    cloud = _dmi("sys_vendor") in CLOUD_VENDORS
    if _in_container(os.environ):
        if cloud:
            return "ac", "cloud vendor"
        if _dmi("chassis_type") in SERVER_CHASSIS and _hypervisor() is False:
            return "ac", "server chassis"
        return "unknown", None
    if _hypervisor() is not False:  # a guest, or nobody said (aarch64): not proof of bare metal
        return ("ac", "cloud vendor") if cloud else ("unknown", None)
    # Bare metal shows its own battery: none visible means mains, whatever an
    # offline dock or a supply without an online file says (#123).
    return "ac", "no battery on bare metal"


def _power_source() -> str | None:
    return _power()[0]


def _unescape(field: str) -> str:
    """mountinfo escapes space, tab, newline and backslash as octal (\\040). An
    escape above one byte is not the kernel's: it stays as written (#123)."""
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)) if int(m.group(1), 8) < 256 else m.group(0), field)


def _cgroup_mounts() -> list[tuple[str, str, str, set[str]]] | None:
    """``(fstype, root, mountpoint, super options)`` for every cgroup mount in
    ``/proc/self/mountinfo``; None when unreadable (#122)."""
    text = _read(PROC_SELF_MOUNTINFO)
    if text is None:
        return None
    mounts = []
    for line in text.splitlines():
        left, sep, right = line.partition(" - ")
        fields, tail = left.split(), right.split()
        if not sep or len(fields) < 5 or len(tail) < 3 or tail[0] not in ("cgroup", "cgroup2"):
            continue
        mounts.append((tail[0], _unescape(fields[3]), _unescape(fields[4]), set(tail[2].split(","))))
    return mounts


def _walk(leaf: str, top: str) -> list[str]:
    """``leaf`` and its ancestors up to ``top``, those that exist; just ``top``
    when the leaf is not visible here or is not under ``top`` (#123)."""
    rel = os.path.relpath(leaf, top)
    parts = [] if rel == "." else rel.split(os.sep)
    if ".." in parts:
        return [top]
    dirs = [os.path.join(top, *parts[:k]) for k in range(len(parts), -1, -1)]
    found = [d for d in dirs if os.path.isdir(d)]
    return found if found and found[0] == dirs[0] else [top]


def _cgroup_dirs(controller: str) -> list[str]:
    """The cgroup directories this process is limited by, leaf first, for one
    controller (``cpu`` or ``memory``): its membership from ``/proc/self/cgroup``
    (a v1 line for the controller wins, else the ``0::`` line), mapped through
    the mount that serves it in ``/proc/self/mountinfo`` (its root and
    mountpoint, #122). Without mountinfo the mount is guessed at ``CGROUP``."""
    entries = [f for f in (line.split(":", 2) for line in (_read(PROC_SELF_CGROUP) or "").splitlines()) if len(f) == 3]
    v1 = next(((c, path) for _, c, path in entries if controller in c.split(",")), None)
    unified = next((path for hid, c, path in entries if hid == "0" and c == ""), None)
    path = v1[1] if v1 else unified
    if path is not None:  # the kernel never writes . or ..; a path that does is not followed (#123)
        path = "/" + "/".join(x for x in path.split("/") if x not in ("", ".", ".."))
    mounts = _cgroup_mounts()
    if mounts:
        kind = [m for m in mounts if m[0] == "cgroup" and controller in m[3]] if v1 else \
            [m for m in mounts if m[0] == "cgroup2"]

        def serves(m) -> bool:
            root = m[1].rstrip("/") or "/"
            return root == "/" or path == root or path.startswith(root + "/")

        # the mount that serves this membership: the longest root that prefixes it (#123)
        serving = [m for m in kind if path is not None and serves(m)]
        mount = max(serving, key=lambda m: len(m[1].rstrip("/"))) if serving else (kind[0] if kind else None)
        if mount and path is not None:
            _, root, mountpoint, _ = mount
            root = root.rstrip("/") or "/"
            if root == "/" or path == root or path.startswith(root + "/"):
                rel = path if root == "/" else path[len(root):]
                return _walk(os.path.join(mountpoint, *[x for x in rel.split("/") if x]), mountpoint)
            return [mountpoint]  # membership outside this mount's view: the mount is what we see
    # no mountinfo: guess the conventional layout under CGROUP
    if v1:
        controllers = v1[0]
        base = next((d for d in (os.path.join(CGROUP, controllers), os.path.join(CGROUP, controller))
                     if os.path.isdir(d)), os.path.join(CGROUP, controller))
    elif unified is not None:
        base = CGROUP
    else:
        return [CGROUP]  # nothing to resolve: the mount is all there is
    return _walk(os.path.join(base, *[x for x in path.split("/") if x]), base)


def _v2_quota(d: str) -> float | None:
    v2 = _read(os.path.join(d, "cpu.max"))
    if not v2:
        return None
    quota, _, period = v2.partition(" ")
    if quota != "max" and quota.isdigit() and period.isdigit() and int(period):
        return int(quota) / int(period)
    return None


def _v1_quota(d: str) -> float | None:
    quota = _read(os.path.join(d, "cpu.cfs_quota_us"))
    period = _read(os.path.join(d, "cpu.cfs_period_us"))
    if quota and period and quota.lstrip("-").isdigit() and int(quota) > 0 and period.isdigit() and int(period):
        return int(quota) / int(period)
    return None


def _cpu_quota() -> float | None:
    """CPUs this process may use: the tightest cgroup quota on its path (v2
    ``cpu.max``, else v1); None if nothing on the path limits it."""
    quotas = [q for d in _cgroup_dirs("cpu") for q in (_v2_quota(d), _v1_quota(d)) if q is not None]
    return min(quotas) if quotas else None


def _memory_limit() -> int | None:
    """Bytes this process may use: the tightest cgroup limit on its path; None if unlimited."""
    limits = []
    for d in _cgroup_dirs("memory"):
        v2 = _read(os.path.join(d, "memory.max"))
        if v2 and v2.isdigit():
            limits.append(int(v2))
        v1 = _read(os.path.join(d, "memory.limit_in_bytes"))
        # cgroup v1 reports "unlimited" as a page-rounded 2**63.
        if v1 and v1.isdigit() and int(v1) < 2**62:
            limits.append(int(v1))
    return min(limits) if limits else None


def _in_container(environ) -> bool:
    """Positive evidence only: an orchestrator's variable, a runtime's marker
    file, ``container=`` in this or PID 1's environment, or a runtime's name in
    PID 1's cgroup (#120)."""
    if "KUBERNETES_SERVICE_HOST" in environ or environ.get("container"):
        return True
    if any(os.path.exists(m) for m in CONTAINER_MARKERS):
        return True
    if any(v.startswith("container=") for v in (_read(PROC1_ENVIRON) or "").split("\0")):
        return True
    return bool(_RUNTIME.search(_read(PROC1_CGROUP) or ""))


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
    power, evidence = _power()
    if not power:
        raise HostProbeError("power source unreadable")
    linux = sys.platform != "darwin"
    return {
        "os": sys.platform,
        "os_version": os_version,
        "arch": platform.machine(),
        "cpu_model": cpu,
        "cpu_cores_physical": physical,
        "cpu_cores_logical": logical,
        "ram_bytes": ram,
        "power_source": power,
        "power_evidence": evidence,
        "power_supplies": None if sys.platform == "darwin" else [n for n, *_ in (_power_supplies() or [])],
        "cpu_quota": None if sys.platform == "darwin" else _cpu_quota(),
        "memory_limit_bytes": None if sys.platform == "darwin" else _memory_limit(),
        "container": linux and _in_container(os.environ),
        "machine_vendor": _dmi("sys_vendor") if linux else None,
        "machine_product": _dmi("product_name") if linux else None,
        "hypervisor": _hypervisor() if linux else None,
        "machine_chassis": _dmi("chassis_type") if linux else None,
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
        if len(parts) > 3 and parts[3].rstrip().endswith("<defunct>"):
            # A zombie runs nothing; ps still reports its lifetime CPU average.
            continue
        try:
            rows.append((int(parts[0]), int(parts[1]), float(parts[2]), parts[3].strip() if len(parts) > 3 else ""))
        except ValueError:
            continue
    return rows or None


def _own_tree(rows: list[tuple[int, int, float, str]]) -> set[int]:
    """This process, every descendant of it (the runner, its lanes, ``ps``) and
    its ancestors up to (not including) PID 1: whatever launched the runner is
    not another session's job."""
    children: dict[int, list[int]] = {}
    parent: dict[int, int] = {}
    for pid, ppid, _, _ in rows:
        children.setdefault(ppid, []).append(pid)
        parent[pid] = ppid
    own, todo = set(), [os.getpid()]
    while todo:
        pid = todo.pop()
        if pid in own:
            continue
        own.add(pid)
        todo.extend(children.get(pid, ()))
    return own | _ancestors(rows)


# A shell's command line is text it was handed (a script that may mention a
# trial job, as the live check of 2026-11-09 showed); the job itself would be
# a separate process.
_SHELL = re.compile(r"^\S*\b(zsh|bash|sh|dash|fish)\b(\s|$)")


def _ancestors(rows: list[tuple[int, int, float, str]]) -> set[int]:
    """Whatever launched this process, up to (not including) PID 1."""
    parent = {pid: ppid for pid, ppid, _, _ in rows}
    found, pid = set(), os.getppid()
    while pid > 1 and pid not in found and pid != os.getpid():
        found.add(pid)
        pid = parent.get(pid, 1)
    return found


def quiet_machine_check() -> dict:
    """AGENTS.md §3: is the machine quiet enough to time an editor?

    Fails closed: no process list means not quiet. Only this process's own
    tree is excluded (by PID, never by name, so another session's runner
    counts), and a Word driver or bench job counts however idle it is.
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
    ancestors = _ancestors(rows)
    # Ancestors (the shell that launched the runner) are spared the CPU rule,
    # not the job rule: a Word driver that started the runner is a Word job (#119).
    for pid, _, _, command in rows:
        if pid in ancestors and _HEAVY_JOBS.search(command) and not _SHELL.match(command):
            heavy = True
            reasons.append("trial job running (launched this runner): %s" % command[:120])
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
        "cpu_ticks": _cpu_ticks(),  # steal between two checks is what a hypervisor withheld (#120)
        "quiet": not reasons,
        "reasons": reasons,
    }
