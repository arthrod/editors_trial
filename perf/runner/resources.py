"""Shared resource sampler for the browser lanes.

``ResourceSampler(run, page, cdp)`` reads one Chromium tree, the one whose
root pid the run launched, and records RAM, CPU, disk and network with the
unit in the field name. Linux-only counters stay
``not_available_on_platform`` on other hosts. They are never stored as zero.
A genuine numeric zero stays zero. Counter deltas (CPU, IO, network bytes
and requests, long tasks, task/script/layout/style durations) need two
samples. One sample emits the unavailable marker with reason
``single_sample_phase``, never zero. Heap, RSS, PSS, USS, storage and
profile size are levels taken from the last sample.
``AsyncResourceSampler`` is the same
contract over an async page and CDP session: ``mark(phase)`` returns a sample
and leaves that phase active, ``totals(phase)`` requires the phase.

Field schema. ``js_heap_used_bytes`` is the natural CDP heap, in bytes.
``js_heap_used_bytes_after_gc`` is a labelled sample taken after
``HeapProfiler.collectGarbage`` and is not written into the natural series.
``retained_growth_js_heap_bytes`` is the after-edit GC heap minus the
after-load GC heap, in bytes. A failed or unsupported collection refuses only
that field (``retained_growth_refusal`` = ``gc_unsupported``). ``cpu_percent``
is summed over cores. ``network_encoded_bytes`` is wire bytes.
``network_decoded_body_bytes`` is decoded body bytes. Cache hits stay in
``network_from_disk_cache_bytes`` and ``network_from_service_worker_bytes``.

The dev/static server is not the editor. Its pid is recorded and excluded.
"""

from __future__ import annotations

import asyncio
import copy
import os
from pathlib import Path
import platform
import subprocess
import time

from perf.runner.memory_tree import tree_pids

NOT_AVAILABLE = "not_available_on_platform"
SINGLE_SAMPLE_PHASE = "single_sample_phase"

# Phase quantities. A level (heap, RSS, storage) is not in this list.
COUNTER_DELTA_FIELDS = (
    "cpu_ms",
    "renderer_cpu_ms",
    "io_read_bytes",
    "io_write_bytes",
    "network_encoded_bytes",
    "network_request_count",
    "longtask_count",
    "longtask_sum_ms",
    "task_duration_ms",
    "script_duration_ms",
    "layout_duration_ms",
    "recalc_style_duration_ms",
)


def unavailable_marker(reason):
    """The unavailable marker. ``reason`` says why there is no number."""
    return {"marker": NOT_AVAILABLE, "reason": reason}


def withheld_marker(reason):
    """A measured field deliberately withheld from publication."""
    return {"marker": "withheld", "reason": reason}

