"""Process-tree RSS sampling on a host without smaps or cgroups.

``perf/runner/memory.py`` validates the Linux shape of a memory sample: RSS,
PSS and USS from ``smaps_rollup`` plus cgroup v2 ``memory.current`` and
``memory.peak``.  Darwin has none of those.  There is no ``/proc``, no
``smaps_rollup`` and no cgroup v2, so the only per-process figure the host
exposes is ``ps -Ao pid=,ppid=,rss=``: a resident-set size in 1024-byte blocks.

This module walks the process tree with ``ps`` and refuses to invent what it
cannot read.  Every sample names ``method: "ps_rss_sum"`` and its ``platform``;
``pss_bytes``, ``uss_bytes``, ``cgroup_current_bytes`` and
``cgroup_peak_bytes`` are ``None`` -- absent, never zero -- and
``validate_tree_sample`` rejects a sample that claims smaps or cgroup numbers
under this method, or any smaps/cgroup claim on darwin.  RSS counts a shared
page once per process, so a tree total over-counts; callers must repeat that in
their evidence field instead of presenting the total as PSS.
"""

from __future__ import annotations

import os
import platform
import subprocess
import time

PS_COMMAND = ("ps", "-Ao", "pid=,ppid=,rss=")
PS_FIELDS = ("pid", "ppid", "rss_kb")
UNAVAILABLE_ON_PS = ("pss_bytes", "uss_bytes", "cgroup_current_bytes", "cgroup_peak_bytes")
METHODS = ("ps_rss_sum",)
_PS_TIMEOUT_S = 10.0


def parse_ps(text):
    """Parse ``ps -Ao pid=,ppid=,rss=`` output into rows of ints.

    Unparsable lines are skipped: a header line, a process that exited between
    the kernel snapshot and our read, or a truncated row is not a sample.
    """
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            pid, ppid, rss_kb = (int(part) for part in parts)
        except ValueError:
            continue
        if pid < 1 or ppid < 0 or rss_kb < 0:
            continue
        rows.append({"pid": pid, "ppid": ppid, "rss_kb": rss_kb})
    return rows


def tree_pids(rows, root_pid):
    """Return the pids of ``root_pid`` and its descendants, sorted.

    A missing root returns an empty list; the caller decides whether an empty
    tree is a legitimately reclaimed process or a failed sample.
    """
    children = {}
    known = set()
    for row in rows:
        known.add(row["pid"])
        children.setdefault(row["ppid"], []).append(row["pid"])
    if root_pid not in known:
        return []
    seen = {root_pid}
    queue = [root_pid]
    while queue:
        parent = queue.pop()
        for child in children.get(parent, ()):
            if child in seen:
                continue
            seen.add(child)
            queue.append(child)
    return sorted(seen)


