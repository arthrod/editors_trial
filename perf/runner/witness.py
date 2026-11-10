"""B1c — the reader and validator of witness records.

`perf/runner/witness.mjs` measures frames in a browser and prints a plain JSON
record. This module is the other half: it reads those records and says
whether a sample may be kept.

The rules are the ones the browser lanes agreed on (and, since #130 and #137,
the ones the adversarial reviews forced closed):

* the record must have the fields the witness module promises, with the right
  types (``outcome``, ``frame_page_ms``, ``frames_total``, ``frames_after``,
  ``diff_ratio``, ``threshold``, ``caret_masked``, ``document_scoped``), all
  finite — ``NaN`` and infinities are refused at parse and at validation;
* a record whose ``outcome`` is ``no_frame`` is **refused**: there was no
  frame that showed the change, so there is no latency to publish;
* a witnessed record must carry its evidence: at least one frame after the
  marker, pixels above the recorded threshold and floor, the caret mask
  applied. A record with no outcome at all is refused (``no_outcome``), not
  quietly accepted. The arm instant (``after_page_ms``), when the record
  carries one, must be a finite number (``invalid_arm_time``) and the witness
  frame must not precede it (``frame_before_arm``); ``frames_after`` may not
  exceed ``frames_total`` (``frame_counts_inconsistent``) and both counts are
  required integers — a null count is refused, not skipped; a ``min_pixels``
  that is not a number of at least 1 cannot gate anything, so it is refused
  (``min_pixels_invalid``) instead of silently skipping the pixel floor;
* an asserted flag is not its evidence. Since #137 round 3 the validator does
  not weigh flags at all — it **recomputes** every derived verdict from the
  raw measurements and compares it with what the record claims:

  - a record produced by ``witnessFrame()`` (it says ``kind:
    "frame_witness"``, or carries a ``clock_check_source``, or its nested
    clock check uses the ``page_clock_offset+pixel_anchor`` method) must
    carry **every field the producer emits, with the producer's type,
    presence and range** (``witness_schema_invalid`` / 
    ``clock_check_schema_invalid``); a null where a number is required is
    refused, and the same holds for the nested ``clock_check``;
  - the nested check's ``checks`` are recomputed from the anchor's own
    times (causality: ``frame_page_ms >= change_page_ms - 2 ms``; lag:
    ``frame_lag_ms == frame_page_ms - change_page_ms`` and within
    ``lag_bound_ms == max(3 frame intervals, 100 ms)``), from the page
    offset's own samples (``page_offset_ms`` is their median, the spread
    their max-min, both within their bounds), and from the pixel diff
    (``diff_ratio == changed_pixels / total_pixels`` within rounding,
    ``changed_pixels >= min_pixels >= 1``, ``frames_after <= frames_total``).
    A claimed ``acceptable: true`` whose recomputation fails — or whose
    recorded ``checks`` are erased, null or false — is refused
    (``clock_check_evidence_contradicted`` / ``clock_check_evidence_missing``);
  - every alias the record carries (``clock_skew_ms``, ``skew_ms``,
    ``clock_skew_method``, ``clock_skew_bound_ms``,
    ``clock_skew_acceptable``, ``time_origin_ms``, ``marker_page_ms``) must
    agree with the evidence it restates, and the deprecated offset alias may
    no longer hide a contradictory nested offset;
  - a record that claims ``document_scoped: true`` while carrying a
    ``document_region_error`` is refused (``document_scope_contradicted``),
    and ``caret_masked: true`` with a recorded ``caret_mask_error`` is
    refused (``caret_mask_contradicted``).

  Simple legacy records (the shape B2–B5 write: ``clock_skew_ms`` +
    ``clock_skew_acceptable``, no production markers) keep their historical
    validation — a finite offset within the bound — but the evidence rules
    that reading a record's own fields (checks integrity, offset bound,
    alias agreement, pixel consistency, mask and scope contradictions) apply
    to them too;
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
``clock_check_evidence_missing``, ``clock_check_evidence_contradicted``,
``clock_check_schema_invalid``, ``witness_schema_invalid``,
``not_document_scoped``, ``document_scope_contradicted``, ``no_outcome``,
``unknown_outcome``, ``no_frame``, ``nonfinite_time``, ``no_frame_time``,
``invalid_arm_time``, ``frame_before_arm``, ``no_frame_after_marker``,
``frame_counts_inconsistent``, ``no_pixel_evidence``, ``min_pixels_invalid``,
``pixel_evidence_contradicted``, ``caret_mask_failed``,
``caret_not_masked``, ``caret_mask_contradicted``, ``invalid_record``.

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

# -- the producer's contract (witness.mjs), mirrored for recomputation ------

#: What a `witnessFrame()` record says in its ``kind`` field.
PRODUCTION_KIND = "frame_witness"

#: The clock-check method that carries pixel-anchor evidence (anything else
#: is the legacy page-offset-only shape, which the producer marks
#: unacceptable itself).
PRODUCTION_CLOCK_METHOD = "page_clock_offset+pixel_anchor"

#: The checks `clockSkew()` records, and recomputes here. (name, message).
CLOCK_CHECK_KEYS = (
    "timestamp_kind_known",
    "page_offset_within_bound",
    "page_offset_spread_within_bound",
    "anchor_found",
    "anchor_pixel_checked",
    "anchor_converted",
    "anchor_causality",
    "anchor_lag_within_bound",
)

#: A frame cannot show a change made more than this before it (the change
#: timestamp itself is a reading). CAUSALITY_SLOP_MS in witness.mjs.
CAUSALITY_SLOP_MS = 2.0

#: The bound on the spread of the page-offset samples. PAGE_OFFSET_SPREAD_
#: BOUND_MS in witness.mjs.
PAGE_OFFSET_SPREAD_BOUND_MS = 2.0

#: The anchor lag bound rule: max(ANCHOR_LAG_BOUND_INTERVALS frame
#: intervals, ANCHOR_LAG_BOUND_MIN_MS ms). ANCHOR_LAG_BOUND_* in witness.mjs.
LAG_BOUND_INTERVALS = 3
LAG_BOUND_MIN_MS = 100.0

#: `witnessFrame()` clamps its window to at least DEFAULT_WINDOW_MS.
PRODUCER_MIN_WINDOW_MS = 500.0

#: The timestamp kinds whose conversion `detectTimestampKind` trusts.
KNOWN_TIMESTAMP_KINDS = ("epoch_seconds", "monotonic_seconds")

#: diff_ratio / max_diff_ratio are round(changed/total, 6); the tolerance
#: covers that rounding (half of 1e-6, plus float error).
RATIO_TOLERANCE = 1e-6

#: The producer rounds its times to 3 decimals, so a difference of rounded
#: readings can drift by one and a half last-digits from the rounded
#: difference of the raw readings.
TIME_TOLERANCE_MS = 16e-4

#: The default number of page-offset samples `clockSkew()` takes (an odd
#: count, so the median is a sample).
CLOCK_OFFSET_SAMPLES = 9

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


def _count(value):
    """A frame count: an integer that is not a boolean, or None."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _nonempty_str(value):
    return isinstance(value, str) and bool(value.strip())


