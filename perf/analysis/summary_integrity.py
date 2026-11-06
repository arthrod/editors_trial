"""Validate ``ci_contract`` summary.json before it is treated as evidence."""

from __future__ import annotations


def assert_ci_contract_summary_valid(payload: dict) -> None:
    """Raise ``ValueError`` if a summary mixes publishable and non-publishable medians."""
    rows = payload.get("editors") or []
    by_crit: dict[str, list[dict]] = {}
    for row in rows:
        cid = row.get("criterion_id")
        if not cid:
            continue
        by_crit.setdefault(cid, []).append(row)

    for cid, group in by_crit.items():
        medians = [
            r
            for r in group
            if r.get("outcome") == "measured" and "median_ms" in r
        ]
        if len(medians) < 2:
            continue
        pub_vals = {r.get("publishable") for r in medians}
        if None in pub_vals:
            raise ValueError("summary row missing publishable for %s" % (cid,))
        if False in pub_vals and True in pub_vals:
            raise ValueError(
                "summary mixes publishable and non-publishable medians for %s" % (cid,)
            )
