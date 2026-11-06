def cgroup_limit_sweep(execution_profile, limits):
    if execution_profile != "dedicated_publish":
        raise ValueError("cgroup limit sweeps require dedicated_publish")
    return {"run_kind": "diagnostic", "publishable": False, "limits": limits}