def _bool(value):
    return isinstance(value, bool)


def _js_round(value):
    """JavaScript's Math.round (half away from zero via floor(x + 0.5))."""
    return math.floor(float(value) + 0.5)


def _median(values):
    """The producer's median: the middle sample, or the mean of the two."""
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


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


def _is_production_record(record):
    """Does the record identify itself as a `witnessFrame()` production
    record? Any of its markers does: the kind, the clock-check source, a
    nested clock check that used the pixel-anchor method, or the nested
    evidence only `clockSkew()` records (its offset samples, its lag bound,
    its conversion statement, its anchor times). Erasing one marker leaves
    the others, so no small set of coordinated corruptions can fall back to
    the lenient legacy shape — and the legacy records B2–B5 write carry none
    of these fields."""
    if record.get("kind") == PRODUCTION_KIND:
        return True
    if isinstance(record.get("clock_check_source"), str):
        return True
    nested = record.get("clock_check")
    if not isinstance(nested, dict):
        return False
    if nested.get("method") == PRODUCTION_CLOCK_METHOD:
        return True
    if isinstance(nested.get("page_offset_samples"), list):
        return True
    if _finite_number(nested.get("lag_bound_ms")) or isinstance(nested.get("conversion"), dict):
        return True
    return (
        _finite_number(nested.get("change_page_ms"))
        and _finite_number(nested.get("frame_page_ms"))
        and _finite_number(nested.get("frame_lag_ms"))
    )


# --------------------------------------------------------------------------
# The strict production schema (#137 round 3, part 1)
# --------------------------------------------------------------------------


def _rect_violations(prefix, rect, *, device):
    """Schema violations of one rect: four numbers (device: four non-negative
    integers, width and height at least 1; CSS: finite, width and height
    positive)."""
    out = []
    for key in ("x", "y", "width", "height"):
        if key not in rect:
            out.append("%s%s is missing" % (prefix, key))
            continue
        value = rect[key]
        if device:
            if _count(value) is None:
                out.append("%s%s must be an integer (got %r)" % (prefix, key, value))
            elif (key in ("x", "y") and value < 0) or (key in ("width", "height") and value < 1):
                out.append("%s%s is out of the producer's range (%r)" % (prefix, key, value))
        else:
            if not _finite_number(value):
                out.append("%s%s must be a finite number (got %r)" % (prefix, key, value))
            elif key in ("width", "height") and value <= 0:
                out.append("%s%s must be positive (%r)" % (prefix, key, value))
    return out


def _region_violations(record):
    """Schema + arithmetic violations of the document region."""
    out = []
    region = record.get("document_region")
    if not isinstance(region, dict):
        return ["document_region must be an object when the record is scoped"]
    source = region.get("source")
    if source not in ("selector", "rect"):
        out.append("document_region.source must be 'selector' or 'rect' (got %r)" % (source,))
    selector = region.get("selector")
    if source == "selector" and not _nonempty_str(selector):
        out.append("a selector-sourced region names its selector (got %r)" % (selector,))
    if source == "rect" and selector is not None:
        out.append("a rect-sourced region carries no selector (got %r)" % (selector,))
    css = region.get("rect_css_px")
    device = region.get("rect_device_px")
    dpr = region.get("device_pixel_ratio")
    if not isinstance(css, dict):
        out.append("document_region.rect_css_px must be an object (got %r)" % (css,))
    if not isinstance(device, dict):
        out.append("document_region.rect_device_px must be an object (got %r)" % (device,))
    if isinstance(css, dict):
        out += _rect_violations("document_region.rect_css_px.", css, device=False)
    if isinstance(device, dict):
        out += _rect_violations("document_region.rect_device_px.", device, device=True)
    if not _finite_number(dpr) or float(dpr) <= 0:
        out.append("document_region.device_pixel_ratio must be positive (got %r)" % (dpr,))
        return out
    # The arithmetic the producer did: device = round(css * dpr), clamped to
    # the frame. The clamp only ever shrinks a width or height and zeroes a
    # negative origin, so the exact checkable relations are these.
    if isinstance(css, dict) and isinstance(device, dict) and all(
        _finite_number(css.get(k)) for k in ("x", "y", "width", "height")
    ):
        for axis in ("x", "y"):
            expected = max(0, _js_round(float(css[axis]) * float(dpr)))
            if _count(device.get(axis)) is not None and device[axis] != expected:
                out.append(
                    "document_region.rect_device_px.%s (%r) is not the CSS rect at "
                    "the recorded dpr (expected %d)"
                    % (axis, device[axis], expected)
                )
        for axis, span in (("x", "width"), ("y", "height")):
            upper = _js_round(float(css[axis]) * float(dpr)) + _js_round(
                float(css[span]) * float(dpr)
            )
            lower = max(0, _js_round(float(css[axis]) * float(dpr)))
            value = device.get(span)
            if _count(value) is None or not lower + 1 <= value <= upper:
                out.append(
                    "document_region.rect_device_px.%s (%r) does not fit the CSS "
                    "rect at the recorded dpr ([%d, %d])"
                    % (span, value, lower + 1, upper)
                )
    pixels = record.get("region_pixels")
    if (
        isinstance(device, dict)
        and _count(device.get("width")) is not None
        and _count(device.get("height")) is not None
    ):
        area = device["width"] * device["height"]
        if _count(pixels) is None or pixels != area:
            out.append(
                "region_pixels (%r) must be the device rect's area (%d)"
                % (pixels, area)
            )
    return out


