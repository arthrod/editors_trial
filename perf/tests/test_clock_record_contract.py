"""The clock check's record is a closed set of keys on both sides.

`witness.mjs` `clockSkew()` writes it, `witness.py` refuses a record with a key it does not know
(`witness_schema_invalid`). On 16 Nov a key added on the JavaScript side alone refused every sample of a
publication round (#245). This test reads the keys out of the JavaScript source.

Run: python -m pytest perf/tests/test_clock_record_contract.py
"""
import re
from pathlib import Path

from perf.runner import witness

SOURCE = Path(__file__).resolve().parents[1] / "runner" / "witness.mjs"


def clock_record_keys(text: str) -> set[str]:
    """Top-level keys of the object `clockSkew()` returns: the `return {` block that holds `anchor_probe_region_px`."""
    anchor = text.index("anchor_probe_region_px: anchor.probe_region_px")
    start = text.rindex("\n  return {", 0, anchor)
    end = text.index("\n  };", anchor)
    keys = set(re.findall(r"^    ([A-Za-z_][A-Za-z0-9_]*)\s*[:,]", text[start:end], flags=re.M))
    assert "anchor_probe_region_px" in keys and "acceptable" in keys, "the record was not found as expected"
    return keys


def test_every_key_the_clock_check_writes_is_one_the_schema_knows():
    written, known = clock_record_keys(SOURCE.read_text()), set(witness._CLOCK_CHECK_FIELDS)
    assert not written - known, f"clockSkew() writes {sorted(written - known)}, which witness.py refuses as unknown"
    # ... and the other way (CodeAnt, #251): the schema requires each of its fields.
    assert not known - written, f"clockSkew() no longer writes {sorted(known - written)}, which witness.py requires"


def test_a_key_added_on_one_side_is_caught():
    text = SOURCE.read_text().replace(
        "    anchor_probe_region_px: anchor.probe_region_px,\n",
        "    anchor_probe_region_px: anchor.probe_region_px,\n    probe_cleared: anchor.probe_cleared || null,\n")
    assert "probe_cleared" in clock_record_keys(text) - set(witness._CLOCK_CHECK_FIELDS)
