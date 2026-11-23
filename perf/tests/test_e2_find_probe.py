"""E2 C15: the find probe tells the full query's reply from a prefix's.

CodeRabbit on #283 (2026-11-23), on perf/runner/find_probe.mjs (moved out of
document_probe.mjs so a page can be probed in a test):

F1  OnlyOffice: a tick that ran with the full query and changed the count is
    that query's reply, even when its text equals an earlier prefix reply's
    (prefix ticks 3, 2, then the full query's 3). Before: never accepted.
F2  BetterOffice: when a prefix reply and the full query's reply are both
    pending at one count change, the cell is refused as ambiguous. Before: the
    later timer's record replaced the earlier one, and the prefix's count was
    taken as the full query's reply.
F3  Control: replies that commit one at a time are measured as before.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def out():
    if shutil.which("node") is None:
        pytest.skip("node is not on PATH")
    if not (REPO / "harness" / "ui" / "node_modules" / "playwright").exists():
        pytest.skip("harness/ui has no playwright package")
    proc = subprocess.run(["node", str(REPO / "perf/tests/e2_find_probe_repro.mjs")], cwd=str(REPO),
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout)


def test_a_full_query_tick_back_to_a_prefix_count_is_its_reply(out):
    assert out["interval_back_to_a_prefix_count"] == {"complete": True, "accepted": "3 results", "ambiguous": False}


def test_overlapping_prefix_and_full_replies_are_refused_not_guessed(out):
    assert out["late_overlap"] == {"complete": False, "accepted": "", "ambiguous": True}


def test_replies_one_at_a_time_are_measured_as_before(out):
    assert out["late_apart"] == {"complete": True, "accepted": "3 results", "ambiguous": False}


def test_document_probe_uses_the_module():
    src = (REPO / "perf/runner/document_probe.mjs").read_text()
    assert "import { INSTALL_FIND_PROBE } from './find_probe.mjs';" in src
    assert "INSTALL_FIND_PROBE,\n" in src
    assert "if (observed.ambiguous_reply) completion = 'ambiguous_reply';" in src
