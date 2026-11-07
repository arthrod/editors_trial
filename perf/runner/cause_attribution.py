"""Attribute warm vs non-warm latency deltas using isolated probe medians."""

from __future__ import annotations

CAUSE_LABELS = (
    "process_startup",
    "browser_launch",
    "wasm_js_compile",
    "document_parse",
    "residual_steady_state",
    "mixed_unresolved",
)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def attribute_delta(
    cold_median: float,
    warm_median: float,
    probes: dict,
) -> tuple[str, dict]:
    """
    Return a cause label and an attribution breakdown.

    ``probes`` may include medians (ms) for:
    - browser_launch_only
    - document_navigation_only
    - model_ready_browser
    - document_reload_same_context
    """
    delta = warm_median - cold_median
    overhead = cold_median - warm_median
    breakdown = {
        "delta_ms": delta,
        "overhead_ms": overhead,
        "cold_median_ms": cold_median,
        "warm_median_ms": warm_median,
    }

    if overhead < 15.0:
        return "residual_steady_state", breakdown

    launch = float(probes.get("browser_launch_only_median", 0) or 0)
    nav = float(probes.get("document_navigation_only_median", 0) or 0)
    model = float(probes.get("model_ready_browser_median", 0) or 0)
    reload = float(probes.get("document_reload_same_context_median", 0) or 0)
    spawn = float(probes.get("process_spawn_ms_median", 0) or 0)

    after_launch = max(0.0, nav - launch)
    compile_est = max(0.0, model - nav) if model and nav else max(0.0, reload * 0.0)
    if model and reload:
        compile_est = max(0.0, min(model, model - reload))
    parse_est = max(0.0, overhead - launch - compile_est - spawn)

    parts = [
        ("browser_launch", launch),
        ("wasm_js_compile", compile_est),
        ("document_parse", parse_est),
        ("process_startup", spawn),
    ]
    ranked = sorted(parts, key=lambda item: item[1], reverse=True)
    top_label, top_share = ranked[0]
    second_share = ranked[1][1] if len(ranked) > 1 else 0.0

    breakdown.update(
        {
            "browser_launch_ms": launch,
            "document_navigation_ms": nav,
            "model_ready_browser_ms": model,
            "document_reload_ms": reload,
            "process_spawn_ms": spawn,
            "ranked_parts_ms": {label: val for label, val in ranked},
        }
    )

    if top_share < 10.0:
        return "mixed_unresolved", breakdown
    if second_share > top_share * 0.65:
        return "mixed_unresolved", breakdown
    if top_label not in CAUSE_LABELS:
        return "mixed_unresolved", breakdown
    return top_label, breakdown


def probe_medians(probe_rows: list[dict]) -> dict:
    """Collapse per-sample probe dicts to median fields used by ``attribute_delta``."""
    if not probe_rows:
        return {}
    keys = (
        "browser_launch_only_ms",
        "document_navigation_only_ms",
        "model_ready_browser_ms",
        "document_reload_same_context_ms",
        "process_spawn_ms",
    )
    out = {}
    for key in keys:
        samples = [row[key] for row in probe_rows if key in row and row[key] is not None]
        if samples:
            med_key = key.replace("_ms", "_median")
            out[med_key] = _median(samples)
    return out


C05_PROBE_KEY = "single_edit_ms"
C06_PROBE_KEY = "sustained_typing_median_ms"


def assert_same_probe_paired(cold_probe_key: str, warm_probe_key: str) -> None:
    """Fail when a warm/cold summary row mixes unlike probe fields."""
    if cold_probe_key != warm_probe_key:
        raise ValueError(
            "warm/cold pair must use the same probe on both sides (got cold=%r warm=%r)"
            % (cold_probe_key, warm_probe_key)
        )


def assert_warm_cold_distinct(cold_samples: list[float], warm_samples: list[float]) -> None:
    """Fail if warm samples appear copied from cold (same list or pairwise equal)."""
    if cold_samples == warm_samples:
        raise ValueError("warm samples must not equal cold samples")
    if len(cold_samples) == len(warm_samples) and all(
        a == b for a, b in zip(cold_samples, warm_samples)
    ):
        raise ValueError("warm samples must not be pairwise identical to cold samples")
