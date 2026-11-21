"""Why a lane has no output file.

A lane that writes nothing has not all done the same thing. Plate refuses the
broken corpus: its importer returns an error and exits. OnlyOffice's converter
never returns from the corpus: the harness's watchdog stops it. A report that
calls both "refused" is wrong about the second (a refusal is a decision the
editor made; a call that does not return is not).

A harness that can tell what happened writes ``no_output.json`` next to where
the output would have been, and removes it when it does write an output:

    {"outcome": "did-not-return", "step": "doc.docx -> bin", "limit_s": 120, ...}

``outcome`` is one of OUTCOMES. A lane with no output and no record is
"not-recorded": the tables then say only "no output", and claim no reason.
"""
from __future__ import annotations

import json
from pathlib import Path

RECORD = "no_output.json"
# outcome -> the words a table cell uses for it
OUTCOMES = {
    "refused": "the importer refused the corpus",
    "did-not-return": "the converter did not return",
    "error": "the editor failed with an error",
}
NOT_RECORDED = "not-recorded"


def read(directory: Path) -> dict | None:
    """The record in an output directory, or None when the lane left none.
    A record beside an output file is stale (the lane has since written one) and is ignored."""
    directory = Path(directory)
    path = directory / RECORD
    if not path.exists() or (directory / "complex.docx").exists():
        return None
    data = json.loads(path.read_text())
    if data.get("outcome") not in OUTCOMES:
        raise ValueError(f"{path}: outcome {data.get('outcome')!r} is not one of {sorted(OUTCOMES)}")
    return data


def outcome(directory: Path) -> str:
    """'refused' | 'did-not-return' | 'error' | 'not-recorded' for a lane that wrote no output."""
    data = read(directory)
    return data["outcome"] if data else NOT_RECORDED


def words(kind: str) -> str:
    """The sentence fragment for an outcome; a lane with no record gets no reason."""
    return OUTCOMES.get(kind, "no reason recorded")
