"""Report E2's later campaign: the editors added after the published one.

``out/report_e2_runs.json`` may carry ``"later": {"roots": [...]}``. Its facts
are built by the same machinery as the published campaign's and renamed to
``perf.e2.later.*``, so no figure of one campaign is read as the other's. The
published facts may be carried byte for byte (TRIAL_E2_CARRY); the later facts
are still built. An editor in both campaigns, another machine type or other
documents are refused. With no later campaign the template still renders.

Run: python3 -m unittest build.test_e2_later_facts (from the repo root)
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT))

import facts as facts_mod  # noqa: E402
import perf_e2_tables as E2  # noqa: E402
import render_reports  # noqa: E402
import test_perf_e2_tables as T  # noqa: E402
from perf.analysis.anti_ranking import assert_markdown_no_editor_speed_ranking  # noqa: E402

TEMPLATE = render_reports.TEMPLATES / "reports/Report E2 - Speed in the Browser (2026).md"


def farm(base: Path, editors, *, tag: str, cpu_model: str | None = None, sha: str = "sha-500w",
         detection: str | None = None) -> list[Path]:
    """Two seeds, one Space each, one input-lane block job measuring C07 (and C10 when asked)."""
    roots = []
    for seed in (1, 2):
        root = base / ("e2-%s--r%d" % (tag, seed))
        job = root / "benchmark_input" / ("%s%d-1" % (tag, seed))
        job.mkdir(parents=True)
        summary = T._summary(job, run_id="%s%d-1" % (tag, seed), seed=seed, editors=list(editors), reps=5)
        summary["block"] = {"index": 1, "of": 2, "repetitions": 5}
        summary["hosts"] = {e: {"host_build": "production", "tree_sha256": "tree-fixture"} for e in editors}
        summary["started_at"] = "2026-11-2%dT08:00:00Z" % seed
        summary["finished_at"] = "2026-11-2%dT09:00:00Z" % seed
        if cpu_model:
            summary["host"]["cpu_model"] = cpu_model
        (job / "summary.json").write_text(json.dumps(summary))
        for editor in editors:
            env = {**T._env(editor), "workload_id": "prose-500w", "fixture_sha256": sha}
            for rep in range(5):
                T._write_trial(root, rep, editor, "C07", outcome="measured", samples=[20.0], environment=env)
                if detection and editor == "onlyoffice":
                    T._write_trial(root, rep, editor, "C10", outcome="measured", samples=[30.0], environment=env,
                                   diagnostic={"frame_interval_ms": 16.7, "detection": detection})
        roots.append(root)
    return roots


def later_keys_in_template() -> set[str]:
    return set(re.findall(r"\{\{(perf\.e2\.later\.[^}]+)\}\}", TEMPLATE.read_text(encoding="utf-8")))


class LaterFacts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.published = farm(self.base / "pub", ["plate"], tag="pub")
        env = mock.patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("TRIAL_E2_CARRY", None)

    def runs_file(self, payload: dict, name: str = "report_e2_runs.json") -> Path:
        path = self.base / name
        path.write_text(json.dumps(payload))
        return path

    def build(self, payload: dict) -> dict:
        out: dict = {}
        facts_mod.perf_e2_facts(self.runs_file(payload), out)
        return out

    def test_later_facts_land_under_their_own_prefix_and_leave_the_published_keys_alone(self):
        later = farm(self.base / "later", ["opendoc", "onlyoffice"], tag="later")
        alone = self.build({"roots": [str(r) for r in self.published]})
        both = self.build({"roots": [str(r) for r in self.published], "later": {"roots": [str(r) for r in later]}})
        published = {k: v for k, v in both.items() if not k.startswith("perf.e2.later.")}
        self.assertEqual(published, {k: v for k, v in alone.items() if not k.startswith("perf.e2.later.")})
        self.assertEqual(both["perf.e2.later.measured"], "measured")
        self.assertIn("OpenDoc", both["perf.e2.later.table.C07"])
        self.assertNotIn("Plate", both["perf.e2.later.table.C07"])
        self.assertNotIn("OpenDoc", both["perf.e2.table.C07"])
        self.assertTrue(any(k.startswith("perf.e2.later.opendoc.C07") for k in both))
        self.assertFalse(any(k.startswith("perf.e2.opendoc.") for k in both))
        self.assertIn("OnlyOffice (CryptPad build) and OpenDoc", both["perf.e2.later.editors"])
        self.assertNotIn("Nutrient", both["perf.e2.later.editors"])
        self.assertIn("Nutrient and react-docx have no browser data", both["perf.e2.later.unmeasured"])
        for name in ("react-docx", "BetterOffice", "OnlyOffice (CryptPad build)", "OpenDoc", "Nutrient"):
            self.assertIn(name, both["perf.e2.later.scope"])
        # the comparison was made against the published campaign's own run folders
        self.assertIn("SHA-256", both["perf.e2.later.comparison"])
        self.assertNotIn("not compared", both["perf.e2.later.comparison"])
        # every later key the template uses exists, and the template renders without a ranking
        self.assertEqual(later_keys_in_template() - set(both), set())
        text = render_reports.reportgen.render(TEMPLATE.read_text(encoding="utf-8"), both)
        assert_markdown_no_editor_speed_ranking(text)
        self.assertIn("## The editors measured later", text)

    def test_the_carried_published_facts_stay_byte_for_byte_and_the_later_facts_are_built(self):
        old = E2.facts_from_roots(self.published)
        old["perf.e2.later.table.C07"] = "a stale later table from the carried file"
        old_file = self.base / "facts-v0.0.0.json"
        old_file.write_text(json.dumps(old))
        later = farm(self.base / "later", ["opendoc"], tag="later")
        os.environ["TRIAL_E2_CARRY"] = str(old_file)
        out = self.build({"roots": [str(self.base / "gone")], "later": {"roots": [str(r) for r in later]}})
        carried = {k: v for k, v in out.items() if not k.startswith("perf.e2.later.") and k != "perf.e2.carried_from"}
        self.assertEqual(carried, {k: v for k, v in json.loads(old_file.read_text()).items()
                                   if k.startswith("perf.e2.") and not k.startswith("perf.e2.later.")})
        self.assertEqual(out["perf.e2.carried_from"], "facts-v0.0.0.json")
        self.assertIn("OpenDoc", out["perf.e2.later.table.C07"])
        self.assertNotEqual(out["perf.e2.later.table.C07"], "a stale later table from the carried file")
        # no run folders of the carried campaign: its documents cannot be compared, and the fact says so
        self.assertIn("not compared by hash", out["perf.e2.later.comparison"])
        self.assertIn("facts-v0.0.0.json", out["perf.e2.later.comparison"])

    def test_carry_without_a_later_campaign_gives_the_placeholders_not_the_carried_later_facts(self):
        old = E2.facts_from_roots(self.published)
        old["perf.e2.later.table.C07"] = "a stale later table from the carried file"
        old_file = self.base / "facts-v0.0.0.json"
        old_file.write_text(json.dumps(old))
        os.environ["TRIAL_E2_CARRY"] = str(old_file)
        out = self.build({"roots": [str(self.base / "gone")]})
        self.assertEqual(out["perf.e2.later.table.C07"], "not yet measured")

    def test_no_later_campaign_gives_honest_placeholders_and_the_report_renders(self):
        for out in (self.build({"roots": [str(r) for r in self.published]}), {}):
            if not out:
                facts_mod.perf_e2_facts(self.base / "absent.json", out)
            self.assertEqual(later_keys_in_template() - set(out), set())
            self.assertEqual(out["perf.e2.later.measured"], "not yet measured")
            self.assertIn("not yet measured", out["perf.e2.later.lead"])
            self.assertEqual(out["perf.e2.later.table.C07"], "not yet measured")
            self.assertEqual(out["perf.e2.later.short_version"], "not yet measured")
            for name in ("react-docx", "BetterOffice", "OnlyOffice (CryptPad build)", "OpenDoc", "Nutrient"):
                self.assertIn(name, out["perf.e2.later.editors"])
            text = render_reports.reportgen.render(TEMPLATE.read_text(encoding="utf-8"), out)
            assert_markdown_no_editor_speed_ranking(text)
            self.assertNotIn("are not in this report", text)

    def test_a_snapshot_from_before_the_later_campaign_renders_its_section_as_not_yet_measured(self):
        tpl = TEMPLATE.read_text(encoding="utf-8")
        snapshot = E2.facts_from_roots(self.published)
        text = render_reports.reportgen.render(tpl, snapshot)
        self.assertIn("That campaign is not yet measured", text)
        partial = {**snapshot, "perf.e2.later.measured": "measured"}  # a later snapshot missing its fields stays strict
        with self.assertRaises(KeyError):
            render_reports.reportgen.render(tpl, partial)

    def test_the_later_section_prints_the_bounds_its_build_generates_and_the_carried_ones_stay(self):
        old = E2.facts_from_roots(self.published)
        old["perf.e2.relaxed_bounds"] = "Relaxed bounds: the published campaign's own text."
        old_file = self.base / "facts-v0.0.0.json"
        old_file.write_text(json.dumps(old))
        later = farm(self.base / "later", ["opendoc"], tag="later")
        os.environ["TRIAL_E2_CARRY"] = str(old_file)
        import perf.runner.lax_bounds as lax
        with mock.patch.object(lax, "relaxed_bounds_paragraph", return_value="Relaxed bounds: built now."):
            out = self.build({"roots": [str(self.base / "gone")], "later": {"roots": [str(r) for r in later]}})
            unset = self.build({"roots": [str(self.base / "gone")]})
        self.assertEqual(out["perf.e2.later.relaxed_bounds"], "Relaxed bounds: built now.")
        self.assertEqual(unset["perf.e2.later.relaxed_bounds"], "Relaxed bounds: built now.")
        self.assertEqual(out["perf.e2.relaxed_bounds"], "Relaxed bounds: the published campaign's own text.")
        text = render_reports.reportgen.render(TEMPLATE.read_text(encoding="utf-8"), out)
        section = text[text.index("## The editors measured later"):text.index("## Appendix A")]
        self.assertIn("Relaxed bounds: built now.", section)

    def test_an_editor_in_both_campaigns_is_refused(self):
        later = farm(self.base / "later", ["plate", "opendoc"], tag="later")
        with self.assertRaisesRegex(ValueError, "Plate.js already in the published campaign"):
            self.build({"roots": [str(r) for r in self.published], "later": {"roots": [str(r) for r in later]}})

    def test_an_editor_in_the_carried_campaign_is_refused(self):
        old_file = self.base / "facts-v0.0.0.json"
        old_file.write_text(json.dumps(E2.facts_from_roots(self.published)))
        os.environ["TRIAL_E2_CARRY"] = str(old_file)
        later = farm(self.base / "later", ["plate"], tag="later")
        with self.assertRaisesRegex(ValueError, "already in the published campaign"):
            self.build({"roots": [str(self.base / "gone")], "later": {"roots": [str(r) for r in later]}})

    def test_another_machine_type_is_refused(self):
        later = farm(self.base / "later", ["opendoc"], tag="later", cpu_model="another CPU")
        with self.assertRaisesRegex(ValueError, "another machine type"):
            self.build({"roots": [str(r) for r in self.published], "later": {"roots": [str(r) for r in later]}})

    def test_another_machine_type_is_refused_against_the_carried_campaign(self):
        old_file = self.base / "facts-v0.0.0.json"
        old_file.write_text(json.dumps(E2.facts_from_roots(self.published)))
        os.environ["TRIAL_E2_CARRY"] = str(old_file)
        later = farm(self.base / "later", ["opendoc"], tag="later", cpu_model="another CPU")
        with self.assertRaisesRegex(ValueError, "another machine type"):
            self.build({"roots": [str(self.base / "gone")], "later": {"roots": [str(r) for r in later]}})

    def test_other_documents_are_refused(self):
        later = farm(self.base / "later", ["opendoc"], tag="later", sha="another-document")
        with self.assertRaisesRegex(ValueError, "other documents"):
            self.build({"roots": [str(r) for r in self.published], "later": {"roots": [str(r) for r in later]}})

    def test_onlyoffice_c10_by_canvas_pixels_is_said_only_when_its_records_say_so(self):
        pixels = farm(self.base / "px", ["onlyoffice"], tag="px", detection="canvas_pixels")
        out = self.build({"roots": [str(r) for r in self.published], "later": {"roots": [str(r) for r in pixels]}})
        self.assertIn("measured from canvas pixels", out["perf.e2.later.c10_onlyoffice"])
        dom = farm(self.base / "dom", ["onlyoffice"], tag="dom", detection="dom_scroll")
        out = self.build({"roots": [str(r) for r in self.published], "later": {"roots": [str(r) for r in dom]}})
        self.assertNotIn("measured from canvas pixels", out["perf.e2.later.c10_onlyoffice"])
        none = farm(self.base / "none", ["opendoc"], tag="none")
        out = self.build({"roots": [str(r) for r in self.published], "later": {"roots": [str(r) for r in none]}})
        self.assertIn("no C10", out["perf.e2.later.c10_onlyoffice"])


if __name__ == "__main__":
    unittest.main()
