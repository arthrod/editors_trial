"""C24 WASM boundary operation contract."""


def required_wasm_operations():
    return (
        "compile_and_instantiate",
        "empty_call",
        "scalar_call",
        "string_conversion",
        "typed_array_transfer",
        "batched_call",
        "memory_grow",
    )


def assert_wasm_report(report, capabilities=None):
    names = required_wasm_operations()
    if capabilities is None:
        capabilities = {name: True for name in names}
    missing = [n for n in names if n not in report]
    if missing:
        raise ValueError("wasm report missing %s" % (", ".join(missing),))
    for name in names:
        enabled = capabilities.get(name, True)
        val = report.get(name)
        if enabled:
            if not isinstance(val, list) or not val:
                raise ValueError("%s requires non-empty sample list" % (name,))
            for sample in val:
                if isinstance(sample, bool) or not isinstance(sample, (int, float)):
                    raise ValueError("%s samples must be numeric" % (name,))
                if sample != sample or sample in (float("inf"), float("-inf")) or sample < 0:
                    raise ValueError("%s sample not finite non-negative" % (name,))
        else:
            if val is not None:
                raise ValueError("%s must be null when capability is disabled" % (name,))
    if "editor_scenario_ms" in report and not any(report.get(n) for n in names):
        raise ValueError("compile_and_instantiate")

