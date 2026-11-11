"""Reference writer for the C04/C07/C08/C09 probe payload.

`perf/runner/criteria_input.mjs` (driven by
`perf/runner/warm_cold_browser.mjs --criteria ...`) emits one JSON payload per
page load. This module turns each criterion entry into one immutable attempt
with the same helpers the warm/cold suite uses, and refuses a payload that
could produce a dishonest trial. The honesty tests live in
`perf/tests/test_input_criteria.py`.
"""

from __future__ import annotations

import json
import math
import uuid
from pathlib import Path

from perf.analysis.publication_gate import trial_publishable_flags
from perf.analysis.summarize import percentile, summarize
from perf.layers.event_timing import event_timing_status
from perf.runner.artifacts import write_attempt
from perf.runner.witness import validate_witness
from perf.runner.benchmark_ci_contract import (
    INTERPRETATION_CONDITIONS,
    _finalize_publishable,
    _host_base,
    _trial_dict,
)
from perf.scenarios.catalog import scenarios
from perf.schema import OUTCOMES, validate_environment, validate_trial

PROBE_SCHEMA = "perf.criteria_input/1"
SUITE = ("C04", "C07", "C08", "C09")
PAINT_MECHANISM = "cdp_screencast_frame"
CORRECTNESS_PREFIX = "correctness:"


def _catalog():
    return {row["id"]: row for row in scenarios()}


def assert_payload_shape(payload):
    """Reject a payload that is not this probe's output before reading entries."""
    if not isinstance(payload, dict):
        raise ValueError("criteria payload must be an object")
    if payload.get("probe") != "criteria_input":
        raise ValueError("criteria payload probe id %r" % (payload.get("probe"),))
    if payload.get("schema") != PROBE_SCHEMA:
        raise ValueError("criteria payload schema %r" % (payload.get("schema"),))
    requested = payload.get("criteria_requested")
    if not isinstance(requested, list) or not requested:
        raise ValueError("criteria_requested must be a non-empty list")
    unknown = [cid for cid in requested if cid not in SUITE]
    if unknown:
        raise ValueError("criteria_requested has unknown ids %r" % (unknown,))
    entries = payload.get("criteria")
    if not isinstance(entries, dict):
        raise ValueError("criteria must be an object")
    missing = [cid for cid in requested if cid not in entries]
    if missing:
        raise ValueError("criteria missing entries for %r" % (missing,))
    extra = [cid for cid in entries if cid not in requested]
    if extra:
        raise ValueError("criteria has unrequested entries %r" % (extra,))
    witness = payload.get("paint_witness") or {}
    for cid in requested:
        entry = entries[cid]
        if not isinstance(entry, dict):
            raise ValueError("%s entry is not an object" % (cid,))
        if entry.get("criterion_id") != cid:
            raise ValueError("%s entry carries criterion_id %r" % (cid, entry.get("criterion_id")))
        scenario = _catalog()[cid]
        for key in ("layer", "boundary", "evidence"):
            if entry.get(key) != scenario[key]:
                raise ValueError(
                    "%s %s is %r, catalog says %r"
                    % (cid, key, entry.get(key), scenario[key])
                )
        _assert_entry_honest(cid, entry, witness)
    return entries


def _frame_interval_ms(witness):
    value = (witness or {}).get("frame_interval_ms")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("paint_witness frame_interval_ms is not a number: %r" % (value,))
    if not math.isfinite(value) or value <= 0:
        raise ValueError("paint_witness frame_interval_ms must be positive: %r" % (value,))
    return float(value)


def _assert_c07_repetition_unit(entry):
    hints = entry.get("trial_hints") or {}
    if hints.get("repetition_unit") != "fresh_process":
        raise ValueError(
            "C07 measured as one value per launch must record repetition_unit fresh_process, got %r"
            % (hints.get("repetition_unit"),)
        )


