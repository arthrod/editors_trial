#!/usr/bin/env python3
"""Browser resource lane: RAM, CPU, disk and network per editor and document size.

One fresh Chromium launch per repetition, through ``run_cli`` / ``BrowserRun``.
The dev/static server is not the editor. Resource numbers live in their own
fields. They are never written to ``samples_ms``.

Publication needs ``dedicated_publish``, 30 scheduled repetitions in each
editor/workload group of each run, at least 10 kept measurements in each of
those groups, and two distinct seeds.

C17 and C19 are endpoint levels: natural and post-GC heap, RSS/PSS/USS,
storage and profile size. They do not carry counter deltas. Those deltas
are phase quantities. The publishable ones are named ``load_cpu_ms``,
``edit_cpu_ms``, ``quiescence_cpu_ms`` (and the same prefixes for the other
counter fields) and are also on the ``phases`` map.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from perf.fixtures.docx_workload import workload_docx
from perf.fixtures.profiles import assert_workload_allowed
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS, _start_server, _stop_server
from perf.runner.browser_hosts import select_fixture
from perf.runner.browser_run import BrowserRun, run_cli, write_json
from perf.runner.resources import (
    COUNTER_DELTA_FIELDS,
    NOT_AVAILABLE,
    ResourceSampler,
    WallClock,
    classify_series,
    drive_quiescence,
)
from perf.schema import sample_budget_for_profile

RESOURCE_WORKLOADS = (
    "prose-500w",
    "prose-5kw",
    "prose-50kw",
    "prose-250kw",
    "complex-corpus",
)

EDIT_BURST = {
    "kind": "keyboard.insertText",
    "text": "B8",
    "repetitions": 8,
}

QUIESCENCE = {
    "no_longtask_s": 2.0,
    "heap_band_percent": 5.0,
    "max_wait_s": 15.0,
    "poll_s": 0.5,
}

REFUSAL_CODES = (
    "constant_series",
    "copied_series",
    "quiescence_not_reached",
    "process_tree_missing",
    "process_tree_not_launched",
    "js_heap_not_measured",
    "series_empty",
    "workload_not_on_ladder",
    "edit_not_applied",
    "process_counters_incomplete",
    "longtask_unavailable",
)

PHASES = ("load", "after_load", "edit_burst", "quiescence", "after_edits", "save_export")
NOT_APPLICABLE_ENDPOINT = "not_applicable_endpoint"
_PUBLISHABLE_PHASES = (("load", "load"), ("edit_burst", "edit"), ("quiescence", "quiescence"))
_ENDPOINT_LEVELS = ("pss_bytes", "uss_bytes", "profile_directory_bytes")
SESSION = Path(__file__).with_name("resources_session.mjs")
_META_KEYS = (
    "workload_id", "sha256", "byte_size", "paragraph_count", "word_count",
    "shape", "unicode_class", "match_count",
)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _store_fixture(run, workload_id, data):
    if hasattr(run, "fixture"):
        return Path(run.fixture(workload_id, data))
    path = Path(run.directory) / "fixtures" / ("%s.docx" % workload_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
    finally:
        os.close(fd)
    return path


def _public_meta(meta):
    return {key: meta[key] for key in _META_KEYS if key in meta}


def _refusal_code(series, *, quiescence_reached):
    if not series:
        return "series_empty"
    if any(row.get("process_tree_status") == "process_tree_not_launched" for row in series):
        return "process_tree_not_launched"
    if any(row.get("process_tree_status") == "process_tree_missing" for row in series):
        return "process_tree_missing"
    if any(not _is_int(row.get("js_heap_used_bytes")) for row in series):
        return "js_heap_not_measured"
    return classify_series(series, quiescence_reached=quiescence_reached)


def _peak(series, key):
    values = [row[key] for row in series if _is_int(row.get(key))]
    if not values:
        return NOT_AVAILABLE
    return max(values)


def _token_count(text, token):
    if not token:
        return 0
    count = 0
    start = 0
    while True:
        at = text.find(token, start)
        if at < 0:
            return count
        count += 1
        start = at + len(token)


def _burst_parts(burst):
    try:
        repetitions = int((burst or {}).get("repetitions") or 0)
    except (TypeError, ValueError):
        repetitions = 0
    return str((burst or {}).get("text") or ""), repetitions


def _delta_applied(before, after, token, repetitions):
    if repetitions <= 0 or not token:
        return False
    return _token_count(str(after), token) - _token_count(str(before), token) == repetitions


def _edit_applied(session, burst, result):
    """This burst counts only when the target gained ``repetitions`` copies of ``text``.

    A host ``edit_check`` must report the same before/after pair. Membership of
    the final text is not a witness: the tokens may already have been there.
    """
    token, repetitions = _burst_parts(burst)
    check = getattr(session, "edit_check", None)
    if callable(check):
        host = check()
        if isinstance(host, dict) and "before" in host and "after" in host:
            return _delta_applied(host.get("before"), host.get("after"), token, repetitions)
        return False
    if isinstance(result, dict) and "beforeText" in result:
        return _delta_applied(result.get("beforeText"), result.get("editorText"), token, repetitions)
    if isinstance(result, dict) and "applied" in result:
        return bool(result.get("applied"))
    text = ""
    if isinstance(result, dict) and result.get("editorText") is not None:
        text = str(result.get("editorText"))
    else:
        reader = getattr(session, "editor_text", None)
        if callable(reader):
            text = str(reader() or "")
    expected = token * repetitions
    if not expected:
        return False
    return expected in text


def _record_gc(sampler, phase):
    sample = sampler.sample_after_gc()
    heap = sample.get("js_heap_used_bytes") if isinstance(sample, dict) else NOT_AVAILABLE
    if not _is_int(heap):
        heap = NOT_AVAILABLE
    sampler.gc_heaps[phase] = heap


def _last_sample(series, phase):
    found = None
    for row in series:
        if row.get("phase") == phase:
            found = row
    return found


def _endpoint_criterion(phase_name, phase_row, series):
    """Levels only. Counter deltas are not applicable on an endpoint."""
    view = {
        key: value
        for key, value in phase_row.items()
        if key not in COUNTER_DELTA_FIELDS
    }
    for key in COUNTER_DELTA_FIELDS:
        view[key] = NOT_APPLICABLE_ENDPOINT
    last = _last_sample(series, phase_name)
    if last is not None:
        for key in _ENDPOINT_LEVELS:
            view[key] = last.get(key, NOT_AVAILABLE)
    view["phase"] = phase_name
    return view


def _named_phase_counters(phases):
    named = {}
    for phase, prefix in _PUBLISHABLE_PHASES:
        row = phases.get(phase)
        if not isinstance(row, dict):
            continue
        for key in COUNTER_DELTA_FIELDS:
            if key in row:
                named["%s_%s" % (prefix, key)] = row[key]
    return named


def assemble_trial(
    sampler, *, quiescence_reached, quiescence, edit_burst, editor_id, workload_id,
    workload_meta, execution_profile, host_class, save_phase, refusal_override=None,
):
    series = sampler.series()
    code = refusal_override or _refusal_code(series, quiescence_reached=quiescence_reached)
    phases = {}
    for phase in ("load", "after_load", "edit_burst", "quiescence", "after_edits"):
        if any(row.get("phase") == phase for row in series):
            phases[phase] = sampler.totals(phase)
    if save_phase is not None:
        phases["save_export"] = save_phase
    elif any(row.get("phase") == "save_export" for row in series):
        phases["save_export"] = sampler.totals("save_export")
    if code is None:
        for phase in phases.values():
            if isinstance(phase, dict) and phase.get("process_accounting") == "incomplete":
                code = "process_counters_incomplete"
                break
    if code is not None and code not in REFUSAL_CODES:
        raise ValueError("refusal code is not closed: %s" % (code,))
    criteria = {}
    if "after_load" in phases:
        criteria["C17"] = _endpoint_criterion("after_load", phases["after_load"], series)
    if "after_edits" in phases and "after_load" in phases:
        growth_heap = NOT_AVAILABLE
        growth_rss = NOT_AVAILABLE
        if _is_int(phases["after_edits"].get("js_heap_used_bytes")) and _is_int(phases["after_load"].get("js_heap_used_bytes")):
            growth_heap = phases["after_edits"]["js_heap_used_bytes"] - phases["after_load"]["js_heap_used_bytes"]
        if _is_int(phases["after_edits"].get("rss_bytes")) and _is_int(phases["after_load"].get("rss_bytes")):
            growth_rss = phases["after_edits"]["rss_bytes"] - phases["after_load"]["rss_bytes"]
        criteria["C19"] = _endpoint_criterion("after_edits", phases["after_edits"], series)
        criteria["C19"]["growth_js_heap_used_bytes"] = growth_heap
        criteria["C19"]["growth_rss_bytes"] = growth_rss
    gc_heaps = getattr(sampler, "gc_heaps", None) or {}
    if "C17" in criteria and "after_load" in gc_heaps:
        criteria["C17"]["js_heap_used_bytes_after_gc"] = gc_heaps["after_load"]
    if "C19" in criteria and ("after_load" in gc_heaps or "after_edits" in gc_heaps):
        before_gc = gc_heaps.get("after_load", NOT_AVAILABLE)
        after_gc = gc_heaps.get("after_edits", NOT_AVAILABLE)
        criteria["C19"]["js_heap_used_bytes_after_gc"] = after_gc
        if _is_int(before_gc) and _is_int(after_gc):
            criteria["C19"]["retained_growth_js_heap_bytes"] = after_gc - before_gc
            criteria["C19"]["retained_growth_refusal"] = None
        else:
            criteria["C19"]["retained_growth_js_heap_bytes"] = NOT_AVAILABLE
            criteria["C19"]["retained_growth_refusal"] = "gc_unsupported"
    meta = workload_meta or {}
    static_server = series[-1]["static_server"] if series else {
        "pid": getattr(sampler.run, "static_server_pid", None),
        "counted_as_editor": False,
        "note": "The dev/static server is not the editor.",
    }
    return {
        "record_kind": "browser_resources",
        "editor_id": editor_id,
        "workload_id": workload_id,
        "outcome": "refused" if code else "measured",
        "refusal_code": code,
        "failure_reason": code,
        "execution_profile": execution_profile,
        "host_class": host_class,
        "platform": sampler.platform_name,
        "fresh_launch": True,
        "fixture_sha256": meta.get("sha256"),
        "fixture_byte_size": meta.get("byte_size"),
        "fixture_paragraph_count": meta.get("paragraph_count"),
        "word_count": meta.get("word_count"),
        "edit_burst": dict(edit_burst),
        "quiescence": {**dict(quiescence), "reached": bool(quiescence_reached)},
        "static_server": static_server,
        "phases": phases,
        **_named_phase_counters(phases),
        "criteria": criteria,
        "peak_ram_bytes": _peak(series, "rss_bytes"),
        "peak_js_heap_used_bytes": _peak(series, "js_heap_used_bytes"),
        "profile_directory_baseline": "before_load",
        "profile_directory_bytes_before": series[0]["profile_directory_bytes"] if series else NOT_AVAILABLE,
        "profile_directory_bytes_before_load": series[0]["profile_directory_bytes"] if series else NOT_AVAILABLE,
        "profile_directory_bytes_after": series[-1]["profile_directory_bytes"] if series else NOT_AVAILABLE,
        "profile_directory_growth_bytes": (
            series[-1]["profile_directory_bytes"] - series[0]["profile_directory_bytes"]
            if series and _is_int(series[0].get("profile_directory_bytes")) and _is_int(series[-1].get("profile_directory_bytes"))
            else NOT_AVAILABLE
        ),
        "bundle_bytes": series[-1]["bundle_bytes"] if series else NOT_AVAILABLE,
        "series": series,
        "field_sources": "perf.runner.resources.FIELD_SOURCES",
    }


def collect_phases(
    sampler, session, clock, *, quiescence, edit_burst, editor_id, workload_id,
    workload_meta, execution_profile, host_class, already_sampled=False,
):
    save_phase = {"outcome": "not_applicable", "reason": "host_has_no_save"}
    reached = True
    refusal_override = None
    if not already_sampled:
        # Same settle before C17 and before C19. The natural sample is the
        # endpoint. A forced GC sample is labelled and kept out of the series.
        try:
            sampler.mark("load")
            session.load()
            sampler.sample()
            sampler.mark("after_load")
            after_load = getattr(session, "after_load", None)
            if after_load is not None:
                after_load()
            reached = drive_quiescence(sampler, clock, quiescence)
            if not reached:
                if getattr(sampler, "quiescence_block", None) == "longtask_unavailable":
                    refusal_override = "longtask_unavailable"
            else:
                sampler.sample()
                _record_gc(sampler, "after_load")
                sampler.mark("edit_burst")
                edited = session.edit(edit_burst)
                sampler.sample()
                if not _edit_applied(session, edit_burst, edited):
                    refusal_override = "edit_not_applied"
                else:
                    after_edits = getattr(session, "after_edits", None)
                    if after_edits is not None:
                        after_edits()
                    sampler.mark("quiescence")
                    reached = drive_quiescence(sampler, clock, quiescence)
                    if not reached:
                        if getattr(sampler, "quiescence_block", None) == "longtask_unavailable":
                            refusal_override = "longtask_unavailable"
                    else:
                        sampler.mark("after_edits")
                        _record_gc(sampler, "after_edits")
                        if getattr(session, "has_save", False):
                            sampler.mark("save_export")
                            session.save()
                            sampler.sample()
                            save_phase = None
        finally:
            close = getattr(session, "close", None)
            if close is not None:
                close()
    return assemble_trial(
        sampler,
        quiescence_reached=reached,
        quiescence=quiescence,
        edit_burst=edit_burst,
        editor_id=editor_id,
        workload_id=workload_id,
        workload_meta=workload_meta,
        execution_profile=execution_profile,
        host_class=host_class,
        save_phase=save_phase,
        refusal_override=refusal_override,
    )


def _early_refusal(*, editor_id, workload_id, code, execution_profile, host_class):
    if code not in REFUSAL_CODES:
        raise ValueError(code)
    return {
        "record_kind": "browser_resources",
        "editor_id": editor_id,
        "workload_id": workload_id,
        "outcome": "refused",
        "refusal_code": code,
        "failure_reason": code,
        "execution_profile": execution_profile,
        "host_class": host_class,
        "fresh_launch": False,
        "criteria": {},
        "series": [],
        "static_server": {
            "counted_as_editor": False,
            "note": "The dev/static server is not the editor.",
        },
    }


def measure_editor(
    *, editor_id, workload_id, run, execution_profile, host_class,
    session_factory=None, clock=None, quiescence=None, platform_name=None,
):
    """One fresh launch of ``editor_id`` on ``workload_id``."""
    quiescence = dict(QUIESCENCE if quiescence is None else quiescence)
    if workload_id not in RESOURCE_WORKLOADS:
        return _early_refusal(
            editor_id=editor_id, workload_id=workload_id, code="workload_not_on_ladder",
            execution_profile=execution_profile, host_class=host_class,
        )
    try:
        assert_workload_allowed(execution_profile, workload_id)
    except ValueError:
        return _early_refusal(
            editor_id=editor_id, workload_id=workload_id, code="workload_not_on_ladder",
            execution_profile=execution_profile, host_class=host_class,
        )
    meta = workload_docx(workload_id, REPO)
    fixture = _store_fixture(run, workload_id, meta["docx"])
    public = _public_meta(meta)
    ctx = {
        "editor_id": editor_id,
        "workload_id": workload_id,
        "workload_meta": public,
        "fixture_path": str(fixture),
        "execution_profile": execution_profile,
        "host_class": host_class,
        "edited": None,
        "run": run,
    }
    factory = session_factory or live_session_factory
    session = factory(ctx)
    launch = getattr(session, "launch", None)
    if launch is not None:
        launch(run)
    run.editor_browser_pid = getattr(session, "browser_pid", None)
    run.static_server_pid = getattr(session, "server_pid", None)
    if getattr(session, "bundle_bytes", None) is not None:
        run.bundle_bytes = session.bundle_bytes
    if getattr(session, "profile_dir", None) is not None:
        run.profile_dir = session.profile_dir
    if getattr(session, "bundle_path", None) is not None:
        run.bundle_path = session.bundle_path
    reader = getattr(session, "process_reader", None)
    sampler = ResourceSampler(
        run,
        session.page,
        session.cdp,
        process_reader=reader,
        platform_name=platform_name,
        clock=clock or WallClock(),
    )
    trial = collect_phases(
        sampler,
        session,
        sampler.clock,
        quiescence=quiescence,
        edit_burst=EDIT_BURST,
        editor_id=editor_id,
        workload_id=workload_id,
        workload_meta=public,
        execution_profile=execution_profile,
        host_class=host_class,
    )
    ctx["edited"] = dict(EDIT_BURST)
    return trial


def _measured_groups(cells):
    """Every editor/workload that appears, counted by measured cells only.

    A failed group stays in the map at zero. Skipping non-measured cells would
    drop that group and let the other editor publish alone.
    """
    groups = {}
    for cell in cells:
        key = (cell.get("editor_id"), cell.get("workload_id"))
        groups.setdefault(key, 0)
        if cell.get("outcome") == "measured":
            groups[key] += 1
    return groups


def _scheduled_groups(cells):
    """Cells attempted per editor/workload, measured or not."""
    groups = {}
    for cell in cells:
        key = (cell.get("editor_id"), cell.get("workload_id"))
        groups[key] = groups.get(key, 0) + 1
    return groups


def _min_group_scheduled(cells):
    groups = _scheduled_groups(cells)
    if not groups:
        return 0
    return min(groups.values())


def publication_verdict(cells, *, seeds, scheduled, execution_profile, host_class):
    """``scheduled`` is the smallest editor/workload group. n >= 10 measured. Two seeds."""
    reasons = []
    if execution_profile != "dedicated_publish":
        reasons.append("execution_profile_not_dedicated_publish")
    if host_class not in ("dedicated", "shared_guarded"):
        reasons.append("host_class_not_publishable")
    if scheduled < 30:
        reasons.append("scheduled_below_30")
    groups = _measured_groups(cells)
    if not groups or any(count < 10 for count in groups.values()):
        reasons.append("kept_below_10")
    distinct = []
    for seed in seeds:
        if seed not in distinct:
            distinct.append(seed)
    if len(distinct) < 2:
        reasons.append("second_seed_required")
    return {
        "publishable": not reasons,
        "publication_block_reasons": reasons,
        "scheduled": scheduled,
        "kept": sum(groups.values()) if groups else 0,
        "seeds": distinct,
    }


def _companion_successful(summary, cells):
    """A companion is a measurement run, not a pair-gate flag.

    ``summary.publishable`` is the pair gate. The first seed is unpublished
    until the second seed exists, so requiring that flag deadlocks the pair.
    """
    if not isinstance(summary, dict):
        return False
    if summary.get("failure_reason"):
        return False
    if summary.get("outcome") == "failed":
        return False
    return any(cell.get("outcome") == "measured" for cell in cells)


def _provenance(profile, host_class, cells, hosts):
    fixtures = tuple(sorted({
        (cell.get("editor_id"), cell.get("workload_id"), cell.get("fixture_sha256"))
        for cell in cells
        if cell.get("outcome") == "measured"
    }))
    trees = []
    if isinstance(hosts, dict):
        for editor, info in hosts.items():
            if isinstance(info, dict) and info.get("tree_sha256"):
                trees.append((editor, info.get("tree_sha256")))
    return (profile, host_class, fixtures, tuple(sorted(trees)))


def _provenance_incomplete(cells, hosts):
    editors = set()
    for cell in cells:
        if cell.get("outcome") != "measured":
            continue
        editors.add(cell.get("editor_id"))
        if not cell.get("fixture_sha256"):
            return True
    present = {}
    if isinstance(hosts, dict):
        for editor, info in hosts.items():
            if isinstance(info, dict) and info.get("tree_sha256"):
                present[editor] = info["tree_sha256"]
    return any(editor not in present for editor in editors)


def publication_from_run(run):
    """Validate each run before pooling. Scheduled is the smaller run.

    An empty companion must not be reported as scheduled 30, and its failed
    gate must not disappear behind the primary run's measured cells.
    """
    primary_cells = _resource_cells(run.directory)
    runs = [{
        "cells": primary_cells,
        "seed": getattr(run, "seed", None),
        "profile": getattr(run, "execution_profile", None),
        "host_class": getattr(run, "host_class", None),
        "hosts": getattr(run, "hosts", None) or {},
        "summary": None,
    }]
    extra = []
    companion = getattr(run, "companion_summary", None)
    if companion:
        try:
            other = json.loads(Path(companion).read_text())
        except (OSError, json.JSONDecodeError):
            other = None
        if not isinstance(other, dict):
            other = {}
            other_cells = []
            extra.append("companion_not_successful")
        else:
            other_cells = _resource_cells(Path(companion).parent)
            if not _companion_successful(other, other_cells):
                extra.append("companion_not_successful")
        runs.append({
            "cells": other_cells,
            "seed": other.get("seed"),
            "profile": other.get("execution_profile"),
            "host_class": other.get("host_class"),
            "hosts": other.get("hosts") if isinstance(other.get("hosts"), dict) else {},
            "summary": other,
        })
        if _provenance(runs[0]["profile"], runs[0]["host_class"], primary_cells, runs[0]["hosts"]) != _provenance(
            runs[1]["profile"], runs[1]["host_class"], other_cells, runs[1]["hosts"],
        ):
            extra.append("companion_provenance_mismatch")
        if _provenance_incomplete(primary_cells, runs[0]["hosts"]) or _provenance_incomplete(other_cells, runs[1]["hosts"]):
            extra.append("provenance_incomplete")
    elif _provenance_incomplete(primary_cells, runs[0]["hosts"]):
        extra.append("provenance_incomplete")
    for item in runs:
        scheduled_groups = _scheduled_groups(item["cells"])
        measured = _measured_groups(item["cells"])
        if not scheduled_groups or any(count < 30 for count in scheduled_groups.values()):
            if "scheduled_below_30" not in extra:
                extra.append("scheduled_below_30")
        if not measured or any(count < 10 for count in measured.values()):
            if "kept_below_10" not in extra:
                extra.append("kept_below_10")
    cells = []
    seeds = []
    scheduled_runs = []
    for item in runs:
        cells.extend(item["cells"])
        if item["seed"] is not None and item["seed"] not in seeds:
            seeds.append(item["seed"])
        scheduled_runs.append(_min_group_scheduled(item["cells"]))
    scheduled = min(scheduled_runs) if scheduled_runs else 0
    verdict = publication_verdict(
        cells,
        seeds=seeds,
        scheduled=scheduled,
        execution_profile=run.execution_profile,
        host_class=run.host_class,
    )
    for reason in extra:
        if reason not in verdict["publication_block_reasons"]:
            verdict["publication_block_reasons"].append(reason)
    verdict["publishable"] = not verdict["publication_block_reasons"]
    return verdict


def _resource_cells(directory):
    root = Path(directory) / "cells"
    if not root.is_dir():
        return []
    cells = []
    for path in sorted(root.glob("*/resource.json")):
        cells.append(json.loads(path.read_text()))
    return cells


class ResourceRun(BrowserRun):
    def finish(self, summary):
        publication = publication_from_run(self)
        merged = {**summary, "resource_publication": publication}
        if not publication["publishable"]:
            merged["publishable"] = False
            merged["publication_block_reason"] = "; ".join(publication["publication_block_reasons"])
        return super().finish(merged)


def _free_port():
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _target_copy(editor_id):
    base = BROWSER_TARGETS[editor_id]
    target = dict(base)
    if "command" in target:
        target["command"] = list(target["command"])
    parts = urlsplit(target["url"])
    port = _free_port()
    host = parts.hostname or "127.0.0.1"
    target["url"] = urlunsplit((parts.scheme, "%s:%d" % (host, port), parts.path, parts.query, parts.fragment))
    return target


class _Bridge:
    def __init__(self, proc, errors):
        self.proc = proc
        self.errors = errors
        self._id = 0
        self._lock = threading.Lock()

    def request(self, method, params=None, timeout=180):
        import time
        with self._lock:
            self._id += 1
            ident = self._id
            line = json.dumps({"id": ident, "method": method, "params": params or {}})
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
            deadline = time.time() + timeout
            while time.time() < deadline:
                raw = self.proc.stdout.readline()
                if raw == "":
                    tail = "".join(self.errors)[-800:]
                    raise RuntimeError("resource session closed: %s" % tail)
                message = json.loads(raw)
                if message.get("id") != ident:
                    continue
                if message.get("error"):
                    raise RuntimeError(message["error"])
                return message.get("result")
            raise TimeoutError(method)


class _BridgePage:
    def __init__(self, bridge):
        self._bridge = bridge

    def evaluate(self, expression):
        return self._bridge.request("evaluate", {"expression": expression}, timeout=60)


class _BridgeCdp:
    def __init__(self, bridge):
        self._bridge = bridge

    def send(self, method, params=None):
        return self._bridge.request("cdp", {"method": method, "params": params or {}}, timeout=60)

    def events(self, method):
        return self._bridge.request("events", {"method": method}, timeout=30)


class LiveSession:
    """Playwright session for one editor launch. The static server is separate."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.has_save = False
        self.browser_pid = None
        self.server_pid = None
        self.profile_dir = None
        self.bundle_path = None
        self.bundle_bytes = None
        self.page = None
        self.cdp = None
        self._server = None
        self._proc = None
        self._bridge = None
        self._target = None

    def launch(self, run):
        editor_id = self.ctx["editor_id"]
        target = _target_copy(editor_id)
        select_fixture(target, Path(self.ctx["fixture_path"]))
        self._target = target
        self._server = _start_server(editor_id, target)
        self.server_pid = os.getpid()
        profile = Path(run.directory) / "profiles" / editor_id / uuid.uuid4().hex
        profile.mkdir(parents=True, exist_ok=True)
        self.profile_dir = profile
        host_meta = run.hosts.get(editor_id) or {}
        if host_meta.get("build_directory"):
            self.bundle_path = host_meta["build_directory"]
        node = shutil.which("node") or "node"
        errors = []
        proc = subprocess.Popen(
            [node, str(SESSION)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        threading.Thread(target=_drain, args=(proc.stderr, errors), daemon=True).start()
        self._proc = proc
        self._bridge = _Bridge(proc, errors)
        ready_js = target.get("ready_js") or ""
        wait_ms = int(target.get("wait_after_ready") or 0)
        result = self._bridge.request("launch", {
            "url": target["url"],
            "profileDir": str(profile),
            "corpusPath": self.ctx["fixture_path"],
            "corpusRoute": target.get("corpus_route") or "/corpus.docx",
            "readySelector": target.get("ready_selector") or "",
            "readyJs": ready_js,
            "waitAfterReadyMs": wait_ms,
            "editSelector": target.get("edit_selector") or "",
            "saveSelector": target.get("save_selector") or "",
        })
        self.browser_pid = result.get("browserPid")
        self.has_save = bool(target.get("save_selector"))
        self.page = _BridgePage(self._bridge)
        self.cdp = _BridgeCdp(self._bridge)

    def load(self):
        self._bridge.request("load", timeout=180)

    def edit(self, burst):
        params = {
            "selector": (self._target or {}).get("edit_selector") or "",
            "text": burst["text"],
            "repetitions": burst["repetitions"],
        }
        check_js = (self._target or {}).get("check_js") or ""
        if check_js:
            params["checkJs"] = check_js
        return self._bridge.request("edit", params, timeout=60)

    def save(self):
        self._bridge.request("save", {"selector": (self._target or {}).get("save_selector") or ""}, timeout=60)

    def close(self):
        if self._bridge is not None and self._proc is not None and self._proc.poll() is None:
            try:
                self._bridge.request("close", timeout=30)
            except Exception:
                pass
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._server is not None:
            _stop_server(self._server)
            self._server = None


def _drain(stream, sink):
    for line in stream:
        sink.append(line)


def live_session_factory(ctx):
    return LiveSession(ctx)


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--editors", nargs="*", default=list(BROWSER_TARGETS))
    parser.add_argument("--out-root", default=None)
    parser.add_argument("--workload", default="prose-500w")
    parser.add_argument("--list-support", action="store_true")
    parser.add_argument("--companion-summary", default=None)
    args = parser.parse_args()
    if args.list_support:
        for editor_id in BROWSER_TARGETS:
            print("%s workloads=%s" % (editor_id, ",".join(RESOURCE_WORKLOADS)))
        return 0
    from perf.runner.browser_run import ACTIVE
    run = ACTIVE.get()
    editor_id = (args.editors or [None])[0]
    if run is not None and args.companion_summary:
        run.companion_summary = args.companion_summary
    out = Path(args.out_root) if args.out_root else REPO / "perf" / "out" / "resources"
    out.mkdir(parents=True, exist_ok=True)
    try:
        trial = measure_editor(
            editor_id=editor_id,
            workload_id=args.workload,
            run=run,
            execution_profile=run.execution_profile if run is not None else "ci_broad",
            host_class=run.host_class if run is not None else "ci_coarse",
            session_factory=getattr(run, "session_factory", None),
            clock=WallClock(),
            quiescence=QUIESCENCE,
        )
    except Exception as exc:
        trial = {
            "record_kind": "browser_resources",
            "editor_id": editor_id,
            "workload_id": args.workload,
            "outcome": "failed",
            "refusal_code": None,
            "failure_reason": "%s: %s" % (type(exc).__name__, exc),
        }
    write_json(out / "resource.json", trial)
    if trial.get("outcome") == "refused":
        write_json(out / "refusal.json", {
            "outcome": "refused",
            "refusal_code": trial.get("refusal_code"),
            "failure_reason": trial.get("refusal_code") or "refused",
        })
    elif trial.get("outcome") == "failed":
        write_json(out / "failure.json", {
            "outcome": "failed",
            "failure_reason": trial.get("failure_reason") or "resource_lane_failed",
        })
    return 0


def main():
    return run_cli(
        _main,
        "benchmark_resources",
        BROWSER_TARGETS,
        run_factory=ResourceRun,
        max_repetitions=lambda profile: sample_budget_for_profile(profile, "fresh_process"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
