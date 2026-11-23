"""E2: the input lane's detached-target rule is react-docx's alone.

A1  On a page without react-docx's global, a click whose target the editor
    replaced during pointerdown is judged as before this branch: not inside,
    and no event path is recorded.
A2  On react-docx's page, the same click is judged by its ancestors at the
    event: inside, flagged ``target_detached``.
A3  On react-docx's page, when the selector matches the replaced element
    itself, the click on it is judged at the event (inside) and a click beside
    it is outside.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "perf" / "tests" / "e2_detached_click.mjs"


@pytest.fixture(scope="module")
def cases():
    """Run the browser repro once; its rows keyed by the page kind."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    if not (REPO / "harness" / "ui" / "node_modules" / "playwright").exists():
        pytest.skip("harness/ui has no playwright package")
    proc = subprocess.run([node, str(SCRIPT)], capture_output=True, text=True, timeout=120, cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr[-2000:]
    rows = {}
    for line in proc.stdout.splitlines():
        row = json.loads(line)
        rows[row["reactDocx"]] = row
    return rows


def test_other_pages_keep_the_old_verdict(cases):
    """A1: without react-docx's global, a replaced target is outside and no path is kept."""
    row = cases[False]
    assert row["verdict"]["inside"] is False, row
    assert "target_detached" not in row["verdict"], row
    assert not row["recordedPath"], row


def test_react_docx_page_judges_by_the_event_path(cases):
    """A2: on react-docx's page the click is judged by its ancestors at the event."""
    row = cases[True]
    assert row["verdict"]["inside"] is True, row
    assert row["verdict"].get("target_detached"), row


def test_a_replaced_matched_element_is_judged_at_the_event(cases):
    """A3: a matched replaced element is inside at the event; a click beside it is outside."""
    # CodeAnt on #283, 2026-11-23: the selector matches the element
    # react-docx replaces; the click on it is inside, flagged as judged at
    # the event, and a click beside it stays outside.
    on_line = cases["replaced_on_line"]["verdict"]
    assert on_line["inside"] is True, on_line
    assert on_line["inside_at_event"] is True, on_line
    below = cases["replaced_below_line"]["verdict"]
    assert below["inside"] is False, below
