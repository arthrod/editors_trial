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

    def test_a_job_pulled_mid_run_without_its_summary_is_refused_by_name(self):
        """Codex review: an unfinished job has cells but no summary; it must not be read as every editor's."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "run"
            self._job(base, "rerunrun", 48, 1)
            half = base / "benchmark_typing" / "otherrun-123"
            (half / "cells").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "otherrun-123 has no readable summary.json"):
                E2._typing_group_for_seed([base], "betteroffice", "throughput", 1)

    def test_an_unfinished_job_of_another_lane_or_editor_leaves_this_editors_typing_alone(self):
        """Gitar review on #286: the refusal reached jobs of other lanes and other editors."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "run"
            self._job(base, "rerunrun", 48, 1)
            (base / "benchmark_input" / "inputrun-7" / "cells" / "0000-betteroffice").mkdir(parents=True)
            (base / "benchmark_typing" / "otherrun-46" / "cells" / "0000-onlyoffice").mkdir(parents=True)
            group = E2._typing_group_for_seed([base], "betteroffice", "throughput", 1)
            self.assertEqual(group["scheduled"], 6)
            # the editor whose job it is still refuses, so the build as a whole still does
            with self.assertRaisesRegex(ValueError, "otherrun-46 has no readable summary.json"):
                E2._typing_group_for_seed([base], "onlyoffice", "throughput", 1)