def _rounded_latency_ms(frame_ms, anchor_ms):
    return round(float(frame_ms) - float(anchor_ms), 3)


def _assert_retained_sample_witness_deltas(cid, entry):
    """Resolve samples by producer identity, never by coincident numeric value."""
    if entry.get("outcome") != "measured":
        return
    samples = entry.get("samples_ms") or []
    identities = entry.get("sample_observation_ids")
    if not isinstance(identities, list) or len(identities) != len(samples):
        raise ValueError(f"{cid} requires an observation identity for every sample")
    observations = entry.get("observations") or []
    by_id = {}
    for observation in observations:
        if not isinstance(observation, dict):
            raise ValueError(f"{cid} observation must be an object")
        identity = observation.get("observation_id")
        if not isinstance(identity, str) or not identity or identity in by_id:
            raise ValueError(f"{cid} observation identity missing or duplicated")
        by_id[identity] = observation
    used = set()
    for identity, sample in zip(identities, samples):
        if not isinstance(identity, str) or identity not in by_id or identity in used:
            raise ValueError(f"{cid} retained observation identity missing or duplicated")
        used.add(identity)
        observation = by_id[identity]
        witness = observation.get("witness") or {}
        for field, witness_field in (("input_ms", "after_page_ms"), ("frame_ms", "frame_page_ms")):
            value, anchor = observation.get(field), witness.get(witness_field)
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in (value, anchor)) or abs(value - anchor) > 0.001:
                raise ValueError(f"{cid} observation {field} anchor disagrees with witness")
        delta = _rounded_latency_ms(witness["frame_page_ms"], witness["after_page_ms"])
        observed_sample = observation.get("sample_ms")
        if (isinstance(observed_sample, bool) or not isinstance(observed_sample, (int, float))
                or not math.isfinite(observed_sample) or abs(observed_sample - sample) > 0.001
                or abs(sample - delta) > 0.001):
            raise ValueError(f"{cid} sample {sample!r} disagrees with witness latency {delta!r}")


def _witness_evidence_from_entry(entry):
    observations = []
    for observation in entry.get("observations") or []:
        if not isinstance(observation, dict):
            raise ValueError("malformed observation in criterion entry")
        evidence = dict(observation)
        if observation.get("witness") is not None:
            verdict = validate_witness(observation["witness"])
            evidence["witness_verdict"] = verdict
            if verdict.get("refused"):
                evidence["witness_refusal"] = verdict.get("reason")
                evidence["witness_errors"] = list(dict.fromkeys(
                    (observation.get("witness_errors") or []) + (verdict.get("errors") or [])))
        observations.append(evidence)
    # Keep every observation, plus the first failing witness for older consumers.
    failed = next((o for o in observations if o.get("witness_refusal")), {})
    return {"observations": observations, **{
        key: failed[key] for key in ("witness", "witness_refusal", "witness_errors", "witness_verdict")
        if key in failed
    }}


def _assert_observation_witnesses(cid, entry):
    """Every retained visible-paint sample must carry a publishable witness record."""
    if entry.get("layer") != "browser_visible" or entry.get("outcome") != "measured":
        return
    observations = entry.get("observations") or []
    sample_count = len(entry.get("samples_ms") or [])
    if not sample_count:
        return
    witnessed = 0
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        if observation.get("frame_ms") is None and observation.get("sample_ms") is None:
            continue
        witness = observation.get("witness")
        if not isinstance(witness, dict):
            raise ValueError(
                "%s observation at %s lacks witness evidence for a retained sample"
                % (cid, observation.get("point") or witnessed)
            )
        verdict = validate_witness(witness)
        if verdict.get("refused"):
            reason = verdict.get("reason") or "witness_refused"
            raise ValueError(
                "%s witness refused for publication: %s" % (cid, reason)
            )
        witnessed += 1
    if witnessed < sample_count:
        raise ValueError(
            "%s has %d samples but only %d observations with publishable witness evidence"
            % (cid, sample_count, witnessed)
        )


