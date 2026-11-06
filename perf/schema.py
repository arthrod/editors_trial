"""Trial records for the performance harness.

A trial either measured a named boundary or it did not. Non-measurements do
not carry a latency. A requestAnimationFrame callback, a constructor return,
and a model-ready mark are real events, and none of them is a user-visible
result by itself.
"""

_FORBIDDEN = (
    ("raf_callback", "visible_paint", "raf_callback cannot claim visible paint"),
    ("constructor_return", "usable", "constructor_return cannot claim usable"),
    ("model_ready", "user_visible", "model_ready cannot claim user-visible latency"),
)


def validate_trial(trial):
    claims = set(trial.get("claims") or [])
    boundary = trial["boundary"]
    for blocked_boundary, blocked_claim, message in _FORBIDDEN:
        if boundary == blocked_boundary and blocked_claim in claims:
            raise ValueError(message)
    if trial["outcome"] == "measured" and not trial.get("samples_ms"):
        raise ValueError("measured trial needs samples")
