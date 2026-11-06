import random


def percentile(samples, p):
    if not samples:
        raise ValueError("empty samples")
    if p < 0 or p > 100:
        raise ValueError("percentile out of range")
    ordered = sorted(samples)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (p / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    fraction = rank - low
    return float(ordered[low] * (1.0 - fraction) + ordered[high] * fraction)


def median_absolute_deviation(samples):
    center = percentile(samples, 50)
    deviations = [abs(sample - center) for sample in samples]
    return percentile(deviations, 50)


def bootstrap_median_ci(samples, seed=0, draws=2000, level=0.95):
    if not samples:
        raise ValueError("empty samples")
    if not 0 < level < 1:
        raise ValueError("level")
    rng = random.Random(seed)
    count = len(samples)
    medians = []
    for _ in range(draws):
        draw = [samples[rng.randrange(count)] for _ in range(count)]
        medians.append(percentile(draw, 50))
    alpha = (1.0 - level) / 2.0
    return (percentile(medians, alpha * 100.0), percentile(medians, (1.0 - alpha) * 100.0))


def summarize(samples, cache_state, repetition_unit, seed=0):
    if cache_state not in ("process_cold_fs_warm", "os_cache_cold", "warm_steady"):
        raise ValueError("cache_state")
    if repetition_unit not in ("fresh_process", "in_process_iteration"):
        raise ValueError("repetition_unit")
    low, high = bootstrap_median_ci(samples, seed=seed)
    return {
        "n": len(samples),
        "median": percentile(samples, 50),
        "p90": percentile(samples, 90),
        "p95": percentile(samples, 95),
        "p99": percentile(samples, 99),
        "mad": median_absolute_deviation(samples),
        "ci95_low": low,
        "ci95_high": high,
        "minimum": percentile(samples, 0),
        "maximum": percentile(samples, 100),
        "cache_state": cache_state,
        "repetition_unit": repetition_unit,
    }


def summarize_groups(groups):
    if not groups:
        raise ValueError("empty groups")
    cache_state = groups[0]["cache_state"]
    repetition_unit = groups[0]["repetition_unit"]
    workload_id = groups[0]["workload_id"]
    pooled = []
    for group in groups:
        if group["cache_state"] != cache_state:
            raise ValueError("cache_state values differ")
        if group["repetition_unit"] != repetition_unit:
            raise ValueError("repetition_unit values differ")
        if group["workload_id"] != workload_id:
            raise ValueError("workload_id values differ")
        pooled.extend(group["samples"])
    return summarize(pooled, cache_state, repetition_unit)
