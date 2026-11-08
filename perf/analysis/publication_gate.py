"""I10 and policy: when a raw timing row may be published as a distribution."""

from perf.runner.policy import publication_decision


def trial_publishable_flags(env, scenario_layer: str, sample_count: int | None):
    """Return ``(publishable, block_reason)`` for a **measured** timing trial."""
    env = dict(env)
    env.setdefault("cache_state", "process_cold_fs_warm")
    env.setdefault("host_class", "ci_coarse")
    try:
        publication_decision(env, scenario_layer)
    except ValueError as exc:
        return False, str(exc)
    if env.get("run_kind") != "timing":
        return False, "diagnostic run_kind is not a timing publication"
    if sample_count is None:
        return True, None
    if sample_count < 2:
        return False, "I10: publishable distribution requires n>=2 independent samples"
    return True, None
