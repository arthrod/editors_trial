"""Lanes that run and are scored, but are not in the published reports yet.

A pending lane is in every runner (build/run_all.sh, run_second_pass.sh,
run_broken.sh) and has a harness and a pin, so it can be measured. It is kept
out of a release's summary, facts and counts until it is published: the scorers
and build/facts.py read it only when asked (--pending), which is a development
run. reports/vendors.md says of each one that it is not in the reports yet, and
build/test_report_claims.py holds the two lists to each other.

Every script that lists the participants passes its list through ``join`` (or reads
``requested``), and build/test_every_lane.py fails on one that does not, so a pending
lane is known everywhere or nowhere.

To publish a lane: move its tuple from PENDING into build/score_all.py's
TARGETS (and its slug out of PENDING_SLUGS' sources here), add it to SLUGS and
VENDOR_HEADINGS in build/test_report_claims.py and to the heading and anchor
maps the same test names, and replace the "not in the reports yet" sentence in
its vendors section with what was measured.
"""
import os
import sys
from pathlib import Path

# display name (the heading of its section in reports/vendors.md), output dir under out/
PENDING = [
    ("react-docx", "reactdocx"),
    ("OpenDoc", "opendoc"),
    ("BetterOffice", "betteroffice"),
    ("OnlyOffice (CryptPad build)", "onlyoffice"),
]
# A second lane through a pending tool (as eigenpal-editor is to eigenpal).
PENDING_LANES = ["betteroffice-editor"]
# On the vendors page as pending, with no round-trip lane at all: Univer has no
# .docx path in its open-source packages (harness/univer/probe.mjs), and Nutrient
# is measured in the UI lane only.
NO_LANE = ["Univer", "Nutrient"]

PENDING_SLUGS = [d for _, d in PENDING]


# The key a pending lane has where lanes are keyed by a short lower-case name:
# the page-image folders, the namespace map, the render inventory.
KEYS = {"reactdocx": "react-docx", "opendoc": "opendoc", "betteroffice": "betteroffice", "onlyoffice": "onlyoffice"}

ROOT = Path(os.environ.get("TRIAL_ROOT") or Path(__file__).resolve().parent.parent)


def requested(argv=None) -> bool:
    """Whether this run asked for the pending lanes too: TRIAL_PENDING=1 in the
    environment (any script), or --pending (the scripts that parse it: score_all.py,
    score_extra.py, facts.py, preserved_matrix.py)."""
    if argv is not None:
        return "--pending" in argv
    return "--pending" in sys.argv[1:] or os.environ.get("TRIAL_PENDING") == "1"


def has_output(slug: str) -> bool:
    """False for a lane that recorded why it wrote nothing (build/no_output.py):
    there is no package to audit, render or offer to Word."""
    d = ROOT / "out" / slug
    return (d / "complex.docx").exists() or not (d / "no_output.json").exists()


def _baseline(item) -> bool:
    text = " ".join(str(x) for x in item) if isinstance(item, (tuple, list)) else str(item)
    return any(w in text for w in ("libreoffice", "lo_baseline", "LibreOffice"))


def join(items, make=None, argv=None, on=None):
    """``items`` with one entry per pending lane, placed before a closing baseline
    entry; ``items`` unchanged unless the run asked for pending lanes. ``make(name,
    slug, key)`` builds the entry (default: the key). A lane with no output is left out."""
    if not (requested(argv) if on is None else on):
        return items
    new = [make(name, slug, KEYS[slug]) if make else KEYS[slug] for name, slug in PENDING if has_output(slug)]
    seq = list(items)
    tail = [seq.pop()] if seq and _baseline(seq[-1]) else []
    return type(items)(seq + new + tail)


def names(argv=None) -> dict:
    """{key: display name} of the pending lanes, empty unless the run asked for them."""
    return {KEYS[slug]: name for name, slug in PENDING} if requested(argv) else {}
