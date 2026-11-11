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

from perf.fixtures.docx_workload import workload_for_lane
from perf.fixtures.profiles import assert_workload_allowed
from perf.runner.benchmark_input import CANVAS_HOSTS
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS, _start_server, _stop_server
from perf.runner.browser_hosts import select_fixture
from perf.runner.browser_run import BrowserRun, run_cli, write_json
from perf.runner.benchmark_document import (
    content_gate_record,
    content_meta_for_workload,
    gate_length_check_for,
)
from perf.runner.resources import (
    COUNTER_DELTA_FIELDS,
    NOT_AVAILABLE,
    ResourceSampler,
    WallClock,
    classify_series,
    drive_quiescence,
    withheld_marker,
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
    "kind": "keyboard.type",
    "text": "B8",
    "repetitions": 8,
}

# The measured browser-tree CPU interval is keyboard.type plus this settle.
# Focus/model preparation and all verification happen outside it.
EDIT_PRE_TYPE_SETTLE_MS = 300
EDIT_SETTLE_MS = 500
EDIT_ORACLE_POLL_BOUND_MS = 10000
EDIT_ORACLE_POLL_INTERVAL_MS = 50

PAINT_INK_EDITORS = frozenset(CANVAS_HOSTS) | frozenset({"wordcraft", "superdoc"})


def _edit_witness(editor_id: str) -> dict:
    if editor_id == "canvas":
        return {"mode": "canvas_model"}
    if editor_id in PAINT_INK_EDITORS:
        return {"mode": "paint_ink"}
    return {"mode": "dom_text"}

QUIESCENCE = {
    "no_longtask_s": 2.0,
    "heap_band_percent": 5.0,
    "max_wait_s": 30.0,
    "poll_s": 0.5,
}

REFUSAL_CODES = (
    "constant_series",
    "copied_series",
    "process_tree_missing",
    "process_tree_not_launched",
    "js_heap_not_measured",
    "series_empty",
    "workload_not_on_ladder",
    "edit_not_applied",
    "editor_load_failed",
    "editor_crashed",
    "process_counters_incomplete",
    "longtask_unavailable",
)

PHASES = ("load", "after_load", "edit_burst", "quiescence", "after_edits", "save_export")
NOT_APPLICABLE_ENDPOINT = "not_applicable_endpoint"
_PUBLISHABLE_PHASES = (
    ("load", "load"), ("after_load", "open_settle"), ("edit_burst", "edit"), ("quiescence", "quiescence"),
)
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


def _edit_oracle(result):
    """Compact, serializable evidence for the oracle used by one edit."""
    if not isinstance(result, dict):
        return {"mode": "not_run", "status": "not_run", "reason": "edit_not_run"}
    oracle = result.get("oracle")
    if isinstance(oracle, dict):
        return dict(oracle)
    return {
        "mode": result.get("witness") or "unknown",
        "witness_mode": result.get("witness") or "unknown",
        "status": "verified" if result.get("applied") else "edit_not_applied",
        "reason": None if result.get("applied") else "legacy_edit_not_applied",
        "model_hook": None,
        "trusted_keys": result.get("trusted_keys"),
        "expected_text_delta": None,
        "text_delta": None,
    }


def _edit_applied(session, burst, result):
    """This burst counts only when the target gained ``repetitions`` copies of ``text``.

    A host ``edit_check`` must report the same before/after pair. Membership of
    the final text is not a witness: the tokens may already have been there.
    A structured oracle is recomputed here rather than trusted by its flag.
    """
    token, repetitions = _burst_parts(burst)
    oracle = result.get("oracle") if isinstance(result, dict) else None
    if isinstance(oracle, dict):
        if oracle.get("status") != "verified":
            return False
        expected = oracle.get("expected_text_delta")
        delta = oracle.get("text_delta")
        keys = oracle.get("trusted_keys")
        min_keys = len(token) * repetitions
        if all(_is_int(value) for value in (expected, delta, keys)):
            return expected == repetitions and delta == repetitions and keys >= min_keys
        return bool(result.get("applied"))
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


def _named_phase_counters(phases, *, include_edit_cpu=True):
    named = {}
    for phase, prefix in _PUBLISHABLE_PHASES:
        row = phases.get(phase)
        if not isinstance(row, dict):
            continue
        for key in COUNTER_DELTA_FIELDS:
            if prefix == "edit" and not include_edit_cpu and key in ("cpu_ms", "renderer_cpu_ms"):
                continue
            if key in row:
                named["%s_%s" % (prefix, key)] = row[key]
    return named