#: The fields `witnessFrame()` always emits (the CLI adds marker_page_ms,
#: an optional alias of the arm; `clockSkew()`'s own fields are below).
_PRODUCTION_FIELDS = (
    "kind",
    "outcome",
    "frame_page_ms",
    "frames_total",
    "frames_after",
    "frames_ack_skipped",
    "diff_ratio",
    "threshold",
    "min_pixels",
    "caret_masked",
    "caret_mask_css",
    "caret_mask_error",
    "window_ms",
    "window_requested_ms",
    "after_page_ms",
    "baseline_page_ms",
    "baseline_source",
    "document_scoped",
    "document_region",
    "document_region_error",
    "region_pixels",
    "changed_pixels",
    "total_pixels",
    "max_diff_ratio",
    "timestamp_kind",
    "time_origin_ms",
    "clock_check",
    "clock_check_source",
    "clock_skew_ms",
    "clock_skew_method",
    "clock_skew_bound_ms",
    "clock_skew_acceptable",
    "elapsed_ms",
)

#: The fields `clockSkew()` always emits in a check of the production
#: method (the page-offset-only legacy shape emits fewer, and is refused by
#: its own unacceptable flag before this schema is reached).
_CLOCK_CHECK_FIELDS = (
    "kind",
    "acceptable",
    "reason",
    "checks",
    "method",
    "timestamp_kind",
    "timestamp_field",
    "bound_ms",
    "page_offset_ms",
    "page_offset_samples",
    "page_offset_spread_ms",
    "skew_ms",
    "time_origin_ms",
    "change_page_ms",
    "frame_page_ms",
    "frame_lag_ms",
    "frame_monotonic_ms",
    "frames_total",
    "anchor_pixel_checked",
    "anchor_diff_ratio",
    "anchor_probe_region_px",
    "frame_interval_ms",
    "frame_interval_source",
    "frame_interval_samples",
    "lag_bound_ms",
    "lag_bound_rule",
    "conversion",
    "caret_masked",
    "caret_mask_error",
    "notes",
)