def _read_ps():
    result = subprocess.run(
        list(PS_COMMAND),
        capture_output=True,
        text=True,
        timeout=_PS_TIMEOUT_S,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("ps failed (rc=%s): %s" % (result.returncode, (result.stderr or "").strip()[:300]))
    return result.stdout or ""


def sample_process_trees(root_pids, *, ps_reader=None, platform_name=None, allow_empty=False, now_ms=None):
    """Sample the union of several process trees, counting a shared pid once.

    Two roots are the normal case for a browser lane: the editor's dev server
    and the probe that owns the browser.  Sampling the runner's own pid would
    also count the ``ps`` process this module spawns, so the caller passes the
    roots it started instead.

    ``ps_reader`` and ``platform_name`` exist so a unit test can sample a
    synthetic table without a live process; the default reads the real host.
    """
    if isinstance(root_pids, int) or not isinstance(root_pids, (list, tuple)) or not root_pids:
        raise ValueError("root_pids")
    roots = []
    for root_pid in root_pids:
        if isinstance(root_pid, bool) or not isinstance(root_pid, int) or root_pid < 1:
            raise ValueError("root_pid")
        roots.append(root_pid)
    reader = ps_reader or _read_ps
    rows = parse_ps(reader())
    pids = set()
    missing = []
    for root_pid in roots:
        found = tree_pids(rows, root_pid)
        if not found:
            missing.append(root_pid)
        pids.update(found)
    if missing and not allow_empty:
        raise ValueError("process tree is empty: pid(s) %s gone or unreadable" % (missing,))
    by_pid = {row["pid"]: row for row in rows}
    ordered = sorted(pids)
    rss_kb = sum(by_pid[pid]["rss_kb"] for pid in ordered)
    sample = {
        "method": "ps_rss_sum",
        "platform": platform_name or platform.system().lower(),
        "ps_command": " ".join(PS_COMMAND),
        "root_pid": roots[0],
        "roots": roots,
        "process_count": len(ordered),
        "rss_bytes": rss_kb * 1024,
        "pss_bytes": None,
        "uss_bytes": None,
        "cgroup_current_bytes": None,
        "cgroup_peak_bytes": None,
        "unavailable": list(UNAVAILABLE_ON_PS),
        "sampled_at_unix_ms": int(now_ms if now_ms is not None else time.time() * 1000),
        "pids": ordered,
    }
    if missing:
        sample["missing_roots"] = missing
    if not ordered:
        sample["empty_tree"] = True
        sample["empty_reason"] = "every root process exited; no process tree remains"
    validate_tree_sample(sample)
    return sample


def sample_process_tree(root_pid, *, ps_reader=None, platform_name=None, allow_empty=False, now_ms=None):
    """Sample the resident set of ``root_pid`` and every descendant."""
    if isinstance(root_pid, bool) or not isinstance(root_pid, int) or root_pid < 1:
        raise ValueError("root_pid")
    return sample_process_trees(
        [root_pid],
        ps_reader=ps_reader,
        platform_name=platform_name,
        allow_empty=allow_empty,
        now_ms=now_ms,
    )


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def validate_tree_sample(sample):
    """Reject a tree sample that cannot be what it claims to be.

    The rules are the honesty rules of C17 on this host: a method that cannot
    produce PSS/USS/cgroup numbers must leave them null, darwin has no smaps or
    cgroup at all, and an empty tree is only allowed when it was explicitly
    sampled as a reclaimed process.
    """
    if not isinstance(sample, dict):
        raise ValueError("sample must be a dict")
    for key in ("method", "platform", "ps_command"):
        value = sample.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(key)
    if sample["method"] not in METHODS:
        raise ValueError("unknown method %r" % (sample["method"],))
    if sample["method"] == "ps_rss_sum":
        for key in UNAVAILABLE_ON_PS:
            if sample.get(key) is not None:
                raise ValueError("%s cannot be produced by ps; refusing a claimed value" % (key,))
    if sample["platform"] == "darwin":
        if sample["method"] != "ps_rss_sum":
            raise ValueError("darwin has no smaps_rollup or cgroup; %s is not readable here" % (sample["method"],))
        if "smaps" in sample["ps_command"] or "cgroup" in sample["ps_command"]:
            raise ValueError("darwin sample claims smaps/cgroup input")
    for key in ("root_pid", "process_count", "rss_bytes", "sampled_at_unix_ms"):
        value = sample.get(key)
        if not _is_int(value) or value < 0:
            raise ValueError(key)
    if sample["root_pid"] < 1:
        raise ValueError("root_pid")
    if sample["sampled_at_unix_ms"] < 1:
        raise ValueError("sampled_at_unix_ms")
    if sample["rss_bytes"] % 1024:
        raise ValueError("rss_bytes: ps reports 1024-byte blocks, refusing sub-block precision")
    empty = sample.get("empty_tree") is True
    if sample["process_count"] < 1:
        if not empty:
            raise ValueError("process_count")
        if sample["rss_bytes"] != 0:
            raise ValueError("an empty tree cannot have resident bytes")
    elif sample["rss_bytes"] == 0:
        raise ValueError("a live process tree reported zero resident bytes")
    if not empty:
        pids = sample.get("pids")
        if not isinstance(pids, list) or len(pids) != sample["process_count"]:
            raise ValueError("pids")
        if any(not _is_int(pid) or pid < 1 for pid in pids):
            raise ValueError("pids")


def peak_process_tree(proc, *, interval_s=0.05, timeout_s=600.0, ps_reader=None, platform_name=None):
    """Poll ``proc``'s tree until it exits; return every sample and the peak.

    ``proc`` is a ``subprocess.Popen``.  The observed peak is a maximum over
    samples taken every ``interval_s``; a shorter spike between two reads is
    not seen and the caller must not present the figure as a true high-water
    mark.
    """
    if interval_s <= 0:
        raise ValueError("interval_s")
    started = time.monotonic()
    samples = []
    while True:
        if proc.poll() is not None and samples:
            break
        if time.monotonic() - started > timeout_s:
            raise TimeoutError("peak_process_tree: pid %s still running after %ss" % (proc.pid, timeout_s))
        if proc.poll() is not None:
            # Exited before the first read: nothing was ever resident.
            break
        try:
            samples.append(
                sample_process_tree(
                    proc.pid,
                    ps_reader=ps_reader,
                    platform_name=platform_name,
                    allow_empty=proc.poll() is not None,
                )
            )
        except ValueError:
            if proc.poll() is not None:
                break
            raise
        time.sleep(interval_s)
    exit_code = proc.wait()
    peak = max(samples, key=lambda s: s["rss_bytes"]) if samples else None
    return {
        "samples": samples,
        "observed_peak_rss_bytes": peak["rss_bytes"] if peak else None,
        "process_count_max": max((s["process_count"] for s in samples), default=0),
        "interval_ms": int(interval_s * 1000),
        "duration_ms": (time.monotonic() - started) * 1000.0,
        "exit_code": exit_code,
    }


def assert_phases_not_copied(series_by_phase):
    """Raise when every phase reports the exact same series.

    Two independently sampled phases agree exactly only when the harness wrote
    one sample into both slots.  Values can still tie by accident inside a
    single phase; identical *vectors* across every phase are the copy guard.
    """
    if not isinstance(series_by_phase, dict) or len(series_by_phase) < 2:
        raise ValueError("need at least two phases to compare")
    series = []
    for name, values in series_by_phase.items():
        if not isinstance(name, str) or not name:
            raise ValueError("phase name")
        if not isinstance(values, (list, tuple)) or not values:
            raise ValueError("phase %s has no samples" % (name,))
        series.append(tuple(values))
    if len(set(series)) == 1:
        raise ValueError("copied sample: every phase reports the same series")


def load_average():
    """Return the 1/5/15-minute load averages, or None when unreadable."""
    try:
        one, five, fifteen = os.getloadavg()
    except OSError:
        return None
    return {"1m": one, "5m": five, "15m": fifteen}
