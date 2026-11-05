"""The performance plans cover every criterion and interpretation condition.

This test does not measure an editor. It fails when the design matrix, the
design doc, or a plan drops a required id, a required field, or a relative link.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "docs" / "superpowers" / "specs"
PLAN_DIR = ROOT / "docs" / "superpowers" / "plans"
MATRIX_PATH = SPEC_DIR / "2026-11-05-editor-performance-coverage.json"
DESIGN_PATH = SPEC_DIR / "2026-11-05-editor-performance-benchmark-design.md"

REQUIRED_CRITERION_FIELDS = (
    "title",
    "measurement_method",
    "tools",
    "existing_implementations",
    "comparability_limitations",
    "implementation_status",
    "plans",
)
REQUIRED_CONDITION_FIELDS = ("title", "rule", "plans")
FORBIDDEN = ("TBD", "TODO", "similar to above", "implement later", "fill in details")
EDITORS = (
    "plate",
    "docxodus",
    "apryse",
    "superdoc",
    "folio",
    "genoffice",
    "eigenpal",
    "office-open",
    "docen",
    "wordcraft",
    "fidus",
    "canvas",
    "docsplus",
    "libreoffice",
)
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _matrix():
    return json.loads(MATRIX_PATH.read_text())


class Matrix(unittest.TestCase):
    def test_twenty_four_criteria_and_twelve_conditions(self):
        data = _matrix()
        ids = [row["id"] for row in data["criteria"]]
        self.assertEqual(ids, ["C%02d" % n for n in range(1, 25)])
        conditions = [row["id"] for row in data["interpretation_conditions"]]
        self.assertEqual(conditions, ["I%02d" % n for n in range(1, 13)])

    def test_every_criterion_field_is_proposed_harness_work(self):
        for row in _matrix()["criteria"]:
            for field in REQUIRED_CRITERION_FIELDS:
                self.assertTrue(row[field], row["id"])
            self.assertEqual(row["implementation_status"], "proposed_harness")
            self.assertGreaterEqual(len(row["tools"]), 1)

    def test_editors_match_the_trial_participants(self):
        data = _matrix()
        self.assertEqual(data["editors"], list(EDITORS))
        excluded = {row["id"] for row in data["excluded"]}
        self.assertEqual(excluded, {"jubarte", "microsoft-word"})


class Documents(unittest.TestCase):
    def test_design_repeats_every_normative_sentence(self):
        text = DESIGN_PATH.read_text()
        data = _matrix()
        for row in data["criteria"]:
            self.assertIn("### %s. %s" % (row["id"], row["title"]), text)
            self.assertIn(row["measurement_method"], text)
            self.assertIn(row["existing_implementations"], text)
            self.assertIn(row["comparability_limitations"], text)
        for row in data["interpretation_conditions"]:
            self.assertIn("### %s. %s" % (row["id"], row["title"]), text)
            self.assertIn(row["rule"], text)

    def test_plans_exist_and_name_their_ids(self):
        data = _matrix()
        owned = {}
        for row in data["criteria"] + data["interpretation_conditions"]:
            for plan in row["plans"]:
                owned.setdefault(plan, set()).add(row["id"])
        self.assertGreaterEqual(len(owned), 7)
        for plan, ids in owned.items():
            path = ROOT / plan
            self.assertTrue(path.is_file(), plan)
            text = path.read_text()
            for identifier in ids:
                self.assertIn(identifier, text, plan)
            self.assertIn("For agentic workers:", text)

    def test_design_names_the_four_layers_and_the_cache_states(self):
        text = DESIGN_PATH.read_text()
        for phrase in (
            "`native`",
            "`model`",
            "`browser_visible`",
            "`wasm_boundary`",
            "`process_cold_fs_warm`",
            "`os_cache_cold`",
            "`warm_steady`",
            "requestAnimationFrame",
        ):
            self.assertIn(phrase, text)

    def test_no_placeholder_language(self):
        files = [DESIGN_PATH, MATRIX_PATH, *PLAN_DIR.glob("*.md")]
        for path in files:
            text = path.read_text()
            for token in FORBIDDEN:
                self.assertNotIn(token, text, "%s contains %r" % (path, token))

    def test_relative_links_resolve(self):
        for path in [DESIGN_PATH, *PLAN_DIR.glob("*.md")]:
            for target in LINK.findall(path.read_text()):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                target = target.split("#", 1)[0]
                if not target:
                    continue
                resolved = (path.parent / target).resolve()
                self.assertTrue(resolved.is_file(), "%s -> %s" % (path, target))


if __name__ == "__main__":
    unittest.main()