def _production_schema_violations(record):
    """(reason, message) pairs: every way a production record can violate the
    schema the producer's fields define. Ordered; the first names the
    verdict's reason."""
    out = []
    witnessed = record.get("outcome") == "witnessed"

    def bad(message):
        out.append(("witness_schema_invalid", "witness schema: " + message))

    # Every field the producer emits is present; a field that vanished is a
    # record that stopped being the evidence it claims (an erased alias, a
    # dropped error slot). Nulls are refused where the producer's value is a
    # number (the per-field checks below do that).
    for field in _PRODUCTION_FIELDS:
        if field not in record:
            bad("the record is missing its %s field" % (field,))

    if record.get("kind") != PRODUCTION_KIND:
        bad("kind must be %r (got %r)" % (PRODUCTION_KIND, record.get("kind")))

    # -- counts and numbers, with the producer's ranges --------------------
    for field in ("frames_total", "frames_after", "frames_ack_skipped"):
        value = record.get(field)
        if _count(value) is None:
            bad("%s must be an integer (got %r)" % (field, value))
        elif value < 0:
            bad("%s must not be negative (got %r)" % (field, value))

    for field, low in (
        ("diff_ratio", None),
        ("threshold", None),
        ("min_pixels", 1),
        ("window_ms", PRODUCER_MIN_WINDOW_MS),
        ("window_requested_ms", 0),
        ("elapsed_ms", 0),
        ("time_origin_ms", None),
        ("max_diff_ratio", None),
    ):
        value = record.get(field)
        if not _finite_number(value):
            bad("%s must be a finite number (got %r)" % (field, value))
            continue
        if field in ("diff_ratio", "max_diff_ratio") and not 0.0 <= float(value) <= 1.0:
            bad("%s must be between 0 and 1 (got %r)" % (field, value))
        if field == "threshold" and float(value) <= 0:
            bad("threshold must be positive (got %r)" % (value,))
        if low is not None and float(value) < low:
            bad("%s must be at least %s (got %r)" % (field, low, value))

    for field in ("changed_pixels", "total_pixels"):
        value = record.get(field)
        if _count(value) is None:
            bad("%s must be an integer (got %r)" % (field, value))
        elif value < 0:
            bad("%s must not be negative (got %r)" % (field, value))
    if witnessed and _count(record.get("total_pixels")) == 0:
        bad("a witnessed frame needs at least one pixel to differ in")

    # -- times --------------------------------------------------------------
    frame_page_ms = record.get("frame_page_ms")
    if witnessed:
        if not _finite_number(frame_page_ms):
            bad("a witnessed frame_page_ms is a finite number (got %r)" % (frame_page_ms,))
    elif frame_page_ms is not None:
        bad("a no_frame record has no frame_page_ms (got %r)" % (frame_page_ms,))
    after_page_ms = record.get("after_page_ms")
    if witnessed:
        if not _finite_number(after_page_ms):
            bad(
                "a witnessed record carries its arm after_page_ms (got %r)"
                % (after_page_ms,)
            )
    elif after_page_ms is not None and not _finite_number(after_page_ms):
        bad("after_page_ms must be a finite number or null (got %r)" % (after_page_ms,))
    if "baseline_page_ms" in record and record["baseline_page_ms"] is not None and (
        not _finite_number(record["baseline_page_ms"]) or float(record["baseline_page_ms"]) < 0
    ):
        bad("baseline_page_ms must be a non-negative number or null (got %r)" % (record["baseline_page_ms"],))
    # The baseline is the picture *before* the change; a baseline after the
    # witness frame is an order no run produced.
    if (
        _finite_number(record.get("baseline_page_ms"))
        and _finite_number(record.get("frame_page_ms"))
        and float(record["baseline_page_ms"])
        > float(record["frame_page_ms"]) + CAUSALITY_SLOP_MS + TIME_TOLERANCE_MS
    ):
        bad(
            "baseline_page_ms (%r) is after the witness frame (%r): the "
            "baseline is taken before the change" % (record["baseline_page_ms"], record["frame_page_ms"])
        )
    if "marker_page_ms" in record:
        marker = record["marker_page_ms"]
        if marker is not None and not _finite_number(marker):
            bad("marker_page_ms must be a finite number or null (got %r)" % (marker,))
        elif record.get("after_page_ms") != marker:
            bad(
                "marker_page_ms (%r) is the CLI's alias of the arm after_page_ms (%r)"
                % (marker, record.get("after_page_ms"))
            )

    # -- strings, flags, enums ----------------------------------------------
    if not _nonempty_str(record.get("timestamp_kind")):
        bad("timestamp_kind must name the timestamps' kind (got %r)" % (record.get("timestamp_kind"),))
    elif witnessed and record["timestamp_kind"] not in KNOWN_TIMESTAMP_KINDS:
        bad(
            "a witnessed frame needed a convertible timestamp kind (got %r)"
            % (record["timestamp_kind"],)
        )
    if not _nonempty_str(record.get("baseline_source")):
        bad("baseline_source must name the baseline's source (got %r)" % (record.get("baseline_source"),))
    if not _nonempty_str(record.get("caret_mask_css")):
        bad("caret_mask_css must be the injected style (got %r)" % (record.get("caret_mask_css"),))
    if record.get("clock_check_source") not in ("caller", "inline", "page_offset_only"):
        bad(
            "clock_check_source must be caller, inline or page_offset_only (got %r)"
            % (record.get("clock_check_source"),)
        )
    if not _bool(record.get("caret_masked")):
        bad("caret_masked must be a boolean (got %r)" % (record.get("caret_masked"),))
    if record.get("caret_mask_error") is not None and not isinstance(record.get("caret_mask_error"), str):
        bad("caret_mask_error must be a string or null (got %r)" % (record.get("caret_mask_error"),))
    if not _bool(record.get("document_scoped")):
        bad("document_scoped must be a boolean (got %r)" % (record.get("document_scoped"),))
    if not _bool(record.get("clock_skew_acceptable")):
        bad("clock_skew_acceptable must be a boolean (got %r)" % (record.get("clock_skew_acceptable"),))
    if record.get("clock_skew_ms") is not None and not _finite_number(record.get("clock_skew_ms")):
        bad("clock_skew_ms must be a finite number or null (got %r)" % (record.get("clock_skew_ms"),))
    if record.get("clock_skew_method") is not None and not _nonempty_str(record.get("clock_skew_method")):
        bad("clock_skew_method must be a non-empty string or null (got %r)" % (record.get("clock_skew_method"),))
    if not _finite_number(record.get("clock_skew_bound_ms")) or (
        _finite_number(record.get("clock_skew_bound_ms")) and float(record["clock_skew_bound_ms"]) <= 0
    ):
        bad("clock_skew_bound_ms must be positive (got %r)" % (record.get("clock_skew_bound_ms"),))

    # -- scope: the region the producer resolves for a scoped record --------
    scoped = record.get("document_scoped") is True
    region = record.get("document_region")
    error = record.get("document_region_error")
    if scoped:
        if error is not None:
            bad("a scoped record carries no document_region_error (got %r)" % (error,))
        out += [("witness_schema_invalid", "witness schema: " + m) for m in _region_violations(record)]
    else:
        if region is not None:
            bad("an unscoped record carries no document_region (got %r)" % (region,))
        if record.get("region_pixels") is not None:
            bad("an unscoped record carries no region_pixels (got %r)" % (record.get("region_pixels"),))
        if error is not None and not isinstance(error, str):
            bad("document_region_error must be a string or null (got %r)" % (error,))

    # -- the nested clock check is part of the record ----------------------
    nested = record.get("clock_check")
    if not isinstance(nested, dict):
        bad("clock_check must be the run's clock-check record (got %r)" % (nested,))
    return out


