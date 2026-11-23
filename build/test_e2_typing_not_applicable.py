"""Report E2's typing table says "does not apply" for a viewer, with its reason.

Nutrient on the Spaces (2026-11-22): its typing job writes not-applicable rows and
then "typing_sessions_unreachable" rows, and its summary's failure_reason is
"insufficient_typing_sessions"; the table printed that as "not enough sessions or
run blocked". Run: python3 -m unittest build.test_e2_typing_not_applicable
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT))

import perf_e2_tables as E2  # noqa: E402

VIEWER = "Nutrient Web SDK is a viewer here: there is no caret and nothing to type into"


def row(outcome, reason, editor="nutrient", kind="latency"):
    return {"editor_id": editor, "criterion_id": "TYPING", "session_kind": kind,
            "outcome": outcome, "failure_reason": reason}


class TypingDoesNotApply(unittest.TestCase):
    def table(self, rows, editor="nutrient", kind="latency"):
        with mock.patch.object(E2, "_iter_trials", side_effect=lambda root: iter(rows)), \
                mock.patch.object(E2, "_distinct_seeds", return_value=[1, 2]):
            facts = {}
            return E2.typing_table(facts, [Path("r1")], editor, kind), facts

    def test_a_viewer_prints_does_not_apply_with_its_reason(self):
        rows = [row("not_applicable", VIEWER)] * 2 + [row("not_run", "typing_sessions_unreachable")] * 4
        text, facts = self.table(rows)
        self.assertEqual(text, "Nutrient — latency: does not apply (%s)." % VIEWER)
        self.assertNotIn("not enough sessions", text)
        self.assertIs(facts["perf.e2.nutrient.TYPING.latency.reproduced"], False)

    def test_any_other_row_keeps_the_usual_table(self):
        for other in (row("measured", None), row("failed", "crash"), row("not_run", "budget_exhausted")):
            rows = [row("not_applicable", VIEWER), other]
            self.assertIsNone(self._rule(rows), other)

    def test_rows_not_tried_alone_are_not_does_not_apply(self):
        self.assertIsNone(self._rule([row("not_run", "typing_sessions_unreachable")] * 6))

    def test_another_editor_or_session_kind_is_not_read(self):
        rows = [row("not_applicable", VIEWER, editor="plate"), row("not_applicable", VIEWER, kind="throughput")]
        self.assertIsNone(self._rule(rows))

    def _rule(self, rows):
        with mock.patch.object(E2, "_iter_trials", side_effect=lambda root: iter(rows)):
            return E2.typing_does_not_apply([Path("r1")], "nutrient", "latency")


if __name__ == "__main__":
    unittest.main()
