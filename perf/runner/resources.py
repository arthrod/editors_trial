"""Shared resource sampler for the browser lanes.

``ResourceSampler(run, page, cdp)`` reads one Chromium tree, the one whose
root pid the run launched, and records RAM, CPU, disk and network with the
unit in the field name. Linux-only counters stay
``not_available_on_platform`` on other hosts. They are never stored as zero.

The dev/static server is not the editor. Its pid is recorded and excluded.
"""

from __future__ import annotations

import os
from pathlib import Path
import platform
import subprocess
import time

from perf.runner.memory_tree import tree_pids

NOT_AVAILABLE = "not_available_on_platform"

PAGE_SNAPSHOT_JS = """async () => {
  const est = (navigator.storage && navigator.storage.estimate)
    ? await navigator.storage.estimate()
    : {usage: 0, usageDetails: {}};
  const details = est.usageDetails || {};
  let localStorageBytes = 0;
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      const value = localStorage.getItem(key) || "";
      localStorageBytes += (String(key).length + String(value).length) * 2;
    }
  } catch (err) {
    localStorageBytes = null;
  }
  const tasks = window.__resourceLongTasks || {count: 0, sum: 0};
  return {
    usage: est.usage || 0,
    usageDetails: {
      indexedDB: details.indexedDB || 0,
      caches: details.caches || details.cacheStorage || 0,
      serviceWorkerRegistrations: details.serviceWorkerRegistrations || details.serviceWorker || 0,
    },
    localStorageBytes,
    longtaskCount: tasks.count || 0,
    longtaskSumMs: tasks.sum || 0,
  };
}"""

STATIC_SERVER_NOTE = (
    "The dev/static server is not the editor. "
    "It serves the page; the editor is the Chromium tree rooted at the browser process this run launched."
)

# What each field is, and where the number comes from. Units are in the name.
FIELD_SOURCES = {
    "js_heap_used_bytes": "CDP Performance.getMetrics JSHeapUsedSize, bytes",
    "js_heap_total_bytes": "CDP Performance.getMetrics JSHeapTotalSize, bytes",
    "js_heap_runtime_used_bytes": "CDP Runtime.getHeapUsage usedSize, bytes",
    "js_heap_runtime_total_bytes": "CDP Runtime.getHeapUsage totalSize, bytes",
    "task_duration_ms": "CDP Performance.getMetrics TaskDuration, seconds converted to ms",
    "script_duration_ms": "CDP Performance.getMetrics ScriptDuration, seconds converted to ms",
    "layout_duration_ms": "CDP Performance.getMetrics LayoutDuration, seconds converted to ms",
    "recalc_style_duration_ms": "CDP Performance.getMetrics RecalcStyleDuration, seconds converted to ms",
    "longtask_count": "PerformanceObserver longtask count, cumulative",
    "longtask_sum_ms": "PerformanceObserver longtask duration sum, ms",
    "rss_bytes": "per-process resident set, Linux /proc/<pid>/status VmRSS or macOS ps rss, bytes",
    "pss_bytes": "Linux /proc/<pid>/smaps_rollup Pss, bytes; not_available_on_platform elsewhere",
    "uss_bytes": "Linux smaps_rollup Private_Clean + Private_Dirty, bytes; not_available_on_platform elsewhere",
    "cpu_ms": "cumulative user+system CPU, Linux /proc/<pid>/stat utime+stime or macOS ps time, ms",
    "cpu_percent": "CPU ms over wall ms since the previous sample, percent",
    "renderer_cpu_ms": "delta of renderer cpu_ms across a phase, ms",
    "io_read_bytes": "Linux /proc/<pid>/io read_bytes; not_available_on_platform elsewhere",
    "io_write_bytes": "Linux /proc/<pid>/io write_bytes; not_available_on_platform elsewhere",
    "storage_usage_bytes": "navigator.storage.estimate usage, bytes",
    "storage_indexeddb_bytes": "navigator.storage.estimate usageDetails.indexedDB, bytes",
    "storage_cache_bytes": "navigator.storage.estimate usageDetails.caches, bytes",
    "storage_service_worker_bytes": "navigator.storage.estimate usageDetails.serviceWorkerRegistrations, bytes",
    "local_storage_bytes": "sum of localStorage key and value lengths, UTF-16 bytes",
    "network_encoded_bytes": "CDP Network.loadingFinished encodedDataLength sum, bytes",
    "network_request_count": "count of Network.loadingFinished events",
    "profile_directory_bytes": "byte size of the browser profile directory",
    "bundle_bytes": "byte size of the built bundle the host serves",
    "cgroup_cpu_usec": "cgroup v2 cpu.stat usage_usec",
    "cgroup_memory_current_bytes": "cgroup v2 memory.current, bytes",
    "cgroup_memory_peak_bytes": "cgroup v2 memory.peak, bytes",
    "cgroup_io_read_bytes": "cgroup v2 io.stat rbytes sum, bytes",
    "cgroup_io_write_bytes": "cgroup v2 io.stat wbytes sum, bytes",
    "cgroup_rss_gap_bytes": "absolute gap between cgroup memory.current and the editor RSS sum, bytes",
    "peak_ram_bytes": "maximum editor-tree rss_bytes across the series, bytes",
    "peak_js_heap_used_bytes": "maximum js_heap_used_bytes across the series, bytes",
}

