def validate_browser_memory(record):
    if record["run_kind"] == "timing" and record.get("heap_snapshot"):
        raise ValueError("heap snapshot is diagnostic")
    js_heap = record["js_heap"]
    if js_heap["source"] == "usedJSHeapSize" and js_heap["role"] != "diagnostic_only":
        raise ValueError("usedJSHeapSize")
    if js_heap["source"] == "measureUserAgentSpecificMemory":
        if js_heap["status"] == "available" and not record["cross_origin_isolated"]:
            raise ValueError("cross_origin_isolated")
    dom = record["dom"]
    if dom["source"] == "Memory.getDOMCounters" and "detached_nodes" in dom:
        raise ValueError("getDOMCounters does not count detached nodes")
    wasm = record["wasm"]
    if wasm.get("meaning") != "capacity":
        raise ValueError("memory.buffer capacity")
    if wasm["status"] == "unverified":
        if wasm["byte_length"] is not None:
            raise ValueError("byte_length")
    elif wasm["status"] == "available":
        length = wasm["byte_length"]
        if isinstance(length, bool) or not isinstance(length, int) or length < 0:
            raise ValueError("byte_length")


def detached_dom_verdict(snapshot):
    if snapshot["retained_by_test"]:
        if snapshot["detached_nodes"] < 1:
            raise ValueError("red case must observe the retained subtree")
        return "red"
    if snapshot["detached_nodes"] != 0:
        return "fail"
    return "green"
