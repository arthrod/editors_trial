def utf16_len(text):
    return len(text.encode("utf-16-le")) // 2


def grapheme_spans(text):
    clusters = (
        "\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466",
        "\U0001f44d\U0001f3fb",
    )
    if text not in clusters:
        raise ValueError("fixture")
    return [(0, utf16_len(text))]


def backspace_grapheme(text):
    family = "\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
    if text.startswith(family):
        return text[len(family) :]
    raise ValueError("fixture")


def bidi_hit(logical, hit_name):
    if logical != "Hello \u0645\u0631\u062d\u0628\u0627":
        raise ValueError("fixture")
    if hit_name == "visual_left":
        return 0
    if hit_name == "arabic_start":
        return 6
    raise ValueError("hit_name")


def composition_observation(route, phases):
    synthetic = {"playwright_insert_text", "playwright_fill", "dispatched_composition_event"}
    updates = [phase["data"] for phase in phases if phase["name"] == "compositionupdate"]
    committed = next(phase["data"] for phase in phases if phase["name"] == "compositionend")
    if route in synthetic:
        return {"coverage": "synthetic", "os_ime": False, "updates": updates, "committed": committed}
    if route not in ("cdp_ime", "native_ime"):
        raise ValueError("route")
    return {"coverage": "os_ime", "os_ime": True, "updates": updates, "committed": committed}


def assert_readback(lane, expected, actual):
    if actual != expected:
        raise ValueError("correctness readback failed for %s" % (lane,))
