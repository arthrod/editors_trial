"""B1c — the reader and validator of witness records.

`perf/runner/witness.mjs` measures frames in a browser and prints a plain JSON
record. This module is the other half: it reads those records and says
whether a sample may be kept.

The rules are the ones the browser lanes agreed on (and, since #130, the ones
the adversarial review forced closed):

* the record must have the fields the witness module promises, with the right
  types (``outcome``, ``frame_page_ms``, ``frames_total``, ``frames_after``,
  ``diff_ratio``, ``threshold``, ``caret_masked``, ``document_scoped``), all
  finite — ``NaN`` and infinities are refused at parse and at validation;
* a record whose ``outcome`` is ``no_frame`` is **refused**: there was no
  frame that showed the change, so there is no latency to publish;
* a witnessed record must carry its evidence: at least one frame after the
  marker, pixels above the recorded threshold and floor, the caret mask
  applied. A record with no outcome at all is refused (``no_outcome``), not
  quietly accepted;
* the record must be document-scoped (``document_scoped: true``): a
  whole-frame diff lets shell damage pose as document paint, so a record
  without a region is refused (``not_document_scoped``);
* the record must carry an **acceptable clock check** from its run — the
  nested ``clock_check`` record (`clockSkew()`'s output: the pixel anchor,
  its causality and lag bounds, the page offset), echoed by every
  ``witnessFrame()`` record. A missing or failed check is refused
  (``clock_check_missing`` / ``clock_check_not_acceptable``), including the
  legacy top-level shape (``clock_skew_acceptable`` + ``clock_skew_ms``),
  which is accepted only when the flag is explicitly true and the offset is
  finite and within the bound;
* a refusal is an outcome, never a zero: `validate_witness` returns the
  verdict with a named ``reason`` and keeps the record's own payload.

The named reasons: ``record_not_a_mapping``, ``clock_skew_above_bound``,
``clock_check_missing``, ``clock_check_not_acceptable``,
``not_document_scoped``, ``no_outcome``, ``unknown_outcome``, ``no_frame``,
``nonfinite_time``, ``no_frame_time``, ``no_frame_after_marker``,
``no_pixel_evidence``, ``caret_mask_failed``, ``caret_not_masked``,
``invalid_record``.

Usage:

    python3 -m perf.runner.witness --file out/witness.json [--bound-ms 2]

prints the verdict as JSON and exits 1 when the record is refused (2 when the
file is not a record at all — unreadable, or not valid JSON such as a bare
``NaN``).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

#: The default bound on the page-local clock offset, in milliseconds. The
#: clock *check* applies it to ``page_offset_ms``; it is not, and was never,
#: a bound on the screencast conversion error (see witness.mjs's header for
#: the published conversion bound: [-2 ms, +the anchor lag bound]).
DEFAULT_SKEW_BOUND_MS = 2.0

#: The absolute pixel floor a witnessed frame must differ by, unless the
#: record carries its own ``min_pixels``.
DEFAULT_MIN_PIXELS = 4

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
    "document_scoped",
)


def _reject_constant(name):
    """`NaN`/`Infinity` are not JSON; a record file carrying them is not one."""
    raise ValueError("not valid JSON evidence: %s is not an accepted number" % (name,))


def load_witness(path):
    """Read one witness record from disk.

    The file holds one JSON object. A JSON array is returned as a list, so a
    caller can tell a bundle from a record. Non-finite JSON constants
    (``NaN``, ``Infinity``) are rejected here: the stdlib reader accepts
    them, and a record that needs one is not evidence (#130 defect 4).
    """
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text, parse_constant=_reject_constant)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _finite_number(value):
    return _number(value) and math.isfinite(float(value))


def _skew_of(record, skew=None):
    """The page-local clock offset of a record, in milliseconds, or None."""
    if _finite_number(skew):
        return float(skew)
    for key in ("clock_skew_ms", "skew_ms"):
        value = record.get(key)
        if _finite_number(value):
            return float(value)
    nested = record.get("clock_check")
    if isinstance(nested, dict) and _finite_number(nested.get("page_offset_ms")):
        return float(nested["page_offset_ms"])
    nested = record.get("clock_skew")
    if isinstance(nested, dict) and _finite_number(nested.get("skew_ms")):
        return float(nested["skew_ms"])
    return None


#: (reason, predicate on the record) in precedence order; the first failure
#: names the verdict's reason.
def _reason_of(record, bound, errors):
    del errors  # the tokens below are decided structurally, in order
    if not isinstance(record, dict):
        return "record_not_a_mapping"
    nested = record.get("clock_check") if isinstance(record.get("clock_check"), dict) else None
    skew = _skew_of(record)
    flag = record.get("clock_skew_acceptable")
    if _finite_number(skew) and abs(float(skew)) > float(bound):
        return "clock_skew_above_bound"
    if nested is not None:
        if nested.get("acceptable") is not True:
            return "clock_check_not_acceptable"
    else:
        if flag is not True:
            return "clock_check_not_acceptable" if flag is False else "clock_check_missing"
        if not _finite_number(skew):
            return "clock_check_missing"
    if record.get("document_scoped") is not True:
        return "not_document_scoped"
    outcome = record.get("outcome")
    if outcome is None:
        return "no_outcome"
    if outcome not in OUTCOMES:
        return "unknown_outcome"
    if outcome == "no_frame":
        return "no_frame"
    frame_page_ms = record.get("frame_page_ms")
    if _number(frame_page_ms) and not math.isfinite(float(frame_page_ms)):
        return "nonfinite_time"
    if not _number(frame_page_ms):
        return "no_frame_time"
    frames_after = record.get("frames_after")
    if isinstance(frames_after, int) and not isinstance(frames_after, bool):
        if frames_after < 1:
            return "no_frame_after_marker"
    diff_ratio = record.get("diff_ratio")
    threshold = record.get("threshold")
    changed = record.get("changed_pixels")
    min_pixels = record.get("min_pixels", DEFAULT_MIN_PIXELS)
    if (
        _finite_number(diff_ratio)
        and _finite_number(threshold)
        and not float(diff_ratio) > float(threshold)
    ):
        return "no_pixel_evidence"
    if _finite_number(changed) and isinstance(min_pixels, int):
        if float(changed) < min_pixels:
            return "no_pixel_evidence"
    if record.get("caret_masked") is not True:
        if record.get("caret_mask_error"):
            return "caret_mask_failed"
        return "caret_not_masked"
    return "invalid_record"


def validate_witness(record, skew=None, bound_ms=DEFAULT_SKEW_BOUND_MS):
    """Validate one witness record.

    Returns a verdict:

    ``{"ok": bool, "refused": bool, "reason": str|None, "errors": [str],
       "outcome": str|None, "skew_ms": float|None, "bound_ms": float,
       "skew_checked": bool, "clock_check_ok": bool|None,
       "document_scoped": bool|None, "record": dict}``

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
            "clock_check_ok": None,
            "document_scoped": None,
            "record": None,
        }

    for field in _REQUIRED_FIELDS:
        if field not in record:
            errors.append("missing field %r" % (field,))

    outcome = record.get("outcome")
    if outcome is None:
        errors.append("the record carries no outcome")
    elif outcome not in OUTCOMES:
        errors.append("unknown outcome %r" % (outcome,))
    if outcome == "no_frame":
        # A refusal is an outcome, not a zero: there was no frame that showed
        # the change, so there is no latency to publish.
        errors.append("no_frame: the witness saw no frame that showed the change")

    frame_page_ms = record.get("frame_page_ms")
    if frame_page_ms is not None and not _finite_number(frame_page_ms):
        errors.append("frame_page_ms must be a finite number or null")
    if outcome == "witnessed" and not _finite_number(frame_page_ms):
        errors.append("a witnessed frame needs a finite frame_page_ms")
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
    if outcome == "witnessed":
        frames_after = record.get("frames_after")
        if isinstance(frames_after, int) and not isinstance(frames_after, bool):
            if frames_after < 1:
                errors.append(
                    "a witnessed frame needs at least one frame after the marker"
                )
        else:
            errors.append("a witnessed frame needs a frames_after count")

    diff_ratio = record.get("diff_ratio")
    if diff_ratio is not None:
        if not _finite_number(diff_ratio):
            errors.append("diff_ratio must be a finite number")
        elif not 0.0 <= float(diff_ratio) <= 1.0:
            errors.append("diff_ratio must be between 0 and 1")
    threshold = record.get("threshold")
    if threshold is not None:
        if not _finite_number(threshold):
            errors.append("threshold must be a finite number")
        elif float(threshold) <= 0:
            errors.append("threshold must be positive")
    if outcome == "witnessed":
        if not (_finite_number(diff_ratio) and _finite_number(threshold)):
            errors.append("a witnessed frame needs diff_ratio and threshold")
        elif not float(diff_ratio) > float(threshold):
            errors.append(
                "a witnessed frame must differ by more than the threshold "
                "(diff_ratio %r <= threshold %r)" % (diff_ratio, threshold)
            )
        changed = record.get("changed_pixels")
        min_pixels = record.get("min_pixels", DEFAULT_MIN_PIXELS)
        if not _finite_number(changed):
            errors.append("a witnessed frame needs changed_pixels")
        elif isinstance(min_pixels, int) and not isinstance(min_pixels, bool):
            if float(changed) < min_pixels:
                errors.append(
                    "a witnessed frame must differ in at least %s pixels "
                    "(changed_pixels %r)" % (min_pixels, changed)
                )

    caret_masked = record.get("caret_masked")
    if caret_masked is not None and not isinstance(caret_masked, bool):
        errors.append("caret_masked must be a boolean")
    if caret_masked is not True:
        if record.get("caret_mask_error"):
            errors.append(
                "the caret mask failed (%r), so the witness is not proven" % (record.get("caret_mask_error"),)
            )
        else:
            errors.append("the caret mask was not applied (caret_masked is false)")

    document_scoped = record.get("document_scoped")
    if document_scoped is not None and not isinstance(document_scoped, bool):
        errors.append("document_scoped must be a boolean")
    if document_scoped is not True:
        errors.append(
            "the record is not document-scoped: a whole-frame diff lets shell "
            "damage pose as document paint (pass a region to witnessFrame)"
        )

    # The clock check of the run (#130 defect 3): publication needs an
    # acceptable one. The nested record is the real evidence; the legacy
    # top-level shape is accepted only when it explicitly says acceptable and
    # its offset is finite and within the bound.
    nested = record.get("clock_check")
    clock_check_ok = None
    if isinstance(nested, dict):
        if nested.get("acceptable") is not True:
            clock_check_ok = False
            nested_reason = nested.get("reason")
            if isinstance(nested_reason, str) and nested_reason:
                errors.append(
                    "the run's clock check is not acceptable: %s" % (nested_reason,)
                )
            else:
                errors.append("the run's clock check is not acceptable")
        else:
            clock_check_ok = True
    else:
        flag = record.get("clock_skew_acceptable")
        skew_ms = _skew_of(record, skew)
        if flag is not True:
            clock_check_ok = False
            if flag is False:
                errors.append(
                    "the record's clock check says acceptable=false "
                    "(clock_skew_acceptable is false)"
                )
            else:
                errors.append(
                    "the record carries no clock check for its run "
                    "(clock_check missing, clock_skew_acceptable absent)"
                )
        elif not _finite_number(skew_ms):
            clock_check_ok = False
            errors.append(
                "the record claims an acceptable clock check without a finite "
                "page offset"
            )
        else:
            clock_check_ok = True

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
    reason = _reason_of(record, bound, errors) if refused else None

    return {
        "ok": not refused,
        "refused": refused,
        "reason": reason,
        "errors": errors,
        "outcome": outcome if isinstance(outcome, str) else None,
        "skew_ms": skew_ms,
        "bound_ms": bound,
        "skew_checked": skew_checked,
        "clock_check_ok": clock_check_ok,
        "document_scoped": document_scoped if isinstance(document_scoped, bool) else None,
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