def _assert_visible_samples(cid, entry, witness):
    frame_interval = _frame_interval_ms(witness)
    if frame_interval is None:
        raise ValueError("%s is measured but paint_witness carries no frame_interval_ms" % (cid,))
    flags = entry.get("sub_frame_samples") or []
    if flags and len(flags) != len(entry["samples_ms"]):
        raise ValueError("%s sub_frame_samples length does not match samples_ms" % (cid,))
    for index, sample in enumerate(entry["samples_ms"]):
        if index < len(flags) and flags[index]:
            continue
        if sample < frame_interval:
            raise ValueError(
                "%s sample %r is below the recorded frame interval %r"
                % (cid, sample, frame_interval)
            )


def _assert_entry_honest(cid, entry, witness):
    outcome = entry.get("outcome")
    if outcome not in OUTCOMES:
        raise ValueError("%s unknown outcome %r" % (cid, outcome))
    samples = entry.get("samples_ms")
    if not isinstance(samples, list):
        raise ValueError("%s samples_ms must be a list" % (cid,))
    reason = entry.get("failure_reason")
    if outcome == "measured":
        if not samples:
            raise ValueError("%s is measured with no samples" % (cid,))
        for sample in samples:
            if isinstance(sample, bool) or not isinstance(sample, (int, float)):
                raise ValueError("%s sample is not a number: %r" % (cid, sample))
            if not math.isfinite(sample):
                raise ValueError("%s sample is not finite" % (cid,))
            if sample < 0:
                raise ValueError("%s sample is negative: %r" % (cid, sample))
            if sample == 0 and cid != "C04":
                # A paint cannot happen at the same instant as its input. For
                # C04 zero is meaningful: quiescence was already true at ready.
                raise ValueError("%s sample is not a positive latency: %r" % (cid, sample))
        assertion = entry.get("assertion") or {}
        if assertion.get("passed") is not True:
            raise ValueError("%s is measured but its assertion did not pass" % (cid,))
        if entry["layer"] == "browser_visible":
            if witness.get("mechanism") != PAINT_MECHANISM:
                raise ValueError(
                    "%s is measured but the paint witness is %r, not %r"
                    % (cid, witness.get("mechanism"), PAINT_MECHANISM)
                )
            if not witness.get("frames_seen"):
                raise ValueError("%s is measured but no composited frame was seen" % (cid,))
            observations = entry.get("observations") or []
            framed = [o for o in observations if isinstance(o, dict) and o.get("frame_ms")]
            if len(framed) < len(samples):
                raise ValueError(
                    "%s has %d samples but %d observations with a frame timestamp"
                    % (cid, len(samples), len(framed))
                )
        if reason not in (None, ""):
            raise ValueError("%s is measured but carries failure_reason %r" % (cid, reason))
        if entry["layer"] == "browser_visible":
            _assert_observation_witnesses(cid, entry)
            _assert_retained_sample_witness_deltas(cid, entry)
            _assert_visible_samples(cid, entry, witness)
        if cid == "C07":
            _assert_c07_repetition_unit(entry)
            _assert_c07_observations(entry)
        return
    if outcome == "not_applicable":
        if samples:
            raise ValueError("%s not_applicable carries samples" % (cid,))
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("%s not_applicable has no failure_reason" % (cid,))
        return
    if samples:
        raise ValueError("%s outcome %r carries samples" % (cid, outcome))
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("%s outcome %r has no failure_reason" % (cid, outcome))


