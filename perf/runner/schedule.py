from perf.fixtures.profiles import allowed_workloads
from perf.schema import sample_budget_for_profile

_RANK = {"ci_contract": 0, "ci_broad": 1, "dedicated_publish": 2}


def profile_rank(execution_profile):
    try:
        return _RANK[execution_profile]
    except KeyError as exc:
        raise ValueError("execution_profile") from exc


def enqueue_cache_states(scenario, env):
    states = list(scenario["cache_states"])
    if env["execution_profile"] != "dedicated_publish":
        states = [state for state in states if state != "os_cache_cold"]
    return states


def plan_attempts(scenario, env, editor_id, lane):
    del editor_id, lane
    if profile_rank(env["execution_profile"]) < profile_rank(scenario["min_execution_profile"]):
        return {"run": False, "failure_reason": "execution_profile", "cache_states": [], "sample_budget": 0}
    if scenario["id"] == "C20" and env["execution_profile"] != "dedicated_publish":
        return {"run": False, "failure_reason": "execution_profile", "cache_states": [], "sample_budget": 0}
    workload_id = env.get("workload_id")
    if workload_id is not None:
        allowed = allowed_workloads(env["execution_profile"])
        if workload_id not in allowed:
            return {"run": False, "failure_reason": "execution_profile", "cache_states": [], "sample_budget": 0}
    if (
        scenario.get("layer") == "browser_visible"
        and env["execution_profile"] == "ci_contract"
    ):
        return {"run": False, "failure_reason": "execution_profile", "cache_states": [], "sample_budget": 0}
    budget = sample_budget_for_profile(env["execution_profile"], env["repetition_unit"])
    return {
        "run": True,
        "failure_reason": None,
        "cache_states": enqueue_cache_states(scenario, env),
        "sample_budget": budget,
    }
