"""Trial records for the performance harness."""

import json
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
    "profiled",
)

_PROFILE_BUDGET = {
    "ci_contract": {"fresh_process": 1, "in_process_iteration": 20},
    "ci_broad": {"fresh_process": 5, "in_process_iteration": 100},
    "dedicated_publish": {"fresh_process": 30, "in_process_iteration": 500},
}

_SHA256 = re.compile(r"[0-9a-f]{64}")
_I_COND = re.compile(r"^I(0[1-9]|1[0-2])$")


def validate_trial(trial):
    outcome = trial["outcome"]
    if outcome not in OUTCOMES:
        raise ValueError("unknown outcome %r" % (outcome,))
    if outcome == "profiled":
        if trial.get("publishable") is not False:
            raise ValueError("profiled trials are never publishable")
        if trial.get("accounting_scope") != "diagnostic":
            raise ValueError("profiled trials must use diagnostic accounting")
        return
    if trial.get("criterion_id") in ("C05", "C06") and outcome == "measured":
        from perf.layers.classify import assert_visible_evidence

        mechanism = trial.get("mechanism") or (trial.get("diagnostic") or {}).get("mechanism")
        # C06 uses the same input-to-paint evidence rule as C05.
        assert_visible_evidence("C05", mechanism)
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
        if trial.get("summary_stats") is not None:
            raise ValueError("summary_stats only for measured trials")
        return
    if not samples:
        raise ValueError("measured trial needs samples")
    for sample in samples:
        if isinstance(sample, bool) or not isinstance(sample, (int, float)):
            raise ValueError("samples must be finite and non-negative")
        if sample != sample or sample in (float("inf"), float("-inf")) or sample < 0:
            raise ValueError("samples must be finite and non-negative")
    stats = trial.get("summary_stats")
    if stats is not None:
        _validate_summary_stats(stats)
    pub = trial.get("publishable")
    if pub is not None and not isinstance(pub, bool):
        raise ValueError("publishable")
    block = trial.get("publication_block_reason")
    if block is not None and not isinstance(block, str):
        raise ValueError("publication_block_reason")
    if pub is False and (not block or not block.strip()):
        raise ValueError("publication_block_reason required when publishable is false")
    if pub is True and block is not None:
        raise ValueError("publication_block_reason must be null when publishable is true")


def _validate_summary_stats(stats):
    required = (
        "n",
        "median",
        "p90",
        "p95",
        "p99",
        "mad",
        "ci95_low",
        "ci95_high",
        "minimum",
        "maximum",
        "cache_state",
        "repetition_unit",
    )
    for key in required:
        if key not in stats:
            raise ValueError("summary_stats missing %s" % (key,))
    if stats["n"] != int(stats["n"]) or stats["n"] < 1:
        raise ValueError("summary_stats n")
    for key in ("median", "p90", "p95", "p99", "mad", "ci95_low", "ci95_high", "minimum", "maximum"):
        val = stats[key]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError("summary_stats %s" % (key,))
        if val != val or val in (float("inf"), float("-inf")):
            raise ValueError("summary_stats %s" % (key,))
    if stats["cache_state"] not in ("process_cold_fs_warm", "os_cache_cold", "warm_steady"):
        raise ValueError("summary_stats cache_state")
    if stats["repetition_unit"] not in ("fresh_process", "in_process_iteration"):
        raise ValueError("summary_stats repetition_unit")


def validate_environment(env):
    if env["host_class"] not in ("dedicated", "ci_coarse", "shared_guarded"):
        raise ValueError("host_class")
    profile = env.get("execution_profile")
    if profile not in ("ci_contract", "ci_broad", "dedicated_publish"):
        raise ValueError("execution_profile")
    if env["cache_state"] not in ("process_cold_fs_warm", "os_cache_cold", "warm_steady"):
        raise ValueError("cache_state")
    if env["host_class"] == "ci_coarse" and env["cache_state"] == "os_cache_cold":
        raise ValueError("os_cache_cold is dedicated-host only")
    if profile == "dedicated_publish" and env["host_class"] not in ("dedicated", "shared_guarded"):
        raise ValueError("dedicated_publish requires dedicated or shared_guarded host")
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
    else:
        if isinstance(refresh, bool) or not isinstance(refresh, (int, float)) or not math.isfinite(refresh) or refresh <= 0:
            raise ValueError("display_refresh_hz")
    _validate_workload_record(env)
    _validate_interpretation_conditions(env)


def _validate_workload_record(env):
    """I05 explicit workload profile (byte size, shape, unicode class, search matches)."""
    for key in (
        "fixture_byte_size",
        "fixture_paragraph_count",
        "paragraph_shape",
        "unicode_class",
        "match_count",
    ):
        if key not in env:
            raise ValueError("workload record missing %s" % (key,))
    size = env["fixture_byte_size"]
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise ValueError("fixture_byte_size")
    pcount = env["fixture_paragraph_count"]
    if not isinstance(pcount, int) or isinstance(pcount, bool) or pcount < 1:
        raise ValueError("fixture_paragraph_count")
    shape = env["paragraph_shape"]
    if not isinstance(shape, str) or not shape:
        raise ValueError("paragraph_shape")
    ucls = env["unicode_class"]
    if ucls not in ("ascii", "mixed"):
        raise ValueError("unicode_class")
    matches = env["match_count"]
    if not isinstance(matches, int) or isinstance(matches, bool) or matches < 0:
        raise ValueError("match_count")


def _validate_interpretation_conditions(env):
    conds = env.get("interpretation_conditions")
    if conds is None:
        raise ValueError("interpretation_conditions")
    if not isinstance(conds, (list, tuple)):
        raise ValueError("interpretation_conditions")
    seen = set()
    for item in conds:
        if not isinstance(item, str) or _I_COND.fullmatch(item) is None:
            raise ValueError("interpretation_conditions entry %r" % (item,))
        if item in seen:
            raise ValueError("duplicate interpretation condition %s" % (item,))
        seen.add(item)
    expected = {"I%02d" % n for n in range(1, 13)}
    if seen != expected:
        raise ValueError("interpretation_conditions must list I01–I12 exactly once")
    fb = env.get("feature_fallback")
    if fb is None:
        return
    if not isinstance(fb, (list, tuple)):
        raise ValueError("feature_fallback")
    for name in fb:
        if not isinstance(name, str) or not name:
            raise ValueError("feature_fallback")


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


def dump_trial(trial):
    validate_trial(trial)
    return json.dumps(trial, sort_keys=True, separators=(",", ":"))


def load_trial(text):
    trial = json.loads(text)
    if not isinstance(trial, dict):
        raise ValueError("trial must be an object")
    validate_trial(trial)
    return trial