_EDIT_CPU_PHASE_FIELDS = (
    "cpu_ms",
    "renderer_cpu_ms",
    "task_duration_ms",
    "script_duration_ms",
    "layout_duration_ms",
    "recalc_style_duration_ms",
    "longtask_sum_ms",
)
_EDIT_CPU_SAMPLE_FIELDS = (
    "cpu_ms",
    "cpu_percent",
    "cpu_percent_by_role",
    "cgroup_cpu_usec",
    "task_duration_ms",
    "script_duration_ms",
    "layout_duration_ms",
    "recalc_style_duration_ms",
    "longtask_sum_ms",
)


def _withhold_edit_cpu(phases, series, reason):
    """Replace every numeric edit CPU path with an explicit withheld marker."""
    marker = withheld_marker(reason)
    phase = phases.get("edit_burst")
    if isinstance(phase, dict):
        for key in _EDIT_CPU_PHASE_FIELDS:
            if key in phase:
                phase[key] = dict(marker)
        for process in phase.get("processes") or []:
            if not isinstance(process, dict):
                continue
            for key in ("cpu_ms", "cpu_percent", "cpu_percent_by_role"):
                if key in process:
                    process[key] = dict(marker)
    for row in series:
        if row.get("phase") != "edit_burst":
            continue
        for key in _EDIT_CPU_SAMPLE_FIELDS:
            if key in row:
                row[key] = dict(marker)
        for process in row.get("processes") or []:
            if not isinstance(process, dict):
                continue
            for key in ("cpu_ms", "cpu_percent", "cpu_percent_by_role"):
                if key in process:
                    process[key] = dict(marker)


