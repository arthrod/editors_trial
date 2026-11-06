"""Trial records for the performance harness."""

import math
import re

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

_PROFILE_BUDGET = {
    "ci_contract": {"fresh_process": 1, "in_process_iteration": 20},
    "ci_broad": {"fresh_process": 5, "in_process_iteration": 100},
    "dedicated_publish": {"fresh_process": 30, "in_process_iteration": 500},
}

_SHA256 = re.compile(r"[0-9a-f]{64}")


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


def validate_environment(env):
    if env["host_class"] not in ("dedicated", "ci_coarse"):
        raise ValueError("host_class")
    profile = env.get("execution_profile")
    if profile not in ("ci_contract", "ci_broad", "dedicated_publish"):
        raise ValueError("execution_profile")
    if env["cache_state"] not in ("process_cold_fs_warm", "os_cache_cold", "warm_steady"):
        raise ValueError("cache_state")
    if env["host_class"] == "ci_coarse" and env["cache_state"] == "os_cache_cold":
        raise ValueError("os_cache_cold is dedicated-host only")
    if profile == "dedicated_publish" and env["host_class"] != "dedicated":
        raise ValueError("dedicated_publish requires dedicated host")
    if profile == "ci_contract" and env.get("headless") is not True:
        raise ValueError("ci_contract requires headless")
    if env["cache_state"] == "os_cache_cold" and env.get("page_cache_dropped") is not True:
        raise ValueError("page_cache_dropped")
    if env["feature_profile"] not in ("P0", "P1", "P2", "P3"):
        raise ValueError("feature_profile")
    if env["repetition_unit"] not in ("fresh_process", "in_process_iteration"):
        raise ValueError("repetition_unit")
    if env["run_kind"] not in ("timing", "diagnostic"):
        raise ValueError("run_kind")
    if not isinstance(env["ram_bytes"], int) or isinstance(env["ram_bytes"], bool) or env["ram_bytes"] <= 0:
        raise ValueError("ram_bytes")
    for key in ("cpu_model", "os", "arch", "power_source", "editor_id", "editor_version", "workload_id"):
        if not isinstance(env[key], str) or not env[key]:
            raise ValueError(key)
    if _SHA256.fullmatch(env["fixture_sha256"]) is None:
        raise ValueError("fixture_sha256")
    if not isinstance(env["headless"], bool):
        raise ValueError("headless")
    refresh = env["display_refresh_hz"]
    if env["headless"]:
        if refresh is not None:
            raise ValueError("display_refresh_hz")
        return
    if isinstance(refresh, bool) or not isinstance(refresh, (int, float)) or not math.isfinite(refresh) or refresh <= 0:
        raise ValueError("display_refresh_hz")


def sample_budget_for_profile(execution_profile, repetition_unit):
    try:
        return _PROFILE_BUDGET[execution_profile][repetition_unit]
    except KeyError as exc:
        raise ValueError("execution_profile") from exc


def validate_sample_budget(env, attempt_count):
    if not isinstance(attempt_count, int) or attempt_count < 1:
        raise ValueError("attempt_count")
    limit = sample_budget_for_profile(env["execution_profile"], env["repetition_unit"])
    if attempt_count > limit:
        raise ValueError("sample budget exceeded for %s" % (env["execution_profile"],))