def _assert_c07_observations(entry):
    """A measured C07 keeps the r3c07b contract on every retained sample.

    At least two distinct painted points measure C07; the same coordinates are
    never measured twice. Every observation that produced a sample must carry:
    a proven quiet window (required_ms >= 1000), fresh-state evidence
    (reloaded or tap/selection-verified untouched), and — where the surface
    exposes a caret — the caret on the clicked line. A refused point keeps its
    named failure in its own observation and produces no sample.
    """
    samples = entry.get("samples_ms") or []
    if len(samples) < 2:
        raise ValueError(
            "C07 measured with %d samples, expected at least two distinct painted points"
            % (len(samples),)
        )
    observations = [o for o in (entry.get("observations") or []) if isinstance(o, dict)]
    sampled_ids = set(entry.get("sample_observation_ids") or [])
    seen_xy = set()
    kept = 0
    for observation in observations:
        xy = (observation.get("x"), observation.get("y"))
        if all(v is not None for v in xy):
            if xy in seen_xy:
                raise ValueError(
                    "C07 measured the same coordinates twice (%r, %r): points must be distinct"
                    % xy
                )
            seen_xy.add(xy)
        is_sample = (
            observation.get("observation_id") in sampled_ids
            or observation.get("sample_ms") is not None
        )
        if not is_sample:
            continue
        kept += 1
        point = observation.get("point")
        if observation.get("failure"):
            raise ValueError("C07 %s: a refused observation cannot carry a sample" % (point,))
        quiet = observation.get("quiet_window")
        if not isinstance(quiet, dict) or quiet.get("proven") is not True:
            raise ValueError("C07 %s: sample lacks a proven quiet window" % (point,))
        required = quiet.get("required_ms")
        if not isinstance(required, (int, float)) or isinstance(required, bool) or required < 1000:
            raise ValueError("C07 %s: quiet required_ms under 1000" % (point,))
        if quiet.get("violated") is True or quiet.get("exhausted") is True:
            raise ValueError("C07 %s: quiet window violated or exhausted" % (point,))
        # The proof lives in the frame witness the sample is timed against;
        # the observation's copy is only an echo of it.
        witness_quiet = (observation.get("witness") or {}).get("quiet_window")
        if not isinstance(witness_quiet, dict) or witness_quiet.get("proven") is not True:
            raise ValueError(
                "C07 %s: the frame witness does not carry the quiet-window proof" % (point,)
            )
        fresh = observation.get("fresh_state") or {}
        if fresh.get("state") not in ("reloaded", "untouched_verified"):
            raise ValueError("C07 %s: no fresh-state evidence for the click" % (point,))
        if observation.get("caret_on_clicked_line") is False:
            raise ValueError("C07 %s: caret not on the clicked line" % (point,))
    if kept < 2:
        raise ValueError(
            "C07 measured with %d sample observations, expected at least 2" % (kept,)
        )


def assert_distinct_samples(entries):
    """Two criteria with the same sample vector mean one was copied, not measured."""
    seen = {}
    for cid, entry in entries.items():
        if entry.get("outcome") != "measured":
            continue
        key = tuple(round(float(s), 6) for s in entry["samples_ms"])
        if key in seen:
            raise ValueError(
                "%s and %s carry the same samples %r: a sample is measured once"
                % (seen[key], cid, list(key))
            )
        seen[key] = cid


def env_for(editor_id, editor_version, fixture_sha256, workload_row, docx_size, cache_state):
    env = _host_base(
        editor_id=editor_id,
        editor_version=editor_version,
        execution_profile="ci_broad",
        fixture_sha256=fixture_sha256,
        workload_row=workload_row,
        docx_size=docx_size,
        cache_state=cache_state,
        repetition_unit="fresh_process",
        run_kind="timing",
        feature_profile_name="P0",
    )
    env["interpretation_conditions"] = list(INTERPRETATION_CONDITIONS)
    return env