_GAP_BYTES = 50 * 1024 * 1024
_LINUX_ONLY = ("pss_bytes", "uss_bytes", "io_read_bytes", "io_write_bytes")


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


class WallClock:
    def monotonic(self):
        return time.monotonic()

    def sleep(self, seconds):
        time.sleep(seconds)


def role_of(cmdline):
    """Chromium process role from its command line. The browser has no --type."""
    text = cmdline or ""
    if "network.mojom.NetworkService" in text or "NetworkService" in text:
        return "network_service"
    if "--type=renderer" in text:
        return "renderer"
    if "--type=gpu-process" in text:
        return "gpu"
    if "--type=utility" in text or "--type=" in text:
        return "utility"
    return "browser"


def parse_ps_time(text):
    """macOS ``ps`` ``time`` column to milliseconds. ``[[dd-]hh:]mm:ss[.ss]``."""
    raw = str(text).strip()
    days = 0
    if "-" in raw:
        day_text, raw = raw.split("-", 1)
        days = int(day_text)
    bits = raw.split(":")
    if len(bits) == 3:
        hours, minutes, seconds = bits
    elif len(bits) == 2:
        hours = "0"
        minutes, seconds = bits
    else:
        raise ValueError("ps time")
    total = days * 86400 + int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return int(round(total * 1000))


def parse_ps_resource_table(text):
    """Parse ``ps -Ao pid=,ppid=,rss=,time=,command=``. PSS, USS and I/O are absent."""
    rows = []
    for line in text.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
            rss_kb = int(parts[2])
            cpu_ms = parse_ps_time(parts[3])
        except ValueError:
            continue
        if pid < 1 or ppid < 0 or rss_kb < 0 or cpu_ms < 0:
            continue
        rows.append({
            "pid": pid,
            "ppid": ppid,
            "cmdline": parts[4],
            "rss_bytes": rss_kb * 1024,
            "cpu_ms": cpu_ms,
            "pss_bytes": NOT_AVAILABLE,
            "uss_bytes": NOT_AVAILABLE,
            "io_read_bytes": NOT_AVAILABLE,
            "io_write_bytes": NOT_AVAILABLE,
        })
    return rows


def _kb_field(text, name):
    if not text:
        return None
    prefix = name + ":"
    for line in text.splitlines():
        if line.startswith(prefix):
            parts = line.split()
            if len(parts) >= 2:
                return int(parts[1])
    return None


def _io_field(text, name):
    if not text:
        return NOT_AVAILABLE
    prefix = name + ":"
    for line in text.splitlines():
        if line.startswith(prefix):
            return int(line.split(":", 1)[1].strip())
    return NOT_AVAILABLE