def assemble_trial(
    sampler, *, quiescence_reached, quiescence, edit_burst, editor_id, workload_id,
    workload_meta, execution_profile, host_class, save_phase, refusal_override=None,
    edit_oracle=None, edit_unverified=False, edit_measurement=None,
    edit_cpu_boundary=None, publish_edit_cpu=True, edit_cpu_withhold_reason=None,
    settle=None, editor_error=None,
):
    series = sampler.series()
    # A settle that hit its cap is a flag on the cell (``settle``), not a refusal.
    code = refusal_override or _refusal_code(series, quiescence_reached=True)
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
    oracle = dict(edit_oracle or {"mode": "not_run", "status": "not_run"})
    edit_unverified = bool(edit_unverified or oracle.get("status") == "edit_unverified")
    publish_edit_cpu = bool(
        publish_edit_cpu
        and not edit_unverified
        and code != "edit_not_applied"
    )
    if publish_edit_cpu and isinstance(edit_cpu_boundary, dict) and "edit_burst" in phases:
        for key in ("cpu_ms", "renderer_cpu_ms"):
            if key in edit_cpu_boundary:
                phases["edit_burst"][key] = edit_cpu_boundary[key]
        if "process_accounting" in edit_cpu_boundary:
            phases["edit_burst"]["process_accounting"] = edit_cpu_boundary["process_accounting"]
    if not publish_edit_cpu:
        reason = edit_cpu_withhold_reason or ("edit_unverified" if edit_unverified else "edit_cpu_withheld")
        _withhold_edit_cpu(phases, series, reason)
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
    content_meta = content_meta_for_workload(workload_id)
    gate_fields = content_gate_record(content_meta, gate_length_check_for(editor_id, content_meta))
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
        "fixture_variant": meta.get("fixture_variant"),
        "fixture_source_sha256": meta.get("fixture_source_sha256"),
        "fixture_byte_size": meta.get("byte_size"),
        "fixture_paragraph_count": meta.get("paragraph_count"),
        "word_count": meta.get("word_count"),
        "edit_burst": dict(edit_burst),
        "edit_oracle": oracle,
        "edit_unverified": edit_unverified,
        "edit_measurement": dict(edit_measurement or {}),
        "edit_cpu_publication": "published" if publish_edit_cpu else "withheld",
        "quiescence": {**dict(quiescence), "reached": bool(quiescence_reached)},
        "settle": dict(settle or {}),
        "editor_error": editor_error,
        "static_server": static_server,
        "phases": phases,
        **_named_phase_counters(phases, include_edit_cpu=publish_edit_cpu),
        "criteria": criteria,
        **gate_fields,
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
    settle = {}
    refusal_override = None
    edit_result = None
    edit_oracle = {"mode": "not_run", "status": "not_run", "reason": "edit_not_run"}
    edit_unverified = False
    edit_measurement = {}
    edit_cpu_boundary = None
    publish_edit_cpu = False
    edit_cpu_withhold_reason = "legacy_combined_edit_window"
    stage = "load"
    if not already_sampled:
        # Same settle before C17 and before C19. The natural sample is the
        # endpoint. A forced GC sample is labelled and kept out of the series.
        try:
            sampler.mark("load")
            try:
                session.load()
            except RuntimeError as exc:
                if "editor_load_failed" not in str(exc):
                    raise
                editor_error = str(exc).split("editor_load_failed:", 1)[1].strip()[:400]
                sampler.sample()
                return assemble_trial(
                    sampler, quiescence_reached=False, settle=settle, quiescence=quiescence,
                    edit_burst=edit_burst, editor_id=editor_id, workload_id=workload_id,
                    workload_meta=workload_meta, execution_profile=execution_profile,
                    host_class=host_class, save_phase=save_phase,
                    refusal_override="editor_load_failed", edit_oracle=edit_oracle,
                    publish_edit_cpu=False, edit_cpu_withhold_reason="editor_load_failed",
                    editor_error=editor_error,
                )
            sampler.sample()
            stage = "settle after load"
            sampler.mark("after_load")
            after_load = getattr(session, "after_load", None)
            if after_load is not None:
                after_load()
            # An editor that never goes idle (WordCraft repaints forever) is
            # measured over the capped settle and flagged, not refused.
            reached = drive_quiescence(sampler, clock, quiescence)
            settle["after_load"] = "reached" if reached else "capped"
            if getattr(sampler, "quiescence_block", None) == "longtask_unavailable":
                refusal_override = "longtask_unavailable"
            else:
                sampler.sample()
                _record_gc(sampler, "after_load")
                prepare = getattr(session, "prepare_edit", None)
                type_edit = getattr(session, "type_edit", None)
                verify_edit = getattr(session, "verify_edit", None)
                split_protocol = all(callable(value) for value in (prepare, type_edit, verify_edit))
                stage = "edit"
                if split_protocol:
                    prepared = prepare(edit_burst)
                    sampler.mark("edit_burst")
                    cpu_before = sampler.process_snapshot()
                    typed = type_edit(edit_burst)
                    clock.sleep(EDIT_SETTLE_MS / 1000.0)
                    cpu_after = sampler.process_snapshot()
                    sampler.sample()
                    edit_result = verify_edit(edit_burst, prepared)
                    cpu_ms, cpu_status = sampler.process_counter_delta(cpu_before, cpu_after, "cpu_ms")
                    renderer_cpu_ms, renderer_status = sampler.process_counter_delta(
                        cpu_before, cpu_after, "cpu_ms", role="renderer",
                    )
                    edit_cpu_boundary = {
                        "cpu_ms": cpu_ms,
                        "renderer_cpu_ms": renderer_cpu_ms,
                        "process_accounting": (
                            "incomplete" if "incomplete" in (cpu_status, renderer_status) else cpu_status
                        ),
                    }
                    publish_edit_cpu = True
                    edit_measurement = {
                        "window": "keystrokes_plus_fixed_settle",
                        "protocol": "split",
                        "pre_type_settle_ms": prepared.get("pre_type_settle_ms", EDIT_PRE_TYPE_SETTLE_MS),
                        "settle_ms": EDIT_SETTLE_MS,
                        "typing_duration_ms": typed.get("typing_duration_ms") if isinstance(typed, dict) else None,
                        "measured_window_duration_ms": (
                            (cpu_after.get("monotonic_s", 0) - cpu_before.get("monotonic_s", 0)) * 1000.0
                        ),
                        "cpu_boundary": "process_only_before_type_after_settle",
                        "verification_outside_measured_phase": True,
                    }
                else:
                    # Compatibility for old test doubles. Its witness window is
                    # unknown, so its edit CPU is withheld rather than published.
                    sampler.mark("edit_burst")
                    edit_result = session.edit(edit_burst)
                    sampler.sample()
                    publish_edit_cpu = False
                    edit_cpu_withhold_reason = "legacy_combined_edit_window"
                    edit_measurement = {
                        "window": "legacy_combined_unpublishable",
                        "protocol": "legacy_combined",
                        "pre_type_settle_ms": None,
                        "settle_ms": None,
                        "typing_duration_ms": None,
                        "measured_window_duration_ms": None,
                        "cpu_boundary": None,
                        "verification_outside_measured_phase": False,
                    }
                edit_oracle = _edit_oracle(edit_result)
                edit_unverified = edit_oracle.get("status") == "edit_unverified"
                if edit_unverified:
                    edit_cpu_withhold_reason = "edit_unverified"
                elif not _edit_applied(session, edit_burst, edit_result):
                    refusal_override = "edit_not_applied"
                    edit_cpu_withhold_reason = "edit_not_applied"
                if refusal_override != "edit_not_applied":
                    after_edits = getattr(session, "after_edits", None)
                    if after_edits is not None:
                        after_edits()
                    stage = "settle after edit"
                    sampler.mark("quiescence")
                    edit_reached = drive_quiescence(sampler, clock, quiescence)
                    settle["after_edit"] = "reached" if edit_reached else "capped"
                    reached = reached and edit_reached
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
        except RuntimeError as exc:
            # A renderer that dies is the editor's result for this document
            # (canvas-editor at 250k words), not a harness failure.
            if not _renderer_crashed(exc):
                raise
            return assemble_trial(
                sampler, quiescence_reached=False, settle=settle, quiescence=quiescence,
                edit_burst=edit_burst, editor_id=editor_id, workload_id=workload_id,
                workload_meta=workload_meta, execution_profile=execution_profile,
                host_class=host_class, save_phase=save_phase,
                refusal_override="editor_crashed", edit_oracle=edit_oracle,
                publish_edit_cpu=False, edit_cpu_withhold_reason="editor_crashed",
                editor_error="renderer crashed during %s" % stage,
            )
        finally:
            close = getattr(session, "close", None)
            if close is not None:
                close()
    return assemble_trial(
        sampler,
        quiescence_reached=reached,
        settle=settle,
        quiescence=quiescence,
        edit_burst=edit_burst,
        editor_id=editor_id,
        workload_id=workload_id,
        workload_meta=workload_meta,
        execution_profile=execution_profile,
        host_class=host_class,
        save_phase=save_phase,
        refusal_override=refusal_override,
        edit_oracle=edit_oracle,
        edit_unverified=edit_unverified,
        edit_measurement=edit_measurement,
        edit_cpu_boundary=edit_cpu_boundary,
        publish_edit_cpu=publish_edit_cpu,
        edit_cpu_withhold_reason=edit_cpu_withhold_reason,
    )


