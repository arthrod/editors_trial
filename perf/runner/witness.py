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
  quietly accepted. The arm instant (``after_page_ms``) must be a finite
  number and the witness frame must not precede it
  (``frame_before_arm``); ``frames_after`` may not exceed ``frames_total``
  (``frame_counts_inconsistent``) and both counts are required integers —
  a null count is refused, not skipped; a ``min_pixels`` below 1 cannot
  gate anything, so it is refused instead of silently skipping the pixel
  floor;
* an asserted flag is not its evidence. Since #137 round 3 the validator does
  not weigh flags at all — it **recomputes** every derived verdict from the
  raw measurements and compares it with what the record claims:

  - the discriminator is positive (#137 round 4): a record is a frame
    witness **only if** it carries the producer's markers — ``kind:
    "frame_witness"``, a ``clock_check_source``, or the production nested
    clock check with its raw measurements (its method, its offset samples,
    its lag bound, its conversion statement, its anchor times). A record
    without them is not a witness record at all and is refused
    (``not_a_witness_record``); there is no lenient "legacy" branch that
    can return ok. The old hand-made "legacy simple" shape stays parseable
    (the validator returns a verdict for it, never a crash), but its
    verdict is that same distinct, never-publishable refusal;
  - a witness record must carry **every field the producer emits, with the
    producer's type, presence and range** (``witness_schema_invalid`` /
    ``clock_check_schema_invalid``): a null where a number is required is
    refused, and the same holds for the nested ``clock_check``. The schema
    is closed **recursively** (#137 round 4 N4; closed at every level in
    round 5): every object the producer emits — the record itself, the
    nested ``clock_check``, its recorded ``checks``, its
    ``anchor_probe_region_px``, its ``conversion`` statement, the
    ``document_region`` and its two rects — carries an allowed-key set
    derived from a real capture, and an unknown key anywhere is refused
    (``witness_schema_invalid``); the ``clock_skew`` alias slot is
    not read at all (the producer never writes it on a frame-witness
    record);
  - the nested check's ``checks`` are recomputed from the anchor's own
    times (causality: ``frame_page_ms >= change_page_ms - 2 ms``; lag:
    ``frame_lag_ms == frame_page_ms - change_page_ms`` and within
    ``lag_bound_ms == max(3 frame intervals, 250 ms)``), from the page
    offset's own samples (``page_offset_ms`` is their median, the spread
    their max-min, both within their bounds), and from the pixel diff
    (``diff_ratio == changed_pixels / total_pixels`` within rounding,
    ``changed_pixels >= min_pixels >= 1``, ``frames_after <= frames_total``).
    A claimed ``acceptable: true`` whose recomputation fails — or whose
    recorded ``checks`` are erased, null or false — is refused
    (``clock_check_evidence_contradicted`` / ``clock_check_evidence_missing``).
    The anchor's evidence must also be **consistent with how
    ``witness.mjs`` finds an anchor** (#137 round 5 R4-2; round 6
    R5-3/R5-4): the producer keeps a pre-change baseline frame and
    searches only later frames, so a claimed anchor needs at least
    ``ANCHOR_MIN_FRAMES`` (two) recorder frames — one frame is as
    impossible as zero — and both frame counts the record carries count
    the same run's recorder, so the check's ``frames_total`` may not
    exceed the record's own; the anchor is accepted only when the probe
    region's diff ratio is strictly above the producer's threshold
    (``1e-5``) with at least ``4`` of its pixels changed, and that probe
    is the producer's constant geometry — a square at the frame's
    top-left corner, ``max(1, round(8 * dpr))`` px to a side at the same
    dpr the record's ``document_region.device_pixel_ratio`` carries —
    whose area is recomputed from that geometry, never taken from the
    record, so an inflated "probe" cannot weaken the floor (both bounds
    tolerant of the producer's six-decimal rounding); the record's
    ``frames_ack_skipped`` — a count of frames the recorder did record —
    may not exceed its ``frames_total``;
  - every alias the record carries (``clock_skew_ms``, the nested
    ``skew_ms``, ``clock_skew_method``, ``clock_skew_bound_ms``,
    ``clock_skew_acceptable``, ``time_origin_ms``, ``marker_page_ms``) must
    agree with the evidence it restates, and the deprecated offset alias may
    not hide a contradictory nested offset;
  - a record that claims ``document_scoped: true`` while carrying a
    ``document_region_error`` is refused (``witness_schema_invalid``: a
    scoped record carries no region error), and ``caret_masked: true``
    with a recorded ``caret_mask_error`` is refused
    (``caret_mask_contradicted``).

* the record must be document-scoped (``document_scoped: true``): a
  whole-frame diff lets shell damage pose as document paint, so a record
  without a region is refused (``not_document_scoped``);
* the record must carry an **acceptable clock check** from its run — the
  nested ``clock_check`` record (`clockSkew()`'s output: the pixel anchor,
  its causality and lag bounds, the page offset), echoed by every
  ``witnessFrame()`` record. A missing or failed check is refused
  (``clock_check_not_acceptable``, or the strict schema's
  ``witness_schema_invalid`` when the record carries no check object at
  all);
* the caller's own arguments are checked too (#137 round 4, N5): a
  ``bound_ms`` that is not a finite positive number, or a supplied
  ``skew`` that is not a finite number inside the supported numeric
  domain ``|x| <= 1e15`` (#137 round 8, R7-1), is refused
  (``nonfinite_time``) — never silently used as a bound that compares
  false against everything, and never silently replaced by the record's
  own offset;
* **no input can make validation raise** (#137 round 5 R4-1; round 6
  R5-1/R5-2): the nested schema runs **before** any helper reads the
  check's values, and the sample statistics are total over every JSON
  value, so a malformed offset sample is the schema's own named refusal
  (``clock_check_schema_invalid``); numbers outside the float domain the
  producer writes (a JSON integer such as ``10**400``) and arithmetic
  that overflows it (a CSS rect multiplied by a ``1e308`` device pixel
  ratio) are refused with the schema's named reasons, never an
  ``OverflowError``; since round 7 (R6-1) the supported numeric domain
  itself is finite — every numeric field accepts only finite values with
  ``|x| <= 1e15``, and anything outside (a 1,000-digit frame count
  included) is the owning schema's refusal with the
  ``value_out_of_range`` message token, named before the value is ever
  formatted (no diagnostic shows its digits; the guards keep every
  arithmetic path total, though `validate_witness`'s own field checks do
  read some values with guarded comparisons before the schema names
  them — the sweep accumulates violations, it does not short-circuit
  the passes after it) — and every diagnostic that names a value
  goes through one bounded, exception-safe describer (``_describe``: the
  type plus at most 64 characters; an out-of-domain integer is
  ``<int, N bits>``), so a 5,001-digit integer is refused, never
  formatted, and Python's integer-to-string conversion limit is never
  touched — since round 8 (R7-2) that includes the lag-bound
  contradiction (the last raw site) and the CLI's own read/abort
  diagnostics, whose paths and exceptions are described boundedly too
  (the verdict still echoes the record's own payload verbatim,
  though: serializing a verdict whose record carries such a number is
  the caller's formatting decision — the CLI never meets one, its
  reader refuses those files first); and the CLI prints a JSON verdict
  **always** —
  ``validation_aborted`` when validation itself fails (a bug to report)
  and ``record_unreadable`` when the file is not a record at all
  (unreadable, not valid JSON, a bare ``NaN``: exit 2, but stdout is
  never empty), never a traceback and never a published number;
* a refusal is an outcome, never a zero: `validate_witness` returns the
  verdict with a named ``reason`` and keeps the record's own payload.

**Consistency is not provenance.** The records this module validates are
produced by `witness.mjs` in the same run as the measurement, and the
validator checks exactly that: internal consistency — every field the
producer emits, every derived verdict recomputed from the raw
measurements, no unknown key anywhere. It catches producer bugs and
corrupted, erased or contradictory evidence; it cannot catch a forgery
that is internally consistent (a fabricated record whose numbers agree
with each other passes, by construction). Resisting a deliberate
coordinated forgery needs a trusted producer boundary or independently
retained capture/run evidence — binding records to more recognizable
markers, or to cryptography the forger can also run, does not do it.

The named reasons: ``record_not_a_mapping``, ``not_a_witness_record``,
``clock_skew_above_bound``, ``clock_check_not_acceptable``,
``clock_check_evidence_missing``, ``clock_check_evidence_contradicted``,
``clock_check_schema_invalid``, ``witness_schema_invalid``,
``not_document_scoped``, ``no_outcome``, ``unknown_outcome``, ``no_frame``,
``nonfinite_time`` (a nonfinite or non-positive caller-supplied bound,
or a skew that is not a finite number inside the supported numeric
domain ``|x| <= 1e15``), ``frame_before_arm``,
``no_frame_after_marker``, ``frame_counts_inconsistent``,
``no_pixel_evidence``, ``pixel_evidence_contradicted``,
``caret_mask_failed``,
``caret_not_masked`` (not an unmasked caret-rect retry: ``caret_masked``
false, ``caret_mask_css`` null, no mask error, document-scoped, and a
``rect`` region at most 48 by 96 CSS pixels — a whole-document unmasked
diff stays ``caret_not_masked``), ``caret_mask_contradicted``, ``invalid_record``,
``value_out_of_range`` (not a verdict reason of its own: the message
token the owning schema writes when a numeric field is outside the
supported finite domain ``|x| <= 1e15``; the reason stays
``witness_schema_invalid`` or ``clock_check_schema_invalid``),
``record_unreadable`` (the CLI's read refusal: the file is not a record
at all),
and ``validation_aborted`` (the CLI's last-resort refusal when
validation itself raises; nothing above may raise, so seeing it is a bug
to report).
(``no_frame_time``, ``invalid_arm_time``, ``min_pixels_invalid``,
``document_scope_contradicted`` and ``clock_check_missing`` were the
round-1..3 reasons of the lenient legacy branch; the strict schema names
those malformations earlier, so the tokens are gone.)

Usage:

    python3 -m perf.runner.witness --file out/witness.json [--bound-ms 2]

prints the verdict as JSON and exits 1 when the record is refused (2 when the
file is not a record at all — unreadable, or not valid JSON such as a bare
``NaN``; that refusal is printed as JSON too, reason ``record_unreadable``).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

#: The default bound on the page-local clock offset, in milliseconds. The
#: clock *check* applies it to ``page_offset_ms``; it is not, and was never,
#: a bound on the screencast conversion error (see witness.mjs's header for
#: the published conversion bound: [-2 ms, +the anchor lag bound]).
#: Lax layer (owner decision 2026-11-11): 2.0 -> 5.0 ms; the bound is echoed
#: on every record (``clock_skew_bound_ms`` / ``bound_ms``) so a trial
#: discloses which value gated it.
DEFAULT_SKEW_BOUND_MS = 5.0

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
#: Lax layer (owner decision 2026-11-11): the floor moves 100.0 -> 250.0 ms
#: (wordcraft anchor lags 101.3-151.8 ms refused C10/C11/C14 on HF); the
#: recomputed bound is recorded on every record (``lag_bound_ms``).
LAG_BOUND_INTERVALS = 3
LAG_BOUND_MIN_MS = 250.0

#: `witnessFrame()` clamps its window to at least DEFAULT_WINDOW_MS.
PRODUCER_MIN_WINDOW_MS = 500.0

#: The timestamp kinds whose conversion `detectTimestampKind` trusts.
KNOWN_TIMESTAMP_KINDS = ("epoch_seconds", "monotonic_seconds")

#: diff_ratio / max_diff_ratio are round(changed/total, 6); the tolerance
#: covers that rounding (half of 1e-6, plus float error).
RATIO_TOLERANCE = 1e-6

#: The anchor's own diff ratio is round(raw, 6) too, and the raw ratio is
#: strictly above ANCHOR_DIFF_THRESHOLD with at least ANCHOR_MIN_PIXELS
#: changed pixels in the probe region (R4-2); the recorded ratio may sit
#: half a rounding step below either bound (ANCHOR_RATIO_TOLERANCE).
ANCHOR_DIFF_THRESHOLD = 1e-5
ANCHOR_MIN_PIXELS = 4
ANCHOR_RATIO_TOLERANCE = 5e-7 + 1e-9

#: The anchor's probe is a square at the frame's top-left corner
#: (`anchorFrame()` in witness.mjs: ``x=0, y=0, width=height=
#: max(1, round(PROBE_CSS_PX * dpr))``). The dpr is the same reading the
#: record's own ``document_region.device_pixel_ratio`` carries, so a
#: scoped record's probe size is pinned to its own dpr (#137 round 6,
#: R5-4): the floor is applied to the area this geometry gives, recomputed
#: -- never to a size the record claims for itself.
PROBE_ORIGIN_X = 0
PROBE_ORIGIN_Y = 0
PROBE_CSS_PX = 8.0

#: `anchorFrame()` keeps a baseline frame from before the change (index
#: ``before - 1``) and searches for the anchor only among later frames
#: (from ``before``), so an anchor means at least this many recorder
#: frames (#137 round 6, R5-3). One frame is as impossible as zero.
ANCHOR_MIN_FRAMES = 2

#: The producer rounds its times to 3 decimals, so a difference of rounded
#: readings can drift by one and a half last-digits from the rounded
#: difference of the raw readings.
TIME_TOLERANCE_MS = 16e-4

#: The supported numeric domain (#137 round 7, R6-1, the owner's
#: decision): every numeric field of a witness record — a top-level
#: field, a nested clock-check field, an offset sample, an anchor-probe
#: coordinate, a conversion bound, a document-region number or one of its
#: rects — accepts only finite values whose magnitude is at most this.
#: The producer writes page times around 1e12 ms (an epoch in
#: milliseconds) and counts far below it; a number past 1e15 is one no
#: producer ever wrote, and the owning schema refuses it with the
#: ``value_out_of_range`` message token. The token is emitted before the
#: value is ever formatted (no diagnostic shows its digits, and every
#: arithmetic pass that reads it is guarded to stay total — the sweep
#: accumulates violations, it does not short-circuit the passes after
#: it, so a guarded comparison may read the value first; none of them
#: raises). The comparison below is exact at any magnitude and never
#: converts a huge integer (comparing int with float is safe); the
#: interpreter's integer-to-string conversion limit is never touched.
NUMERIC_DOMAIN_LIMIT = 1e15

#: The hard bound on one described value inside a diagnostic: no message
#: the validator builds for one value runs past this (#137 round 7,
#: R6-1).
DESCRIBE_MAX_CHARS = 64

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


def _number_out_of_domain(value):
    """True when ``value`` is a number (an int or float; booleans are not
    numbers) outside the supported numeric domain: not finite, or of a
    magnitude above ``NUMERIC_DOMAIN_LIMIT`` (#137 round 7, R6-1).

    The chained comparison is exact at any magnitude — Python compares
    int with float without converting either — and a NaN fails it, so
    every non-finite float is outside the domain too."""
    if not _number(value):
        return False
    return not (-NUMERIC_DOMAIN_LIMIT <= value <= NUMERIC_DOMAIN_LIMIT)


def _describe(value):
    """ONE bounded, exception-safe description of an input value, for every
    diagnostic that names one (#137 round 7, R6-1).

    Never ``str()``/``repr()``/``%d`` of an unbounded value: formatting a
    5,001-digit integer raises ``ValueError`` at the interpreter's
    4,300-digit conversion limit, which turned refusals into crashes
    (R6-1). The description names the value's type and is at most
    ``DESCRIBE_MAX_CHARS`` characters in total; an integer outside the
    supported numeric domain is described only by its bit length
    (``<int, N bits>``), never by its digits. Total over any Python
    object — the direct API accepts mappings (keys and values alike)
    the producer never wrote, including objects whose repr raises."""
    try:
        if value is None:
            text = "null"
        elif isinstance(value, bool):
            text = "bool true" if value else "bool false"
        elif isinstance(value, int):
            if _number_out_of_domain(value):
                text = "<int, %d bits>" % (value.bit_length(),)
            else:
                text = "int %d" % (value,)
        elif isinstance(value, float):
            text = "float %r" % (value,)  # a float's repr is short, always
        elif isinstance(value, str):
            text = "str '%s'%s" % (value[:40], "..." if len(value) > 40 else "")
        elif isinstance(value, (list, tuple)):
            text = "%s (%d items)" % (type(value).__name__, len(value))
        elif isinstance(value, dict):
            text = "object (%d keys)" % (len(value),)
        else:
            text = "<%s>" % (type(value).__name__,)
    except Exception:  # noqa: BLE001 -- a describer that raises is the bug
        text = "<undescribable>"
    if len(text) > DESCRIBE_MAX_CHARS:
        return text[: DESCRIBE_MAX_CHARS - 3] + "..."
    return text


def _as_float(value):
    """The value as a finite float, or None when it is not a number or is
    outside the float domain the producer writes (#137 round 5, R4-1).

    A JSON integer such as ``10**400`` is a number no producer ever wrote
    (it does not fit a float); converting it must be a refusal, never an
    ``OverflowError``."""
    if not _number(value):
        return None
    try:
        out = float(value)
    except OverflowError:
        return None
    return out if math.isfinite(out) else None


def _finite_number(value):
    return _as_float(value) is not None


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
    """JavaScript's Math.round (half away from zero via floor(x + 0.5)).

    None when the value, or the arithmetic around it, is outside the
    representable range (#137 round 5, R4-1): the caller's equality then
    cannot hold, and it must say so instead of raising."""
    x = _as_float(value)
    if x is None:
        return None
    x += 0.5  # two finite floats can still overflow here
    if not math.isfinite(x):
        return None
    return math.floor(x)


def _median(values):
    """The producer's median: the middle sample, or the mean of the two.
    None when there are no samples, the value is not a list, or a sample
    is not a finite float the producer could have written (#137 round 6,
    R5-1: total over every JSON value -- the caller's recomputation then
    fails named, never with a TypeError or ValueError)."""
    if not isinstance(values, list) or not values:
        return None
    as_floats = [_as_float(sample) for sample in values]
    if any(sample is None for sample in as_floats):
        return None
    ordered = sorted(as_floats)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _samples_range(values):
    """max-min of the samples as floats, or None when there are no samples,
    the value is not a list, or one of them is outside the float domain the
    producer writes (R4-1/R5-1: the spread's recomputation then fails
    named, never with an exception)."""
    if not isinstance(values, list) or not values:
        return None
    as_floats = [_as_float(sample) for sample in values]
    if any(sample is None for sample in as_floats):
        return None
    return max(as_floats) - min(as_floats)


def _probe_side_px(dpr):
    """The producer's anchor-probe side in device pixels at a device pixel
    ratio: ``max(1, round(PROBE_CSS_PX * dpr))``, the one expression
    `anchorFrame()` writes for both width and height. None when the ratio
    is not a positive finite number (the record carries no usable dpr, or
    one whose probe is outside the representable range -- the schema's or
    the anchor evidence's to refuse, each named)."""
    ratio = _as_float(dpr)
    if ratio is None or ratio <= 0:
        return None
    side = _js_round(PROBE_CSS_PX * ratio)
    return None if side is None else max(1, side)


def _skew_of(record, skew=None):
    """The page-local clock offset of a record, in milliseconds, or None.

    A caller's explicit offset wins — absolutely (#137 round 8, R7-1):
    an explicit offset that is not a finite number inside the supported
    numeric domain is never silently swapped for the record's own; it
    returns None here and the caller-argument boundary in
    `validate_witness` refuses it. The record's own aliases follow only
    when no explicit offset was supplied: the deprecated top-level
    ``clock_skew_ms``, then the nested check's ``page_offset_ms``. The
    ``clock_skew`` dict slot is deliberately not
    read: the producer never writes it on a frame-witness record (it is a
    section key of the ``--op all`` bundle, not of a witness record), and
    the closed schema refuses the key outright (#137 round 4, N4).

    #137 round 7, R6-1: a record's own offset outside the supported
    numeric domain is not usable arithmetic input either — the schema's
    domain sweep refuses the field it came from, and no gate downstream
    (the skew comparison included) reads the value first."""
    if skew is not None:
        if _finite_number(skew) and not _number_out_of_domain(skew):
            return float(skew)
        return None
    value = record.get("clock_skew_ms")
    if _finite_number(value) and not _number_out_of_domain(value):
        return float(value)
    nested = record.get("clock_check")
    if isinstance(nested, dict):
        offset = nested.get("page_offset_ms")
        if _finite_number(offset) and not _number_out_of_domain(offset):
            return float(offset)
    return None


def _is_production_record(record):
    """Does the record carry the producer's markers? (#137 round 4: the
    discriminator is positive.)

    A record IS a frame witness only when it says so the way
    `witnessFrame()` says it: the ``kind``, the ``clock_check_source``, or
    a nested clock check that carries the production method or the raw
    measurements only `clockSkew()` records (its offset samples, its lag
    bound, its conversion statement, its anchor times). Any one marker
    makes it a witness record, which then faces the full strict schema;
    erasing markers one at a time leaves the others (verified by test), and
    the coordinated nine-field erasure leaves a record that is refused as
    ``not_a_witness_record`` instead of falling back to anything lenient.
    No producer writes a record without these markers: every B2–B5 writer
    calls `witnessFrame()`, which always emits ``kind: 'frame_witness'``."""
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
                out.append(
                    "%s%s must be an integer (got %s)" % (prefix, key, _describe(value))
                )
            elif (key in ("x", "y") and value < 0) or (key in ("width", "height") and value < 1):
                out.append(
                    "%s%s is out of the producer's range (got %s)"
                    % (prefix, key, _describe(value))
                )
        else:
            if not _finite_number(value):
                out.append(
                    "%s%s must be a finite number (got %s)"
                    % (prefix, key, _describe(value))
                )
            elif key in ("width", "height") and value <= 0:
                out.append(
                    "%s%s must be positive (got %s)"
                    % (prefix, key, _describe(value))
                )
    return out


def _region_violations(record):
    """Schema + arithmetic violations of the document region."""
    out = []
    region = record.get("document_region")
    if not isinstance(region, dict):
        return ["document_region must be an object when the record is scoped"]
    source = region.get("source")
    if source not in ("selector", "rect"):
        out.append(
            "document_region.source must be 'selector' or 'rect' (got %s)"
            % (_describe(source),)
        )
    selector = region.get("selector")
    if source == "selector" and not _nonempty_str(selector):
        out.append(
            "a selector-sourced region names its selector (got %s)"
            % (_describe(selector),)
        )
    if source == "rect" and selector is not None:
        out.append(
            "a rect-sourced region carries no selector (got %s)"
            % (_describe(selector),)
        )
    css = region.get("rect_css_px")
    device = region.get("rect_device_px")
    dpr = region.get("device_pixel_ratio")
    if not isinstance(css, dict):
        out.append(
            "document_region.rect_css_px must be an object (got %s)"
            % (_describe(css),)
        )
    if not isinstance(device, dict):
        out.append(
            "document_region.rect_device_px must be an object (got %s)"
            % (_describe(device),)
        )
    if isinstance(css, dict):
        out += _rect_violations("document_region.rect_css_px.", css, device=False)
    if isinstance(device, dict):
        out += _rect_violations("document_region.rect_device_px.", device, device=True)
    if not _finite_number(dpr) or float(dpr) <= 0:
        out.append(
            "document_region.device_pixel_ratio must be positive (got %s)"
            % (_describe(dpr),)
        )
        return out
    # The arithmetic the producer did: device = round(css * dpr), clamped to
    # the frame. The clamp only ever shrinks a width or height and zeroes a
    # negative origin, so the exact checkable relations are these. The
    # products are overflow-guarded (#137 round 5, R4-1): a css rect at a
    # 1e308 dpr is outside the representable pixel range, and that is a
    # named violation, never an OverflowError.
    if isinstance(css, dict) and isinstance(device, dict) and all(
        _finite_number(css.get(k)) for k in ("x", "y", "width", "height")
    ):
        rounded = {
            key: _js_round(float(css[key]) * float(dpr))
            for key in ("x", "y", "width", "height")
        }
        if any(value is None for value in rounded.values()):
            out.append(
                "document_region's CSS rect at the recorded dpr (%s) is "
                "outside the representable pixel range" % (_describe(dpr),)
            )
        else:
            for axis in ("x", "y"):
                expected = max(0, rounded[axis])
                if _count(device.get(axis)) is not None and device[axis] != expected:
                    out.append(
                        "document_region.rect_device_px.%s (%s) is not the CSS rect at "
                        "the recorded dpr (expected %s)"
                        % (axis, _describe(device[axis]), _describe(expected))
                    )
            for axis, span in (("x", "width"), ("y", "height")):
                upper = rounded[axis] + rounded[span]
                lower = max(0, rounded[axis])
                value = device.get(span)
                if _count(value) is None or not 1 <= value <= upper - lower:
                    out.append(
                        "document_region.rect_device_px.%s (%s) does not fit the CSS "
                        "rect at the recorded dpr ([%s, %s])"
                        % (span, _describe(value), _describe(1), _describe(upper - lower))
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
                "region_pixels (%s) must be the device rect's area (%s)"
                % (_describe(pixels), _describe(area))
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

#: The closed set of top-level keys a frame-witness record may carry
#: (#137 round 4, N4): every field `witnessFrame()` emits, plus
#: `marker_page_ms`, which the CLI adds as its alias of the arm (a record
#: made through the module API does not carry it). Anything else is a key
#: the producer never writes, and the record is refused.
#: ``quiet_window`` is the r3c07b C07 evidence block: present only when the
#: producer proved the watched box repainted nothing for at least
#: ``required_ms`` before the arm fired. Other criteria's records do not
#: carry it, so it sits in the allowed set without joining the required
#: field list.
_PRODUCTION_ALLOWED_KEYS = frozenset(_PRODUCTION_FIELDS) | {
    "marker_page_ms",
    "quiet_window",
}

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

#: The closed set of keys the nested clock check may carry (#137 round 4,
#: N4): exactly `clockSkew()`'s output. The `page_offset_only` fallback
#: shape emits a subset of it; nothing may add to it.
_CLOCK_CHECK_ALLOWED_KEYS = frozenset(_CLOCK_CHECK_FIELDS)

#: The closed key sets of the objects the producer nests inside those
#: (#137 round 5, N4: the schema is closed recursively, at every object
#: the producer emits). Each set is asserted equal to a real capture's
#: keys by the permanent tests.
_CHECKS_ALLOWED_KEYS = frozenset(CLOCK_CHECK_KEYS)
_PROBE_REGION_ALLOWED_KEYS = frozenset(("x", "y", "width", "height"))
_CONVERSION_ALLOWED_KEYS = frozenset(
    (
        "formula",
        "error_lower_ms",
        "error_lower_why",
        "error_upper_ms",
        "error_upper_why",
        "published",
    )
)
_DOCUMENT_REGION_ALLOWED_KEYS = frozenset(
    ("source", "selector", "rect_css_px", "rect_device_px", "device_pixel_ratio")
)
_RECT_ALLOWED_KEYS = frozenset(("x", "y", "width", "height"))

#: The closed key set of a ``quiet_window`` block (r3c07b): what the
#: producer's quiet proof emits — no more, no less.
_QUIET_WINDOW_ALLOWED_KEYS = frozenset(
    (
        "required_ms",
        "budget_ms",
        "proven",
        "observed_ms",
        "start_page_ms",
        "end_page_ms",
        "changes_seen",
        "events",
        "exhausted",
        "violated",
    )
)
_QUIET_EVENT_ALLOWED_KEYS = frozenset(("frame_page_ms", "changed", "ratio"))

#: Every numeric field of the record itself, of its document region and of
#: the nested clock check (its anchor probe region and its conversion
#: statement included): the fields the supported-numeric-domain check
#: sweeps (#137 round 7, R6-1). The names are the producer's own, pinned
#: to the real capture by the permanent tests.
_TOP_LEVEL_NUMERIC_FIELDS = frozenset(
    (
        "frame_page_ms",
        "frames_total",
        "frames_after",
        "frames_ack_skipped",
        "diff_ratio",
        "threshold",
        "min_pixels",
        "window_ms",
        "window_requested_ms",
        "elapsed_ms",
        "time_origin_ms",
        "max_diff_ratio",
        "after_page_ms",
        "baseline_page_ms",
        "marker_page_ms",
        "changed_pixels",
        "total_pixels",
        "region_pixels",
        "clock_skew_ms",
        "clock_skew_bound_ms",
    )
)
_CHECK_NUMERIC_FIELDS = frozenset(
    (
        "bound_ms",
        "page_offset_ms",
        "skew_ms",
        "page_offset_spread_ms",
        "time_origin_ms",
        "change_page_ms",
        "frame_page_ms",
        "frame_lag_ms",
        "frame_monotonic_ms",
        "frames_total",
        "anchor_diff_ratio",
        "frame_interval_ms",
        "frame_interval_samples",
        "lag_bound_ms",
    )
)
_RECT_NUMERIC_FIELDS = frozenset(("x", "y", "width", "height"))
_CONVERSION_NUMERIC_FIELDS = frozenset(("error_lower_ms", "error_upper_ms"))


def _domain_message(what, value):
    """The owning schema's ``value_out_of_range`` violation for one numeric
    field outside the supported domain (#137 round 7, R6-1). The value is
    described, never formatted."""
    return (
        "%s is outside the supported numeric domain (value_out_of_range): "
        "every number the producer writes is finite with |x| <= %g (got %s)"
        % (what, NUMERIC_DOMAIN_LIMIT, _describe(value))
    )


def _quiet_window_violations(quiet, witnessed, bad):
    """The r3c07b quiet-box block's own invariants.

    A ``witnessed`` record whose quiet window exists must carry a *proven*
    one: a sample timed against a box that repainted inside the required
    window is a latency the witness never earned. A ``no_frame`` record may
    carry either proof state — the quiet refusal itself is a named outcome
    and a proven window can still end in no_frame (the click painted
    nothing inside the box).
    """
    for field in ("required_ms", "budget_ms", "observed_ms"):
        value = quiet.get(field)
        if not _finite_number(value) or float(value) < 0:
            bad(
                "quiet_window.%s must be a non-negative number (got %s)"
                % (field, _describe(value))
            )
    for field in ("proven", "exhausted", "violated"):
        if not _bool(quiet.get(field)):
            bad(
                "quiet_window.%s must be a boolean (got %s)"
                % (field, _describe(quiet.get(field)))
            )
    seen = quiet.get("changes_seen")
    if _count(seen) is None or seen < 0:
        bad("quiet_window.changes_seen must be a count (got %s)" % (_describe(seen),))
    events = quiet.get("events")
    if not isinstance(events, list):
        bad("quiet_window.events must be a list (got %s)" % (_describe(events),))
    elif _count(seen) is not None and len(events) > seen:
        bad(
            "quiet_window.events (%d) cannot outnumber changes_seen (%d)"
            % (len(events), seen)
        )
    else:
        for event in events:
            if not isinstance(event, dict):
                bad("quiet_window.events entries are objects (got %s)" % (_describe(event),))
                continue
            for key in sorted(set(event) - _QUIET_EVENT_ALLOWED_KEYS, key=_describe):
                bad(
                    "unknown quiet_window.events field %s: the producer emits a closed set of keys"
                    % (_describe(key),)
                )
            for field in ("frame_page_ms", "ratio"):
                if not _finite_number(event.get(field)):
                    bad(
                        "quiet_window.events.%s must be a finite number (got %s)"
                        % (field, _describe(event.get(field)))
                    )
            if _count(event.get("changed")) is None or event.get("changed", -1) < 0:
                bad(
                    "quiet_window.events.changed must be a count (got %s)"
                    % (_describe(event.get("changed")),)
                )
    for field in ("start_page_ms", "end_page_ms"):
        value = quiet.get(field)
        if value is not None and not _finite_number(value):
            bad(
                "quiet_window.%s must be a finite number or null (got %s)"
                % (field, _describe(value))
            )
    proven = quiet.get("proven") is True
    if quiet.get("exhausted") is True and proven:
        bad("quiet_window cannot be exhausted and proven")
    if quiet.get("violated") is True and _count(seen) == 0:
        bad("quiet_window.violated requires at least one change seen")
    if proven:
        required = quiet.get("required_ms")
        observed = quiet.get("observed_ms")
        if _finite_number(required) and _finite_number(observed) and float(observed) < float(required):
            bad(
                "quiet_window.observed_ms (%s) is below required_ms (%s): the window is not proven"
                % (_describe(observed), _describe(required))
            )
        if _finite_number(required) and float(required) < 1000:
            bad(
                "quiet_window.required_ms below 1000 (%s) is not the C07 quiet box"
                % (_describe(required),)
            )
    if witnessed:
        if not proven:
            bad(
                "a witnessed frame needs quiet_window.proven: a latency timed "
                "against a box the proof could not show quiet"
            )
        elif quiet.get("violated") is True or quiet.get("exhausted") is True:
            bad(
                "a witnessed frame needs a quiet_window with no violation and no exhaustion"
            )


def _production_schema_violations(record):
    """(reason, message) pairs: every way a production record can violate the
    schema the producer's fields define. Ordered; the first names the
    verdict's reason."""
    out = []
    witnessed = record.get("outcome") == "witnessed"

    def bad(message):
        out.append(("witness_schema_invalid", "witness schema: " + message))

    # #137 round 7, R6-1: the supported numeric domain, checked BEFORE any
    # arithmetic or formatting reads a value. Everything below (the
    # per-field checks, the region arithmetic, the evidence recomputation)
    # then only ever describes an out-of-domain number — through
    # _describe, never by formatting it — and round 6's boundary is gone:
    # a huge-but-valid informational number is refused here, not accepted.
    for field in sorted(set(record) & _TOP_LEVEL_NUMERIC_FIELDS):
        if _number_out_of_domain(record[field]):
            bad(_domain_message(field, record[field]))
    region = record.get("document_region")
    if isinstance(region, dict):
        if _number_out_of_domain(region.get("device_pixel_ratio")):
            bad(
                _domain_message(
                    "document_region.device_pixel_ratio",
                    region["device_pixel_ratio"],
                )
            )
        for rect_key in ("rect_css_px", "rect_device_px"):
            rect = region.get(rect_key)
            if isinstance(rect, dict):
                for field in sorted(set(rect) & _RECT_NUMERIC_FIELDS):
                    if _number_out_of_domain(rect[field]):
                        bad(
                            _domain_message(
                                "document_region.%s.%s" % (rect_key, field),
                                rect[field],
                            )
                        )

    # The schema is closed, recursively (#137 round 4 N4; round 5: at every
    # object the producer emits). A key the producer does not emit — at the
    # root, in the clock check, in its recorded checks, its anchor probe
    # region, its conversion statement, the document region or its rects —
    # is a record the producer did not write, including the `clock_skew`
    # alias slot, which could otherwise restate an offset the reader would
    # never cross-check. Every allowed set is pinned to a real capture by
    # the tests.
    def unknown_keys(obj, allowed, what):
        if not isinstance(obj, dict):
            return
        # sorted by the described key (#137 round 7, R6-1): the direct API
        # accepts mappings whose keys need share no order — and the message
        # describes the key, it never formats it.
        for field in sorted(set(obj) - allowed, key=_describe):
            bad(
                "unknown %s field %s: the producer emits a closed set of keys"
                % (what, _describe(field))
            )

    unknown_keys(record, _PRODUCTION_ALLOWED_KEYS, "top-level")
    nested = record.get("clock_check")
    if isinstance(nested, dict):
        unknown_keys(nested, _CLOCK_CHECK_ALLOWED_KEYS, "clock_check")
        unknown_keys(
            nested.get("checks"), _CHECKS_ALLOWED_KEYS, "clock_check.checks"
        )
        unknown_keys(
            nested.get("anchor_probe_region_px"),
            _PROBE_REGION_ALLOWED_KEYS,
            "clock_check.anchor_probe_region_px",
        )
        unknown_keys(
            nested.get("conversion"),
            _CONVERSION_ALLOWED_KEYS,
            "clock_check.conversion",
        )
    region = record.get("document_region")
    if isinstance(region, dict):
        unknown_keys(region, _DOCUMENT_REGION_ALLOWED_KEYS, "document_region")
        for rect_key in ("rect_css_px", "rect_device_px"):
            unknown_keys(
                region.get(rect_key),
                _RECT_ALLOWED_KEYS,
                "document_region.%s" % (rect_key,),
            )
    quiet = record.get("quiet_window")
    if quiet is not None:
        if not isinstance(quiet, dict):
            bad("quiet_window must be an object (got %s)" % (_describe(quiet),))
        else:
            unknown_keys(quiet, _QUIET_WINDOW_ALLOWED_KEYS, "quiet_window")
            _quiet_window_violations(quiet, witnessed, bad)

    # Every field the producer emits is present; a field that vanished is a
    # record that stopped being the evidence it claims (an erased alias, a
    # dropped error slot). Nulls are refused where the producer's value is a
    # number (the per-field checks below do that).
    for field in _PRODUCTION_FIELDS:
        if field not in record:
            bad("the record is missing its %s field" % (field,))

    if record.get("kind") != PRODUCTION_KIND:
        bad(
            "kind must be %r (got %s)"
            % (PRODUCTION_KIND, _describe(record.get("kind")))
        )

    # -- counts and numbers, with the producer's ranges --------------------
    for field in ("frames_total", "frames_after", "frames_ack_skipped"):
        value = record.get(field)
        if _count(value) is None:
            bad("%s must be an integer (got %s)" % (field, _describe(value)))
        elif value < 0:
            bad("%s must not be negative (got %s)" % (field, _describe(value)))
    # #137 round 5, R4-2: a skipped ack is one of the recorder's frames
    # (the producer counts it while iterating them), so it cannot outnumber
    # them.
    if _count(record.get("frames_ack_skipped")) is not None and _count(
        record.get("frames_total")
    ) is not None:
        if record["frames_ack_skipped"] > record["frames_total"]:
            bad(
                "frames_ack_skipped (%s) exceeds frames_total (%s): a skipped "
                "frame is still one of the recorder's frames"
                % (
                    _describe(record["frames_ack_skipped"]),
                    _describe(record["frames_total"]),
                )
            )

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
            bad("%s must be a finite number (got %s)" % (field, _describe(value)))
            continue
        if field in ("diff_ratio", "max_diff_ratio") and not 0.0 <= float(value) <= 1.0:
            bad("%s must be between 0 and 1 (got %s)" % (field, _describe(value)))
        if field == "threshold" and float(value) <= 0:
            bad("threshold must be positive (got %s)" % (_describe(value),))
        if low is not None and float(value) < low:
            bad("%s must be at least %s (got %s)" % (field, low, _describe(value)))

    for field in ("changed_pixels", "total_pixels"):
        value = record.get(field)
        if _count(value) is None:
            bad("%s must be an integer (got %s)" % (field, _describe(value)))
        elif value < 0:
            bad("%s must not be negative (got %s)" % (field, _describe(value)))
    if witnessed and _count(record.get("total_pixels")) == 0:
        bad("a witnessed frame needs at least one pixel to differ in")

    # -- times --------------------------------------------------------------
    frame_page_ms = record.get("frame_page_ms")
    if witnessed:
        if not _finite_number(frame_page_ms):
            bad(
                "a witnessed frame_page_ms is a finite number (got %s)"
                % (_describe(frame_page_ms),)
            )
    elif frame_page_ms is not None:
        bad("a no_frame record has no frame_page_ms (got %s)" % (_describe(frame_page_ms),))
    after_page_ms = record.get("after_page_ms")
    if witnessed:
        if not _finite_number(after_page_ms):
            bad(
                "a witnessed record carries its arm after_page_ms (got %s)"
                % (_describe(after_page_ms),)
            )
    elif after_page_ms is not None and not _finite_number(after_page_ms):
        bad(
            "after_page_ms must be a finite number or null (got %s)"
            % (_describe(after_page_ms),)
        )
    if "baseline_page_ms" in record and record["baseline_page_ms"] is not None and (
        not _finite_number(record["baseline_page_ms"]) or float(record["baseline_page_ms"]) < 0
    ):
        bad(
            "baseline_page_ms must be a non-negative number or null (got %s)"
            % (_describe(record["baseline_page_ms"]),)
        )
    # The baseline is the picture *before* the change; a baseline after the
    # witness frame is an order no run produced.
    if (
        _finite_number(record.get("baseline_page_ms"))
        and _finite_number(record.get("frame_page_ms"))
        and float(record["baseline_page_ms"])
        > float(record["frame_page_ms"]) + CAUSALITY_SLOP_MS + TIME_TOLERANCE_MS
    ):
        bad(
            "baseline_page_ms (%s) is after the witness frame (%s): the "
            "baseline is taken before the change"
            % (
                _describe(record["baseline_page_ms"]),
                _describe(record["frame_page_ms"]),
            )
        )
    if "marker_page_ms" in record:
        marker = record["marker_page_ms"]
        if marker is not None and not _finite_number(marker):
            bad("marker_page_ms must be a finite number or null (got %s)" % (_describe(marker),))
        elif record.get("after_page_ms") != marker:
            bad(
                "marker_page_ms (%s) is the CLI's alias of the arm after_page_ms (%s)"
                % (_describe(marker), _describe(record.get("after_page_ms")))
            )

    # -- strings, flags, enums ----------------------------------------------
    if not _nonempty_str(record.get("timestamp_kind")):
        bad(
            "timestamp_kind must name the timestamps' kind (got %s)"
            % (_describe(record.get("timestamp_kind")),)
        )
    elif witnessed and record["timestamp_kind"] not in KNOWN_TIMESTAMP_KINDS:
        bad(
            "a witnessed frame needed a convertible timestamp kind (got %s)"
            % (_describe(record["timestamp_kind"]),)
        )
    if not _nonempty_str(record.get("baseline_source")):
        bad(
            "baseline_source must name the baseline's source (got %s)"
            % (_describe(record.get("baseline_source")),)
        )
    if not _nonempty_str(record.get("caret_mask_css")) and not _intentional_unmasked_caret(record):
        bad(
            "caret_mask_css must be the injected style (got %s)"
            % (_describe(record.get("caret_mask_css")),)
        )
    if record.get("clock_check_source") not in ("caller", "inline", "page_offset_only"):
        bad(
            "clock_check_source must be caller, inline or page_offset_only (got %s)"
            % (_describe(record.get("clock_check_source")),)
        )
    if not _bool(record.get("caret_masked")):
        bad("caret_masked must be a boolean (got %s)" % (_describe(record.get("caret_masked")),))
    if record.get("caret_mask_error") is not None and not isinstance(record.get("caret_mask_error"), str):
        bad(
            "caret_mask_error must be a string or null (got %s)"
            % (_describe(record.get("caret_mask_error")),)
        )
    if not _bool(record.get("document_scoped")):
        bad(
            "document_scoped must be a boolean (got %s)"
            % (_describe(record.get("document_scoped")),)
        )
    if not _bool(record.get("clock_skew_acceptable")):
        bad(
            "clock_skew_acceptable must be a boolean (got %s)"
            % (_describe(record.get("clock_skew_acceptable")),)
        )
    if record.get("clock_skew_ms") is not None and not _finite_number(record.get("clock_skew_ms")):
        bad(
            "clock_skew_ms must be a finite number or null (got %s)"
            % (_describe(record.get("clock_skew_ms")),)
        )
    if record.get("clock_skew_method") is not None and not _nonempty_str(record.get("clock_skew_method")):
        bad(
            "clock_skew_method must be a non-empty string or null (got %s)"
            % (_describe(record.get("clock_skew_method")),)
        )
    if not _finite_number(record.get("clock_skew_bound_ms")) or (
        _finite_number(record.get("clock_skew_bound_ms")) and float(record["clock_skew_bound_ms"]) <= 0
    ):
        bad(
            "clock_skew_bound_ms must be positive (got %s)"
            % (_describe(record.get("clock_skew_bound_ms")),)
        )

    # -- scope: the region the producer resolves for a scoped record --------
    scoped = record.get("document_scoped") is True
    region = record.get("document_region")
    error = record.get("document_region_error")
    if scoped:
        if error is not None:
            bad(
                "a scoped record carries no document_region_error (got %s)"
                % (_describe(error),)
            )
        out += [("witness_schema_invalid", "witness schema: " + m) for m in _region_violations(record)]
    else:
        if region is not None:
            bad(
                "an unscoped record carries no document_region (got %s)"
                % (_describe(region),)
            )
        if record.get("region_pixels") is not None:
            bad(
                "an unscoped record carries no region_pixels (got %s)"
                % (_describe(record.get("region_pixels")),)
            )
        if error is not None and not isinstance(error, str):
            bad("document_region_error must be a string or null (got %s)" % (_describe(error),))

    # -- the nested clock check is part of the record ----------------------
    nested = record.get("clock_check")
    if not isinstance(nested, dict):
        bad(
            "clock_check must be the run's clock-check record (got %s)"
            % (_describe(nested),)
        )
    return out


def _clock_schema_violations(nested):
    """(reason, message) pairs for the nested clock check of a production
    record that claims acceptable: every field `clockSkew()` emits, with its
    type, presence and range."""
    out = []

    def bad(message):
        out.append(("clock_check_schema_invalid", "clock check schema: " + message))

    # #137 round 7, R6-1: the supported numeric domain for the check's own
    # fields -- its offset samples, its anchor probe region and its
    # conversion statement included -- before anything reads them.
    for field in sorted(set(nested) & _CHECK_NUMERIC_FIELDS):
        if _number_out_of_domain(nested[field]):
            bad(_domain_message(field, nested[field]))
    samples = nested.get("page_offset_samples")
    if isinstance(samples, list):
        for index, sample in enumerate(samples):
            if _number_out_of_domain(sample):
                bad(_domain_message("page_offset_samples[%d]" % (index,), sample))
    probe = nested.get("anchor_probe_region_px")
    if isinstance(probe, dict):
        for field in sorted(set(probe) & _RECT_NUMERIC_FIELDS):
            if _number_out_of_domain(probe[field]):
                bad(
                    _domain_message(
                        "anchor_probe_region_px.%s" % (field,), probe[field]
                    )
                )
    conversion = nested.get("conversion")
    if isinstance(conversion, dict):
        for field in sorted(set(conversion) & _CONVERSION_NUMERIC_FIELDS):
            if _number_out_of_domain(conversion[field]):
                bad(
                    _domain_message(
                        "conversion.%s" % (field,), conversion[field]
                    )
                )

    for field in _CLOCK_CHECK_FIELDS:
        if field not in nested:
            bad("the check is missing its %s field" % (field,))

    if nested.get("kind") != "clock_skew":
        bad("kind must be 'clock_skew' (got %s)" % (_describe(nested.get("kind")),))
    if nested.get("method") != PRODUCTION_CLOCK_METHOD:
        bad(
            "method must be %r (got %s)"
            % (PRODUCTION_CLOCK_METHOD, _describe(nested.get("method")))
        )
    if not _bool(nested.get("acceptable")):
        bad("acceptable must be a boolean (got %s)" % (_describe(nested.get("acceptable")),))
    if nested.get("reason") is not None:
        bad("an acceptable check records no reason (got %s)" % (_describe(nested.get("reason")),))
    checks = nested.get("checks")
    if not isinstance(checks, dict):
        bad("checks must be the recorded checks (got %s)" % (_describe(checks),))
    else:
        for key in CLOCK_CHECK_KEYS:
            if key not in checks:
                bad("the recorded checks are missing %r" % (key,))
            elif not _bool(checks[key]):
                bad("the recorded check %r must be a boolean (got %s)" % (key, _describe(checks[key])))
    if not _nonempty_str(nested.get("timestamp_kind")):
        bad("timestamp_kind must name the timestamps' kind (got %s)" % (_describe(nested.get("timestamp_kind")),))
    elif nested["timestamp_kind"] not in KNOWN_TIMESTAMP_KINDS:
        bad("an acceptable check needed a convertible timestamp kind (got %s)" % (_describe(nested["timestamp_kind"]),))
    if not _nonempty_str(nested.get("timestamp_field")):
        bad("timestamp_field must name the metadata field (got %s)" % (_describe(nested.get("timestamp_field")),))
    bound = nested.get("bound_ms")
    if not _finite_number(bound) or float(bound) <= 0:
        bad("bound_ms must be positive (got %s)" % (_describe(bound),))
    if not _finite_number(nested.get("page_offset_ms")):
        bad("page_offset_ms must be a finite number (got %s)" % (_describe(nested.get("page_offset_ms")),))
    if not _finite_number(nested.get("skew_ms")):
        bad("skew_ms must be a finite number (got %s)" % (_describe(nested.get("skew_ms")),))
    samples = nested.get("page_offset_samples")
    if not isinstance(samples, list) or not samples:
        bad("page_offset_samples must be a non-empty list (got %s)" % (_describe(samples),))
    elif not all(_finite_number(s) for s in samples):
        bad("page_offset_samples must be finite numbers (got %s)" % (_describe(samples),))
    spread = nested.get("page_offset_spread_ms")
    if not _finite_number(spread) or float(spread) < 0:
        bad("page_offset_spread_ms must be a non-negative number (got %s)" % (_describe(spread),))
    if not _finite_number(nested.get("time_origin_ms")):
        bad("time_origin_ms must be a finite number (got %s)" % (_describe(nested.get("time_origin_ms")),))
    for field in ("change_page_ms", "frame_page_ms", "frame_lag_ms"):
        if not _finite_number(nested.get(field)):
            bad(
                "an acceptable check's anchor carries %s as a finite number (got %s)"
                % (field, _describe(nested.get(field)))
            )
    change = nested.get("change_page_ms")
    if _finite_number(change) and float(change) < 0:
        bad("change_page_ms is a page time (got %s)" % (_describe(change),))
    if nested.get("frame_monotonic_ms") is not None and (
        not _finite_number(nested.get("frame_monotonic_ms"))
        or float(nested["frame_monotonic_ms"]) < 0
    ):
        bad("frame_monotonic_ms must be a non-negative number or null (got %s)" % (_describe(nested.get("frame_monotonic_ms")),))
    if _count(nested.get("frames_total")) is None or nested.get("frames_total", -1) < 0:
        bad("the check's frames_total must be a non-negative integer (got %s)" % (_describe(nested.get("frames_total")),))
    if nested.get("anchor_pixel_checked") is not True:
        bad("an acceptable check pixel-checked its anchor (got %s)" % (_describe(nested.get("anchor_pixel_checked")),))
    ratio = nested.get("anchor_diff_ratio")
    if not _finite_number(ratio) or not 0.0 < float(ratio) <= 1.0:
        bad("anchor_diff_ratio must be in (0, 1] (got %s)" % (_describe(ratio),))
    probe = nested.get("anchor_probe_region_px")
    if not isinstance(probe, dict):
        bad("anchor_probe_region_px must be an object (got %s)" % (_describe(probe),))
    else:
        for key in ("width", "height"):
            if _count(probe.get(key)) is None or probe[key] < 1:
                bad("anchor_probe_region_px.%s must be at least 1 (got %s)" % (key, _describe(probe.get(key))))
        for key in ("x", "y"):
            if _count(probe.get(key)) is None:
                bad("anchor_probe_region_px.%s must be an integer (got %s)" % (key, _describe(probe.get(key))))
    interval = nested.get("frame_interval_ms")
    if interval is not None and (not _finite_number(interval) or float(interval) <= 0):
        bad("frame_interval_ms must be positive or null (got %s)" % (_describe(interval),))
    if not _nonempty_str(nested.get("frame_interval_source")):
        bad("frame_interval_source must name the interval's source (got %s)" % (_describe(nested.get("frame_interval_source")),))
    if nested.get("frame_interval_samples") is not None and (
        _count(nested.get("frame_interval_samples")) is None
        or nested["frame_interval_samples"] < 0
    ):
        bad(
            "frame_interval_samples must be a non-negative integer or null (got %s)"
            % (_describe(nested.get("frame_interval_samples")),)
        )
    lag_bound = nested.get("lag_bound_ms")
    if not _finite_number(lag_bound) or float(lag_bound) < LAG_BOUND_MIN_MS:
        bad(
            "lag_bound_ms must be at least the rule's minimum %s ms (got %s)"
            % (LAG_BOUND_MIN_MS, _describe(lag_bound))
        )
    if not _nonempty_str(nested.get("lag_bound_rule")):
        bad("lag_bound_rule must state the bound's rule (got %s)" % (_describe(nested.get("lag_bound_rule")),))
    conversion = nested.get("conversion")
    if not isinstance(conversion, dict):
        bad("conversion must state the published bound (got %s)" % (_describe(conversion),))
    else:
        for key in ("formula", "error_lower_why", "error_upper_why", "published"):
            if not _nonempty_str(conversion.get(key)):
                bad("conversion.%s must be stated (got %s)" % (key, _describe(conversion.get(key))))
        for key in ("error_lower_ms", "error_upper_ms"):
            if not _finite_number(conversion.get(key)):
                bad("conversion.%s must be a finite number (got %s)" % (key, _describe(conversion.get(key))))
    if not _bool(nested.get("caret_masked")):
        bad("the check's caret_masked must be a boolean (got %s)" % (_describe(nested.get("caret_masked")),))
    elif nested.get("caret_masked") is not True:
        bad("an acceptable check masked its own caret (caret_masked=%s)" % (_describe(nested.get("caret_masked")),))
    if nested.get("caret_mask_error") is not None and not isinstance(nested.get("caret_mask_error"), str):
        bad("the check's caret_mask_error must be a string or null (got %s)" % (_describe(nested.get("caret_mask_error")),))
    elif isinstance(nested.get("caret_mask_error"), str) and nested["caret_mask_error"]:
        bad(
            "an acceptable check records no mask failure (caret_mask_error=%s)"
            % (_describe(nested["caret_mask_error"]),)
        )
    notes = nested.get("notes")
    if not isinstance(notes, list) or not notes or not all(_nonempty_str(n) for n in notes):
        bad("notes must be a non-empty list of strings (got %s)" % (_describe(notes),))
    return out


# --------------------------------------------------------------------------
# The recomputation (#137 round 3, part 2)
# --------------------------------------------------------------------------


def _anchor_pixel_evidence(nested, dpr=None):
    """(ok, why-not) for the anchor's own diff evidence, checked exactly
    against how `witness.mjs` finds an anchor (#137 round 5 R4-2; round 6
    R5-3/R5-4).

    The producer picks an anchor only while iterating the recorder's
    actual frames -- and only after keeping a pre-change baseline frame to
    compare against -- so a claimed anchor needs at least
    ``ANCHOR_MIN_FRAMES`` recorder frames, whatever the timestamps say. It
    accepts a frame only when the probe region's raw diff ratio is
    strictly above ANCHOR_DIFF_THRESHOLD and at least ANCHOR_MIN_PIXELS of
    its pixels changed; the recorded `anchor_diff_ratio` is that raw ratio
    rounded to six decimals, so both bounds tolerate half a rounding step
    (ANCHOR_RATIO_TOLERANCE) -- a floor-edge anchor is not refused.

    The probe itself is the producer's constant geometry: a square at the
    frame's top-left corner whose side is ``max(1, round(PROBE_CSS_PX *
    dpr))`` at the same dpr the record's document region records. A probe
    that is not that geometry is not evidence the producer produced, and
    the pixel floor is applied to the area that geometry gives --
    recomputed here, never taken from the record's own claim -- so an
    inflated "probe" cannot weaken the floor. When the record carries no
    usable dpr (an unscoped record, refused for that by the schema and the
    scope gate), the exact size cannot be cross-checked; the origin, the
    square shape and the floor on the recomputed area still are.
    """
    frames = nested.get("frames_total")
    if _count(frames) is None or frames < ANCHOR_MIN_FRAMES:
        return (
            False,
            "an anchor is a recorder frame after the pre-change baseline "
            "(witness.mjs keeps a baseline frame and searches only later "
            "frames), but the check records frames_total=%s: the "
            "producer's minimum is %d frames" % (_describe(frames), ANCHOR_MIN_FRAMES),
        )
    ratio = _as_float(nested.get("anchor_diff_ratio"))
    if ratio is None:
        return (
            False,
            "the anchor's own diff ratio is missing or outside the float "
            "domain (anchor_diff_ratio=%s)" % (_describe(nested.get("anchor_diff_ratio")),),
        )
    if ratio < ANCHOR_DIFF_THRESHOLD - ANCHOR_RATIO_TOLERANCE:
        return (
            False,
            "anchor_diff_ratio (%s) is below the producer's threshold %s, "
            "below which no frame is an anchor" % (_describe(ratio), ANCHOR_DIFF_THRESHOLD),
        )
    probe = nested.get("anchor_probe_region_px")
    if not isinstance(probe, dict):
        return (
            False,
            "the anchor's probe region is the producer's own square at the "
            "frame's corner (got %s)" % (_describe(probe),),
        )
    x = _count(probe.get("x"))
    y = _count(probe.get("y"))
    width = _count(probe.get("width"))
    height = _count(probe.get("height"))
    if x is None or y is None or width is None or height is None or width < 1 or height < 1:
        return (
            False,
            "the anchor's probe region is not the producer's (x=y=0, a "
            "positive square; got %s)" % (_describe(probe),),
        )
    if x != PROBE_ORIGIN_X or y != PROBE_ORIGIN_Y:
        return (
            False,
            "the producer's anchor probe sits at the frame's top-left corner "
            "(x=y=%d); this record claims x=%s, y=%s"
            % (PROBE_ORIGIN_X, _describe(x), _describe(y)),
        )
    if width != height:
        return (
            False,
            "the producer's anchor probe is square (max(1, round(%s*dpr)) px "
            "to a side); this record claims %sx%s px"
            % (PROBE_CSS_PX, _describe(width), _describe(height)),
        )
    expected_side = _probe_side_px(dpr)
    if expected_side is not None and width != expected_side:
        return (
            False,
            "the producer's probe is max(1, round(%s*dpr)) px to a side, and "
            "this record's own device_pixel_ratio is %s, so its probe is "
            "%sx%s px -- not the claimed %sx%s"
            % (
                PROBE_CSS_PX,
                _describe(dpr),
                _describe(expected_side),
                _describe(expected_side),
                _describe(width),
                _describe(height),
            ),
        )
    width_f = _as_float(width)
    height_f = _as_float(height)
    if width_f is None or height_f is None:
        return (
            False,
            "the anchor's probe region (%sx%s px) is outside the float "
            "domain the producer writes" % (_describe(width), _describe(height)),
        )
    area = width_f * height_f  # floats: the comparison cannot overflow
    if ratio * area < ANCHOR_MIN_PIXELS - ANCHOR_RATIO_TOLERANCE * area:
        return (
            False,
            "anchor_diff_ratio (%s) over the producer's %sx%s px probe region "
            "(area %s px, recomputed from the geometry) is under the "
            "producer's %d-changed-pixel floor"
            % (
                _describe(ratio),
                _describe(width),
                _describe(height),
                _describe(area),
                ANCHOR_MIN_PIXELS,
            ),
        )
    return True, None


def _recomputed_checks(nested, dpr=None):
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
    anchor_ok, _why_not = _anchor_pixel_evidence(nested, dpr)
    frames_total = nested.get("frames_total")
    has_frames = _count(frames_total) is not None and frames_total >= ANCHOR_MIN_FRAMES
    return {
        "timestamp_kind_known": nested.get("timestamp_kind") in KNOWN_TIMESTAMP_KINDS,
        "page_offset_within_bound": _finite_number(offset)
        and _finite_number(bound)
        and abs(float(offset)) <= float(bound) + 1e-9,
        "page_offset_spread_within_bound": _finite_number(spread)
        and float(spread) <= PAGE_OFFSET_SPREAD_BOUND_MS + 1e-9,
        # R4-2/R5-3: an anchor is a recorder frame after the pre-change
        # baseline; fewer than the producer's minimum frames can yield
        # none, whatever the timestamp claims.
        "anchor_found": _finite_number(frame) and has_frames,
        # R4-2: recomputed from the anchor's own diff evidence (the frames
        # to choose from, the producer's probe geometry, a ratio above its
        # threshold and its pixel floor), not from the flag it proves.
        "anchor_pixel_checked": anchor_ok,
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
        and _samples_range(samples) is not None
        and abs(float(spread) - _samples_range(samples)) <= TIME_TOLERANCE_MS,
    }


def _clock_evidence_violations(record, nested, bound):
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
            missing("the check claims acceptable without its recorded checks (checks=%s)" % (_describe(checks),))
        else:
            # #137 round 7, R6-1: the keys are described, never formatted
            # or joined raw -- the direct API accepts non-string keys, and
            # ", ".join() over one raises.
            false_checks = sorted(
                (k for k, v in checks.items() if v is False), key=_describe
            )
            if false_checks:
                contradicted(
                    "the check claims acceptable but its recorded checks fail: %s"
                    % (", ".join(_describe(k) for k in false_checks),)
                )
    anchor_flag = nested.get("anchor_pixel_checked")
    if anchor_flag is False:
        contradicted(
            "the check claims acceptable but the pixel anchor was not checked "
            "(anchor_pixel_checked=%s)" % (_describe(anchor_flag),)
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
                "the recorded page offset %s ms is above the bound of %s ms"
                % (_describe(float(offset)), _describe(effective_bound))
            )
        alias = record.get("clock_skew_ms")
        if alias is None or not _finite_number(alias) or abs(float(alias) - float(offset)) > 1e-9:
            contradicted(
                "the deprecated clock_skew_ms alias (%s) disagrees with the "
                "page offset it restates (%s)" % (_describe(alias), _describe(offset))
            )
        nested_alias = nested.get("skew_ms")
        if not _finite_number(nested_alias) or abs(float(nested_alias) - float(offset)) > 1e-9:
            contradicted(
                "the nested skew_ms alias (%s) disagrees with the page offset "
                "it restates (%s)" % (_describe(nested_alias), _describe(offset))
            )
    method = nested.get("method")
    alias_method = record.get("clock_skew_method")
    if method is not None and alias_method != method:
        contradicted(
            "the clock_skew_method alias (%s) disagrees with the check's method (%s)"
            % (_describe(alias_method), _describe(method))
        )
    if _finite_number(nested_bound):
        alias_bound = record.get("clock_skew_bound_ms")
        if not _finite_number(alias_bound) or abs(float(alias_bound) - float(nested_bound)) > 1e-9:
            contradicted(
                "the clock_skew_bound_ms alias (%s) disagrees with the check's "
                "bound (%s)" % (_describe(alias_bound), _describe(nested_bound))
            )
    alias_acceptable = record.get("clock_skew_acceptable")
    if alias_acceptable is not (nested.get("acceptable") is True):
        contradicted(
            "the clock_skew_acceptable alias (%s) disagrees with the check (%s)"
            % (_describe(alias_acceptable), _describe(nested.get("acceptable")))
        )
    nested_origin = nested.get("time_origin_ms")
    top_origin = record.get("time_origin_ms")
    if _finite_number(nested_origin) and _finite_number(top_origin) and abs(
        float(top_origin) - float(nested_origin)
    ) > 1e-9:
        contradicted(
            "the record's time_origin_ms (%s) disagrees with the check's (%s)"
            % (_describe(top_origin), _describe(nested_origin))
        )
    marker = record.get("marker_page_ms")
    if nested.get("reason") is not None and nested.get("acceptable") is True:
        contradicted(
            "an acceptable check records no refusal reason (reason=%s)"
            % (_describe(nested.get("reason")),)
        )

    # The recomputation proper (#137 round 4, N2: it is never gated on the
    # check's method). A record that erased its method keeps its recorded
    # claims and must still face them; `_recomputed_checks` recomputes each
    # verdict from whatever raw measurements remain, so an erased raw field
    # shows up as a claim its own evidence no longer supports.
    #
    # The anchor's probe size is checked at the dpr the record's own
    # document region carries (R5-4): the producer reads the same
    # window.devicePixelRatio for both.
    region = record.get("document_region")
    dpr = region.get("device_pixel_ratio") if isinstance(region, dict) else None
    if isinstance(checks, dict):
        raw = _recomputed_checks(nested, dpr)
        for key in CLOCK_CHECK_KEYS:
            if key in checks and key in raw and bool(checks[key]) is not bool(raw[key]):
                contradicted(
                    "the recorded check %s=%s disagrees with its own measurements "
                    "(recomputed %r)" % (key, _describe(checks[key]), raw[key])
                )
        for key, claim, label in (
            ("_median_is_offset", offset, "the samples' median"),
            ("_spread_is_range", nested.get("page_offset_spread_ms"), "the samples' spread"),
        ):
            if key in raw and not raw[key]:
                contradicted(
                    "%s (%s) is not what the samples give" % (label, _describe(claim))
                )
    # #137 round 5, R4-2: the anchor's own diff evidence, checked against
    # how the producer finds an anchor (its frames, its threshold, its
    # pixel floor). Named here as well as through the recomputed checks
    # above, so the refusal names it even when the recorded checks were
    # left out entirely.
    anchor_ok, why_not = _anchor_pixel_evidence(nested, dpr)
    if not anchor_ok:
        contradicted(why_not)
    # #137 round 6, R5-3: the anchor is one of this run's recorder frames,
    # found while the recorder was already running -- the check's
    # frames_total counts them at the check's instant and the record's at
    # the witness's end, over the same recorder whose frames only
    # accumulate. A check claiming more frames than the run recorded is
    # evidence no run produced (its anchor's index would sit past the
    # record's own frames).
    nested_frames = _count(nested.get("frames_total"))
    record_frames = _count(record.get("frames_total"))
    if nested_frames is not None and record_frames is not None and nested_frames > record_frames:
        contradicted(
            "the check's frames_total (%s) exceeds the record's own (%s): "
            "both count the same run's recorder, whose frames only accumulate"
            % (_describe(nested_frames), _describe(record_frames))
        )
    change = nested.get("change_page_ms")
    frame = nested.get("frame_page_ms")
    lag = nested.get("frame_lag_ms")
    if _finite_number(frame) and _finite_number(change) and _finite_number(lag):
        if abs(float(lag) - (float(frame) - float(change))) > TIME_TOLERANCE_MS:
            contradicted(
                "frame_lag_ms (%s) is not the anchor's own difference "
                "frame_page_ms - change_page_ms (%s)"
                % (_describe(lag), _describe(float(frame) - float(change)))
            )
        if float(frame) < float(change) - CAUSALITY_SLOP_MS - TIME_TOLERANCE_MS:
            contradicted(
                "the anchor frame (%s ms) precedes its own change (%s ms)"
                % (_describe(frame), _describe(change))
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
                "lag_bound_ms (%s) is not the rule's bound max(%d intervals, %s ms) "
                "= %s"
                # #137 round 8, R7-2: the value is described, never
                # formatted — the last raw diagnostic site (an int
                # subclass whose repr raises crashed here; 10**308
                # printed all 309 digits).
                % (_describe(lag_bound), LAG_BOUND_INTERVALS, LAG_BOUND_MIN_MS, _describe(expected))
            )
    conversion = nested.get("conversion")
    if isinstance(conversion, dict):
        lower = conversion.get("error_lower_ms")
        if _finite_number(lower) and abs(float(lower) + CAUSALITY_SLOP_MS) > 1e-9:
            contradicted(
                "the conversion's lower bound is -%s ms by causality (got %s)"
                % (CAUSALITY_SLOP_MS, _describe(lower))
            )
        upper = conversion.get("error_upper_ms")
        if _finite_number(upper) and _finite_number(lag_bound) and abs(
            float(upper) - float(lag_bound)
        ) > 1e-9:
            contradicted(
                "the conversion's upper bound is the lag bound (%s, got %s)"
                % (_describe(lag_bound), _describe(upper))
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
                "(total_pixels=%s)" % (_describe(total),)
            )
        )
        return out
    if _count(changed) is not None and _count(total) is not None:
        if changed > total:
            out.append(
                (
                    "pixel_evidence_contradicted",
                    "changed_pixels (%s) exceeds total_pixels (%s): a subset "
                    "cannot be larger than the whole"
                    % (_describe(changed), _describe(total)),
                )
            )
            return out
        if total > 0:
            changed_f = _as_float(changed)
            total_f = _as_float(total)
            if changed_f is None or total_f is None:
                out.append(
                    (
                        "pixel_evidence_contradicted",
                        "the pixel counts (changed_pixels=%s, total_pixels=%s) "
                        "are outside the float domain the producer writes, so "
                        "the ratios they claim cannot be recomputed"
                        % (_describe(changed), _describe(total)),
                    )
                )
                return out
            exact = changed_f / total_f
            if _finite_number(ratio) and abs(float(ratio) - exact) > RATIO_TOLERANCE:
                out.append(
                    (
                        "pixel_evidence_contradicted",
                        "diff_ratio (%s) is not changed_pixels / total_pixels (%s)"
                        % (_describe(ratio), _describe(exact)),
                    )
                )
            if _finite_number(max_ratio) and abs(float(max_ratio) - exact) > RATIO_TOLERANCE:
                out.append(
                    (
                        "pixel_evidence_contradicted",
                        "max_diff_ratio (%s) is not changed_pixels / total_pixels (%s)"
                        % (_describe(max_ratio), _describe(exact)),
                    )
                )
    return out


# A caret-move retry diffs only the caret box with the mask removed. The
# boxes the producer builds are about 16 CSS px wide and one caret tall.
# Anything larger is a document diff and still needs the mask.
_UNMASKED_CARET_MAX_CSS_WIDTH = 48
_UNMASKED_CARET_MAX_CSS_HEIGHT = 96


def _intentional_unmasked_caret(record):
    """True when the producer deliberately witnessed a caret move unmasked.

    The clock check stays masked. Only the frame record drops the mask, and
    only over a caret-sized rect. A whole-document unmasked diff is refused.
    """
    if not isinstance(record, dict):
        return False
    if record.get("caret_masked") is not False:
        return False
    if record.get("caret_mask_css") is not None:
        return False
    if record.get("caret_mask_error") is not None:
        return False
    if record.get("document_scoped") is not True:
        return False
    region = record.get("document_region")
    if not isinstance(region, dict) or region.get("source") != "rect":
        return False
    css = region.get("rect_css_px")
    if not isinstance(css, dict):
        return False
    width = css.get("width")
    height = css.get("height")
    if not _finite_number(width) or not _finite_number(height):
        return False
    if not 0 < float(width) <= _UNMASKED_CARET_MAX_CSS_WIDTH:
        return False
    if not 0 < float(height) <= _UNMASKED_CARET_MAX_CSS_HEIGHT:
        return False
    return True


def _mask_violations(record):
    """(reason, message) pairs for the caret-mask contradiction."""
    error = record.get("caret_mask_error")
    if record.get("caret_masked") is True and isinstance(error, str) and error:
        return [
            (
                "caret_mask_contradicted",
                "caret_masked=true but the mask recorded its own failure "
                "(caret_mask_error=%s)" % (_describe(error),)
            )
        ]
    return []


#: (reason, predicate on the record) in precedence order; the first failure
#: names the verdict's reason. `skew` is the caller's explicit offset, which
#: wins over the record's own (the same rule `_skew_of` applies) so a refusal
#: names the check that actually failed for the effective skew.
def _outcome_of(record):
    """The record's outcome string, or None (a non-mapping has none)."""
    if isinstance(record, dict):
        outcome = record.get("outcome")
        return outcome if isinstance(outcome, str) else None
    return None


def _scope_of(record):
    """The record's document_scoped flag, or None (a non-mapping has none)."""
    if isinstance(record, dict):
        scoped = record.get("document_scoped")
        return scoped if isinstance(scoped, bool) else None
    return None


def _reason_of(record, bound, errors, skew=None):
    del errors  # the tokens below are decided structurally, in order
    if not isinstance(record, dict):
        return "record_not_a_mapping"
    # #137 round 4: the discriminator is positive. A record without the
    # producer's markers is not a witness record at all; the strict schema
    # below is what every record that IS one must satisfy. The reason
    # tokens the lenient branch used to name (no_frame_time,
    # invalid_arm_time, min_pixels_invalid, document_scope_contradicted,
    # clock_check_missing) are unreachable for a record that passed the
    # schema: the schema names those malformations first.
    if not _is_production_record(record):
        return "not_a_witness_record"
    nested = record.get("clock_check") if isinstance(record.get("clock_check"), dict) else None
    skew = _skew_of(record, skew)
    if _finite_number(skew) and abs(float(skew)) > float(bound):
        return "clock_skew_above_bound"
    schema = _production_schema_violations(record)
    if schema:
        return schema[0][0]
    if nested is not None:
        if nested.get("acceptable") is not True:
            return "clock_check_not_acceptable"
        # #137 round 6, R5-1: the nested schema runs BEFORE the evidence
        # recomputation reads the check's values -- a malformed sample or
        # a wrong type is the schema's own named refusal, and no helper
        # ever floats a value the schema has not checked.
        schema = _clock_schema_violations(nested)
        if schema:
            return schema[0][0]
        evidence = _clock_evidence_violations(record, nested, bound)
        if evidence:
            return evidence[0][0]
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
    # #137: the witness frame must not precede its arm -- the producer keeps
    # a frame only at `pageMs >= afterPageMs`, so a frame below the recorded
    # arm is evidence no run produced. (A missing or non-finite arm or frame
    # is the schema's to refuse.)
    after_page_ms = record.get("after_page_ms")
    if _finite_number(after_page_ms) and _finite_number(frame_page_ms) and float(frame_page_ms) < float(after_page_ms):
        return "frame_before_arm"
    frames_after = record.get("frames_after")
    if _count(frames_after) is not None and frames_after < 1:
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
    if _finite_number(changed) and _finite_number(min_pixels):
        if float(changed) < float(min_pixels):
            return "no_pixel_evidence"
    # #137 round 3: the pixel evidence, recomputed from the raw counts.
    pixels = _pixel_evidence_violations(record)
    if pixels:
        return pixels[0][0]
    if record.get("caret_masked") is not True and not _intentional_unmasked_caret(record):
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
    errors = []
    # #137 round 4, N5: the caller's own arguments are checked before
    # anything else. A non-finite or non-positive bound makes every skew
    # comparison false (a dead gate), and a non-finite skew argument used
    # to be silently dropped in favour of the record's own offset; both are
    # refusals now, never silent fallbacks.
    if not _finite_number(bound_ms) or float(bound_ms) <= 0:
        bound_echo = _as_float(bound_ms)
        return {
            "ok": False,
            "refused": True,
            "reason": "nonfinite_time",
            "errors": [
                "bound_ms must be a finite positive number of milliseconds "
                "(got %s)" % (_describe(bound_ms),)
            ],
            "outcome": _outcome_of(record),
            "skew_ms": None,
            "bound_ms": bound_echo if bound_echo is not None else bound_ms,
            "skew_checked": False,
            "clock_check_ok": None,
            "document_scoped": None,
            "record": record,
        }
    bound = float(bound_ms)
    if skew is not None and (not _finite_number(skew) or _number_out_of_domain(skew)):
        # #137 round 8, R7-1: the boundary covers the numeric domain too.
        # A finite skew past 1e15 used to pass this check and then be
        # silently dropped by `_skew_of` in favour of the record's own
        # offset — the refusal disappeared. An explicit offset wins
        # absolutely: an unusable one is refused here, first.
        return {
            "ok": False,
            "refused": True,
            "reason": "nonfinite_time",
            "errors": [
                "a supplied skew must be a finite number of milliseconds "
                "inside the supported numeric domain |x| <= %g (got %s); "
                "it is never replaced by the record's own offset"
                % (NUMERIC_DOMAIN_LIMIT, _describe(skew))
            ],
            "outcome": _outcome_of(record),
            "skew_ms": None,
            "bound_ms": bound,
            "skew_checked": False,
            "clock_check_ok": None,
            "document_scoped": None,
            "record": record,
        }
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

    # #137 round 4, N1: the discriminator is positive. A record without the
    # producer's markers is not a witness record -- it stays parseable (a
    # verdict is returned, never a crash), but the verdict is a refusal
    # that can never be ok, no matter what else the record claims.
    if not _is_production_record(record):
        return {
            "ok": False,
            "refused": True,
            "reason": "not_a_witness_record",
            "errors": [
                "the record carries none of the producer's markers (kind "
                "%r, a clock_check_source, a production clock_check with "
                "its raw measurements): it is not a frame_witness record "
                "and can never be published" % (PRODUCTION_KIND,)
            ],
            "outcome": _outcome_of(record),
            "skew_ms": _skew_of(record),
            "bound_ms": bound,
            "skew_checked": _skew_of(record) is not None,
            "clock_check_ok": None,
            "document_scoped": _scope_of(record),
            "record": record,
        }

    for field in _REQUIRED_FIELDS:
        if field not in record:
            errors.append("missing field %r" % (field,))

    outcome = record.get("outcome")
    if outcome is None:
        errors.append("the record carries no outcome")
    elif outcome not in OUTCOMES:
        errors.append("unknown outcome %s" % (_describe(outcome),))
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
            "the witness frame (%s ms) precedes its arm after_page_ms=%s: a "
            "frame before the change cannot show it"
            % (_describe(frame_page_ms), _describe(after_page_ms))
        )

    for field in ("frames_total", "frames_after"):
        value = record.get(field)
        if value is None or isinstance(value, bool) or not isinstance(value, int):
            # #137 round 3 (finding 4): a null count is refused, not skipped.
            errors.append("%s must be an integer (got %s)" % (field, _describe(value)))
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
            % (_describe(record["frames_after"]), _describe(record["frames_total"]))
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
                "(diff_ratio %s <= threshold %s)"
                % (_describe(diff_ratio), _describe(threshold))
            )
        changed = record.get("changed_pixels")
        min_pixels = record.get("min_pixels", DEFAULT_MIN_PIXELS)
        if not _finite_number(min_pixels) or float(min_pixels) < 1:
            errors.append(
                "min_pixels must be a number of at least 1 (got %s)"
                % (_describe(record.get("min_pixels")),)
            )
        elif not _finite_number(changed):
            errors.append("a witnessed frame needs changed_pixels")
        elif float(changed) < float(min_pixels):
            errors.append(
                "a witnessed frame must differ in at least %s pixels "
                "(changed_pixels %s)" % (_describe(min_pixels), _describe(changed))
            )

    caret_masked = record.get("caret_masked")
    if caret_masked is not None and not isinstance(caret_masked, bool):
        errors.append("caret_masked must be a boolean")
    if caret_masked is not True and not _intentional_unmasked_caret(record):
        if record.get("caret_mask_error"):
            errors.append(
                "the caret mask failed (%s), so the witness is not proven"
                % (_describe(record.get("caret_mask_error")),)
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
    # (#137 round 4: a scoped record carrying a document_region_error is
    # the closed schema's to refuse -- "a scoped record carries no
    # document_region_error" -- so no duplicate token is needed here.)

    # The clock check of the run (#130 defect 3): publication needs an
    # acceptable one. The nested record is the real evidence; a record
    # without a check object is the strict schema's to refuse (the
    # lenient top-level-alias branch is gone, #137 round 4).
    nested = record.get("clock_check")
    clock_check_ok = None
    if isinstance(nested, dict):
        if nested.get("acceptable") is not True:
            clock_check_ok = False
            nested_reason = nested.get("reason")
            if isinstance(nested_reason, str) and nested_reason:
                errors.append(
                    "the run's clock check is not acceptable: %s"
                    % (_describe(nested_reason),)
                )
            else:
                errors.append("the run's clock check is not acceptable")
        else:
            clock_check_ok = True
    else:
        clock_check_ok = False

    # #137 rounds 3-6: the strict closed schema, the recomputed evidence,
    # the pixel consistency and the mask contradiction -- every token carries
    # its message into the verdict, and the first names the reason. The
    # nested schema precedes its evidence (#137 round 6, R5-1), so the
    # recomputation never reads a value the schema has not checked (its
    # helpers are total over JSON values regardless -- belt and braces).
    for _reason, message in _production_schema_violations(record):
        errors.append(message)
    if isinstance(nested, dict) and nested.get("acceptable") is True:
        for _reason, message in _clock_schema_violations(nested):
            errors.append(message)
        for _reason, message in _clock_evidence_violations(record, nested, bound):
            errors.append(message)
    for _reason, message in _pixel_evidence_violations(record):
        errors.append(message)
    for _reason, message in _mask_violations(record):
        errors.append(message)

    skew_ms = _skew_of(record, skew)
    skew_checked = skew_ms is not None
    if skew_checked and abs(skew_ms) > bound:
        errors.append(
            "clock skew %s ms is above the bound of %s ms"
            % (_describe(skew_ms), _describe(bound))
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


def _describe_error(error):
    """A bounded description of an exception for the CLI's own refusals
    (#137 round 8, R7-2): its type name plus a truncated ``str()`` —
    never a raising or unbounded ``__str__`` (the direct API's totality
    discipline extends to the CLI's diagnostics, which the last-resort
    printers must not turn into a second crash)."""
    name = type(error).__name__
    try:
        detail = str(error)
    except Exception:  # noqa: BLE001 -- describing it is the bug's report
        detail = "<undescribable>"
    return "%s: %s" % (name, detail[:DESCRIBE_MAX_CHARS])


def _print_validation_aborted(error):
    """The CLI's last resort (#137 round 5, R4-1): validation itself raised,
    which no input may make happen -- the numeric paths are overflow-guarded
    -- so this is a bug to report. The CLI's contract still holds: one JSON
    refusal on stdout, exit 1, never a traceback."""
    import sys

    sys.stdout.write(
        json.dumps(
            {
                "ok": False,
                "refused": True,
                "reason": "validation_aborted",
                "errors": [
                    "validation raised %s (a validator bug: report it; "
                    "the record is refused)" % (_describe_error(error),)
                ],
            }
        )
        + "\n"
    )


def _print_record_unreadable(path, error):
    """The CLI's read refusal (#137 round 6, R5-2): the file is not a
    record at all -- unreadable, not valid JSON, a bare ``NaN``. The exit
    stays 2 (not a verdict on a record), but stdout keeps the contract
    every consumer was promised: one JSON refusal, named, never silence."""
    import sys

    sys.stdout.write(
        json.dumps(
            {
                "ok": False,
                "refused": True,
                "reason": "record_unreadable",
                "errors": [
                    "cannot read the witness record %s: %s"
                    % (_describe(path), _describe_error(error))
                ],
            }
        )
        + "\n"
    )


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
        _print_record_unreadable(args.file, error)
        sys.stderr.write(
            "witness: cannot read %s: %s\n"
            % (_describe(args.file), _describe_error(error))
        )
        return 2

    if isinstance(record, list):
        try:
            verdicts = [
                validate_witness(item, bound_ms=args.bound_ms) for item in record
            ]
        except Exception as error:  # noqa: BLE001 -- the last resort below
            _print_validation_aborted(error)
            return 1
        refused = any(v["refused"] for v in verdicts)
        sys.stdout.write(
            json.dumps({"records": len(verdicts), "refused": refused, "verdicts": verdicts})
            + "\n"
        )
        return 1 if refused else 0

    try:
        verdict = validate_witness(record, bound_ms=args.bound_ms)
    except Exception as error:  # noqa: BLE001 -- the last resort below
        _print_validation_aborted(error)
        return 1
    sys.stdout.write(json.dumps(verdict) + "\n")
    return 1 if verdict["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