def _stat_after_comm(stat):
    end = stat.rfind(")")
    if end < 0:
        raise ValueError("stat")
    return stat[end + 1:].split()


def parse_linux_process(*, pid, stat, cmdline, status, io_text, rollup, hz):
    """One /proc/<pid> snapshot. ``hz`` is USER_HZ (SC_CLK_TCK)."""
    rest = _stat_after_comm(stat)
    ppid = int(rest[1])
    utime = int(rest[11])
    stime = int(rest[12])
    rss_kb = _kb_field(status, "VmRSS")
    pss_kb = _kb_field(rollup, "Pss") if rollup else None
    private_clean = _kb_field(rollup, "Private_Clean") if rollup else None
    private_dirty = _kb_field(rollup, "Private_Dirty") if rollup else None
    if private_clean is None or private_dirty is None:
        uss = NOT_AVAILABLE
    else:
        uss = (private_clean + private_dirty) * 1024
    return {
        "pid": int(pid),
        "ppid": ppid,
        "cmdline": cmdline,
        "rss_bytes": rss_kb * 1024 if rss_kb is not None else NOT_AVAILABLE,
        "cpu_ms": int(round((utime + stime) * 1000 / hz)),
        "pss_bytes": pss_kb * 1024 if pss_kb is not None else NOT_AVAILABLE,
        "uss_bytes": uss,
        "io_read_bytes": _io_field(io_text, "read_bytes"),
        "io_write_bytes": _io_field(io_text, "write_bytes"),
        "role": role_of(cmdline),
    }


def read_linux_process_table(proc_root, hz):
    rows = []
    root = Path(proc_root)
    if not root.is_dir():
        return rows
    for entry in root.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            stat = (entry / "stat").read_text()
            cmdline = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace").strip()
            status = (entry / "status").read_text() if (entry / "status").is_file() else ""
            io_text = (entry / "io").read_text() if (entry / "io").is_file() else ""
            rollup = (entry / "smaps_rollup").read_text() if (entry / "smaps_rollup").is_file() else ""
        except OSError:
            continue
        try:
            rows.append(parse_linux_process(
                pid=pid, stat=stat, cmdline=cmdline, status=status,
                io_text=io_text, rollup=rollup, hz=hz,
            ))
        except (ValueError, IndexError, OSError):
            continue
    return rows


def parse_cgroup_text(*, cpu_stat, memory_current, memory_peak, io_stat):
    stat = {}
    for line in (cpu_stat or "").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            stat[parts[0]] = int(parts[1])
    read_bytes = 0
    write_bytes = 0
    for line in (io_stat or "").splitlines():
        for token in line.split():
            if token.startswith("rbytes="):
                read_bytes += int(token.split("=", 1)[1])
            elif token.startswith("wbytes="):
                write_bytes += int(token.split("=", 1)[1])
    return {
        "cgroup_cpu_usec": stat["usage_usec"],
        "cgroup_memory_current_bytes": int(str(memory_current).strip()),
        "cgroup_memory_peak_bytes": int(str(memory_peak).strip()),
        "cgroup_io_read_bytes": read_bytes,
        "cgroup_io_write_bytes": write_bytes,
    }


def unavailable_cgroup():
    return {
        "cgroup_cpu_usec": NOT_AVAILABLE,
        "cgroup_memory_current_bytes": NOT_AVAILABLE,
        "cgroup_memory_peak_bytes": NOT_AVAILABLE,
        "cgroup_io_read_bytes": NOT_AVAILABLE,
        "cgroup_io_write_bytes": NOT_AVAILABLE,
    }