def _clock_schema_violations(nested):
    """(reason, message) pairs for the nested clock check of a production
    record that claims acceptable: every field `clockSkew()` emits, with its
    type, presence and range."""
    out = []

    def bad(message):
        out.append(("clock_check_schema_invalid", "clock check schema: " + message))

    for field in _CLOCK_CHECK_FIELDS:
        if field not in nested:
            bad("the check is missing its %s field" % (field,))

    if nested.get("kind") != "clock_skew":
        bad("kind must be 'clock_skew' (got %r)" % (nested.get("kind"),))
    if nested.get("method") != PRODUCTION_CLOCK_METHOD:
        bad(
            "method must be %r (got %r)"
            % (PRODUCTION_CLOCK_METHOD, nested.get("method"))
        )
    if not _bool(nested.get("acceptable")):
        bad("acceptable must be a boolean (got %r)" % (nested.get("acceptable"),))
    if nested.get("reason") is not None:
        bad("an acceptable check records no reason (got %r)" % (nested.get("reason"),))
    checks = nested.get("checks")
    if not isinstance(checks, dict):
        bad("checks must be the recorded checks (got %r)" % (checks,))
    else:
        for key in CLOCK_CHECK_KEYS:
            if key not in checks:
                bad("the recorded checks are missing %r" % (key,))
            elif not _bool(checks[key]):
                bad("the recorded check %r must be a boolean (got %r)" % (key, checks[key]))
    if not _nonempty_str(nested.get("timestamp_kind")):
        bad("timestamp_kind must name the timestamps' kind (got %r)" % (nested.get("timestamp_kind"),))
    elif nested["timestamp_kind"] not in KNOWN_TIMESTAMP_KINDS:
        bad("an acceptable check needed a convertible timestamp kind (got %r)" % (nested["timestamp_kind"],))
    if not _nonempty_str(nested.get("timestamp_field")):
        bad("timestamp_field must name the metadata field (got %r)" % (nested.get("timestamp_field"),))
    bound = nested.get("bound_ms")
    if not _finite_number(bound) or float(bound) <= 0:
        bad("bound_ms must be positive (got %r)" % (bound,))
    if not _finite_number(nested.get("page_offset_ms")):
        bad("page_offset_ms must be a finite number (got %r)" % (nested.get("page_offset_ms"),))
    if not _finite_number(nested.get("skew_ms")):
        bad("skew_ms must be a finite number (got %r)" % (nested.get("skew_ms"),))
    samples = nested.get("page_offset_samples")
    if not isinstance(samples, list) or not samples:
        bad("page_offset_samples must be a non-empty list (got %r)" % (samples,))
    elif not all(_finite_number(s) for s in samples):
        bad("page_offset_samples must be finite numbers (got %r)" % (samples,))
    spread = nested.get("page_offset_spread_ms")
    if not _finite_number(spread) or float(spread) < 0:
        bad("page_offset_spread_ms must be a non-negative number (got %r)" % (spread,))
    if not _finite_number(nested.get("time_origin_ms")):
        bad("time_origin_ms must be a finite number (got %r)" % (nested.get("time_origin_ms"),))
    for field in ("change_page_ms", "frame_page_ms", "frame_lag_ms"):
        if not _finite_number(nested.get(field)):
            bad(
                "an acceptable check's anchor carries %s as a finite number (got %r)"
                % (field, nested.get(field))
            )
    change = nested.get("change_page_ms")
    if _finite_number(change) and float(change) < 0:
        bad("change_page_ms is a page time (got %r)" % (change,))
    if nested.get("frame_monotonic_ms") is not None and (
        not _finite_number(nested.get("frame_monotonic_ms"))
        or float(nested["frame_monotonic_ms"]) < 0
    ):
        bad("frame_monotonic_ms must be a non-negative number or null (got %r)" % (nested.get("frame_monotonic_ms"),))
    if _count(nested.get("frames_total")) is None or nested.get("frames_total", -1) < 0:
        bad("the check's frames_total must be a non-negative integer (got %r)" % (nested.get("frames_total"),))
    if nested.get("anchor_pixel_checked") is not True:
        bad("an acceptable check pixel-checked its anchor (got %r)" % (nested.get("anchor_pixel_checked"),))
    ratio = nested.get("anchor_diff_ratio")
    if not _finite_number(ratio) or not 0.0 < float(ratio) <= 1.0:
        bad("anchor_diff_ratio must be in (0, 1] (got %r)" % (ratio,))
    probe = nested.get("anchor_probe_region_px")
    if not isinstance(probe, dict):
        bad("anchor_probe_region_px must be an object (got %r)" % (probe,))
    else:
        for key in ("width", "height"):
            if _count(probe.get(key)) is None or probe[key] < 1:
                bad("anchor_probe_region_px.%s must be at least 1 (got %r)" % (key, probe.get(key)))
        for key in ("x", "y"):
            if _count(probe.get(key)) is None:
                bad("anchor_probe_region_px.%s must be an integer (got %r)" % (key, probe.get(key)))
    interval = nested.get("frame_interval_ms")
    if interval is not None and (not _finite_number(interval) or float(interval) <= 0):
        bad("frame_interval_ms must be positive or null (got %r)" % (interval,))
    if not _nonempty_str(nested.get("frame_interval_source")):
        bad("frame_interval_source must name the interval's source (got %r)" % (nested.get("frame_interval_source"),))
    if nested.get("frame_interval_samples") is not None and (
        _count(nested.get("frame_interval_samples")) is None
        or nested["frame_interval_samples"] < 0
    ):
        bad(
            "frame_interval_samples must be a non-negative integer or null (got %r)"
            % (nested.get("frame_interval_samples"),)
        )
    lag_bound = nested.get("lag_bound_ms")
    if not _finite_number(lag_bound) or float(lag_bound) < LAG_BOUND_MIN_MS:
        bad(
            "lag_bound_ms must be at least the rule's minimum %s ms (got %r)"
            % (LAG_BOUND_MIN_MS, lag_bound)
        )
    if not _nonempty_str(nested.get("lag_bound_rule")):
        bad("lag_bound_rule must state the bound's rule (got %r)" % (nested.get("lag_bound_rule"),))
    conversion = nested.get("conversion")
    if not isinstance(conversion, dict):
        bad("conversion must state the published bound (got %r)" % (conversion,))
    else:
        for key in ("formula", "error_lower_why", "error_upper_why", "published"):
            if not _nonempty_str(conversion.get(key)):
                bad("conversion.%s must be stated (got %r)" % (key, conversion.get(key)))
        for key in ("error_lower_ms", "error_upper_ms"):
            if not _finite_number(conversion.get(key)):
                bad("conversion.%s must be a finite number (got %r)" % (key, conversion.get(key)))
    if not _bool(nested.get("caret_masked")):
        bad("the check's caret_masked must be a boolean (got %r)" % (nested.get("caret_masked"),))
    elif nested.get("caret_masked") is not True:
        bad("an acceptable check masked its own caret (caret_masked=%r)" % (nested.get("caret_masked"),))
    if nested.get("caret_mask_error") is not None and not isinstance(nested.get("caret_mask_error"), str):
        bad("the check's caret_mask_error must be a string or null (got %r)" % (nested.get("caret_mask_error"),))
    elif isinstance(nested.get("caret_mask_error"), str) and nested["caret_mask_error"]:
        bad(
            "an acceptable check records no mask failure (caret_mask_error=%r)"
            % (nested["caret_mask_error"],)
        )
    notes = nested.get("notes")
    if not isinstance(notes, list) or not notes or not all(_nonempty_str(n) for n in notes):
        bad("notes must be a non-empty list of strings (got %r)" % (notes,))
    return out


