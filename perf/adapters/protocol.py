from perf.adapters.capabilities import capability

_REFUSALS = ("unsupported", "not_applicable", "unverified", "failed", "not_run")


def refusal_trial(editor_id, lane, feature, outcome, criterion_id, failure_reason=None):
    if outcome not in _REFUSALS:
        raise ValueError("refusal outcome required, got %r" % (outcome,))
    if outcome in ("failed", "not_run"):
        if not isinstance(failure_reason, str) or not failure_reason:
            raise ValueError("failure_reason")
    trial = {
        "editor_id": editor_id,
        "lane": lane,
        "feature": feature,
        "outcome": outcome,
        "boundary": "not_measured",
        "claims": [],
        "samples_ms": [],
        "latency_ms": None,
        "criterion_id": criterion_id,
    }
    if failure_reason is not None:
        trial["failure_reason"] = failure_reason
    return trial


def trial_or_refusal(editor_id, lane, feature, criterion_id, feature_profile="P0"):
    if feature_profile not in ("P0", "P1", "P2", "P3"):
        raise ValueError("feature_profile")
    state = capability(editor_id, lane, feature)
    if state == "supported":
        trial = refusal_trial(
            editor_id,
            lane,
            feature,
            "not_run",
            criterion_id,
            failure_reason="adapter-not-implemented",
        )
    else:
        trial = refusal_trial(editor_id, lane, feature, state, criterion_id)
    trial["feature_profile"] = feature_profile
    return trial
