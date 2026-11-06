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