# --------------------------------------------------------------------------
# The recomputation (#137 round 3, part 2)
# --------------------------------------------------------------------------


def _recomputed_checks(nested):
    """The eight checks recomputed from the nested check's own raw
    measurements, exactly as `clockSkew()` derived them."""
    offset = nested.get("page_offset_ms")
    spread = nested.get("page_offset_spread_ms")
    bound = nested.get("bound_ms")
    samples = nested.get("page_offset_samples")
    change = nested.get("change_page_ms")
    frame = nested.get("frame_page_ms")
    lag = nested.get("frame_lag_ms")
    lag_bound = nested.get("lag_bound_ms")
    median = _median(samples) if isinstance(samples, list) and samples else None
    return {
        "timestamp_kind_known": nested.get("timestamp_kind") in KNOWN_TIMESTAMP_KINDS,
        "page_offset_within_bound": _finite_number(offset)
        and _finite_number(bound)
        and abs(float(offset)) <= float(bound) + 1e-9,
        "page_offset_spread_within_bound": _finite_number(spread)
        and float(spread) <= PAGE_OFFSET_SPREAD_BOUND_MS + 1e-9,
        "anchor_found": _finite_number(frame),
        "anchor_pixel_checked": nested.get("anchor_pixel_checked") is True,
        "anchor_converted": _finite_number(frame),
        "anchor_causality": _finite_number(frame)
        and _finite_number(change)
        and float(frame) >= float(change) - CAUSALITY_SLOP_MS - TIME_TOLERANCE_MS,
        "anchor_lag_within_bound": _finite_number(lag)
        and _finite_number(lag_bound)
        and float(lag) <= float(lag_bound) + TIME_TOLERANCE_MS,
        # the samples' own statistics (kept out of the dict; compared below)
        "_median_is_offset": _finite_number(offset)
        and median is not None
        and abs(float(offset) - median) <= TIME_TOLERANCE_MS,
        "_spread_is_range": _finite_number(spread)
        and isinstance(samples, list)
        and bool(samples)
        and abs(float(spread) - (max(float(s) for s in samples) - min(float(s) for s in samples)))
        <= TIME_TOLERANCE_MS,
    }