def trial_from_entry(cid, entry, env, witness=None, workload_row=None):
    hints = entry.get("trial_hints") or {}
    if hints.get("cache_state") and hints["cache_state"] != env["cache_state"]:
        raise ValueError(
            "%s cache_state hint %r does not match the environment %r"
            % (cid, hints["cache_state"], env["cache_state"])
        )
    if hints.get("repetition_unit"):
        env = dict(env)
        env["repetition_unit"] = hints["repetition_unit"]
    validate_environment(env)
    from perf.runner.benchmark_document import (
        content_gate_record,
        content_meta_for_workload,
        gate_length_check_for,
    )

    row = workload_row or {}
    content_meta = content_meta_for_workload(row.get("workload_id") or "micro-paragraphs")
    gate = gate_length_check_for(env["editor_id"], content_meta)
    diagnostic = {
        "suite": "criteria_input",
        "probe": "criteria_input",
        "schema": PROBE_SCHEMA,
        "assertion": entry.get("assertion"),
        "evidence": entry.get("evidence"),
        "observations": entry.get("observations") or [],
        "sample_observation_ids": entry.get("sample_observation_ids") or [],
        "fixture_reset": entry.get("fixture_reset"),
        "notes": entry.get("notes") or [],
        **content_gate_record(content_meta, gate),
    }
    frame_interval = _frame_interval_ms(witness)
    if frame_interval is not None:
        diagnostic["frame_interval_ms"] = frame_interval
    if entry.get("sub_frame_samples"):
        diagnostic["sub_frame_samples"] = list(entry["sub_frame_samples"])
    outcome = entry["outcome"]
    if outcome != "measured":
        trial = _trial_dict(
            criterion_id=cid,
            layer=entry["layer"],
            boundary=entry["boundary"],
            outcome=outcome,
            env=env,
            samples_ms=[],
            failure_reason=entry["failure_reason"],
            editor_id=env["editor_id"],
            lane=env.get("lane"),
            diagnostic=diagnostic,
        )
        reason = str(entry["failure_reason"])
        trial["refusal_code"] = (
            outcome if outcome in ("not_applicable", "not_run", "unsupported", "unverified") else
            "cpu_throttled" if reason.startswith("cpu_throttled") else
            "editor_load_failed" if reason.startswith("editor_load_failed") else
            "document_protected_read_only" if "document_protected_read_only" in reason else
            "caret_move_not_painted" if "caret_move_not_painted" in reason else
            "click_paint_not_observed" if "click_paint_not_observed" in reason else
            "first_click_painted_nothing_in_click_region" if "first_click_painted_nothing_in_click_region" in reason else
            "editor_mode_did_not_open" if "editor_mode_did_not_open" in reason else
            "editable_not_found" if reason.startswith(("editable_not_found", "editable_not_in_viewport")) else
            "surface_not_dom_editable" if reason.startswith(("surface_not_dom_editable", "no_correctness_adapter")) else
            "surface_not_dom_editable" if reason.startswith(("editor_model_unavailable", "document_text_not_readable")) else
            "click_points_unavailable" if "click_points_unavailable" in reason else
            "unverified" if (
                reason.startswith((
                    "correctness:",
                    "no_keydown_",
                    "typed_character_not_observable",
                    "no_click_point_resolved",
                    "quiescence_not_reached_",
                    "fixture_reset_failed",
                    "editable_has_no_observable_text",
                    "selection_not_collapsed_before_typing",
                    "click_box_not_quiet_before_click",
                    "editor_state_not_untouched",
                    "fewer_than_two_distinct_painted_lines",
                    "quiet_window_evidence_missing",
                ))
                or "caret_not_on_clicked_line" in reason
                or "editor_did_not_take_focus_after_click" in reason
                or "no_pointerdown_observed" in reason
                or "pointer_target_outside_editable" in reason
            ) else
            "paint_witness_unavailable" if any(
                token in reason for token in ("no_painted_frame", "witness", "clock_skew", "frame_interval")
            ) else
            "malformed_samples" if "malformed_observation" in reason else
            "crash"
        )
        validate_trial(trial)
        return trial
    samples = [float(s) for s in entry["samples_ms"]]
    if cid in ("C04", "C08", "C09") and env["repetition_unit"] == "fresh_process" and len(samples) > 1:
        diagnostic["rejected_samples_ms"] = samples
        trial = _trial_dict(criterion_id=cid, layer=entry["layer"], boundary=entry["boundary"],
            outcome="failed", env=env, samples_ms=[], failure_reason="fresh_process_multi_sample",
            publishable=False, editor_id=env["editor_id"], lane=env.get("lane"), diagnostic=diagnostic)
        trial["refusal_code"] = "malformed_samples"
        return trial
    sub_frame_samples = entry.get("sub_frame_samples")
    if cid == "C07" and len(samples) > 1:
        diagnostic["c07_click_samples_ms"] = list(samples)
        if sub_frame_samples:
            ordered = sorted(zip(samples, sub_frame_samples), key=lambda pair: pair[0])
            middle = len(ordered) // 2
            middle_flags = [ordered[middle][1]]
            if len(ordered) % 2 == 0:
                middle_flags.append(ordered[middle - 1][1])
            sub_frame_samples = [all(middle_flags)]
        samples = [percentile(samples, 50)]
    stats = summarize(samples, env["cache_state"], env["repetition_unit"], seed=0)
    # One value per browser launch; the two-run cell gate owns publication n.
    publication_n = None if env["repetition_unit"] == "fresh_process" else stats["n"]
    publishable, reason = trial_publishable_flags(env, entry["layer"], publication_n)
    publishable, reason = _finalize_publishable(publishable, reason, env)
    trial = _trial_dict(
        criterion_id=cid,
        layer=entry["layer"],
        boundary=entry["boundary"],
        outcome="measured",
        env=env,
        samples_ms=samples,
        editor_id=env["editor_id"],
        lane=env.get("lane"),
        summary_stats=stats,
        publishable=publishable,
        publication_block_reason=reason,
        diagnostic=diagnostic,
    )
    if sub_frame_samples:
        trial["sub_frame_samples"] = list(sub_frame_samples)
    elif entry.get("sub_frame_samples"):
        trial["sub_frame_samples"] = list(entry["sub_frame_samples"])
    validate_trial(trial)
    return trial


