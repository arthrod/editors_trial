#!/usr/bin/env python3
"""
Dump the namespace-survival measurement as JSON so the reports can be
generated from measured data rather than transcribed by hand.

usage: python3 build/ns_json.py [out.json]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ns_map  # noqa: E402


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ns_map.BASE, "out", "ns_map.json")

    base_el, base_at, base_parts, base_names = ns_map.scan(
        os.path.join(ns_map.BASE, "fixture", "complex.docx"))
    uris = sorted(set(base_el) | set(base_at),
                  key=lambda u: -(base_el[u] + base_at[u]))

    data = {
        "labels": [t[0] for t in ns_map.TARGETS],
        "namespaces": [],
    }
    for u in uris:
        row = {
            "uri": u,
            "prefix": ns_map.NAMES.get(u, u.split("/")[-1][:16]),
            "corpus_elements": base_el[u],
            "corpus_attrs": base_at[u],
            "corpus_parts": base_parts[u],
            "corpus_names": sorted(base_names.get(u, set())),
            "survival": {},
        }
        for label, rel in ns_map.TARGETS:
            p = os.path.join(ns_map.BASE, rel)
            if not os.path.exists(p):
                row["survival"][label] = None
                continue
            e, a, _, names = ns_map.scan(p)
            if e is None:
                row["survival"][label] = None
                continue
            want = base_names.get(u, set())
            got = names.get(u, set())
            row["survival"][label] = {
                "kept": len(want & got),
                "total": len(want),
                "lost": sorted(want - got),
                "added": sorted(got - want),
                "elements": e[u],
                "attrs": a[u],
            }
        data["namespaces"].append(row)

    with open(out_path, "w") as f:
        json.dump(data, f, indent=1)
    print("wrote %s (%d namespaces)" % (out_path, len(data["namespaces"])))


if __name__ == "__main__":
    main()