def _clock_evidence_violations(record, nested, bound, production=False):
    """(reason, message) pairs: the evidence contradictions of the nested
    clock check and of the aliases that restate it. The flag was already
    checked; everything here is recomputed from raw measurements."""
    out = []

    def contradicted(message):
        out.append(("clock_check_evidence_contradicted", message))

    def missing(message):
        out.append(("clock_check_evidence_missing", message))

    checks = nested.get("checks")
    if "checks" in nested:
        if not isinstance(checks, dict):
            missing("the check claims acceptable without its recorded checks (checks=%r)" % (checks,))
        else:
            false_checks = sorted(k for k, v in checks.items() if v is False)
            if false_checks:
                contradicted(
                    "the check claims acceptable but its recorded checks fail: %s"
                    % (", ".join(false_checks),)
                )
    anchor_flag = nested.get("anchor_pixel_checked")
    if anchor_flag is False:
        contradicted(
            "the check claims acceptable but the pixel anchor was not checked "
            "(anchor_pixel_checked=%r)" % (anchor_flag,)
        )
    erased = []
    if isinstance(checks, dict):
        erased = sorted(
            k for k in CLOCK_CHECK_KEYS if k not in checks or not _bool(checks[k])
        )
    if anchor_flag is not None and not _bool(anchor_flag):
        # a null or non-boolean anchor flag is erased evidence, not a pass
        erased = sorted(set(erased) | {"anchor_pixel_checked"})
    if erased:
        missing(
            "the check claims acceptable but its recorded checks are "
            "erased or non-boolean: %s" % (", ".join(erased),)
        )

    offset = nested.get("page_offset_ms")
    nested_bound = nested.get("bound_ms")
    effective_bound = float(nested_bound) if _finite_number(nested_bound) else float(bound)
    if _finite_number(offset):
        if abs(float(offset)) > effective_bound + 1e-9:
            contradicted(
                "the recorded page offset %.3f ms is above the bound of %.3f ms"
                % (float(offset), effective_bound)
            )
        alias = record.get("clock_skew_ms")
        if (production or _finite_number(alias)) and (
            alias is None or not _finite_number(alias) or abs(float(alias) - float(offset)) > 1e-9
        ):
            contradicted(
                "the deprecated clock_skew_ms alias (%r) disagrees with the "
                "page offset it restates (%r)" % (alias, offset)
            )
        nested_alias = nested.get("skew_ms")
        if (production or "skew_ms" in nested) and (
            not _finite_number(nested_alias)
            or abs(float(nested_alias) - float(offset)) > 1e-9
        ):
            contradicted(
                "the nested skew_ms alias (%r) disagrees with the page offset "
                "it restates (%r)" % (nested_alias, offset)
            )
    method = nested.get("method")
    alias_method = record.get("clock_skew_method")
    if method is not None and alias_method != method:
        contradicted(
            "the clock_skew_method alias (%r) disagrees with the check's method (%r)"
            % (alias_method, method)
        )
    if _finite_number(nested_bound):
        alias_bound = record.get("clock_skew_bound_ms")
        if not _finite_number(alias_bound) or abs(float(alias_bound) - float(nested_bound)) > 1e-9:
            contradicted(
                "the clock_skew_bound_ms alias (%r) disagrees with the check's "
                "bound (%r)" % (alias_bound, nested_bound)
            )
    alias_acceptable = record.get("clock_skew_acceptable")
    if alias_acceptable is not (nested.get("acceptable") is True):
        contradicted(
            "the clock_skew_acceptable alias (%r) disagrees with the check (%r)"
            % (alias_acceptable, nested.get("acceptable"))
        )
    nested_origin = nested.get("time_origin_ms")
    top_origin = record.get("time_origin_ms")
    if _finite_number(nested_origin) and _finite_number(top_origin) and abs(
        float(top_origin) - float(nested_origin)
    ) > 1e-9:
        contradicted(
            "the record's time_origin_ms (%r) disagrees with the check's (%r)"
            % (top_origin, nested_origin)
        )
    marker = record.get("marker_page_ms")
    if nested.get("reason") is not None and nested.get("acceptable") is True:
        contradicted(
            "an acceptable check records no refusal reason (reason=%r)"
            % (nested.get("reason"),)
        )

    # The recomputation proper (production checks carry the raw fields).
    if not isinstance(checks, dict) or nested.get("method") != PRODUCTION_CLOCK_METHOD:
        return out
    raw = _recomputed_checks(nested)
    for key in CLOCK_CHECK_KEYS:
        if key in checks and key in raw and bool(checks[key]) is not bool(raw[key]):
            contradicted(
                "the recorded check %s=%r disagrees with its own measurements "
                "(recomputed %r)" % (key, checks[key], raw[key])
            )
    for key, claim, label in (
        ("_median_is_offset", offset, "the samples' median"),
        ("_spread_is_range", nested.get("page_offset_spread_ms"), "the samples' spread"),
    ):
        if key in raw and not raw[key]:
            contradicted(
                "%s (%r) is not what the samples give" % (label, claim)
            )
    change = nested.get("change_page_ms")
    frame = nested.get("frame_page_ms")
    lag = nested.get("frame_lag_ms")
    if _finite_number(frame) and _finite_number(change) and _finite_number(lag):
        if abs(float(lag) - (float(frame) - float(change))) > TIME_TOLERANCE_MS:
            contradicted(
                "frame_lag_ms (%r) is not the anchor's own difference "
                "frame_page_ms - change_page_ms (%r)" % (lag, float(frame) - float(change))
            )
        if float(frame) < float(change) - CAUSALITY_SLOP_MS - TIME_TOLERANCE_MS:
            contradicted(
                "the anchor frame (%r ms) precedes its own change (%r ms)"
                % (frame, change)
            )
    interval = nested.get("frame_interval_ms")
    lag_bound = nested.get("lag_bound_ms")
    if _finite_number(lag_bound):
        expected = (
            max(LAG_BOUND_INTERVALS * float(interval), LAG_BOUND_MIN_MS)
            if _finite_number(interval)
            else LAG_BOUND_MIN_MS
        )
        if abs(float(lag_bound) - expected) > TIME_TOLERANCE_MS:
            contradicted(
                "lag_bound_ms (%r) is not the rule's bound max(%d intervals, %s ms) "
                "= %r" % (lag_bound, LAG_BOUND_INTERVALS, LAG_BOUND_MIN_MS, expected)
            )
    conversion = nested.get("conversion")
    if isinstance(conversion, dict):
        lower = conversion.get("error_lower_ms")
        if _finite_number(lower) and abs(float(lower) + CAUSALITY_SLOP_MS) > 1e-9:
            contradicted(
                "the conversion's lower bound is -%s ms by causality (got %r)"
                % (CAUSALITY_SLOP_MS, lower)
            )
        upper = conversion.get("error_upper_ms")
        if _finite_number(upper) and _finite_number(lag_bound) and abs(
            float(upper) - float(lag_bound)
        ) > 1e-9:
            contradicted(
                "the conversion's upper bound is the lag bound (%r, got %r)"
                % (lag_bound, upper)
            )
    return out


def _pixel_evidence_violations(record):
    """(reason, message) pairs: the pixel evidence recomputed from the raw
    counts, whenever the record carries them."""
    out = []
    if record.get("outcome") != "witnessed":
        return out
    changed = record.get("changed_pixels")
    total = record.get("total_pixels")
    ratio = record.get("diff_ratio")
    max_ratio = record.get("max_diff_ratio")
    if _count(total) is not None and total < 1:
        out.append(
            (
                "pixel_evidence_contradicted",
                "a witnessed frame needs at least one pixel to differ in "
                "(total_pixels=%r)" % (total,),
            )
        )
        return out
    if _count(changed) is not None and _count(total) is not None:
        if changed > total:
            out.append(
                (
                    "pixel_evidence_contradicted",
                    "changed_pixels (%s) exceeds total_pixels (%s): a subset "
                    "cannot be larger than the whole" % (changed, total),
                )
            )
            return out
        if total > 0:
            exact = float(changed) / float(total)
            if _finite_number(ratio) and abs(float(ratio) - exact) > RATIO_TOLERANCE:
                out.append(
                    (
                        "pixel_evidence_contradicted",
                        "diff_ratio (%r) is not changed_pixels / total_pixels (%r)"
                        % (ratio, exact),
                    )
                )
            if _finite_number(max_ratio) and abs(float(max_ratio) - exact) > RATIO_TOLERANCE:
                out.append(
                    (
                        "pixel_evidence_contradicted",
                        "max_diff_ratio (%r) is not changed_pixels / total_pixels (%r)"
                        % (max_ratio, exact),
                    )
                )
    return out


def _mask_violations(record):
    """(reason, message) pairs for the caret-mask contradiction."""
    error = record.get("caret_mask_error")
    if record.get("caret_masked") is True and isinstance(error, str) and error:
        return [
            (
                "caret_mask_contradicted",
                "caret_masked=true but the mask recorded its own failure "
                "(caret_mask_error=%r)" % (error,),
            )
        ]
    return []