def read_cgroup_for_pid(proc_root, sysfs_root, pid):
    try:
        text = Path(proc_root, str(pid), "cgroup").read_text()
    except OSError:
        return unavailable_cgroup()
    relative = None
    for line in text.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3 and parts[0] == "0":
            relative = parts[2].strip()
    if relative is None:
        return unavailable_cgroup()
    base = Path(sysfs_root) if relative in ("", "/") else Path(sysfs_root) / relative.lstrip("/")
    def _read(name):
        try:
            return (base / name).read_text()
        except OSError:
            return None
    cpu = _read("cpu.stat")
    current = _read("memory.current")
    peak = _read("memory.peak")
    io_stat = _read("io.stat")
    if cpu and current and peak and io_stat:
        try:
            return parse_cgroup_text(
                cpu_stat=cpu, memory_current=current, memory_peak=peak, io_stat=io_stat,
            )
        except (ValueError, KeyError, IndexError):
            return unavailable_cgroup()
    result = unavailable_cgroup()
    if cpu:
        try:
            usage = dict(line.split()[:2] for line in cpu.splitlines() if line.strip())
            result["cgroup_cpu_usec"] = int(usage["usage_usec"])
        except (ValueError, KeyError, IndexError):
            pass
    for key, raw in (
        ("cgroup_memory_current_bytes", current),
        ("cgroup_memory_peak_bytes", peak),
    ):
        if raw:
            try:
                result[key] = int(raw.strip())
            except ValueError:
                pass
    if io_stat:
        try:
            parsed = parse_cgroup_text(
                cpu_stat="usage_usec 0\n",
                memory_current="0\n",
                memory_peak="0\n",
                io_stat=io_stat,
            )
            result["cgroup_io_read_bytes"] = parsed["cgroup_io_read_bytes"]
            result["cgroup_io_write_bytes"] = parsed["cgroup_io_write_bytes"]
        except (ValueError, KeyError):
            pass
    return result


def directory_size(path):
    if path is None:
        return NOT_AVAILABLE
    root = Path(path)
    if not root.exists():
        return NOT_AVAILABLE
    if root.is_file():
        try:
            return root.stat().st_size
        except OSError:
            return NOT_AVAILABLE
    total = 0
    for dirpath, _names, files in os.walk(root):
        for name in files:
            try:
                total += (Path(dirpath) / name).stat().st_size
            except OSError:
                continue
    return total


def _default_process_reader(platform_name):
    if platform_name == "linux":
        hz = os.sysconf("SC_CLK_TCK")

        def read_linux():
            return read_linux_process_table("/proc", hz)

        return read_linux

    def read_ps():
        proc = subprocess.run(
            ["ps", "-axww", "-o", "pid=,ppid=,rss=,time=,command="],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or "").strip()[:300])
        return parse_ps_resource_table(proc.stdout or "")

    return read_ps


def _default_cgroup_reader(platform_name):
    if platform_name != "linux":
        return lambda pid: unavailable_cgroup()

    def read(pid):
        return read_cgroup_for_pid("/proc", "/sys/fs/cgroup", pid)

    return read


def _signature(sample):
    processes = tuple(sorted(
        (row["pid"], row["role"], row["rss_bytes"], row["cpu_ms"])
        for row in sample.get("processes") or []
    ))
    return (
        sample.get("js_heap_used_bytes"),
        sample.get("rss_bytes"),
        sample.get("network_encoded_bytes"),
        sample.get("storage_usage_bytes"),
        sample.get("longtask_count"),
        processes,
    )


def classify_series(series, *, quiescence_reached):
    """Closed reason a series must not be published, or None.

    Quiescence that never held wins over a flat or copied series: the run
    already failed its declared settle condition.
    """
    if quiescence_reached is False:
        return "quiescence_not_reached"
    grouped = {}
    for sample in series:
        grouped.setdefault(sample.get("phase"), []).append(_signature(sample))
    phases = [sigs for name, sigs in grouped.items() if name is not None and sigs]
    for left in range(len(phases)):
        for right in range(left + 1, len(phases)):
            if phases[left] == phases[right]:
                return "copied_series"
    if len(series) >= 2:
        sigs = [_signature(sample) for sample in series]
        if all(sig == sigs[0] for sig in sigs):
            return "constant_series"
    return None


