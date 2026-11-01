#!/usr/bin/env python3
"""Name the kind of protection a bomb cell showed.

The safety word bounded-reject is not a resource bound. It only means the
process exited non-zero and did not crash, hang, or leak. The level here is
a separate reading of that exit, of the fidelity field, and of the tool's
own words.

Levels
------
bounded-refusal
    A named ceiling rejected the package. No finished document carries the
    weapon. The process exited with an error.
sanitation
    The process exited 0, wrote a document, and the weapon is not in it.
erroring
    The process exited with an error for a parse or a name/policy reason.
    The log does not name a resource ceiling.
stack-exhaustion
    Recursion ran out of call stack. That is not a declared ceiling.
preserved
    The weapon is still in the output and the process survived.
errored-but-preserved
    The process errored and the weapon is still in the output.
hang, crash, leak
    The process did not finish, died, or returned file contents or a slip.
failed-load-exit-zero
    No document was written and the process still exited 0.
not-in-view
    A text view was written and this weapon is not something that view
    carries. Absence is not sanitation.
unexpanded-kept
    The process exited 0 and wrote the raw entity references. It did not
    expand them. Keeping the references is not sanitation.
bounded-delivery
    A declared cap was applied and a reduced form was written. The hostile
    value itself is absent. This is not a refusal and it is not sanitation.
not-run
    No measurement.
"""
from __future__ import annotations

LEVELS = (
    "bounded-refusal",
    "sanitation",
    "erroring",
    "stack-exhaustion",
    "preserved",
    "errored-but-preserved",
    "hang",
    "crash",
    "leak",
    "failed-load-exit-zero",
    "not-in-view",
    "unexpanded-kept",
    "bounded-delivery",
    "not-run",
)

# A phrase here is a ceiling the tool named. Stack overflow is not in this list.
_BOUNDED = (
    "limit-exceeded",
    "maxentrybytes",
    "maxentries",
    "maxxmldepth",
    "too-large",
    "too-many-entries",
    "too-deep",
    "resourcelimitexceeded",
    "zip.maxratio",
    "zip.maxentries",
    "xml.maxdepth",
    "maximum compression ratio",
    "too many entries",
    "nested deeper than",
    "maximum nested tags",
    "limit exceeded",
    "too many attributes",
    "parts exceeds the",
    "input_limit",
    "xml nesting too deep",
    "max_part",
    "max_entries",
    "max_xml_depth",
)

_STACK = ("maximum call stack", "call stack size exceeded")


def _has(evidence: str, needles: tuple[str, ...]) -> bool:
    text = evidence.lower()
    return any(needle in text for needle in needles)


def _names_ceiling(evidence: str) -> bool:
    if _has(evidence, _BOUNDED):
        return True
    # Jubarte names this as INVALID_XML, and the sentence is still a cap:
    # "element exceeds 1024 attributes".
    low = evidence.lower()
    return "element" in low and "exceeds" in low and "attributes" in low


def _unexpanded_entities(evidence: str) -> bool:
    low = evidence.lower()
    if "bomb_lol" in low:
        return False
    return "&lol" in low or "&xxe;" in low or "&canary;" in low


def classify(fidelity: str, safety: str, evidence: str = "") -> str:
    """Return one protection level. ``evidence`` is the tool's own text."""
    if fidelity == "not-run" or safety == "not-run":
        return "not-run"
    if safety == "hang":
        return "hang"
    if safety == "crash":
        return "crash"
    if safety == "leak":
        return "leak"
    if _has(evidence, _STACK) and safety == "bounded-reject":
        return "stack-exhaustion"
    if fidelity == "preserved" and safety == "ok" and _unexpanded_entities(evidence):
        return "unexpanded-kept"
    if fidelity == "preserved" and safety == "ok":
        return "preserved"
    if fidelity == "preserved" and safety == "bounded-reject":
        return "errored-but-preserved"
    if fidelity == "dropped" and safety == "ok":
        return "sanitation"
    if fidelity == "not-in-view" and safety == "ok":
        return "not-in-view"
    if fidelity == "refused" and safety == "ok":
        return "failed-load-exit-zero"
    if safety == "bounded-reject" and _names_ceiling(evidence):
        return "bounded-refusal"
    if safety == "bounded-reject":
        return "erroring"
    if fidelity == "dropped":
        return "sanitation"
    if fidelity == "not-in-view":
        return "not-in-view"
    if fidelity == "refused":
        return "erroring"
    return "preserved"
