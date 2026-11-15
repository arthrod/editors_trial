"""C14 reads the whole document of editors whose page shows only a window of it (#183).

Folio and SuperDoc mount only the pages near the start of a long document and
WordCraft paints into a canvas, so the page read never reached C14's I01-I03
lines. The probe now asks the editor itself, after the timed sample:
SuperDoc's model, Folio's hidden ProseMirror model, or the editor's own
select all + copy.
"""

from __future__ import annotations

import unittest

import perf.runner.benchmark_document as bd
from perf.analysis.interpretation import check_correctness
from perf.scenarios.catalog import scenarios
from perf.tests import test_b3_document as b3  # noqa: F401 (server and probe helpers)

C14 = next(row for row in scenarios() if row["id"] == "C14")
# UTF-16 code units, as the page counts them: the I01-I03 lines hold astral characters.
FAKE_CHARS = 285077
CLOSING = "ZZ-END-OF-DOCUMENT c14-fake"


class ProbeReadsTheWholeText(unittest.TestCase):
    """The real probe in Chromium against fake hosts that keep the document in script."""

    setUpClass = classmethod(b3.FakeHostMeasurers.setUpClass.__func__)
    tearDownClass = classmethod(b3.FakeHostMeasurers.tearDownClass.__func__)
    probe = b3.FakeHostMeasurers.probe

    def _assert_whole(self, payload, source):
        whole = payload.get("c14_text")
        self.assertIsInstance(whole, dict, payload.keys())
        self.assertIsNone(whole["error"], whole)
        self.assertEqual(whole["source"], source)
        self.assertEqual(whole["chars"], FAKE_CHARS)
        self.assertLessEqual(len(whole["head"]), 4000)
        self.assertTrue(whole["tail"].endswith(CLOSING), whole["tail"][-80:])
        # The page itself shows one paragraph: the old read could never pass.
        self.assertFalse(check_correctness(C14["correctness"], payload.get("document_text"))[0])
        ok, reason = check_correctness(C14["correctness"], bd.c14_correctness_text(payload))
        self.assertTrue(ok, reason)

    def test_a_canvas_editor_is_read_by_its_own_select_all_and_copy(self):
        payload = self.probe("scale", "c14_canvas_copy.html", ["--editor", "wordcraft"])
        self._assert_whole(payload, "select_all_copy")

    def test_superdoc_is_read_from_its_model(self):
        payload = self.probe("scale", "c14_model_text.html", ["--editor", "superdoc"])
        self._assert_whole(payload, "superdoc_model")

    def test_folio_is_read_from_its_hidden_prosemirror_model(self):
        payload = self.probe("scale", "c14_folio_pm.html", ["--editor", "folio"])
        self._assert_whole(payload, "folio_pm_model")

    def test_a_copy_that_never_happens_is_an_error_not_a_document(self):
        payload = self.probe("scale", "c14_canvas_copy.html?nocopy",
                             ["--editor", "wordcraft", "--c14-copy-wait-ms", "1500"])
        whole = payload.get("c14_text")
        self.assertIsNotNone(whole)
        self.assertIsNone(whole["chars"])
        self.assertIn("clipboard unchanged", whole["error"])
        # The check falls back to the page read.
        self.assertEqual(bd.c14_correctness_text(payload),
                         bd.c14_correctness_text({k: v for k, v in payload.items() if k != "c14_text"}))

    def test_a_missing_focus_target_fails_fast(self):
        payload = self.probe("scale", "c14_model_text.html",
                             ["--editor", "wordcraft", "--c14-copy-wait-ms", "1500"])
        whole = payload.get("c14_text")
        self.assertIn("not found", whole["error"])
        self.assertLess(whole["read_ms"], 10_000)

    def test_other_editors_keep_the_page_read(self):
        payload = self.probe("scale", "b3_long_fixture_at_end.html", ["--editor", "plate"])
        self.assertIsNone(payload.get("c14_text"))


class CorrectnessTextPrefersTheWholeRead(unittest.TestCase):
    WHOLE = {"source": "select_all_copy", "chars": 2_024_050, "head": "Article 1.",
             "tail": "Hello\n" + CLOSING, "error": None}
    PROSE = {"augmented_paragraphs": 4, "closing": CLOSING, "text_chars": 2_024_047}

    def test_the_whole_read_is_checked_head_and_tail(self):
        payload = {"document_text": "Article 1.", "document_text_chars": 9305, "c14_text": self.WHOLE}
        self.assertEqual(bd.c14_correctness_text(payload), "Article 1.\nHello\n" + CLOSING)

    def test_a_failed_whole_read_falls_back_to_the_page(self):
        payload = {"document_text": "Article 1.", "document_text_chars": 9305,
                   "c14_text": {**self.WHOLE, "chars": None, "head": None, "tail": None, "error": "boom"}}
        self.assertEqual(bd.c14_correctness_text(payload), "Article 1.")

    def test_a_whole_read_that_fails_the_check_is_the_editors_failure(self):
        payload = {"document_text": "Article 1.", "document_text_chars": 9305, "c14_text": self.WHOLE}
        self.assertIsNone(bd.c14_correctness_limit(payload, self.PROSE))

    def test_an_empty_whole_read_is_a_failed_read(self):
        # Review of e0c237de, L1: an error-free empty copy must not override the page's text.
        empty = {**self.WHOLE, "chars": 0, "head": "", "tail": ""}
        payload = {"document_text": "Article 1.", "document_text_chars": 9305, "c14_text": empty}
        self.assertEqual(bd.c14_correctness_text(payload), "Article 1.")
        self.assertEqual(bd.c14_correctness_limit(payload, self.PROSE)["reason"], bd.C14_TEXT_WINDOW)

    def test_the_evidence_names_the_text_that_was_checked(self):
        # Review of e0c237de, M2: the record said "rendered DOM text" whatever was read.
        whole = bd.c14_correctness_evidence({"document_text": "x", "c14_text": self.WHOLE})
        self.assertIn("select_all_copy", whole)
        self.assertNotIn("rendered DOM", whole)
        page = bd.c14_correctness_evidence({"document_text": "x"})
        self.assertIn("probe's document text", page)

    def test_a_short_whole_read_is_still_a_window(self):
        short = {**self.WHOLE, "chars": 9305, "tail": "Article 9."}
        payload = {"document_text": "Article 1.", "document_text_chars": 9305, "c14_text": short}
        self.assertEqual(bd.c14_correctness_limit(payload, self.PROSE)["reason"], bd.C14_TEXT_WINDOW)


if __name__ == "__main__":
    unittest.main()
