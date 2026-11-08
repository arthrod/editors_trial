"""Apply scenario interpretation conditions (I01–I12) to measured trials."""

from __future__ import annotations

from perf.fixtures.generate import correctness_fixtures


def _check_i05(env: dict) -> tuple[bool, str]:
    required = (
        "workload_id",
        "fixture_sha256",
        "fixture_byte_size",
        "paragraph_shape",
        "unicode_class",
        "match_count",
        "fixture_paragraph_count",
    )
    missing = [k for k in required if k not in env]
    if missing:
        return False, "I05: missing workload fields: %s" % (", ".join(missing),)
    for key in ("fixture_byte_size", "fixture_paragraph_count", "match_count"):
        val = env.get(key)
        if not isinstance(val, int) or isinstance(val, bool):
            return False, "I05: %s must be int" % key
    if env["fixture_byte_size"] < 1 or env["fixture_paragraph_count"] < 1 or env["match_count"] < 0:
        return False, "I05: invalid numeric workload field"
    return True, ""


def _check_i06(env: dict) -> tuple[bool, str]:
    if "feature_fallback" not in env:
        return False, "I06: feature_fallback must be present (list, possibly empty)"
    fb = env["feature_fallback"]
    if not isinstance(fb, (list, tuple)):
        return False, "I06: feature_fallback must be a list"
    return True, ""


def _check_i10(summary_stats: dict | None, env: dict) -> tuple[bool, str]:
    if summary_stats is None:
        return False, "I10: summary_stats required for measured timing trials"
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
    )
    for key in required:
        if key not in summary_stats:
            return False, "I10: summary_stats missing %s" % (key,)
    if summary_stats["n"] < 1:
        return False, "I10: invalid n"
    if env.get("run_kind") != "timing":
        return False, "I10: run_kind must be timing for published stats"
    return True, ""


def _check_i11(env: dict) -> tuple[bool, str]:
    if env.get("run_kind") == "diagnostic":
        return False, "I11: diagnostic run_kind cannot be published as timing distribution"
    return True, ""


def evaluate_measured_trial(
    scenario: dict,
    env: dict,
    *,
    doc_output_text: str | None = None,
    summary_stats: dict | None = None,
) -> tuple[bool, str]:
    """
    Return ``(ok, reason)`` for interpretation conditions that apply to a
    measured trial before ``publishable`` may be true.
    """
    for check, args in (
        (_check_i05, (env,)),
        (_check_i06, (env,)),
        (_check_i10, (summary_stats, env)),
        (_check_i11, (env,)),
    ):
        ok, msg = check(*args)
        if not ok:
            return False, msg

    conds = list(scenario.get("correctness") or [])
    if "I01" in conds:
        if doc_output_text is None:
            return False, "I01: missing doc output text for Unicode check"
        if "\u0301" not in doc_output_text or "\U0002000b" not in doc_output_text:
            return False, "I01: combining mark or non-BMP scalar not preserved in output"

    if "I02" in conds:
        if doc_output_text is None:
            return False, "I02: missing doc output text for emoji/grapheme check"
        fam = "\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
        if fam not in doc_output_text:
            return False, "I02: ZWJ family sequence not preserved in output"
        if "\U0001f44d\U0001f3fb" not in doc_output_text:
            return False, "I02: skin-tone thumbs-up sequence not preserved in output"

    if "I03" in conds:
        if doc_output_text is None:
            return False, "I03: missing doc output text for bidi check"
        if "Hello" not in doc_output_text or "\u0645\u0631\u062d\u0628\u0627" not in doc_output_text:
            return False, "I03: bidi logical text not preserved in output"

    if "I04" in conds:
        return False, "I04: IME composition requires os_ime probe (not available on ci_contract headless)"

    return True, ""
