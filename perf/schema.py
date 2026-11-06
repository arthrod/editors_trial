"""Trial records for the performance harness.

A trial either measured a named boundary or it did not. Non-measurements do
not carry a latency. A requestAnimationFrame callback, a constructor return,
and a model-ready mark are real events, and none of them is a user-visible
result by itself.
"""

import json

_FORBIDDEN = (
    ("raf_callback", "visible_paint", "raf_callback cannot claim visible paint"),
    ("constructor_return", "usable", "constructor_return cannot claim usable"),
    ("model_ready", "user_visible", "model_ready cannot claim user-visible latency"),
)

OUTCOMES = (
    "measured",
    "unsupported",
    "not_applicable",
    "unverified",
    "failed",
    "not_run",
)


def validate_trial(trial):
    outcome = trial["outcome"]
    if outcome not in OUTCOMES:
        raise ValueError("unknown outcome %r" % (outcome,))
    claims = set(trial.get("claims") or [])
    boundary = trial["boundary"]
    for blocked_boundary, blocked_claim, message in _FORBIDDEN:
        if boundary == blocked_boundary and blocked_claim in claims:
            raise ValueError(message)
    raw_samples = trial.get("samples_ms", [])
    if raw_samples is None:
        raw_samples = []
    if not isinstance(raw_samples, list):
        raise ValueError("samples_ms")
    samples = raw_samples
    if outcome in ("failed", "not_run"):
        reason = trial.get("failure_reason")
        if not isinstance(reason, str) or not reason:
            raise ValueError("failure_reason")
    if outcome != "measured":
        if trial.get("latency_ms") is not None:
            raise ValueError("non-measured latency must be null")
        if samples:
            raise ValueError("non-measured samples must be empty")
        return
    if not samples:
        raise ValueError("measured trial needs samples")
    for sample in samples:
        if isinstance(sample, bool) or not isinstance(sample, (int, float)):
            raise ValueError("samples must be finite and non-negative")
        if sample != sample or sample in (float("inf"), float("-inf")) or sample < 0:
            raise ValueError("samples must be finite and non-negative")


def dump_trial(trial):
    validate_trial(trial)
    return json.dumps(trial, sort_keys=True, separators=(",", ":"))


def load_trial(text):
    trial = json.loads(text)
    if not isinstance(trial, dict):
        raise ValueError("trial must be an object")
    validate_trial(trial)
    return trial