def trials_from_payload(payload, *, editor_version, fixture_sha256, workload_row, docx_size):
    entries = assert_payload_shape(payload)
    assert_distinct_samples(entries)
    trials = {}
    for cid in payload["criteria_requested"]:
        entry = entries[cid]
        cache_state = (entry.get("trial_hints") or {}).get("cache_state") or "warm_steady"
        env = env_for(
            payload.get("editor_id") or "unknown",
            editor_version,
            fixture_sha256,
            workload_row,
            docx_size,
            cache_state,
        )
        trial = trial_from_entry(
            cid, entry, env, witness=payload.get("paint_witness"), workload_row=workload_row
        )
        row = workload_row or {}
        variant = payload.get("fixture_variant") or row.get("fixture_variant")
        if variant:
            diagnostic = trial.setdefault("diagnostic", {})
            diagnostic["fixture_variant"] = variant
            diagnostic["fixture_source_sha256"] = (
                payload.get("fixture_source_sha256") or row.get("fixture_source_sha256")
            )
        trials[cid] = trial
    return trials


def build_support_matrix(summary):
    """Per-criterion hosts measured, refused, and failed: correctness."""
    matrix = {}
    for cid in SUITE:
        matrix[cid] = {
            "measured": [],
            "refused": {},
            "failed_correctness": [],
            "not_applicable": [],
        }
    for row in summary.get("editors") or []:
        editor_id = row.get("editor_id") or "unknown"
        if row.get("outcome") != "ok":
            for cid in SUITE:
                matrix[cid]["refused"][editor_id] = row.get("failure_reason") or "host_run_failed"
            continue
        criteria = row.get("criteria") or {}
        for cid in SUITE:
            cell = criteria.get(cid) or {}
            outcome = cell.get("outcome")
            reason = cell.get("failure_reason") or ""
            if outcome == "measured":
                matrix[cid]["measured"].append(editor_id)
            elif outcome == "not_applicable":
                matrix[cid]["not_applicable"].append(editor_id)
            elif reason.startswith(CORRECTNESS_PREFIX) or reason == "correctness" or ": correctness" in reason:
                matrix[cid]["failed_correctness"].append(editor_id)
            elif outcome in ("unsupported", "unverified", "failed", "not_run"):
                matrix[cid]["refused"][editor_id] = reason or outcome
    return matrix


