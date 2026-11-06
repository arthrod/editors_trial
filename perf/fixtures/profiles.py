from pathlib import Path

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


def size_ladder():
    return [
        {"workload_id": "micro-paragraphs", "paragraphs": 5, "paragraph_chars": 20, "unicode_class": "ascii", "match_count": 0, "seed": 1, "shape": "micro"},
        {"workload_id": "micro-search", "paragraphs": 10, "paragraph_chars": 20, "unicode_class": "ascii", "match_count": 5, "seed": 1, "shape": "micro-search"},
        {"workload_id": "short-paragraphs", "paragraphs": 100, "paragraph_chars": 40, "unicode_class": "ascii", "match_count": 0, "seed": 1, "shape": "short"},
        {"workload_id": "long-paragraphs", "paragraphs": 20, "paragraph_chars": 4000, "unicode_class": "ascii", "match_count": 0, "seed": 1, "shape": "long"},
        {"workload_id": "one-paragraph", "paragraphs": 1, "paragraph_chars": 8000, "unicode_class": "ascii", "match_count": 0, "seed": 1, "shape": "single"},
        {"workload_id": "mixed-utf8", "paragraphs": 10, "paragraph_chars": 80, "unicode_class": "mixed", "match_count": 0, "seed": 1, "shape": "mixed"},
        {"workload_id": "search-dense", "paragraphs": 200, "paragraph_chars": 40, "unicode_class": "ascii", "match_count": 1000, "seed": 1, "shape": "search"},
        {"workload_id": "paginated-equivalent", "paragraphs": 6, "paragraph_chars": 400, "unicode_class": "ascii", "match_count": 0, "seed": 1, "shape": "pages"},
    ]


def assert_not_hostile(path, root):
    candidate = Path(path).resolve()
    corpus = Path(root).resolve()
    try:
        candidate.relative_to(corpus)
    except ValueError:
        return
    raise ValueError("hostile packages are not performance fixtures: %s" % (candidate,))
