"""OpenDoc's measured page switches off automatic lists (owner's decision, 2026-11-22).

A typed "1. " at a paragraph start became list numbering; the engine read gives
a list flag, not the painted number, so the typing text check refused the
session (character 2,915 of the typing text).
"""
from pathlib import Path

HOST = Path(__file__).resolve().parents[2] / "harness/ui/opendoc/host.js"


def test_the_page_sets_the_lists_switch_off_before_the_editor_reads_it():
    src = HOST.read_text()
    assert "localStorage.setItem('opendoc.autoFormatLists', 'off')" in src
    assert "localStorage.setItem('opendoc.autoCapitalise', 'off')" in src
    # Replace-as-you-type (lone "i" -> "I", owner's decision 2026-11-22); dashes inherit it.
    assert "localStorage.setItem('opendoc.autocorrect', 'off')" in src
    assert "localStorage.setItem('opendoc.autoFormatDashes'" not in src


def test_the_page_publishes_both_switches():
    assert "autocorrect: { capitalise: 'off', lists: 'off', replace: 'off', dashes: 'off (inherits replace)' }" in HOST.read_text()
