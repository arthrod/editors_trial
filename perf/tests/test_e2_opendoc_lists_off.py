"""OpenDoc's measured page switches off automatic lists (owner's decision, 2026-11-22).

A typed "1. " at a paragraph start became list numbering; the engine read gives
a list flag, not the painted number, so the typing text check refused the
session (character 2,915 of the typing text).
"""
from pathlib import Path

HOST = Path(__file__).resolve().parents[2] / "harness/ui/opendoc/host.js"


def test_the_page_sets_the_lists_switch_off_before_the_editor_reads_it():
    src = HOST.read_text()
    assert "capitalise: 'opendoc.autoCapitalise'" in src
    assert "lists: 'opendoc.autoFormatLists'" in src
    # Replace-as-you-type (lone "i" -> "I", owner's decision 2026-11-22); dashes inherit it.
    assert "replace: 'opendoc.autocorrect'" in src
    assert "window.localStorage.setItem(PREFS[key], 'off')" in src
    assert ": 'opendoc.autoFormatDashes'" not in src  # never written: it inherits replace


def test_the_page_publishes_both_switches():
    assert "{ capitalise: 'off', lists: 'off', replace: 'off', dashes: 'off (inherits replace)' }" in HOST.read_text()


def _prefs() -> dict:
    import json
    import subprocess
    proc = subprocess.run(["node", str(HOST.parents[3] / "perf/tests/e2_opendoc_prefs_repro.mjs")],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_a_preference_the_page_could_not_set_is_an_error_not_a_claim():
    """CodeAnt on #283 (2026-11-23): one try around the three writes swallowed a
    failed write, and the page still published every switch "off". A switch
    that does not read back "off" now stops the page (host.error; it never
    becomes ready) and the published switches are the ones read back."""
    import shutil

    import pytest
    if shutil.which("node") is None:
        pytest.skip("node is not on PATH")
    out = _prefs()
    assert out["works"]["error"] is None
    assert out["works"]["autocorrect"] == {"capitalise": "off", "lists": "off", "replace": "off", "dashes": "off (inherits replace)"}
    for case in ("refuses_second", "forgets"):
        row = out[case]
        assert row["error"] and "autocorrect" in row["error"], (case, row)
        assert row["ready"] is not True, (case, row)
        assert row["autocorrect"] != out["works"]["autocorrect"], (case, row)
