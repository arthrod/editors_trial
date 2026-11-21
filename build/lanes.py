"""Lanes that run and are scored, but are not in the published reports yet.

A pending lane is in every runner (build/run_all.sh, run_second_pass.sh,
run_broken.sh) and has a harness and a pin, so it can be measured. It is kept
out of a release's summary, facts and counts until it is published: the scorers
and build/facts.py read it only when asked (--pending), which is a development
run. reports/vendors.md says of each one that it is not in the reports yet, and
build/test_report_claims.py holds the two lists to each other.

To publish a lane: move its tuple from PENDING into build/score_all.py's
TARGETS (and its slug out of PENDING_SLUGS' sources here), add it to SLUGS and
VENDOR_HEADINGS in build/test_report_claims.py and to the heading and anchor
maps the same test names, and replace the "not in the reports yet" sentence in
its vendors section with what was measured.
"""
import sys

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


def requested(argv=None) -> bool:
    """Whether this run asked for the pending lanes too."""
    return "--pending" in (sys.argv[1:] if argv is None else argv)