def write_support_matrix(summary, out_root):
    out_root = Path(out_root)
    path = out_root / "support_matrix.json"
    payload = {
        "suite": summary.get("suite", "criteria_input"),
        "criteria": build_support_matrix(summary),
    }
    from perf.runner.browser_run import write_json
    write_json(path, payload)
    return path


def _single_criterion_payload(payload, cid):
    entry = payload["criteria"][cid]
    return {
        **payload,
        "criteria_requested": [cid],
        "criteria": {cid: entry},
    }


def _contract_refusal_trial(payload, cid, entry, env_args, reason):
    """A refused trial for a payload entry that violates the probe contract."""
    from perf.runner.benchmark_document import (
        content_gate_record,
        content_meta_for_workload,
        gate_length_check_for,
    )

    hints = entry.get("trial_hints") if isinstance(entry, dict) else None
    cache_state = (hints or {}).get("cache_state") or "warm_steady"
    env = env_for(
        payload.get("editor_id") or "unknown",
        env_args["editor_version"],
        env_args["fixture_sha256"],
        env_args["workload_row"],
        env_args["docx_size"],
        cache_state,
    )
    scenario = _catalog()[cid]
    trial = _trial_dict(
        criterion_id=cid,
        layer=scenario["layer"],
        boundary=scenario["boundary"],
        outcome="failed",
        env=env,
        samples_ms=[],
        failure_reason=reason,
        editor_id=env["editor_id"],
        lane=env.get("lane"),
        diagnostic={
            "suite": "criteria_input",
            "probe": "criteria_input",
            "schema": PROBE_SCHEMA,
            **content_gate_record(
                content_meta_for_workload((env_args.get("workload_row") or {}).get("workload_id") or "micro-paragraphs"),
                gate_length_check_for(
                    payload.get("editor_id") or "unknown",
                    content_meta_for_workload((env_args.get("workload_row") or {}).get("workload_id") or "micro-paragraphs"),
                ),
            ),
        },
    )
    trial["refusal_code"] = "harness_error"
    trial["refusal_detail"] = reason
    return trial


def write_trials_from_payload(payload, attempt_dir, **env_args):
    attempt_dir = Path(attempt_dir)
    by_criterion = {}
    for cid in payload["criteria_requested"]:
        try:
            single = _single_criterion_payload(payload, cid)
            trial = trials_from_payload(single, **env_args)[cid]
        except ValueError as exc:
            entry = payload["criteria"][cid]
            try:
                witness_evidence = _witness_evidence_from_entry(entry)
            except ValueError:
                witness_evidence = {"observations": []}
                reason = f"{exc}; malformed_observation"
            else:
                reason = str(exc)
            trial = _contract_refusal_trial(payload, cid, entry, env_args, reason)
            attempt_id = "%s-%s-%s" % (
                cid.lower(),
                trial["environment"]["editor_id"],
                uuid.uuid4().hex[:10],
            )
            path = write_attempt(attempt_dir, attempt_id, trial)
            by_criterion[cid] = {
                "written": False,
                "path": path,
                "failure_reason": reason,
                **witness_evidence,
            }
            continue
        attempt_id = "%s-%s-%s" % (
            cid.lower(),
            trial["environment"]["editor_id"],
            uuid.uuid4().hex[:10],
        )
        path = write_attempt(attempt_dir, attempt_id, trial)
        by_criterion[cid] = {
            "written": True,
            "path": path,
            "failure_reason": None,
        }
    return by_criterion
