#!/usr/bin/env python3
"""Compare the two typing witnesses on a trial run's samples (#245) and record the result.

usage: python3 -I build/e2_witness_trial.py <trial pull dir> [--harness <commit>] [--out <record.json>]

A trial (shakedown) run reads the settled-pixel witness as a shadow beside the glyph witness for the
editors that have glyph outlines. Each such key press that both witnesses timed is compared: do the two
end on the same frame? The record (default ``perf/container/e2_witness_trial.json``) is what Report E2
prints; no figure of this comparison is typed by hand (#255).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "perf" / "container" / "e2_witness_trial.json"
SAME_FRAME_MS = 0.01  # both times are frame timestamps: the same frame is the same number


def compare(pull: Path) -> dict:
    compared = same = 0
    editors: set[str] = set()
    runs: set[str] = set()
    not_compared: dict[str, int] = {}
    differed: dict[tuple[str, str, int], list[float]] = {}
    for path in sorted(pull.glob("*/runs/*/benchmark_warm_cold/*/samples/input-*.json")):
        row = json.loads(path.read_text())
        confirmation = row.get("edit_confirmation") or {}
        shadow = confirmation.get("pixel_settle_shadow")
        if not isinstance(shadow, dict) or row.get("outcome") != "measured":
            continue
        glyph, pixels = confirmation.get("witness_page_ms"), shadow.get("match_page_ms")
        if shadow.get("failure_reason") or not isinstance(pixels, (int, float)) or not isinstance(glyph, (int, float)):
            not_compared["shadow_refused"] = not_compared.get("shadow_refused", 0) + 1
            continue
        compared += 1
        editors.add(row["editor_id"])
        runs.add(f"{path.parents[5].name}/{path.parents[3].name}")  # <space>/<run id>
        later = glyph - pixels
        if abs(later) <= SAME_FRAME_MS:
            same += 1
        else:
            differed.setdefault((row["editor_id"], row["criterion_id"], int(row.get("iteration") or 0)), []).append(later)
    return {
        "issue": 245,
        "compared": compared,
        "same_frame": same,
        "editors": sorted(editors),
        "differed": [{"editor": editor, "criterion": criterion, "key": key, "count": len(values),
                      "glyph_later_ms": [round(min(values), 1), round(max(values), 1)]}
                     for (editor, criterion, key), values in sorted(differed.items())],
        "not_compared": not_compared,
        "runs": sorted(runs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pull", type=Path)
    parser.add_argument("--harness", default=None, help="the harness commit of the trial run")
    parser.add_argument("--out", type=Path, default=RECORD)
    args = parser.parse_args()
    record = compare(args.pull)
    if not record["compared"]:
        parser.error(f"no key press with both witnesses under {args.pull}")
    if args.harness:
        record["harness"] = args.harness
    args.out.write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
