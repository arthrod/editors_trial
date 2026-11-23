"""E2 OpenDoc: a reader of OpenDoc's engine returns the whole document or nothing.

CodeRabbit and CodeAnt on #283 (2026-11-23): the readers of ``opendoc.ai.read``
returned a shorter text as if it were the document when a page was truncated
with no cursor, when a table's page was refused, or (the C07/C08 snapshot) when
the read rejected; and the C07/C08 snapshot left table cells out. CodeRabbit on
#283 (4669191003): the typing check's read (READ_MODEL_DOCUMENT_TEXT) kept the
partial text in the same cases. The pinned engine always gives a cursor with a
truncated page, and no table in the campaign's documents needed a second page,
so no recorded figure came from these paths; the readers now refuse them anyway.

The mock engine answers only the request it expects (no cursor first, then the
cursor the previous page gave; CodeRabbit on #287, 4669322255), so a reader
that repeats or drops a cursor gets no document.

R1  A paragraph, a two-page table and a paragraph read whole by every reader
    (the census and the typing read list paragraphs only).
R2  A truncated page with no cursor: no text from any reader.
R3  Every page truncated (the page cap reached): no text from any reader.
R4  A refused table page: no text from the snapshot or the oracle.
R5  A rejected read: the snapshot and the census say unavailable, they do not throw.
R6  The mock refuses a repeated or invented cursor.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")


@pytest.fixture(scope="module")
def out():
    """Run the node repro once and return its JSON: one row per case, plus the mock's self-check."""
    proc = subprocess.run(["node", str(REPO / "perf" / "tests" / "e2_opendoc_readers_repro.mjs")],
                          cwd=str(REPO), capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_a_whole_document_is_read_with_its_table_cells(out):
    """R1: every reader returns the whole text, the snapshot and oracle with the table's cells."""
    row = out["whole"]
    assert row["state"] == {"text": "Alpha\nA1\nB1\nA2\nB2\nOmega", "error": None}
    assert row["oracle"]["text"] == "Alpha\nA1\nB1\nA2\nB2\nOmega"
    assert row["oracle"]["oracle"] == "perf_model"
    assert row["census"] == ["Alpha", "Omega"]
    assert row["typing"]["text"] == "Alpha\nOmega"


def test_the_typing_read_returns_every_page(out):
    """R1: the typing check's read follows the cursor to the last page."""
    assert out["two_pages"]["typing"] == {"text": "Alpha\nOmega", "absorbed_items": []}


def test_a_truncated_page_without_a_cursor_gives_no_text(out):
    """R2: a truncated page with no cursor is no document for any reader."""
    row = out["no_cursor"]
    assert row["state"]["error"] == "editor_model_unavailable"
    assert row["state"]["text"] == ""
    assert row["oracle"]["oracle"] == "absent"
    assert row["oracle"]["text"] == ""
    assert row["census"] is None
    assert row["typing"] is None


def test_the_page_cap_gives_no_text(out):
    """R3: a document still truncated at the page cap is no document for any reader."""
    row = out["endless"]
    assert row["state"]["error"] == "editor_model_unavailable"
    assert row["state"]["text"] == ""
    assert row["oracle"]["oracle"] == "absent"
    assert row["oracle"]["text"] == ""
    assert row["census"] is None
    assert row["typing"] is None


def test_a_refused_table_page_gives_no_text(out):
    """R4: a refused table page leaves the snapshot and the oracle with no text."""
    row = out["table_refused"]
    assert row["state"]["error"] == "editor_model_unavailable"
    assert row["state"]["text"] == ""
    assert row["oracle"]["oracle"] == "absent"
    assert row["oracle"]["text"] == ""
    assert "busy" in row["oracle"]["error"]


def test_a_rejected_read_is_unavailable_not_thrown(out):
    """R5: a rejected read is an unavailable model with no text, not an exception."""
    row = out["rejected"]
    assert row["state"]["error"] == "editor_model_unavailable"
    assert row["state"]["text"] == ""
    assert row["oracle"]["oracle"] == "absent"
    assert row["oracle"]["text"] == ""
    assert row["census"] is None
    assert row["typing"] is None


def test_the_mock_refuses_a_cursor_it_did_not_give(out):
    """R6: the mock engine answers only the cursor it gave, for blocks and for table rows."""
    assert out["mock"] == {
        "first_ok": True, "repeated_ok": False, "invented_ok": False, "followed_ok": True,
        "table_first_ok": True, "table_repeated_ok": False,
    }
