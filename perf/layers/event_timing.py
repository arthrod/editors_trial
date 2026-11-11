def effective_duration_threshold(requested):
    if requested is None:
        return 104
    return max(16, int(requested))


def rounded_duration_ms(raw):
    return int((raw + 4) // 8 * 8)


def event_timing_status(raw_duration, requested_threshold, buffered_default=False):
    threshold = 104 if buffered_default else effective_duration_threshold(requested_threshold)
    if raw_duration < 16:
        return {"status": "censored", "duration_ms": None, "rounded_ms": None,
                "below_16_ms": True}
    duration = rounded_duration_ms(raw_duration)
    if duration < threshold:
        return {"status": "censored", "duration_ms": None, "rounded_ms": duration, "below_16_ms": False}
    return {"status": "observed", "duration_ms": duration, "rounded_ms": duration, "below_16_ms": False}


def aggregate_inp(entries):
    grouped = {}
    for entry in entries:
        interaction_id = entry["interaction_id"]
        if not interaction_id or entry.get("duration_ms") is None or entry.get("below_16_ms"):
            continue
        grouped.setdefault(interaction_id, []).append(entry["duration_ms"])
    if not grouped:
        return None
    return max(max(samples) for samples in grouped.values())


def samples_ms(entries):
    """Only observed entries contribute numerical durations to a distribution."""
    return [entry["duration_ms"] for entry in entries
            if entry.get("status") == "observed" and not entry.get("below_16_ms")
            and entry.get("duration_ms") is not None]