def _renderer_crashed(exc):
    text = str(exc)
    return "Target crashed" in text or "Page crashed" in text


def _early_refusal(*, editor_id, workload_id, code, execution_profile, host_class):
    if code not in REFUSAL_CODES:
        raise ValueError(code)
    content_meta = content_meta_for_workload(workload_id)
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
        **content_gate_record(content_meta, gate_length_check_for(editor_id, content_meta)),
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
    meta = workload_for_lane(workload_id, "resources", REPO)
    fixture = _store_fixture(run, workload_id, meta["docx"])
    public = _public_meta(meta)
    if meta.get("fixture_variant"):
        public["fixture_variant"] = meta["fixture_variant"]
        public["fixture_source_sha256"] = meta["fixture_source_sha256"]
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
    # wordcraft-host/server.mjs listens on PORT (default 5219) and does not read the URL.
    if editor_id == "wordcraft":
        target["env"] = {**(target.get("env") or {}), "PORT": str(port)}
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
        self.server_pid = getattr(self._server, "pid", None) or os.getpid()
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
            "editWitness": _edit_witness(editor_id),
            "editorId": editor_id,
            "errorJs": target.get("error_js") or "",
        })
        self.browser_pid = result.get("browserPid")
        self.has_save = bool(target.get("save_selector"))
        self.page = _BridgePage(self._bridge)
        self.cdp = _BridgeCdp(self._bridge)

    def load(self):
        self._bridge.request("load", timeout=660)

    def after_load(self):
        # An editor whose host opens in a viewer (Docxodus) enters its editing
        # mode here: before the settle, outside the measured edit window.
        self._bridge.request("enter_edit_mode", timeout=660)

    def _edit_params(self, burst):
        editor_id = self.ctx["editor_id"]
        return {
            "editorId": editor_id,
            "selector": (self._target or {}).get("edit_selector") or "",
            "text": burst["text"],
            "repetitions": burst["repetitions"],
            "witness": _edit_witness(editor_id),
            "preTypeSettleMs": EDIT_PRE_TYPE_SETTLE_MS,
            "settleMs": EDIT_SETTLE_MS,
            "pollBoundMs": EDIT_ORACLE_POLL_BOUND_MS,
            "pollIntervalMs": EDIT_ORACLE_POLL_INTERVAL_MS,
        }

    def prepare_edit(self, burst):
        return self._bridge.request("edit_prepare", self._edit_params(burst), timeout=300)

    def type_edit(self, burst):
        return self._bridge.request("edit_type", self._edit_params(burst), timeout=600)

    def verify_edit(self, burst, prepared):
        params = self._edit_params(burst)
        params["prepared"] = prepared
        return self._bridge.request("edit_verify", params, timeout=120)

    def edit(self, burst):
        return self._bridge.request("edit", self._edit_params(burst), timeout=120)

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
        refusal = {
            "outcome": "refused",
            "refusal_code": trial.get("refusal_code"),
            "failure_reason": trial.get("refusal_code") or "refused",
        }
        for key in ("edit_oracle", "edit_measurement", "edit_unverified", "edit_cpu_publication"):
            if key in trial:
                refusal[key] = trial[key]
        write_json(out / "refusal.json", refusal)
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