#: (reason, predicate on the record) in precedence order; the first failure
#: names the verdict's reason. `skew` is the caller's explicit offset, which
#: wins over the record's own (the same rule `_skew_of` applies) so a refusal
#: names the check that actually failed for the effective skew.
def _reason_of(record, bound, errors, skew=None):
    del errors  # the tokens below are decided structurally, in order
    if not isinstance(record, dict):
        return "record_not_a_mapping"
    production = _is_production_record(record)
    nested = record.get("clock_check") if isinstance(record.get("clock_check"), dict) else None
    skew = _skew_of(record, skew)
    flag = record.get("clock_skew_acceptable")
    if _finite_number(skew) and abs(float(skew)) > float(bound):
        return "clock_skew_above_bound"
    if production:
        schema = _production_schema_violations(record)
        if schema:
            return schema[0][0]
    if nested is not None:
        if nested.get("acceptable") is not True:
            return "clock_check_not_acceptable"
        evidence = _clock_evidence_violations(record, nested, bound, production)
        if evidence:
            return evidence[0][0]
        if production:
            schema = _clock_schema_violations(nested)
            if schema:
                return schema[0][0]
    else:
        if flag is not True:
            return "clock_check_not_acceptable" if flag is False else "clock_check_missing"
        if not _finite_number(skew):
            return "clock_check_missing"
    if record.get("document_scoped") is not True:
        return "not_document_scoped"
    # #137: a scope flag asserted over the region's own recorded failure.
    if record.get("document_region_error"):
        return "document_scope_contradicted"
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
    # #137: the arm, when the record carries one, must be a finite number, and
    # the witness frame must not precede it -- the producer keeps a frame only
    # at `pageMs >= afterPageMs`, so a frame below the recorded arm is
    # evidence no run produced.
    after_page_ms = record.get("after_page_ms")
    if after_page_ms is not None and not _finite_number(after_page_ms):
        return "invalid_arm_time"
    if _finite_number(after_page_ms) and float(frame_page_ms) < float(after_page_ms):
        return "frame_before_arm"
    frames_after = record.get("frames_after")
    if isinstance(frames_after, int) and not isinstance(frames_after, bool):
        if frames_after < 1:
            return "no_frame_after_marker"
    # #137: frames_after counts a subset of frames_total.
    if _count(frames_after) is not None and _count(record.get("frames_total")) is not None:
        if frames_after > record.get("frames_total"):
            return "frame_counts_inconsistent"
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
    # #137: a pixel floor of the wrong type gates nothing; refuse it instead
    # of skipping the floor. Round 3: a floor below 1 gates nothing either.
    if "min_pixels" in record and (not _finite_number(min_pixels) or float(min_pixels) < 1):
        return "min_pixels_invalid"
    if _finite_number(changed) and _finite_number(min_pixels):
        if float(changed) < float(min_pixels):
            return "no_pixel_evidence"
    # #137 round 3: the pixel evidence, recomputed from the raw counts.
    pixels = _pixel_evidence_violations(record)
    if pixels:
        return pixels[0][0]
    if record.get("caret_masked") is not True:
        if record.get("caret_mask_error"):
            return "caret_mask_failed"
        return "caret_not_masked"
    # #137 round 3: the mask flag asserted over its own recorded failure.
    mask = _mask_violations(record)
    if mask:
        return mask[0][0]
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

    production = _is_production_record(record)
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

    # #137: the arm instant, when the record carries one, and causality.
    after_page_ms = record.get("after_page_ms")
    if after_page_ms is not None and not _finite_number(after_page_ms):
        errors.append("after_page_ms must be a finite number or null")
    if (
        _finite_number(after_page_ms)
        and _finite_number(frame_page_ms)
        and float(frame_page_ms) < float(after_page_ms)
    ):
        errors.append(
            "the witness frame (%r ms) precedes its arm after_page_ms=%r: a "
            "frame before the change cannot show it" % (frame_page_ms, after_page_ms)
        )

    for field in ("frames_total", "frames_after"):
        value = record.get(field)
        if value is None or isinstance(value, bool) or not isinstance(value, int):
            # #137 round 3 (finding 4): a null count is refused, not skipped.
            errors.append("%s must be an integer (got %r)" % (field, value))
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
    # #137: frames_after counts a subset of frames_total.
    if (
        _count(record.get("frames_after")) is not None
        and _count(record.get("frames_total")) is not None
        and record["frames_after"] > record["frames_total"]
    ):
        errors.append(
            "frames_after (%s) exceeds frames_total (%s): a subset cannot be "
            "larger than the whole"
            % (record["frames_after"], record["frames_total"])
        )

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
        if not _finite_number(min_pixels) or float(min_pixels) < 1:
            errors.append(
                "min_pixels must be a number of at least 1 (got %r)"
                % (record.get("min_pixels"),)
            )
        elif not _finite_number(changed):
            errors.append("a witnessed frame needs changed_pixels")
        elif float(changed) < float(min_pixels):
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
    # #137: the scope flag asserted over the region's own recorded failure.
    elif record.get("document_region_error"):
        errors.append(
            "the record claims document_scoped=true but carries "
            "document_region_error=%r" % (record.get("document_region_error"),)
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

    # #137 round 3: the strict production schema, the recomputed evidence,
    # the pixel consistency and the mask contradiction -- every token carries
    # its message into the verdict, and the first names the reason.
    if production:
        for _reason, message in _production_schema_violations(record):
            errors.append(message)
    if isinstance(nested, dict) and nested.get("acceptable") is True:
        for _reason, message in _clock_evidence_violations(record, nested, bound, production):
            errors.append(message)
        if production:
            for _reason, message in _clock_schema_violations(nested):
                errors.append(message)
    for _reason, message in _pixel_evidence_violations(record):
        errors.append(message)
    for _reason, message in _mask_violations(record):
        errors.append(message)

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
    reason = _reason_of(record, bound, errors, skew_ms) if refused else None

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
