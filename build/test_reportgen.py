#!/usr/bin/env python3
"""Tests for the report generator: templates + facts -> reports.

    cd build && python3 -m unittest test_reportgen
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))

import reportgen  # noqa: E402

FACTS = {
    "rt.superdoc.weighted": 100.0,
    "rt.superdoc.critical_pct": 100.0,
    "rt.superdoc.critical_passed": 29,
    "rt.superdoc.critical_total": 29,
    "rt.superdoc.text_pct": 100.0,
    "rt.superdoc.failed": 0,
    "rt.folio.weighted": 97.5,
    "rt.folio.critical_pct": 96.6,
    "rt.folio.critical_passed": 28,
    "rt.folio.critical_total": 29,
    "rt.folio.text_pct": 100.0,
    "rt.folio.failed": 2,
    "rt.plate.bytes": 42964,
    "p2.plate.bytes": 8010,
    "p2.folio.weighted": 97.5,
    "checks.total": 99,
    "ver.superdoc.commit": "f52c959b2",
}


class Render(unittest.TestCase):
    def test_substitutes_and_formats(self):
        t = "SuperDoc {{rt.superdoc.weighted:.1f}}% and Folio {{rt.folio.weighted:g}}%, {{rt.plate.bytes:,}} bytes"
        self.assertEqual(reportgen.render(t, FACTS), "SuperDoc 100.0% and Folio 97.5%, 42,964 bytes")

    def test_string_precision_truncates_a_commit(self):
        self.assertEqual(reportgen.render("`{{ver.superdoc.commit:.7}}`", FACTS), "`f52c959`")

    def test_missing_key_names_the_key(self):
        with self.assertRaisesRegex(KeyError, "rt.nobody.weighted"):
            reportgen.render("{{rt.nobody.weighted}}", FACTS)

    def test_counts_are_written_as_words(self):
        facts = {"n": 13, "m": 4, "big": 21}
        self.assertEqual(reportgen.render("{{m:W}} of the {{n:w}}; {{big:w}}", facts), "Four of the thirteen; 21")

    def test_ordinals_are_written_as_words(self):
        self.assertEqual(reportgen.render("the {{n:ord}}", {"n": 14}), "the fourteenth")

    def test_plain_text_is_untouched(self):
        t = "No placeholders: `w14:paraId`, 2026-10-29, §5.4, {single} braces.\n"
        self.assertEqual(reportgen.render(t, FACTS), t)


class Templatize(unittest.TestCase):
    def roundtrip(self, text):
        tpl, _ = reportgen.templatize(text, FACTS)
        self.assertEqual(reportgen.render(tpl, FACTS), text, "templatize must not lose content")
        return tpl

    def test_table_binds_row_subject_and_column_metric(self):
        text = (
            "| Editor | Weighted score | Critical features | Text retention | Failed checks |\n"
            "|---|---|---|---|---|\n"
            "| **SuperDoc V2** | **100.0%** | **100.0%** (29/29) | **100.0%** | **0** |\n"
            "| **Folio** | 97.5% | 96.6% (28/29) | 100.0% | 2 |\n"
        )
        tpl = self.roundtrip(text)
        self.assertIn("| **SuperDoc V2** | **{{rt.superdoc.weighted:.1f}}%** | **{{rt.superdoc.critical_pct:.1f}}%** "
                      "({{rt.superdoc.critical_passed}}/{{rt.superdoc.critical_total}}) | **{{rt.superdoc.text_pct:.1f}}%** "
                      "| **{{rt.superdoc.failed}}** |", tpl)
        self.assertIn("| {{rt.folio.weighted:.1f}}% | {{rt.folio.critical_pct:.1f}}% "
                      "({{rt.folio.critical_passed}}/{{rt.folio.critical_total}}) | {{rt.folio.text_pct:.1f}}% "
                      "| {{rt.folio.failed}} |", tpl)

    def test_prose_binds_to_the_nearest_subject(self):
        tpl = self.roundtrip("Folio scores 97.5% while Plate.js shrinks from 42,964 to 8,010 bytes.\n")
        self.assertIn("Folio scores {{rt.folio.weighted:.1f}}%", tpl)
        self.assertIn("from {{rt.plate.bytes:,}} to {{p2.plate.bytes:,}} bytes", tpl)

    def test_global_check_count(self):
        tpl = self.roundtrip("scored on the same 99 checks; a 99-check score.\n")
        self.assertEqual(tpl, "scored on the same {{checks.total}} checks; a {{checks.total}}-check score.\n")

    def test_ambiguous_figure_stays_literal_and_is_reported(self):
        # 97.5 is both Folio's first and second pass; nothing in the sentence says which.
        tpl, unbound = reportgen.templatize("Folio: 97.5.\n", FACTS)
        self.assertEqual(tpl, "Folio: 97.5.\n")
        self.assertTrue(any(u["literal"] == "97.5" for u in unbound))

    def test_code_dates_versions_and_identifiers_are_never_bound(self):
        text = "Folio `packages/core/src/docx/parser.ts:426`, w14, 2026-10-29, Word 16.115, §5.4, 0.27.0-next.15 and fig_p2.\n"
        tpl, _ = reportgen.templatize(text, FACTS)
        self.assertEqual(tpl, text)

    def test_keywords_are_read_next_to_the_figure_not_across_the_sentence(self):
        facts = dict(FACTS, **{"rt.superdoc.text_pct": 100.0})
        tpl, _ = reportgen.templatize("SuperDoc also scores 100% — 29/29 critical, 100% text, all parts.\n", facts)
        self.assertIn("{{rt.superdoc.text_pct:g}}% text", tpl)

    def test_part_counts_bind_to_part_facts(self):
        facts = dict(FACTS, **{"parts.docxodus.changed": 0, "parts.docxodus.dropped": 0,
                               "parts.docxodus.added": 0, "rt.docxodus.critical_failed": 0})
        tpl, _ = reportgen.templatize("Docxodus, 35/35 parts with 0 changed and 0 dropped; 0 parts lost and 0 added.\n", facts)
        self.assertIn("with {{parts.docxodus.changed}} changed and {{parts.docxodus.dropped}} dropped", tpl)
        self.assertIn("{{parts.docxodus.dropped}} parts lost and {{parts.docxodus.added}} added", tpl)

    def test_a_total_outside_a_fraction_is_the_trial_wide_count(self):
        facts = dict(FACTS, **{"rt.plate.total": 99})
        tpl, _ = reportgen.templatize("Plate.js was scored on the same 99 checks.\n", facts)
        self.assertIn("same {{checks.total}} checks", tpl)

    def test_a_section_heading_names_the_subject_of_its_prose(self):
        text = "#### Folio\n\n**Measured [MEASURED].** 97.5%, text intact.\n\n## Next\n\n97.5% again.\n"
        tpl, _ = reportgen.templatize(text, FACTS)
        self.assertIn("**Measured [MEASURED].** {{rt.folio.weighted:.1f}}%", tpl)
        self.assertTrue(tpl.endswith("97.5% again.\n"), "a heading without a subject ends the section")

    def test_n_of_m_parts(self):
        facts = dict(FACTS, **{"parts.canvas.dropped": 21, "parts.plate.kept": 11, "parts.plate.total": 35,
                               "fixture.parts": 35})
        tpl, _ = reportgen.templatize("canvas-editor: 21 of 35 parts lost. Plate.js: 11 of 35 parts kept.\n", facts)
        self.assertIn("{{parts.canvas.dropped}} of {{fixture.parts}} parts lost", tpl)
        self.assertIn("{{parts.plate.kept}} of {{fixture.parts}} parts kept", tpl)

    def test_a_figure_before_a_colon(self):
        facts = dict(FACTS, **{"rt.folio.passed": 97, "rt.folio.total": 99})
        tpl, _ = reportgen.templatize("Folio — 97/99: two losses, at `parser.ts:426`.\n", facts)
        self.assertIn("{{rt.folio.passed}}/{{rt.folio.total}}: two", tpl)
        self.assertIn("`parser.ts:426`", tpl)

    def test_a_word_beside_the_figure_beats_the_column_header(self):
        text = ("| Project | Measured round trip |\n|---|---|\n"
                "| SuperDoc V2 | **100.0%** · 29/29 · text 100.0% |\n")
        tpl, _ = reportgen.templatize(text, FACTS)
        self.assertIn("| **{{rt.superdoc.weighted:.1f}}%** · {{rt.superdoc.critical_passed}}/{{rt.superdoc.critical_total}}"
                      " · text {{rt.superdoc.text_pct:.1f}}% |", tpl)

    def test_a_fraction_binds_only_when_its_partner_matches(self):
        facts = dict(FACTS, **{"parts.fidus.kept": 11, "parts.fidus.total": 35})
        text = "Fidus Writer keeps **11/60** namespaces and 11/35 parts.\n"
        tpl, _ = reportgen.templatize(text, facts)
        self.assertIn("**11/60**", tpl)
        self.assertIn("{{parts.fidus.kept}}/{{parts.fidus.total}} parts", tpl)

    def test_a_column_or_a_cell_can_name_its_own_subject(self):
        facts = dict(FACTS, **{"rt.docxodus.weighted": 100.0})
        text = ("| | **Docxodus** | best other participant |\n|---|---|---|\n"
                "| 99-check round-trip score | **100.0 %** | 100.0 % (SuperDoc) |\n")
        tpl, _ = reportgen.templatize(text, facts)
        self.assertIn("| **{{rt.docxodus.weighted:.1f}} %** | {{rt.superdoc.weighted:.1f}} % (SuperDoc) |", tpl)

    def test_a_tie_in_a_column_follows_the_column(self):
        facts = {"parts.folio.out": 35, "parts.folio.total": 35, "parts.folio.kept": 35, "fixture.parts": 35,
                 "parts.plate.out": 11, "parts.docen.out": 29}
        text = ("| Editor | Parts out |\n|---|---|\n| Folio | 35 |\n| Plate.js | 11 |\n| Docen | 29 |\n")
        tpl, _ = reportgen.templatize(text, facts)
        self.assertIn("| Folio | {{parts.folio.out}} |", tpl)

    def test_second_pass_context_selects_p2(self):
        tpl = self.roundtrip("Folio's second pass scores 97.5%.\n")
        self.assertIn("{{p2.folio.weighted:.1f}}", tpl)


class Stars(unittest.TestCase):
    F = dict(FACTS, **{"stars.storytold/wordcraft": 16875, "stars.udecode/plate": 16684,
                       "stars.dolanmiu/docx": 5984, "rt.wordcraft.weighted": 85.9, "rt.plate.weighted": 20.6})

    def test_the_star_table_binds_by_repository(self):
        text = ("| Project | ★ | In this trial? |\n|---|---|---|\n"
                "| `storytold/wordcraft` | **16,875** | yes |\n| `dolanmiu/docx` | 5,984 | no |\n")
        tpl, _ = reportgen.templatize(text, self.F)
        self.assertIn("| **{{stars.storytold/wordcraft:,}}** |", tpl)
        self.assertIn("| {{stars.dolanmiu/docx:,}} |", tpl)

    def test_prose_stars_bind_to_the_editor_beside_them(self):
        tpl, _ = reportgen.templatize("the two most-starred (WordCraft 16,875★, Plate 16,684★) score 85.9% and 20.6%.\n", self.F)
        self.assertIn("(WordCraft {{stars.storytold/wordcraft:,}}★, Plate {{stars.udecode/plate:,}}★)", tpl)

    def test_a_section_headed_by_a_slug(self):
        tpl, _ = reportgen.templatize("### 7. storytold/wordcraft\n\n**Measured [MEASURED].** 85.9%, text.\n", self.F)
        self.assertIn("**Measured [MEASURED].** {{rt.wordcraft.weighted:.1f}}%", tpl)


class Bombs(unittest.TestCase):
    F = dict(FACTS, **{"bomb.fidus.grade": 0.72, "bomb.eigenpal.grade": 0.56, "bomb.eigenpal-editor.grade": 0.56,
                       "bomb.folio.grade": 0.56, "bomb.folio-editor.grade": 0.56, "bomb.wordcraft.grade": 0.6,
                       "bomb.cells": 150, "bomb.count.sanitation": 39, "bomb.count.preserved": 51,
                       "bomb.count.hang": 4, "rt.lo_baseline.failed": 4})

    def test_grades_bind_per_lane(self):
        text = ("| Editor | Grade | Still unsafe |\n| --- | --- | --- |\n| Fidus Writer | 0.72 | x |\n"
                "| eigenpal store | 0.56 | x |\n| eigenpal editor | 0.56 | x |\n| Folio model | 0.56 | x |\n"
                "| Folio editor | 0.56 | x |\n| wordcraft | 0.60 | x |\n")
        tpl, _ = reportgen.templatize(text, self.F)
        for key in ("fidus", "eigenpal", "eigenpal-editor", "folio", "folio-editor", "wordcraft"):
            self.assertIn("{{bomb.%s.grade:.2f}}" % key, tpl)

    def test_level_totals_are_trial_wide(self):
        text = ("Of the 150 measured cells, fourteen editors and LibreOffice across the ten packages, "
                "the primary labels are sanitation 39, preserved 51, hang 4.\n")
        tpl, _ = reportgen.templatize(text, self.F)
        self.assertIn("Of the {{bomb.cells}} measured cells", tpl)
        self.assertIn("sanitation {{bomb.count.sanitation}}, preserved {{bomb.count.preserved}}, hang {{bomb.count.hang}}.", tpl)


class ListMarkers(unittest.TestCase):
    def test_a_numbered_list_marker_is_not_a_figure(self):
        facts = {"bomb.count.stack-exhaustion": 5, "bomb.cells": 150}
        text = "5. `stack-exhaustion`. Recursion ran out of call stack.\n### 5. Hang\n"
        tpl, _ = reportgen.templatize(text, facts)
        self.assertEqual(tpl, text)


class Stale(unittest.TestCase):
    def test_a_literal_that_was_a_changed_fact_is_reported(self):
        old = dict(FACTS)
        new = dict(FACTS, **{"rt.folio.weighted": 96.0})
        template = "Folio scores {{rt.folio.weighted:.1f}}%. Earlier: Folio scores 97.5% here.\n"
        hits = reportgen.stale(template, old, new)
        self.assertEqual([(h["key"], h["literal"]) for h in hits], [("rt.folio.weighted", "97.5")])

    def test_an_unchanged_fact_is_not_reported(self):
        template = "Folio scores 97.5% here.\n"
        self.assertEqual(reportgen.stale(template, FACTS, dict(FACTS)), [])


class Published(unittest.TestCase):
    """Every committed template renders to the committed report, byte for byte."""

    def test_every_template_renders_to_its_report(self):
        facts_path = ROOT / "out" / "facts.json"
        templates = sorted((ROOT / "templates").rglob("*.md"))
        self.assertTrue(templates, "no templates under templates/")
        facts = json.loads(facts_path.read_text())
        for t in templates:
            rel = t.relative_to(ROOT / "templates")
            with self.subTest(report=str(rel)):
                self.assertEqual(reportgen.render(t.read_text(), facts), (ROOT / rel).read_text())


if __name__ == "__main__":
    unittest.main()
