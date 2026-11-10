"""B1c — the reader and validator of witness records.

`perf/runner/witness.mjs` measures frames in a browser and prints a plain JSON
record. This module is the other half: it reads those records and says
whether a sample may be kept.

The rules are the ones the browser lanes agreed on:

* the record must have the fields the witness module promises, with the right
  types (``outcome``, ``frame_page_ms``, ``frames_total``, ``frames_after``,
  ``diff_ratio``, ``threshold``, ``caret_masked``);
* a record whose ``outcome`` is ``no_frame`` is **refused**: there was no
  frame that showed the change, so there is no latency to publish;
* a record whose clock skew is above the bound is **refused**: the frame's
  timestamp could not be placed in the page's clock, so the sample would be a
  number without a meaning;
* a refusal is an outcome, never a zero: `validate_witness` returns the
  verdict with the reason and keeps the record's own payload.

Usage:

    python3 -m perf.runner.witness --file out/witness.json [--bound-ms 2]

prints the verdict as JSON and exits 1 when the record is refused.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

#: The default bound on the clock skew, in milliseconds. The browser lanes
#: refuse a sample whose |skew| is above it.
DEFAULT_SKEW_BOUND_MS = 2.0

#: The outcomes a witness record may carry.
OUTCOMES = ("witnessed", "no_frame")

_REQUIRED_FIELDS = (
    "outcome",
    "frame_page_ms",
    "frames_total",
    "frames_after",
    "diff_ratio",
    "threshold",
    "caret_masked",
)


def load_witness(path):
    """Read one witness record from disk.

    The file holds one JSON object. A JSON array is returned as a list, so a
    caller can tell a bundle from a record.
    """
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _skew_of(record, skew=None):
    """The clock skew of a record, in milliseconds, or None."""
    if _number(skew):
        return float(skew)
    for key in ("clock_skew_ms", "skew_ms"):
        value = record.get(key)
        if _number(value):
            return float(value)
    nested = record.get("clock_skew")
    if isinstance(nested, dict) and _number(nested.get("skew_ms")):
        return float(nested["skew_ms"])
    return None


def validate_witness(record, skew=None, bound_ms=DEFAULT_SKEW_BOUND_MS):
    """Validate one witness record.

    Returns a verdict:

    ``{"ok": bool, "refused": bool, "reason": str|None, "errors": [str],
       "outcome": str|None, "skew_ms": float|None, "bound_ms": float,
       "skew_checked": bool, "record": dict}``

    `ok` is true only for a record that may be published; `refused` is the
    opposite, with the reason.
    """
    bound = float(bound_ms)
    errors = []
    if not isinstance(record, dict):
        return {
            "ok": False,
            "refused": True,
            "reason": "record_not_a_mapping",
            "errors": ["the witness record must be a JSON object"],
            "outcome": None,
            "skew_ms": None,
            "bound_ms": bound,
            "skew_checked": False,
            "record": None,
        }

    for field in _REQUIRED_FIELDS:
        if field not in record:
            errors.append("missing field %r" % (field,))

    outcome = record.get("outcome")
    if outcome is not None and outcome not in OUTCOMES:
        errors.append("unknown outcome %r" % (outcome,))
    if outcome == "no_frame":
        # A refusal is an outcome, not a zero: there was no frame that showed
        # the change, so there is no latency to publish.
        errors.append("no_frame: the witness saw no frame that showed the change")

    frame_page_ms = record.get("frame_page_ms")
    if frame_page_ms is not None and not _number(frame_page_ms):
        errors.append("frame_page_ms must be a number or null")
    if outcome == "witnessed" and not _number(frame_page_ms):
        errors.append("a witnessed frame needs a frame_page_ms")
    if outcome == "no_frame" and frame_page_ms is not None:
        errors.append("a no_frame witness has no frame_page_ms")

    for field in ("frames_total", "frames_after"):
        value = record.get(field)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append("%s must be an integer" % (field,))
        elif value < 0:
            errors.append("%s must not be negative" % (field,))

    diff_ratio = record.get("diff_ratio")
    if diff_ratio is not None:
        if not _number(diff_ratio):
            errors.append("diff_ratio must be a number")
        elif not 0.0 <= float(diff_ratio) <= 1.0:
            errors.append("diff_ratio must be between 0 and 1")

    threshold = record.get("threshold")
    if threshold is not None:
        if not _number(threshold):
            errors.append("threshold must be a number")
        elif float(threshold) <= 0:
            errors.append("threshold must be positive")

    caret_masked = record.get("caret_masked")
    if caret_masked is not None and not isinstance(caret_masked, bool):
        errors.append("caret_masked must be a boolean")

    skew_ms = _skew_of(record, skew)
    skew_checked = skew_ms is not None
    if skew_checked and math.isnan(skew_ms):
        errors.append("the clock skew is not a number")
        skew_checked = False
    if skew_checked and abs(skew_ms) > bound:
        errors.append(
            "clock skew %.3f ms is above the bound of %.3f ms" % (skew_ms, bound)
        )

    refused = bool(errors)
    reason = None
    if refused:
        if any(e.startswith("clock skew") for e in errors):
            reason = "clock_skew_above_bound"
        elif any(e.startswith("no_frame") for e in errors):
            reason = "no_frame"
        else:
            reason = "invalid_record"

    return {
        "ok": not refused,
        "refused": refused,
        "reason": reason,
        "errors": errors,
        "outcome": outcome if isinstance(outcome, str) else None,
        "skew_ms": skew_ms,
        "bound_ms": bound,
        "skew_checked": skew_checked,
        "record": record,
    }


def main(argv=None):
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Read and validate a witness record.")
    parser.add_argument("--file", required=True, help="the witness record (JSON)")
    parser.add_argument(
        "--bound-ms",
        type=float,
        default=DEFAULT_SKEW_BOUND_MS,
        help="the clock-skew bound in milliseconds (default: %s)"
        % (DEFAULT_SKEW_BOUND_MS,),
    )
    args = parser.parse_args(argv)

    try:
        record = load_witness(args.file)
    except (OSError, ValueError) as error:
        sys.stderr.write("witness: cannot read %s: %s\n" % (args.file, error))
        return 2

    if isinstance(record, list):
        verdicts = [validate_witness(item, bound_ms=args.bound_ms) for item in record]
        refused = any(v["refused"] for v in verdicts)
        sys.stdout.write(
            json.dumps({"records": len(verdicts), "refused": refused, "verdicts": verdicts})
            + "\n"
        )
        return 1 if refused else 0

    verdict = validate_witness(record, bound_ms=args.bound_ms)
    sys.stdout.write(json.dumps(verdict) + "\n")
    return 1 if verdict["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
