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
