_FIELDS = (
    "rss_bytes",
    "pss_bytes",
    "uss_bytes",
    "cgroup_current_bytes",
    "cgroup_peak_bytes",
)


def validate_memory_sample(sample):
    for key in _FIELDS:
        if key not in sample:
            raise ValueError(key)
        value = sample[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(key)
    count = sample["process_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("process_count")
    if sample["pss_bytes"] > sample["rss_bytes"]:
        raise ValueError("pss_bytes exceeds rss_bytes")
    if sample["uss_bytes"] > sample["pss_bytes"]:
        raise ValueError("uss_bytes exceeds pss_bytes")
