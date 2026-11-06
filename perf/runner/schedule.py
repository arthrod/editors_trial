from perf.schema import sample_budget_for_profile

_RANK = {"ci_contract": 0, "ci_broad": 1, "dedicated_publish": 2}


def profile_rank(execution_profile):
    try:
        return _RANK[execution_profile]
    except KeyError as exc:
        raise ValueError("execution_profile") from exc


def enqueue_cache_states(scenario, env):
    states = list(scenario["cache_states"])
    if env["execution_profile"] != "dedicated_publish" or env["host_class"] != "dedicated":
        states = [state for state in states if state != "os_cache_cold"]
    return states


def _not_run():
    return {
        "run": False,
        "failure_reason": "execution_profile",
        "cache_states": [],
        "sample_budget": 0,
        "publishable": False,
    }


def plan_attempts(scenario, env, editor_id, lane):
    del editor_id, lane
    if profile_rank(env["execution_profile"]) < profile_rank(scenario["min_execution_profile"]):
        return _not_run()
    if env["execution_profile"] == "ci_contract" and scenario["layer"] == "browser_visible":
        return _not_run()
    if scenario["id"] == "C20" and env["execution_profile"] != "dedicated_publish":
        return _not_run()
    budget = sample_budget_for_profile(env["execution_profile"], env["repetition_unit"])
    publishable = scenario["run_kind"] == "timing"
    return {
        "run": True,
        "failure_reason": None,
        "cache_states": enqueue_cache_states(scenario, env),
        "sample_budget": budget,
        "publishable": publishable,
    }
