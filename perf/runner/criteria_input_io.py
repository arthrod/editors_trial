"""Reference writer for the C04/C07/C08/C09 probe payload.

`perf/runner/criteria_input.mjs` (driven by
`perf/runner/warm_cold_browser.mjs --criteria ...`) emits one JSON payload per
page load. This module turns each criterion entry into one immutable attempt
with the same helpers the warm/cold suite uses, and refuses a payload that
could produce a dishonest trial. The honesty tests live in
`perf/tests/test_input_criteria.py`.
"""

from __future__ import annotations

import math
import uuid
from pathlib import Path

from perf.analysis.publication_gate import trial_publishable_flags
from perf.analysis.summarize import summarize
from perf.runner.artifacts import write_attempt
from perf.runner.benchmark_ci_contract import (
    INTERPRETATION_CONDITIONS,
    _finalize_publishable,
    _host_base,
    _trial_dict,
)
from perf.scenarios.catalog import scenarios
from perf.schema import OUTCOMES, validate_environment, validate_trial

def _catalog():
    return {row["id"]: row for row in scenarios()}


PROBE_SCHEMA = "perf.criteria_input/1"
SUITE = ("C04", "C07", "C08", "C09")
PAINT_MECHANISM = "cdp_screencast_frame"


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
        if cid == "C07":
            _assert_c07_observations(entry)
        return
    if samples:
        raise ValueError("%s outcome %r carries samples" % (cid, outcome))
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("%s outcome %r has no failure_reason" % (cid, outcome))


def _assert_c07_observations(entry):
    """A measured hit-test sample must show where the caret landed.

    A point resolved from a text line box has to place the caret on that line;
    the page centre has no line box and only has to keep the caret in the
    editable surface. Without this, three painted frames with no caret proof
    would read as hit-test latency.
    """
    observations = [o for o in (entry.get("observations") or []) if isinstance(o, dict)]
    if len(observations) != 3:
        raise ValueError("C07 measured with %d observations, expected 3" % (len(observations),))
    for observation in observations:
        if observation.get("scope") != "dom_caret_on_clicked_line":
            continue
        point = observation.get("point")
        if observation.get("line") is not None:
            if observation.get("caret_on_clicked_line") is not True:
                raise ValueError("C07 %s: caret not on the clicked line" % (point,))
        elif observation.get("anchor_inside") is not True:
            raise ValueError("C07 %s: caret not inside the editable" % (point,))


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


def trial_from_entry(cid, entry, env):
    hints = entry.get("trial_hints") or {}
    if hints.get("cache_state") and hints["cache_state"] != env["cache_state"]:
        raise ValueError(
            "%s cache_state hint %r does not match the environment %r"
            % (cid, hints["cache_state"], env["cache_state"])
        )
    validate_environment(env)
    diagnostic = {
        "suite": "criteria_input",
        "probe": "criteria_input",
        "schema": PROBE_SCHEMA,
        "assertion": entry.get("assertion"),
        "evidence": entry.get("evidence"),
        "observations": entry.get("observations") or [],
        "notes": entry.get("notes") or [],
    }
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
        validate_trial(trial)
        return trial
    samples = [float(s) for s in entry["samples_ms"]]
    stats = summarize(samples, env["cache_state"], env["repetition_unit"], seed=0)
    publishable, reason = trial_publishable_flags(env, entry["layer"], stats["n"])
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
        trials[cid] = trial_from_entry(cid, entry, env)
    return trials


def write_trials_from_payload(payload, attempt_dir, **env_args):
    attempt_dir = Path(attempt_dir)
    written = []
    for cid, trial in trials_from_payload(payload, **env_args).items():
        attempt_id = "%s-%s-%s" % (
            cid.lower(),
            trial["environment"]["editor_id"],
            uuid.uuid4().hex[:10],
        )
        written.append(write_attempt(attempt_dir, attempt_id, trial))
    return written
