"""E2: BetterOffice's find dialog renders its reply after the reply's timer.

The C15 probe credits a find reply only when the count text changes inside a
timer the find input scheduled. @betteroffice/docx-react 0.5.1's dialog runs
the search in such a timer (a 220 ms debounce) but sets React state there,
and the status line ("1 of 5 matches") is rendered in a later task, so the
probe saw no reply (completion no_event). For ``--editor betteroffice`` only,
the next change of the count text after such a timer is that timer's reply.

A1  the fake host (same timing as the dialog) measures with --editor betteroffice;
A2  the same host stays unverified for any other editor: the rule is gated.
"""

from __future__ import annotations

import unittest

from perf.tests import test_b3_document as b3

EXTRA = [
    "--find-input-selector", "input.find",
    "--find-query", "NEEDLE",
    "--find-count-selector", ".find-count",
    "--find-expected-matches", "2",
    "--timeout-ms", "4000",
]


class BetterOfficeLateFindReply(b3.FakeHostMeasurers):
    def test_a_reply_rendered_after_its_timer_measures_for_betteroffice(self):
        payload = self.probe("find", "e2_betteroffice_find.html", EXTRA + ["--editor", "betteroffice"])
        self.assertEqual(payload.get("status"), "measured", payload)
        self.assertEqual(payload.get("completion"), "event", payload)
        self.assertGreaterEqual(payload.get("search_complete_ms") or 0, 200, payload)
        self.assertEqual(payload.get("observed_count_text"), "1 of 2 matches", payload)

    def test_the_rule_is_gated_to_betteroffice(self):
        payload = self.probe("find", "e2_betteroffice_find.html", EXTRA + ["--editor", "plate"])
        self.assertEqual(payload.get("status"), "unverified", payload)
        self.assertEqual(payload.get("completion"), "no_event", payload)


# Only this module's tests: the inherited fake-host tests run in test_b3_document.
for _name in [n for n in dir(b3.FakeHostMeasurers) if n.startswith("test_")]:
    if _name not in BetterOfficeLateFindReply.__dict__:
        setattr(BetterOfficeLateFindReply, _name, None)

if __name__ == "__main__":
    unittest.main()
