_LAYERS = {"native", "model", "browser_visible", "wasm_boundary"}
_VISIBLE = {"browser_visible"}


def publication_decision(env, layer):
    if layer not in _LAYERS:
        raise ValueError("layer")
    if env["run_kind"] != "timing":
        raise ValueError("diagnostic runs are not timing publications")
    if env["host_class"] == "ci_coarse" and layer in _VISIBLE:
        raise ValueError("ci_coarse cannot publish visible latency")
    if env["cache_state"] == "os_cache_cold" and env["host_class"] not in ("dedicated", "laboratory"):
        raise ValueError("os_cache_cold is dedicated-host only")
    if layer in _VISIBLE and env["repetition_unit"] != "fresh_process":
        raise ValueError("visible latency requires fresh_process")
    return "publish"