def _window_quiet(samples, now, declaration):
    span = float(declaration["no_longtask_s"])
    band = float(declaration["heap_band_percent"])
    earlier = [sample for sample in samples if sample["monotonic_s"] <= now - span + 1e-9]
    if not earlier:
        return False
    anchor = earlier[-1]
    if now - anchor["monotonic_s"] < span - 1e-9:
        return False
    window = [anchor] + [
        sample for sample in samples
        if anchor["monotonic_s"] < sample["monotonic_s"] <= now + 1e-9
    ]
    if not _is_int(anchor.get("longtask_count")) or not _is_int(anchor.get("js_heap_used_bytes")):
        return False
    for sample in window:
        if sample.get("longtask_count") != anchor["longtask_count"]:
            return False
        heap = sample.get("js_heap_used_bytes")
        if not _is_int(heap):
            return False
        limit = abs(anchor["js_heap_used_bytes"]) * band / 100.0
        if abs(heap - anchor["js_heap_used_bytes"]) > limit + 0.5:
            return False
    return True


def drive_quiescence(sampler, clock, declaration):
    """Sample until the declared settle holds, or ``max_wait_s`` elapses."""
    start = clock.monotonic()
    while True:
        sampler.sample()
        now = clock.monotonic()
        if _window_quiet(sampler.series(), now, declaration):
            return True
        if now - start >= float(declaration["max_wait_s"]):
            return False
        clock.sleep(float(declaration["poll_s"]))


def _delta(first, last, key):
    before = first.get(key)
    after = last.get(key)
    if _is_int(before) and _is_int(after):
        return after - before
    return NOT_AVAILABLE


def _renderer_cpu(sample):
    total = 0
    for row in sample.get("processes") or []:
        if row.get("role") == "renderer" and _is_int(row.get("cpu_ms")):
            total += row["cpu_ms"]
    return total


def phase_totals(rows):
    first, last = rows[0], rows[-1]
    rss_values = [row["rss_bytes"] for row in rows if _is_int(row.get("rss_bytes"))]
    heap_values = [row["js_heap_used_bytes"] for row in rows if _is_int(row.get("js_heap_used_bytes"))]
    return {
        "sample_count": len(rows),
        "js_heap_used_bytes": last.get("js_heap_used_bytes"),
        "js_heap_total_bytes": last.get("js_heap_total_bytes"),
        "js_heap_runtime_used_bytes": last.get("js_heap_runtime_used_bytes"),
        "rss_bytes": last.get("rss_bytes"),
        "peak_rss_bytes": max(rss_values) if rss_values else NOT_AVAILABLE,
        "peak_js_heap_used_bytes": max(heap_values) if heap_values else NOT_AVAILABLE,
        "renderer_cpu_ms": _renderer_cpu(last) - _renderer_cpu(first),
        "cpu_ms": _delta(first, last, "cpu_ms"),
        "task_duration_ms": _delta(first, last, "task_duration_ms"),
        "script_duration_ms": _delta(first, last, "script_duration_ms"),
        "layout_duration_ms": _delta(first, last, "layout_duration_ms"),
        "recalc_style_duration_ms": _delta(first, last, "recalc_style_duration_ms"),
        "longtask_count": _delta(first, last, "longtask_count"),
        "longtask_sum_ms": _delta(first, last, "longtask_sum_ms"),
        "network_encoded_bytes": _delta(first, last, "network_encoded_bytes"),
        "network_request_count": _delta(first, last, "network_request_count"),
        "io_read_bytes": _delta(first, last, "io_read_bytes"),
        "io_write_bytes": _delta(first, last, "io_write_bytes"),
        "storage_usage_bytes": last.get("storage_usage_bytes"),
        "storage_indexeddb_bytes": last.get("storage_indexeddb_bytes"),
        "storage_cache_bytes": last.get("storage_cache_bytes"),
        "storage_service_worker_bytes": last.get("storage_service_worker_bytes"),
        "local_storage_bytes": last.get("local_storage_bytes"),
        "processes": last.get("processes") or [],
    }