PAGE_SNAPSHOT_JS = """async () => {
  let est = null;
  if (navigator.storage && navigator.storage.estimate) {
    try {
      est = await navigator.storage.estimate();
    } catch (err) {
      est = null;
    }
  }
  const details = est && est.usageDetails ? est.usageDetails : null;
  const member = (source, name, alias) => {
    if (!source) return null;
    if (Object.prototype.hasOwnProperty.call(source, name)) return source[name];
    if (alias && Object.prototype.hasOwnProperty.call(source, alias)) return source[alias];
    return null;
  };
  let localStorageBytes = null;
  try {
    localStorageBytes = 0;
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      const value = localStorage.getItem(key) || "";
      localStorageBytes += (String(key).length + String(value).length) * 2;
    }
  } catch (err) {
    localStorageBytes = null;
  }
  const tasks = window.__resourceLongTasks;
  const longtaskKnown = !!(tasks && tasks.available !== false && tasks.count != null && tasks.sum != null);
  return {
    usage: est && est.usage != null ? est.usage : null,
    usageDetails: details ? {
      indexedDB: member(details, "indexedDB"),
      caches: member(details, "caches", "cacheStorage"),
      serviceWorkerRegistrations: member(details, "serviceWorkerRegistrations", "serviceWorker"),
    } : null,
    localStorageBytes,
    longtaskCount: longtaskKnown ? tasks.count : null,
    longtaskSumMs: longtaskKnown ? tasks.sum : null,
    longtaskReason: longtaskKnown ? null : ((tasks && tasks.reason) || "longtask_unavailable"),
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
    "cpu_percent": "CPU ms over wall ms since the previous sample, percent, summed over cores (250% = 2.5 cores), not capped at 100",
    "renderer_cpu_ms": "delta of renderer cpu_ms across a phase, ms",
    "edit_cpu_ms": "browser-tree process CPU from immediately after the baseline probe through keyboard.type plus the fixed settle; verification and full endpoint probes are outside the boundary",
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
    "bundle_bytes": "on-disk recursive footprint of the built bundle, not bytes served",
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


def parse_ps_lstart(text):
    """Parse ``ps -axww -o pid=,lstart=``. ``lstart`` is ctime and may contain spaces.

    ``etime`` changes every second and is not a stable identity. This parser
    never reads it.
    """
    found = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, started = stripped.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if started.strip():
            found[pid] = started.strip()
    return found


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
    # Field 22 (starttime) is rest[19]. A short stat has no stable start tick.
    start_time = int(rest[19]) if len(rest) > 19 else None
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
        "start_time": start_time,
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
        rows = parse_ps_resource_table(proc.stdout or "")
        started = subprocess.run(
            ["ps", "-axww", "-o", "pid=,lstart="],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if started.returncode == 0:
            lstarts = parse_ps_lstart(started.stdout or "")
            for row in rows:
                if row["pid"] in lstarts:
                    row["start_time"] = lstarts[row["pid"]]
        return rows

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
    """Sample until the declared settle holds, or ``max_wait_s`` elapses.

    An unknown long-task count cannot prove quiet. That refuses immediately
    instead of treating a synthesized zero as two seconds of silence.
    """
    start = clock.monotonic()
    sampler.quiescence_block = None
    while True:
        sampler.sample()
        now = clock.monotonic()
        last = sampler.series()[-1]
        if not _is_int(last.get("longtask_count")):
            sampler.quiescence_block = "longtask_unavailable"
            return False
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


def _optional_number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    return None


def _detail_number(details, name, alias=None):
    if not isinstance(details, dict):
        return NOT_AVAILABLE
    if name in details:
        raw = details[name]
    elif alias and alias in details:
        raw = details[alias]
    else:
        return NOT_AVAILABLE
    parsed = _optional_number(raw)
    if parsed is None:
        return NOT_AVAILABLE
    return parsed


def storage_from_snapshot(snap):
    """Storage and long-task fields. Missing keys stay unavailable, never zero."""
    missing = {
        "storage_usage_bytes": NOT_AVAILABLE,
        "storage_indexeddb_bytes": NOT_AVAILABLE,
        "storage_cache_bytes": NOT_AVAILABLE,
        "storage_service_worker_bytes": NOT_AVAILABLE,
        "local_storage_bytes": NOT_AVAILABLE,
        "longtask_count": NOT_AVAILABLE,
        "longtask_sum_ms": NOT_AVAILABLE,
    }
    if not isinstance(snap, dict) or not snap:
        return missing
    if "usage" in snap:
        parsed = _optional_number(snap.get("usage"))
        missing["storage_usage_bytes"] = parsed if parsed is not None else NOT_AVAILABLE
    details = snap.get("usageDetails") if "usageDetails" in snap else None
    missing["storage_indexeddb_bytes"] = _detail_number(details, "indexedDB")
    missing["storage_cache_bytes"] = _detail_number(details, "caches", "cacheStorage")
    missing["storage_service_worker_bytes"] = _detail_number(
        details, "serviceWorkerRegistrations", "serviceWorker",
    )
    if "localStorageBytes" in snap:
        parsed = _optional_number(snap.get("localStorageBytes"))
        missing["local_storage_bytes"] = parsed if parsed is not None else NOT_AVAILABLE
    if "longtaskCount" in snap:
        parsed = _optional_number(snap.get("longtaskCount"))
        missing["longtask_count"] = parsed if parsed is not None else NOT_AVAILABLE
    if "longtaskSumMs" in snap:
        parsed = _optional_number(snap.get("longtaskSumMs"))
        missing["longtask_sum_ms"] = parsed if parsed is not None else NOT_AVAILABLE
    return missing


def _network_unavailable(reason):
    return {
        "network_encoded_bytes": NOT_AVAILABLE,
        "network_request_count": NOT_AVAILABLE,
        "network_decoded_body_bytes": NOT_AVAILABLE,
        "network_from_disk_cache_bytes": NOT_AVAILABLE,
        "network_from_service_worker_bytes": NOT_AVAILABLE,
        "network_observation": "incomplete",
        "network_observation_reason": reason,
    }


def _wire_length(event):
    """Integer ``encodedDataLength``, or None when the field is not a real int.

    Zero is a real observation. A missing field, ``None``, a ``bool``, or any
    other type is not zero: ``or 0`` would publish a transfer that was not seen.
    """
    if "encodedDataLength" not in event:
        return None
    value = event.get("encodedDataLength")
    if not _is_int(value):
        return None
    return value


def account_network(payload):
    """Recompute wire, decoded, and cache bytes from one full event list.

    A bare list is a complete page observation (older sessions and FakeCdp).
    A dict must say ``worker_observation == 'ok'`` and carry a real ``events``
    list. A missing observation, a missing list, or a finished request with no
    integer ``encodedDataLength`` is incomplete, never a complete zero.
    A dict whose observation is not ``ok`` refuses every numeric field.
    Cache-hit wire length may be zero and is not replaced with the decoded body.
    """
    if isinstance(payload, dict):
        if "worker_observation" not in payload:
            return _network_unavailable("worker_observation_missing")
        observation = payload.get("worker_observation")
        if observation != "ok":
            reason = payload.get("worker_observation_reason") or payload.get("reason") or "worker_targets_unobserved"
            return _network_unavailable(reason)
        if "events" not in payload or not isinstance(payload.get("events"), list):
            return _network_unavailable("cdp_events_unavailable")
        events = payload["events"]
    elif isinstance(payload, list):
        events = payload
    else:
        return _network_unavailable("cdp_events_unavailable")
    encoded = 0
    count = 0
    decoded = 0
    decoded_complete = True
    disk = 0
    worker = 0
    seen = set()
    for event in events:
        if not isinstance(event, dict):
            return _network_unavailable("encoded_length_missing")
        request_id = event.get("requestId")
        if request_id is not None and request_id in seen:
            continue
        wire = _wire_length(event)
        if wire is None:
            return _network_unavailable("encoded_length_missing")
        if request_id is not None:
            seen.add(request_id)
        encoded += wire
        count += 1
        from_disk = bool(event.get("fromDiskCache"))
        from_worker = bool(event.get("fromServiceWorker"))
        if "decodedBodyBytes" not in event or event.get("decodedBodyBytes") is None:
            decoded_complete = False
            continue
        try:
            body = int(event["decodedBodyBytes"])
        except (TypeError, ValueError):
            decoded_complete = False
            continue
        decoded += body
        if from_disk:
            disk += body
        if from_worker:
            worker += body
    return {
        "network_encoded_bytes": encoded,
        "network_request_count": count,
        "network_decoded_body_bytes": decoded if decoded_complete else NOT_AVAILABLE,
        "network_from_disk_cache_bytes": disk if decoded_complete else NOT_AVAILABLE,
        "network_from_service_worker_bytes": worker if decoded_complete else NOT_AVAILABLE,
        "network_observation": "ok",
        "network_observation_reason": None,
    }


def _process_identity(row):
    return (row.get("pid"), row.get("start_time"))


def _process_list(sample):
    return list(sample.get("processes") or [])


def process_accounting_status(rows):
    """``incomplete`` when an identity disappears or a numeric counter goes backwards.

    A counter that is unavailable on this platform (the marker, not an int)
    does not make the phase incomplete. A process that appears only on the
    last sample is new, not an exit.
    """
    if not rows:
        return "complete"
    last_ids = {_process_identity(row) for row in _process_list(rows[-1])}
    # A process missed by the first sample is not a birth: it would bill its
    # lifetime CPU to this window. A birth started after every process the
    # first sample saw; one with no start time cannot be told apart.
    opening = _process_list(rows[0])
    opening_ids = {_process_identity(row) for row in opening}
    opening_starts = [row.get("start_time") for row in opening if _is_int(row.get("start_time"))]
    for sample in rows[1:]:
        for proc in _process_list(sample):
            if _process_identity(proc) in opening_ids:
                continue
            start = proc.get("start_time")
            if start is None:
                return "incomplete"
            if _is_int(start) and opening_starts and start < max(opening_starts):
                return "incomplete"
    first_seen = {}
    for index, sample in enumerate(rows):
        for proc in _process_list(sample):
            identity = _process_identity(proc)
            if index < len(rows) - 1 and identity not in last_ids:
                return "incomplete"
            previous = first_seen.get(identity)
            if previous is None:
                first_seen[identity] = proc
                continue
            for key in ("cpu_ms", "io_read_bytes", "io_write_bytes"):
                before = previous.get(key)
                after = proc.get(key)
                if _is_int(before) and _is_int(after) and after < before:
                    return "incomplete"
    return "complete"


def _identity_delta(rows, key, *, role=None):
    """Sum per-identity deltas. A birth contributes its full last-sight counter.

    The process was absent from the first sample, so its baseline is zero.
    Subtracting the first sighting would drop work done before that sample.
    An exit or a counter that goes backwards is incomplete, not a negative
    delta and not zero. A platform-unavailable counter stays unavailable.
    """
    status = process_accounting_status(rows)
    if status == "incomplete":
        return NOT_AVAILABLE, status
    if not rows:
        return NOT_AVAILABLE, status
    first = {}
    for proc in _process_list(rows[0]):
        first[_process_identity(proc)] = proc
    total = 0
    saw = False
    unavailable = False
    for proc in _process_list(rows[-1]):
        if role is not None and proc.get("role") != role:
            continue
        previous = first.get(_process_identity(proc))
        if previous is None:
            before = 0
        else:
            if role is not None and previous.get("role") != role:
                continue
            before = previous.get(key)
        after = proc.get(key)
        if not _is_int(before) or not _is_int(after):
            unavailable = True
            continue
        total += after - before
        saw = True
    if unavailable or not saw:
        return NOT_AVAILABLE, status
    return total, status


def _renderer_cpu(sample):
    total = 0
    saw = False
    for row in sample.get("processes") or []:
        if row.get("role") == "renderer" and _is_int(row.get("cpu_ms")):
            total += row["cpu_ms"]
            saw = True
    if not saw:
        return NOT_AVAILABLE
    return total


def phase_totals(rows):
    first, last = rows[0], rows[-1]
    rss_values = [row["rss_bytes"] for row in rows if _is_int(row.get("rss_bytes"))]
    heap_values = [row["js_heap_used_bytes"] for row in rows if _is_int(row.get("js_heap_used_bytes"))]
    renderer_cpu, status = _identity_delta(rows, "cpu_ms", role="renderer")
    cpu_ms, cpu_status = _identity_delta(rows, "cpu_ms")
    io_read, _io_status = _identity_delta(rows, "io_read_bytes")
    io_write, _io_write_status = _identity_delta(rows, "io_write_bytes")
    if "incomplete" in (status, cpu_status):
        status = "incomplete"
    totals = {
        "sample_count": len(rows),
        "js_heap_used_bytes": last.get("js_heap_used_bytes"),
        "js_heap_total_bytes": last.get("js_heap_total_bytes"),
        "js_heap_runtime_used_bytes": last.get("js_heap_runtime_used_bytes"),
        "rss_bytes": last.get("rss_bytes"),
        "peak_rss_bytes": max(rss_values) if rss_values else NOT_AVAILABLE,
        "peak_js_heap_used_bytes": max(heap_values) if heap_values else NOT_AVAILABLE,
        "renderer_cpu_ms": renderer_cpu,
        "cpu_ms": cpu_ms,
        "process_accounting": status,
        "task_duration_ms": _delta(first, last, "task_duration_ms"),
        "script_duration_ms": _delta(first, last, "script_duration_ms"),
        "layout_duration_ms": _delta(first, last, "layout_duration_ms"),
        "recalc_style_duration_ms": _delta(first, last, "recalc_style_duration_ms"),
        "longtask_count": _delta(first, last, "longtask_count"),
        "longtask_sum_ms": _delta(first, last, "longtask_sum_ms"),
        "network_encoded_bytes": _delta(first, last, "network_encoded_bytes"),
        "network_request_count": _delta(first, last, "network_request_count"),
        "io_read_bytes": io_read,
        "io_write_bytes": io_write,
        "storage_usage_bytes": last.get("storage_usage_bytes"),
        "storage_indexeddb_bytes": last.get("storage_indexeddb_bytes"),
        "storage_cache_bytes": last.get("storage_cache_bytes"),
        "storage_service_worker_bytes": last.get("storage_service_worker_bytes"),
        "local_storage_bytes": last.get("local_storage_bytes"),
        "processes": last.get("processes") or [],
    }
    if len(rows) < 2:
        for key in COUNTER_DELTA_FIELDS:
            totals[key] = unavailable_marker(SINGLE_SAMPLE_PHASE)
    return totals


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
        self._network_account = account_network([])
        self.quiescence_block = None
        self.gc_heaps = {}

    def mark(self, phase):
        self._phase = phase
        return self.sample()

    def sample(self, record=True):
        row = self._observe()
        if record:
            self._samples.append(row)
        return row

    def sample_after_gc(self):
        """Forced-GC heap for a labelled endpoint. Never appended to the series."""
        try:
            self.cdp.send("HeapProfiler.collectGarbage")
        except Exception:
            return None
        return self.sample(record=False)

    def process_snapshot(self):
        """A process-only boundary: no CDP, page evaluation, or storage probe."""
        processes, status, error = self._processes()
        return {
            "monotonic_s": self.clock.monotonic(),
            "processes": processes,
            "process_tree_status": status,
            "process_tree_error": error,
        }

    def process_counter_delta(self, before, after, key, *, role=None):
        """CPU delta between two process-only boundaries."""
        return _identity_delta([before, after], key, role=role)

    def series(self):
        return [copy.deepcopy(row) for row in self._samples]

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
        network = self._network_account
        processes, status, read_error = self._processes()
        cgroup = self._cgroup(processes)
        rss_values = [row["rss_bytes"] for row in processes if _is_int(row.get("rss_bytes"))]
        cpu_values = [row["cpu_ms"] for row in processes if _is_int(row.get("cpu_ms"))]
        rss_bytes = sum(rss_values) if processes and len(rss_values) == len(processes) else NOT_AVAILABLE
        cpu_ms = sum(cpu_values) if processes and len(cpu_values) == len(processes) else NOT_AVAILABLE
        io_read, io_write = _sum_optional(processes, "io_read_bytes"), _sum_optional(processes, "io_write_bytes")
        pss, uss = _sum_optional(processes, "pss_bytes"), _sum_optional(processes, "uss_bytes")
        previous = self._samples[-1] if self._samples else None
        cpu_percent, cpu_percent_by_role = _annotate_cpu_percent(processes, previous, now)
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
            "network_decoded_body_bytes": network.get("network_decoded_body_bytes", NOT_AVAILABLE),
            "network_from_disk_cache_bytes": network.get("network_from_disk_cache_bytes", NOT_AVAILABLE),
            "network_from_service_worker_bytes": network.get("network_from_service_worker_bytes", NOT_AVAILABLE),
            "network_observation": network.get("network_observation", "ok"),
            "network_observation_reason": network.get("network_observation_reason"),
            "rss_bytes": rss_bytes,
            "pss_bytes": pss,
            "uss_bytes": uss,
            "cpu_ms": cpu_ms,
            "cpu_percent": cpu_percent,
            "cpu_percent_by_role": cpu_percent_by_role,
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
        try:
            snap = self.page.evaluate(PAGE_SNAPSHOT_JS)
        except Exception:
            snap = None
        return storage_from_snapshot(snap)

    def _network(self):
        try:
            payload = self.cdp.events("Network.loadingFinished")
        except Exception:
            payload = None
        if payload is None:
            self._network_account = _network_unavailable("cdp_events_unavailable")
        else:
            self._network_account = account_network(payload)
        account = self._network_account
        return account["network_encoded_bytes"], account["network_request_count"]

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
        "start_time": row.get("start_time"),
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


def _annotate_cpu_percent(processes, previous, now):
    """Per-process and per-role percents. A lost identity makes the sample percent None.

    Percents are summed across cores. 250 means two and a half cores, not a cap at 100.
    """
    previous_rows = {}
    if previous is not None:
        for row in previous.get("processes") or []:
            previous_rows[_process_identity(row)] = row
    wall_ms = None
    if previous is not None:
        wall_ms = (now - previous["monotonic_s"]) * 1000.0
    current_ids = {_process_identity(row) for row in processes}
    lost_roles = set()
    lost = False
    if previous is not None:
        for identity, row in previous_rows.items():
            if identity not in current_ids:
                lost = True
                lost_roles.add(row.get("role"))
    by_role = {}
    for row in processes:
        prior = previous_rows.get(_process_identity(row))
        percent = None
        if prior is not None and wall_ms is not None and wall_ms > 0:
            before = prior.get("cpu_ms")
            after = row.get("cpu_ms")
            if _is_int(before) and _is_int(after):
                percent = (after - before) / wall_ms * 100.0
        row["cpu_percent"] = percent
        role = row.get("role")
        if role in lost_roles or percent is None:
            if previous is not None:
                by_role[role] = None
            continue
        if by_role.get(role) is None and role in by_role:
            continue
        by_role[role] = (by_role.get(role) or 0) + percent
    if lost or previous is None:
        return None, by_role
    percents = [row.get("cpu_percent") for row in processes]
    if any(percent is None for percent in percents):
        return None, by_role
    if not percents:
        return None, by_role
    return sum(percents), by_role


def _gap(rss_bytes, cgroup_bytes):
    if not _is_int(rss_bytes) or not _is_int(cgroup_bytes):
        return NOT_AVAILABLE, NOT_AVAILABLE
    gap = abs(cgroup_bytes - rss_bytes)
    threshold = max(_GAP_BYTES, int(0.25 * max(cgroup_bytes, rss_bytes)))
    return gap, gap > threshold


class _SyncFacade:
    """Sync stand-in filled from one awaited prefetch. Accounting stays in ResourceSampler."""

    def __init__(self):
        self.send_results = {}
        self.send_errors = {}
        self.eval_result = None
        self.eval_error = None
        self.events_result = None
        self.events_error = None

    def send(self, method, params=None):
        if method in self.send_errors:
            raise self.send_errors[method]
        if method not in self.send_results:
            raise AssertionError(method)
        return self.send_results[method]

    def evaluate(self, expression):
        if self.eval_error is not None:
            raise self.eval_error
        return self.eval_result

    def events(self, method):
        if self.events_error is not None:
            raise self.events_error
        return self.events_result


_WORKER_ATTACH_FILTER = (
    {"type": "service_worker"},
    {"type": "worker"},
    {"type": "shared_worker"},
)


def _callable_attr(owner, name):
    """Read an attribute. A missing frame on a service worker is absence, not a crash.

    Playwright raises ``Service Worker requests do not have an associated frame``
    from the ``frame`` property. That request is still a worker transfer.
    """
    try:
        value = getattr(owner, name, None)
    except Exception:
        return None
    if not callable(value):
        return value
    try:
        return value()
    except Exception:
        return None


def _sizes_wire(sizes):
    """Wire bytes from Playwright ``request.sizes()``.

    CDP ``encodedDataLength`` is the header length plus the encoded body.
    Python names the same fields ``response_headers_size`` and
    ``response_body_size``.
    """
    if not isinstance(sizes, dict):
        return None
    headers = sizes.get("responseHeadersSize", sizes.get("response_headers_size"))
    body = sizes.get("responseBodySize", sizes.get("response_body_size"))
    if not _is_int(headers) or not _is_int(body) or headers < 0 or body < 0:
        return None
    return headers + body


class AsyncResourceSampler(ResourceSampler):
    """Same phase contract as ``ResourceSampler`` for an async page and CDP session.

    ``mark(phase)`` samples and leaves ``phase`` active. ``totals(phase)`` requires
    the phase. ``series()`` is synchronous. Transport waits happen before the
    shared sync accounting path runs.

    Call ``install`` before navigation. A session that already has ``events()``
    keeps that transport. Native Playwright ``CDPSession`` has no ``events()``;
    ``install`` listens with ``on``, requires browser ``Target.setAutoAttach``
    ``flatten: true``, and feeds the same ``account_network`` core. Worker and
    service-worker bodies come from ``requestfinished`` ``sizes()``.
    """

    def __init__(self, run, page, cdp, **kwargs):
        self._async_page = page
        self._async_cdp = cdp
        self._transport_ready = False
        self._event_buffer = None
        self._pending = set()
        self._request_state = {}
        self._seen_native = set()
        self._encoded_missing = False
        self._worker_observation = "ok"
        self._worker_reason = None
        super().__init__(run, _SyncFacade(), _SyncFacade(), **kwargs)

    async def install(self):
        """Subscribe before the first navigation. Idempotent."""
        if self._transport_ready:
            return
        if hasattr(self._async_cdp, "events"):
            self._transport_ready = True
            return
        await self._install_native()
        self._transport_ready = True

    async def mark(self, phase):
        self._phase = phase
        return await self.sample()

    async def sample(self, record=True):
        await self._prefetch()
        return super().sample(record=record)

    async def sample_after_gc(self):
        try:
            await self._async_cdp.send("HeapProfiler.collectGarbage")
        except Exception:
            return None
        return await self.sample(record=False)

    def _note_native(self, method, params, target_type):
        if not isinstance(params, dict):
            return
        request_id = params.get("requestId")
        if request_id is None:
            return
        if method == "Network.responseReceived":
            response = params.get("response") or {}
            self._request_state[request_id] = {
                "fromDiskCache": bool(response.get("fromDiskCache")),
                "fromServiceWorker": bool(response.get("fromServiceWorker")),
                "targetType": target_type,
            }
            return
        if method == "Network.dataReceived":
            prior = dict(self._request_state.get(request_id) or {})
            added = params.get("dataLength")
            body = added if _is_int(added) else 0
            prior["sawDecoded"] = True
            prior["decodedBodyBytes"] = int(prior.get("decodedBodyBytes") or 0) + body
            prior["targetType"] = prior.get("targetType") or target_type
            self._request_state[request_id] = prior
            return
        if method != "Network.loadingFinished" or request_id in self._seen_native:
            return
        self._seen_native.add(request_id)
        if not _is_int(params.get("encodedDataLength")) or "encodedDataLength" not in params:
            self._encoded_missing = True
            return
        prior = self._request_state.get(request_id) or {}
        row = {
            "requestId": request_id,
            "encodedDataLength": params["encodedDataLength"],
            "fromDiskCache": bool(prior.get("fromDiskCache")),
            "fromServiceWorker": bool(prior.get("fromServiceWorker")),
            "targetType": target_type or prior.get("targetType") or "page",
        }
        if prior.get("sawDecoded"):
            row["decodedBodyBytes"] = prior.get("decodedBodyBytes")
        self._event_buffer.append(row)

    def _fail_workers(self, reason="worker_targets_unobserved"):
        self._worker_observation = "failed"
        self._worker_reason = reason

    async def _install_native(self):
        cdp = self._async_cdp
        self._event_buffer = []
        self._request_state = {}
        self._seen_native = set()
        self._encoded_missing = False
        self._worker_observation = "ok"
        self._worker_reason = None
        if not hasattr(cdp, "on"):
            self._fail_workers("cdp_events_unavailable")
            return
        for method in ("Network.responseReceived", "Network.dataReceived", "Network.loadingFinished"):
            cdp.on(method, lambda params, method=method: self._note_native(method, params, "page"))
        try:
            await cdp.send("Network.enable")
        except Exception:
            self._fail_workers("cdp_events_unavailable")
            return
        await self._attach_browser_workers()
        self._listen_worker_requests()

    async def _attach_browser_workers(self):
        """Browser auto-attach only accepts the flatten protocol."""
        page = self._async_page
        context = getattr(page, "context", None)
        browser = getattr(context, "browser", None) if context is not None else None
        if callable(browser):
            browser = _callable_attr(context, "browser")
        opener = getattr(browser, "new_browser_cdp_session", None) if browser is not None else None
        if opener is None:
            self._fail_workers()
            return
        try:
            session = opener()
            if hasattr(session, "__await__"):
                session = await session
            if hasattr(session, "on"):
                session.on("Target.attachedToTarget", self._on_browser_attached)
            await session.send("Target.setAutoAttach", {
                "autoAttach": True,
                "waitForDebuggerOnStart": False,
                "flatten": True,
                "filter": list(_WORKER_ATTACH_FILTER),
            })
            try:
                await session.send("Target.setDiscoverTargets", {"discover": True})
            except Exception:
                pass
        except Exception:
            self._fail_workers()

    def _on_browser_attached(self, event):
        """Flattened child sessions are not visible on the Python CDP object.

        Bytes for those targets are taken from ``requestfinished`` instead.
        A failed attach still refuses the numeric total.
        """
        if not isinstance(event, dict):
            return
        info = event.get("targetInfo") or {}
        if info.get("type") not in ("service_worker", "worker", "shared_worker"):
            return

    def _listen_worker_requests(self):
        page = self._async_page
        context = getattr(page, "context", None)
        if context is not None and hasattr(context, "on"):
            context.on("requestfinished", self._on_request_finished)
            context.on("serviceworker", lambda worker: None)
        if hasattr(page, "on"):
            page.on("worker", lambda worker: None)

    def _is_worker_request(self, request):
        worker = _callable_attr(request, "service_worker")
        frame = _callable_attr(request, "frame")
        if worker is not None:
            return True
        return frame is None

    def _on_request_finished(self, request):
        try:
            if self._event_buffer is None or not self._is_worker_request(request):
                return
            task = asyncio.create_task(self._absorb_worker_request(request))
        except Exception:
            self._fail_workers()
            return
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _absorb_worker_request(self, request):
        try:
            sizes = request.sizes()
            if hasattr(sizes, "__await__"):
                sizes = await sizes
        except Exception:
            self._fail_workers()
            return
        wire = _sizes_wire(sizes)
        if wire is None:
            self._encoded_missing = True
            return
        guid = getattr(request, "_guid", None)
        if guid is None:
            guid = getattr(request, "guid", None)
        self._event_buffer.append({
            "requestId": guid if guid is not None else "sw-%s" % id(request),
            "encodedDataLength": wire,
            "targetType": "service_worker",
        })

    def _native_payload(self):
        events = list(self._event_buffer or [])
        if self._encoded_missing:
            events.append({"requestId": "encoded-length-missing"})
        if self._worker_observation != "ok":
            return {
                "worker_observation": "failed",
                "worker_observation_reason": self._worker_reason or "worker_targets_unobserved",
                "events": events,
            }
        return {"worker_observation": "ok", "events": events}

    async def _prefetch(self):
        if not self._transport_ready:
            await self.install()
        if self._pending:
            await asyncio.gather(*list(self._pending))
        page = self.page
        cdp = self.cdp
        cdp.send_results = {}
        cdp.send_errors = {}
        methods = ["Performance.getMetrics", "Runtime.getHeapUsage"]
        if not self._enabled:
            methods = ["Performance.enable", "Network.enable", *methods]
        for method in methods:
            try:
                cdp.send_results[method] = await self._async_cdp.send(method)
            except Exception as exc:
                cdp.send_errors[method] = exc
        try:
            page.eval_result = await self._async_page.evaluate(PAGE_SNAPSHOT_JS)
            page.eval_error = None
        except Exception as exc:
            page.eval_error = exc
        if self._event_buffer is None:
            try:
                cdp.events_result = await self._async_cdp.events("Network.loadingFinished")
                cdp.events_error = None
            except Exception as exc:
                cdp.events_error = exc
        else:
            cdp.events_result = self._native_payload()
            cdp.events_error = None
