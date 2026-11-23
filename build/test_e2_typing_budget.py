"""Report E2: a typing session stopped by the one-hour budget is said so, with the words typed.

The later campaign, 2026-11-23: every OpenDoc typing session ran into the
3,600 s budget every editor gets (refusal ``editor_timeout``, reason
``budget_exceeded``), and after two such sessions the job did not try the
rest. The job summary says ``insufficient_typing_sessions``, which hides that.
The owner keeps the budget the same for every editor; the report says the
editor did not finish within the hour and how many words it typed.

Run: python3 -m pytest build/test_e2_typing_budget.py (from the repo root)
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT))

import perf_e2_tables as E2  # noqa: E402
import test_perf_e2_tables as T  # noqa: E402


def _session(root, rep, *, seed=1, kind="throughput", words=6675, outcome="refused",
             code="editor_timeout", why="budget_exceeded", editor="opendoc", budget=3600.0):
    """One typing session; the seed lives in the job's summary, as on the Spaces."""
    root = root / ("seed%d" % seed)
    root.mkdir(exist_ok=True)
    (root / "summary.json").write_text(json.dumps({"seed": seed}))
    T._write_trial(root, rep, editor, "TYPING", outcome=outcome, refusal_code=code, failure_reason=why,
                   session_kind=kind, seed=seed, words_typed=words, characters_typed=None if words is None else words * 6,
                   budget_s=budget)


class TypingBudget(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def roots(self):
        return sorted(self.root.glob("seed*"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_timeouts_and_the_untried_rest_read_as_did_not_finish_within_the_hour(self):
        _session(self.root, 0, words=6675)
        _session(self.root, 1, words=6802)
        for rep in range(2, 6):
            _session(self.root, rep, outcome="not_run", code="not_run", why="typing_sessions_unreachable", words=None)
        text = E2._typing_budget_text(self.roots(), "opendoc", "throughput", 1)
        self.assertEqual(
            text, "did not finish within the hour: 2 sessions stopped at the one-hour limit every editor has, "
                  "with 6,675 and 6,802 words typed; the other 4 were not tried")

    def test_other_seed_kind_or_editor_does_not_count(self):
        _session(self.root, 0, seed=2)
        _session(self.root, 1, kind="latency")
        _session(self.root, 2, editor="betteroffice")
        self.assertIsNone(E2._typing_budget_text(self.roots(), "opendoc", "throughput", 1))

    def test_a_crash_beside_a_timeout_is_not_called_a_timeout(self):
        _session(self.root, 0)
        _session(self.root, 1, code="crash", why="page_crashed")
        self.assertIsNone(E2._typing_budget_text(self.roots(), "opendoc", "throughput", 1))

    def test_one_timeout_reads_in_the_singular(self):
        _session(self.root, 0, words=1)
        self.assertEqual(E2._typing_budget_text(self.roots(), "opendoc", "throughput", 1),
                         "did not finish within the hour: 1 session stopped at the one-hour limit every editor has, "
                         "with 1 word typed")


    def test_another_budget_is_not_called_the_limit_every_editor_has(self):
        """Codex review: only the campaign's own 3,600 s budget is the one every editor gets."""
        _session(self.root, 0, budget=120.0)
        self.assertIsNone(E2._typing_budget_text(self.roots(), "opendoc", "throughput", 1))

    def test_a_refusal_the_rows_do_not_show_keeps_the_usual_explanation(self):
        """Codex review: a veto, quarantine or unreadable attempt is in the group's tally, not in the rows."""
        _session(self.root, 0)
        _session(self.root, 1, outcome="not_run", code="not_run", why="typing_sessions_unreachable", words=None)
        roots = self.roots()
        self.assertIsNotNone(E2._typing_budget_text(roots, "opendoc", "throughput", 1,
                                                    {"budget_exceeded": 1, "typing_sessions_unreachable": 1}))
        self.assertIsNone(E2._typing_budget_text(roots, "opendoc", "throughput", 1,
                                                 {"budget_exceeded": 1, "typing_sessions_unreachable": 1, "quarantined": 1}))
        self.assertIsNone(E2._typing_budget_text(roots, "opendoc", "throughput", 1,
                                                 {"budget_exceeded": 2, "typing_sessions_unreachable": 1}))


class SupersededTypingJobs(unittest.TestCase):
    """Later campaign, 2026-11-23: a typing job measured again must not count twice.

    The trial build read BetterOffice's and OnlyOffice's typing cells as
    "n = 6 of 12": the campaign's job (superseded) and the rerun's job of the
    same index were both pooled, so the replaced job's schedule and its
    run-policy block came back with it.
    """

    def _job(self, base, run_id, index, seed, editor="betteroffice"):
        job = base / "benchmark_typing" / ("%s-%d" % (run_id, index))
        job.mkdir(parents=True)
        summary = T._summary(job, run_id=run_id, seed=seed, editors=[editor], reps=6)
        summary.update(runner="benchmark_typing", session_kind="throughput")
        (job / "summary.json").write_text(json.dumps(summary))
        (job / "cells").mkdir()
        return job

    def test_the_superseded_campaign_job_is_left_out_of_the_seed_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            camp, rerun = Path(tmp) / "camp", Path(tmp) / "rerun"
            self._job(camp, "camprun", 48, 1)
            self._job(rerun, "rerunrun", 48, 1)
            from perf.analysis import e2_cells
            entry = {"editor": "betteroffice", "jobs": [48], "kept_runs": ["rerunrun"]}
            with e2_cells.superseded_cells([entry]):
                group = E2._typing_group_for_seed([camp, rerun], "betteroffice", "throughput", 1)
            self.assertEqual(group["scheduled"], 6)
            without = E2._typing_group_for_seed([camp, rerun], "betteroffice", "throughput", 1)
            self.assertEqual(without["scheduled"], 12)


if __name__ == "__main__":
    unittest.main()