class ResourceSampler:
    def __init__(self, run, page, cdp, *, process_reader=None, cgroup_reader=None, platform_name=None, clock=None):
        self.run = run
        self.page = page
        self.cdp = cdp
        self.platform_name = (platform_name or platform.system().lower())
        self.process_reader = process_reader or _default_process_reader(self.platform_name)
        self.cgroup_reader = cgroup_reader or _default_cgroup_reader(self.platform_name)
        self.clock = clock or WallClock()
        self._phase = None
        self._samples = []
        self._seen_requests = set()
        self._net_bytes = 0
        self._net_count = 0
        self._enabled = False
        self._bundle_bytes = None

    def mark(self, phase):
        self._phase = phase
        return self.sample()

    def sample(self):
        row = self._observe()
        self._samples.append(row)
        return row

    def series(self):
        return [dict(row) for row in self._samples]

    def totals(self, phase):
        rows = [row for row in self._samples if row.get("phase") == phase]
        if not rows:
            raise KeyError(phase)
        return phase_totals(rows)

    def _enable(self):
        if self._enabled:
            return
        for method in ("Performance.enable", "Network.enable"):
            try:
                self.cdp.send(method)
            except Exception:
                pass
        self._enabled = True

    def _observe(self):
        self._enable()
        now = self.clock.monotonic()
        heap = self._heap()
        storage = self._storage()
        network_bytes, network_count = self._network()
        processes, status, read_error = self._processes()
        cgroup = self._cgroup(processes)
        rss_values = [row["rss_bytes"] for row in processes if _is_int(row.get("rss_bytes"))]
        cpu_values = [row["cpu_ms"] for row in processes if _is_int(row.get("cpu_ms"))]
        rss_bytes = sum(rss_values) if processes and len(rss_values) == len(processes) else NOT_AVAILABLE
        cpu_ms = sum(cpu_values) if processes and len(cpu_values) == len(processes) else NOT_AVAILABLE
        io_read, io_write = _sum_optional(processes, "io_read_bytes"), _sum_optional(processes, "io_write_bytes")
        pss, uss = _sum_optional(processes, "pss_bytes"), _sum_optional(processes, "uss_bytes")
        previous = self._samples[-1] if self._samples else None
        cpu_percent = _cpu_percent(previous, now, cpu_ms)
        gap, gap_large = _gap(rss_bytes, cgroup.get("cgroup_memory_current_bytes"))
        browser_pid = getattr(self.run, "editor_browser_pid", None)
        server_pid = getattr(self.run, "static_server_pid", None)
        return {
            "phase": self._phase,
            "monotonic_s": now,
            "platform": self.platform_name,
            "process_tree_status": status,
            "process_tree_error": read_error,
            "editor_browser_pid": browser_pid,
            "js_heap_used_bytes": heap["js_heap_used_bytes"],
            "js_heap_total_bytes": heap["js_heap_total_bytes"],
            "js_heap_runtime_used_bytes": heap["js_heap_runtime_used_bytes"],
            "js_heap_runtime_total_bytes": heap["js_heap_runtime_total_bytes"],
            "task_duration_ms": heap["task_duration_ms"],
            "script_duration_ms": heap["script_duration_ms"],
            "layout_duration_ms": heap["layout_duration_ms"],
            "recalc_style_duration_ms": heap["recalc_style_duration_ms"],
            "longtask_count": storage["longtask_count"],
            "longtask_sum_ms": storage["longtask_sum_ms"],
            "storage_usage_bytes": storage["storage_usage_bytes"],
            "storage_indexeddb_bytes": storage["storage_indexeddb_bytes"],
            "storage_cache_bytes": storage["storage_cache_bytes"],
            "storage_service_worker_bytes": storage["storage_service_worker_bytes"],
            "local_storage_bytes": storage["local_storage_bytes"],
            "network_encoded_bytes": network_bytes,
            "network_request_count": network_count,
            "rss_bytes": rss_bytes,
            "pss_bytes": pss,
            "uss_bytes": uss,
            "cpu_ms": cpu_ms,
            "cpu_percent": cpu_percent,
            "io_read_bytes": io_read,
            "io_write_bytes": io_write,
            "processes": processes,
            "static_server": {
                "pid": server_pid,
                "role": "static_server",
                "counted_as_editor": False,
                "in_process": server_pid == os.getpid(),
                "note": STATIC_SERVER_NOTE,
            },
            "profile_directory_bytes": directory_size(getattr(self.run, "profile_dir", None)),
            "bundle_bytes": self._bundle(),
            "cgroup_cpu_usec": cgroup["cgroup_cpu_usec"],
            "cgroup_memory_current_bytes": cgroup["cgroup_memory_current_bytes"],
            "cgroup_memory_peak_bytes": cgroup["cgroup_memory_peak_bytes"],
            "cgroup_io_read_bytes": cgroup["cgroup_io_read_bytes"],
            "cgroup_io_write_bytes": cgroup["cgroup_io_write_bytes"],
            "cgroup_rss_gap_bytes": gap,
            "cgroup_gap_large": gap_large,
        }

    def _heap(self):
        missing = {
            "js_heap_used_bytes": NOT_AVAILABLE,
            "js_heap_total_bytes": NOT_AVAILABLE,
            "js_heap_runtime_used_bytes": NOT_AVAILABLE,
            "js_heap_runtime_total_bytes": NOT_AVAILABLE,
            "task_duration_ms": NOT_AVAILABLE,
            "script_duration_ms": NOT_AVAILABLE,
            "layout_duration_ms": NOT_AVAILABLE,
            "recalc_style_duration_ms": NOT_AVAILABLE,
        }
        try:
            payload = self.cdp.send("Performance.getMetrics")
            metrics = {item["name"]: item["value"] for item in payload.get("metrics") or []}
            runtime = self.cdp.send("Runtime.getHeapUsage")
        except Exception:
            return missing
        def metric_ms(name):
            if name not in metrics:
                return NOT_AVAILABLE
            return int(round(float(metrics[name]) * 1000))
        try:
            missing.update({
                "js_heap_used_bytes": int(round(float(metrics["JSHeapUsedSize"]))),
                "js_heap_total_bytes": int(round(float(metrics["JSHeapTotalSize"]))),
                "js_heap_runtime_used_bytes": int(round(float(runtime["usedSize"]))),
                "js_heap_runtime_total_bytes": int(round(float(runtime["totalSize"]))),
                "task_duration_ms": metric_ms("TaskDuration"),
                "script_duration_ms": metric_ms("ScriptDuration"),
                "layout_duration_ms": metric_ms("LayoutDuration"),
                "recalc_style_duration_ms": metric_ms("RecalcStyleDuration"),
            })
        except (KeyError, TypeError, ValueError):
            return missing
        return missing

    def _storage(self):
        missing = {
            "storage_usage_bytes": NOT_AVAILABLE,
            "storage_indexeddb_bytes": NOT_AVAILABLE,
            "storage_cache_bytes": NOT_AVAILABLE,
            "storage_service_worker_bytes": NOT_AVAILABLE,
            "local_storage_bytes": NOT_AVAILABLE,
            "longtask_count": NOT_AVAILABLE,
            "longtask_sum_ms": NOT_AVAILABLE,
        }
        try:
            snap = self.page.evaluate(PAGE_SNAPSHOT_JS)
        except Exception:
            return missing
        if not isinstance(snap, dict):
            return missing
        details = snap.get("usageDetails") or {}
        local = snap.get("localStorageBytes")
        try:
            missing.update({
                "storage_usage_bytes": int(snap.get("usage") or 0),
                "storage_indexeddb_bytes": int(details.get("indexedDB") or 0),
                "storage_cache_bytes": int(details.get("caches") or 0),
                "storage_service_worker_bytes": int(details.get("serviceWorkerRegistrations") or 0),
                "local_storage_bytes": NOT_AVAILABLE if local is None else int(local),
                "longtask_count": int(snap.get("longtaskCount") or 0),
                "longtask_sum_ms": int(round(float(snap.get("longtaskSumMs") or 0))),
            })
        except (TypeError, ValueError):
            return missing
        return missing

    def _network(self):
        try:
            events = self.cdp.events("Network.loadingFinished") or []
        except Exception:
            events = []
        for event in events:
            if not isinstance(event, dict):
                continue
            request_id = event.get("requestId")
            if request_id in self._seen_requests:
                continue
            self._seen_requests.add(request_id)
            try:
                self._net_bytes += int(event.get("encodedDataLength") or 0)
            except (TypeError, ValueError):
                continue
            self._net_count += 1
        return self._net_bytes, self._net_count

    def _processes(self):
        browser_pid = getattr(self.run, "editor_browser_pid", None)
        server_pid = getattr(self.run, "static_server_pid", None)
        if not _is_int(browser_pid) or browser_pid < 1:
            return [], "process_tree_not_launched", None
        try:
            table = self.process_reader() or []
        except Exception as exc:
            return [], "process_tree_missing", "%s: %s" % (type(exc).__name__, exc)
        normalized = []
        for row in table:
            try:
                copied = _normalize_process(row, self.platform_name)
            except (KeyError, TypeError, ValueError):
                continue
            normalized.append(copied)
        pids = set(tree_pids(normalized, browser_pid))
        if server_pid in pids:
            pids.discard(server_pid)
        kept = [row for row in normalized if row["pid"] in pids]
        if not kept:
            return [], "process_tree_missing", None
        return kept, "ok", None

    def _cgroup(self, processes):
        if self.platform_name != "linux":
            return unavailable_cgroup()
        browser_pid = getattr(self.run, "editor_browser_pid", None)
        if not _is_int(browser_pid):
            return unavailable_cgroup()
        try:
            reading = self.cgroup_reader(browser_pid) or unavailable_cgroup()
        except Exception:
            return unavailable_cgroup()
        result = unavailable_cgroup()
        result.update({key: reading.get(key, NOT_AVAILABLE) for key in result})
        return result

    def _bundle(self):
        if self._bundle_bytes is not None:
            return self._bundle_bytes
        declared = getattr(self.run, "bundle_bytes", None)
        if _is_int(declared) and declared >= 0:
            self._bundle_bytes = declared
            return declared
        self._bundle_bytes = directory_size(getattr(self.run, "bundle_path", None))
        return self._bundle_bytes


