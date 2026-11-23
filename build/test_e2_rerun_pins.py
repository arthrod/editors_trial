"""Report E2: a re-measured editor's cells may carry their own built-editor pin, disclosed (#149).

Owner's decision (2026-11-23, later campaign): OnlyOffice's typing cells were
measured again on a host build that differs from the campaign's by one line
(hyphens-with-dash off on the measured page). Its pin, the hash of the built
tree, therefore differs. Rows of a run listed in ``superseded_cells`` as the
editor's ``kept_runs`` may carry another pin; the host note names both pins,
the jobs, and the entry's ``note``. Any other pin difference is still refused,
and the kept rows of one entry must agree with each other.

Run: python3 -m unittest build.test_e2_rerun_pins (from the repo root)
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT))

import perf_e2_tables as E2  # noqa: E402
import test_perf_e2_tables as T  # noqa: E402
from test_e2_later_facts import farm  # noqa: E402

NOTE = "its host page turns hyphens-with-dash off (owner's decision); the vendor editor is the same"


def _repin(root: Path, editor: str, tree: str) -> None:
    """Give every attempt of ``editor`` under ``root`` another built-editor tree."""
    for path in root.rglob("attempts/*.json"):
        row = json.loads(path.read_text())
        if row.get("editor_id") == editor:
            row["host_provenance"] = {**row["host_provenance"], "tree_sha256": tree}
            path.write_text(json.dumps(row))


def _rerun(base: Path, tag: str, editor: str, tree: str, campaign: list[Path], seeds=(1, 2)) -> list[Path]:
    """The editor's cells of job 2 measured again by a run of its own, on another build.

    The campaign's other job (1) keeps the editor's rows on the campaign build,
    as the later campaign's OnlyOffice lanes do. A real re-run attests the
    campaign's whole ``versions`` block (the plan's, not the job's editors), so
    the fixture copies it from the campaign.
    """
    versions = json.loads(next(campaign[0].glob("benchmark_*/*/summary.json")).read_text())["versions"]
    roots = farm(base, [editor], tag=tag, seeds=seeds)
    for root in roots:
        _repin(root, editor, tree)
        for job in list(root.glob("benchmark_*/*-1")):
            summary = json.loads((job / "summary.json").read_text())
            summary["versions"] = versions
            summary["run_id"] = job.name[:-1] + "2"
            (job / "summary.json").write_text(json.dumps(summary))
            job.rename(job.with_name(job.name[:-1] + "2"))
    return roots


def _entry(editor: str, kept: list[Path], note: str | None = NOTE) -> dict:
    runs = sorted({job.name.rpartition("-")[0] for root in kept for job in root.glob("benchmark_*/*")})
    entry = {"issue": "later-rerun", "editor": editor, "jobs": [2], "kept_runs": runs}
    if note:
        entry["note"] = note
    return entry


def _host_note(facts: dict) -> str:
    notes = [v for k, v in facts.items() if isinstance(v, str) and "Editor pins (" in v]
    assert notes, "no host note with editor pins among the facts"
    return notes[0]


class RerunPins(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.campaign = farm(self.base, ["onlyoffice", "betteroffice"], tag="camp")

    def tearDown(self):
        self.tmp.cleanup()

    def test_kept_rerun_with_its_own_pin_builds_and_discloses_both(self):
        rerun = _rerun(self.base, "plate", "onlyoffice", "tree-rebuilt", self.campaign)
        facts = E2.facts_from_roots(self.campaign + rerun, superseded_cells=[_entry("onlyoffice", rerun)])
        note = _host_note(facts)
        self.assertIn("tree-fixture", note)
        self.assertIn("tree-rebuilt", note)
        self.assertIn(NOTE, note)
        self.assertRegex(note, r"OnlyOffice \(CryptPad build\)'s re-measured cells \(job 2\) ran on built-editor tree tree-rebuilt; its cells not re-measured, on tree-fixture")

    def test_same_rerun_without_its_entry_is_still_refused(self):
        rerun = _rerun(self.base, "plate", "onlyoffice", "tree-rebuilt", self.campaign)
        with self.assertRaisesRegex(ValueError, "other editor pins"):
            E2.facts_from_roots(self.campaign + rerun)

    def test_entry_for_another_editor_does_not_excuse_the_pin(self):
        rerun = _rerun(self.base, "plate", "onlyoffice", "tree-rebuilt", self.campaign)
        with self.assertRaisesRegex(ValueError, "other editor pins"):
            E2.facts_from_roots(self.campaign + rerun, superseded_cells=[_entry("betteroffice", rerun)])

    def test_campaign_root_on_another_build_is_still_refused(self):
        _repin(self.campaign[1], "betteroffice", "tree-other")
        rerun = _rerun(self.base, "plate", "onlyoffice", "tree-rebuilt", self.campaign)
        with self.assertRaisesRegex(ValueError, "other editor pins"):
            E2.facts_from_roots(self.campaign + rerun, superseded_cells=[_entry("onlyoffice", rerun)])

    def test_kept_rows_of_one_entry_must_agree(self):
        rerun = _rerun(self.base, "plate", "onlyoffice", "tree-rebuilt", self.campaign)
        _repin(rerun[1], "onlyoffice", "tree-third")
        with self.assertRaisesRegex(ValueError, "re-measured cells .*other editor pins"):
            E2.facts_from_roots(self.campaign + rerun, superseded_cells=[_entry("onlyoffice", rerun)])

    def test_rerun_on_the_campaign_build_adds_no_rerun_sentence(self):
        rerun = _rerun(self.base, "plate", "onlyoffice", "tree-fixture", self.campaign)
        facts = E2.facts_from_roots(self.campaign + rerun, superseded_cells=[_entry("onlyoffice", rerun)])
        self.assertNotIn("re-measured cells", _host_note(facts))

    def test_pin_disclosure_without_a_note_is_refused(self):
        rerun = _rerun(self.base, "plate", "onlyoffice", "tree-rebuilt", self.campaign)
        with self.assertRaisesRegex(ValueError, "note"):
            E2.facts_from_roots(self.campaign + rerun, superseded_cells=[_entry("onlyoffice", rerun, note=None)])

    def test_rerun_only_first_root_does_not_hide_a_campaign_mismatch(self):
        """Codex P1: the pin comparison must not be against the first root only."""
        rerun = _rerun(self.base, "plate", "onlyoffice", "tree-rebuilt", self.campaign)
        _repin(self.campaign[1], "onlyoffice", "tree-other")
        with self.assertRaisesRegex(ValueError, "other editor pins"):
            E2.facts_from_roots(rerun + self.campaign, superseded_cells=[_entry("onlyoffice", rerun)])

    def test_two_entries_on_two_builds_with_no_campaign_rows_are_refused(self):
        """Codex P2: with every row of an editor re-measured, two entries may not attest two builds unexplained."""
        first = _rerun(self.base, "plate", "onlyoffice", "tree-rebuilt", self.campaign)
        second = farm(self.base, ["onlyoffice"], tag="late", seeds=(1, 2))
        for root in second:
            _repin(root, "onlyoffice", "tree-third")
            for path in root.glob("benchmark_*/*/summary.json"):
                summary = json.loads(path.read_text())
                summary["versions"] = json.loads(next(self.campaign[0].glob("benchmark_*/*/summary.json")).read_text())["versions"]
                path.write_text(json.dumps(summary))
        entries = [_entry("onlyoffice", first, note=None),
                   {**_entry("onlyoffice", second, note=None), "jobs": [1]}]
        with self.assertRaisesRegex(ValueError, "other editor pins"):
            E2.facts_from_roots(self.campaign + first + second, superseded_cells=entries)

    def test_classic_two_root_comparison_grants_no_rerun_exemption(self):
        """Codex P3: the classic primary/reproduction path never uses superseded cells, so it excuses nothing."""
        a, b = (Path(self.tmp.name) / "a", Path(self.tmp.name) / "b")
        for tag, root in (("ra", a), ("rb", b)):
            root.mkdir()
        rows = {a: "tree-a", b: "tree-b"}
        original = E2._pins
        E2._RERUN_ENTRIES = ({"editor": "onlyoffice", "jobs": [1], "kept_runs": ["x"], "note": NOTE},)
        try:
            with mock.patch.object(E2, "_pins", lambda root, **kw: {"onlyoffice": [rows[Path(root)]]} if kw.get("reruns", "include") == "include" else {}):
                with self.assertRaisesRegex(ValueError, "other editor pins"):
                    E2._require_same_pins(a, b)
        finally:
            E2._RERUN_ENTRIES = ()


class NotApplicablePins(unittest.TestCase):
    """An attempt the runner records as not applicable launched no editor: it has no pin to report."""

    def test_not_applicable_rows_add_no_not_recorded_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = farm(Path(tmp), ["nutrient", "betteroffice"], tag="camp")
            for root in roots:
                T._write_trial(root, 0, "nutrient", "C04", outcome="not_applicable", samples=[],
                               host_provenance={}, environment=T._env("nutrient"))
            note = _host_note(E2.facts_from_roots(roots))
            self.assertRegex(note, r"Nutrient: tree-fixture[.;]")
            self.assertNotIn("not recorded", note.split("Editor pins (")[1])


if __name__ == "__main__":
    unittest.main()
