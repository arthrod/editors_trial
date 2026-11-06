_FEATURES = ("collaboration", "ai_panel", "proofing", "style_display", "busy_panel")
_BASE = {
    "P0": {"collaboration": "off", "ai_panel": "off", "proofing": "off", "style_display": "off", "busy_panel": "off"},
    "P1": {"collaboration": "off", "ai_panel": "off", "proofing": "off", "style_display": "on", "busy_panel": "off"},
    "P2": {"collaboration": "off", "ai_panel": "off", "proofing": "on", "style_display": "on", "busy_panel": "off"},
    "P3": {"collaboration": "off", "ai_panel": "off", "proofing": "on", "style_display": "on", "busy_panel": "on"},
}


def feature_profile(name):
    if name not in _BASE:
        raise ValueError("feature profile %r" % (name,))
    profile = dict(_BASE[name])
    profile["name"] = name
    profile["disabled_features"] = []
    return profile


def with_fallback(profile, disabled):
    updated = dict(profile)
    updated["disabled_features"] = list(disabled)
    for feature in disabled:
        if feature not in _FEATURES:
            raise ValueError("unknown feature %r" % (feature,))
        updated[feature] = "off"
    return updated