def _normalize_process(row, platform_name):
    copied = {
        "pid": int(row["pid"]),
        "ppid": int(row["ppid"]),
        "cmdline": row.get("cmdline") or "",
        "rss_bytes": int(row["rss_bytes"]) if _is_int(row.get("rss_bytes")) else NOT_AVAILABLE,
        "cpu_ms": int(row["cpu_ms"]) if _is_int(row.get("cpu_ms")) else NOT_AVAILABLE,
        "role": role_of(row.get("cmdline") or ""),
    }
    for key in _LINUX_ONLY:
        value = row.get(key, NOT_AVAILABLE)
        if platform_name != "linux":
            value = NOT_AVAILABLE
        copied[key] = value
    return copied


def _sum_optional(processes, key):
    if not processes:
        return NOT_AVAILABLE
    values = [row.get(key) for row in processes]
    if any(not _is_int(value) for value in values):
        return NOT_AVAILABLE
    return sum(values)


def _cpu_percent(previous, now, cpu_ms):
    if previous is None or not _is_int(cpu_ms) or not _is_int(previous.get("cpu_ms")):
        return None
    wall_ms = (now - previous["monotonic_s"]) * 1000.0
    if wall_ms <= 0:
        return None
    return (cpu_ms - previous["cpu_ms"]) / wall_ms * 100.0


def _gap(rss_bytes, cgroup_bytes):
    if not _is_int(rss_bytes) or not _is_int(cgroup_bytes):
        return NOT_AVAILABLE, NOT_AVAILABLE
    gap = abs(cgroup_bytes - rss_bytes)
    threshold = max(_GAP_BYTES, int(0.25 * max(cgroup_bytes, rss_bytes)))
    return gap, gap > threshold
