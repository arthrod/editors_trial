"""The typing lane's keystroke witness watches every page of the paged canvas editors.

Spaces, 2026-11-22: BetterOffice's latency session typed onto page 2, page 1
(its witness region) scrolled out of view, and 770 of 811 keystrokes were
refused as not_document_scoped. OpenDoc named page 1 the same way.
"""
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS


def test_the_keystroke_witness_watches_the_pages_container():
    assert BROWSER_TARGETS["betteroffice"]["typing_present_selector"] == "[data-docx-pages-host]"
    assert BROWSER_TARGETS["opendoc"]["typing_present_selector"] == "#pages"


def test_the_load_witness_keeps_page_one_as_before():
    for editor in ("betteroffice", "opendoc"):
        target = BROWSER_TARGETS[editor]
        assert target["typing_load_present_selector"] == target["edit_selector"], editor


def test_both_editors_pin_their_load_region():
    # Only these two gained the pair; react-docx already watched its root.
    have = {e for e, t in BROWSER_TARGETS.items() if "typing_load_present_selector" in t}
    assert {"betteroffice", "opendoc"} <= have
