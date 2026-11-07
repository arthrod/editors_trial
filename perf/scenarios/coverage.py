_OWNED_CONDITIONS = ("I01", "I02", "I03", "I04", "I12")


def matrix_gaps(matrix, rows):
    present = {row["id"] for row in rows}
    mentioned = set()
    for row in rows:
        mentioned.update(row.get("correctness") or [])
    declared_conditions = {item["id"] for item in matrix["interpretation_conditions"]}
    gaps = [item["id"] for item in matrix["criteria"] if item["id"] not in present]
    for condition_id in _OWNED_CONDITIONS:
        if condition_id in declared_conditions and condition_id not in mentioned:
            gaps.append(condition_id)
    unknown = sorted(mentioned - declared_conditions)
    if unknown:
        raise ValueError("unknown correctness id %s" % (unknown,))
    return gaps