class TypingMismatch(unittest.TestCase):
    """react-docx, later campaign: every session typed all its keys but the text read back differed.

    It drops the first key after each Enter (checklist 8.1.1), so the check
    refuses the session (failure_reason ``text_mismatch``) at the same
    character every time, and after two the job stops trying. The table said
    "not enough sessions or run blocked (insufficient_typing_sessions)"; it
    now names the mismatch and where it starts.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, rep, **kw):
        root = self.root / "seed1"
        root.mkdir(exist_ok=True)
        (root / "summary.json").write_text(json.dumps({"seed": 1}))
        row = dict(outcome="refused", refusal_code="correctness_failure", failure_reason="text_mismatch",
                   session_kind="throughput", characters_typed=81225, first_divergence_offset=23)
        row.update(kw)
        T._write_trial(root, rep, "reactdocx", "TYPING", **row)
        return [root]

    def test_mismatch_sessions_name_the_mismatch_and_where_it_starts(self):
        self._write(0)
        self._write(1)
        for rep in range(2, 6):
            roots = self._write(rep, outcome="not_run", refusal_code="not_run",
                                failure_reason="typing_sessions_unreachable", characters_typed=None,
                                first_divergence_offset=None)
        text = E2._typing_mismatch_text(roots, "reactdocx", "throughput", 1,
                                        {"text_mismatch": 2, "typing_sessions_unreachable": 4})
        self.assertEqual(
            text, "the typed text did not match: 2 sessions typed 81,225 characters each, and the text "
                  "read back first differs from it after 23 characters of the compared text (spaces collapsed, "
                  "quotes folded, list markers set aside); the other 4 were not tried")

    def test_another_refusal_beside_a_mismatch_keeps_the_usual_explanation(self):
        roots = self._write(0)
        self.assertIsNone(E2._typing_mismatch_text(roots, "reactdocx", "throughput", 1,
                                                   {"text_mismatch": 1, "crash": 1}))


class CampaignInventory(unittest.TestCase):
    """The later campaign's "N run folders contributed M jobs" counted the 12
    typing jobs its reruns measured again as well as the reruns (164, not 152).
    A job every editor of which was measured again contributed nothing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _job(self, root, run_id, index, seed, editors, *, order=None, cells=None):
        job = root / "benchmark_typing" / f"{run_id}-{index:03d}"
        job.mkdir(parents=True)
        for i, editor in enumerate(editors if cells is None else cells):
            (job / "cells" / f"{i:04d}-{editor}" / "attempts").mkdir(parents=True)
        summary = {"seed": seed, "run_id": f"{run_id}-{index:03d}"}
        if order is not None:
            summary["order"] = order
        (job / "summary.json").write_text(json.dumps(summary))
        return job

    def _replaced(self, job, editors=("onlyoffice",), jobs=(46,)):
        entry = [{"issue": "later-rerun", "editor": e, "jobs": list(jobs), "kept_runs": ["other-run"]} for e in editors]
        with E2.e2_cells.superseded_cells(entry):
            return E2.e2_cells.job_replaced_whole(job)

    def test_the_order_names_the_editors_not_the_folders(self):
        """Codex: B scheduled but without a cell folder still contributed."""
        camp = self.base / "c" / "20261122T000000000000Z-1-1"
        job = self._job(camp, camp.name, 46, 1, [], order=[[0, "onlyoffice"], [0, "betteroffice"]], cells=["onlyoffice"])
        self.assertFalse(self._replaced(job))

    def test_a_summary_only_job_replaced_whole_is_left_out(self):
        camp = self.base / "c" / "20261122T000000000000Z-1-1"
        job = self._job(camp, camp.name, 46, 1, [], order=[[0, "onlyoffice"], [1, "onlyoffice"]], cells=[])
        self.assertTrue(self._replaced(job))

    def test_a_folder_of_another_shape_keeps_the_job(self):
        camp = self.base / "c" / "20261122T000000000000Z-1-1"
        job = self._job(camp, camp.name, 46, 1, [], cells=["onlyoffice"])
        (job / "cells" / "profile-trace").mkdir()
        self.assertFalse(self._replaced(job))

    def test_the_host_load_table_skips_a_job_replaced_whole(self):
        import perf_e2_host_load as HL
        camp = self.base / "c" / "20261122T000000000000Z-1-1"
        rerun = self.base / "r" / "20261123T000000000000Z-2-2"
        for root in (camp, rerun):
            job = self._job(root, root.name, 46, 1, ["onlyoffice"], order=[[0, "onlyoffice"]])
            (job / "samples").mkdir()
            (job / "samples" / "s.json").write_text(json.dumps({"host_load": {"start_1m": 1.0, "end_1m": 1.0, "logical_cpus": 64}}))
        entry = [{"issue": "later-rerun", "editor": "onlyoffice", "jobs": [46], "kept_runs": [rerun.name]}]
        with E2.e2_cells.superseded_cells(entry):
            rows = HL.job_rows([camp, rerun])
        self.assertEqual([row["job"] for row in rows], [f"{rerun.name}-046"])

    def test_a_job_measured_again_for_every_editor_is_not_counted(self):
        camp = self.base / "camp" / "20261122T000000000000Z-1-1"
        rerun = self.base / "rerun" / "20261123T000000000000Z-2-2"
        self._job(camp, camp.name, 46, 1, ["onlyoffice"])
        self._job(camp, camp.name, 7, 1, ["onlyoffice", "betteroffice"])
        self._job(rerun, rerun.name, 46, 1, ["onlyoffice"])
        entry = [{"issue": "later-rerun", "editor": "onlyoffice", "jobs": [46, 7], "kept_runs": [rerun.name]}]
        with E2.e2_cells.superseded_cells(entry):
            view = E2._campaign_view([camp, rerun])
        # Job 46 of the campaign is replaced whole; job 7 still holds BetterOffice's cells.
        self.assertEqual(view["jobs"], 2)
        self.assertEqual(len(view["by_seed"][1]), 2)

    def test_the_machine_note_counts_the_same_jobs(self):
        camp = self.base / "camp" / "20261122T000000000000Z-1-1"
        rerun = self.base / "rerun" / "20261123T000000000000Z-2-2"
        self._job(camp, camp.name, 46, 1, ["onlyoffice"])
        self._job(camp, camp.name, 7, 1, ["onlyoffice", "betteroffice"])
        self._job(rerun, rerun.name, 46, 1, ["onlyoffice"])
        entry = [{"issue": "later-rerun", "editor": "onlyoffice", "jobs": [46, 7], "kept_runs": [rerun.name]}]
        with E2.e2_cells.superseded_cells(entry):
            note = E2._host_note_campaign([camp, rerun], ["onlyoffice", "betteroffice"])
        self.assertIn("Seed 1 — 2 jobs", note)

    def test_without_reruns_every_job_counts(self):
        camp = self.base / "camp" / "20261122T000000000000Z-1-1"
        self._job(camp, camp.name, 46, 1, ["onlyoffice"])
        self._job(camp, camp.name, 7, 2, ["onlyoffice", "betteroffice"])
        self.assertEqual(E2._campaign_view([camp])["jobs"], 2)


if __name__ == "__main__":
    unittest.main()


def test_another_editors_unfinished_typing_job_does_not_block_this_editor(tmp_path):
    """CodeRabbit on #287: read as ``{}``, another editor's unfinished job reached
    ``_sessions_from_jobs`` and blocked this editor's complete cell ("run policy")."""
    base = tmp_path / "run"
    SupersededTypingJobs._job(None, base, "rerunrun", 48, 1)
    (base / "benchmark_typing" / "otherrun-46" / "cells" / "0000-onlyoffice").mkdir(parents=True)
    group = E2._typing_group_for_seed([base], "betteroffice", "throughput", 1)
    assert group["scheduled"] == 6
    assert group["blocked"] is False, group.get("block_reason")
    assert group["block_reason"] is None
