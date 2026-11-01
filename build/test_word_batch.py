#!/usr/bin/env python3
"""Word verdicts and PDFs come from the audited driver's manifest, not from our own osascript."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import word_batch  # noqa: E402


def rec(name, status, error="", kind="pdf"):
    return {"original_filename": name, "status": status, "kind": kind, "error": error,
            "converted_filename": name.replace(".docx", "_byword.pdf") if status == "ok" else ""}


class Verdict(unittest.TestCase):
    def test_an_exported_pdf_means_word_opened_it(self):
        self.assertEqual(word_batch.verdict(rec("plate.docx", "ok")), "OPENED")

    def test_a_declined_repair_prompt_is_a_refusal(self):
        r = rec("folio.docx", "failed", "repair prompt declined; Word could not read it (empty)")
        self.assertEqual(word_batch.verdict(r), "REFUSED")

    def test_a_file_word_opened_no_document_for_is_a_refusal_too(self):
        # The watchdog does not always record that it declined the prompt; the
        # driver then reports the empty load. Either way Word did not open it.
        r = rec("folio.docx", "failed", "Word could not load it in 2 passes: open produced 0 new documents, "
                "none named 00009__trial__folio.docx; refusing to guess")
        self.assertEqual(word_batch.verdict(r), "REFUSED")

    def test_any_other_failure_is_named_not_guessed(self):
        r = rec("x.docx", "failed", "timeout after 180 s")
        self.assertEqual(word_batch.verdict(r), "FAILED: timeout after 180 s")


class Manifest(unittest.TestCase):
    def test_the_last_pdf_record_per_file_wins_and_renames_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = Path(tmp) / "manifest.jsonl"
            lines = [rec("a.docx", "failed", "timeout"), rec("a.docx", "ok"),
                     {"original_filename": "b.docx", "status": "renamed", "kind": "rename"},
                     rec("b.docx", "failed", "repair prompt declined; Word could not read it")]
            m.write_text("".join(json.dumps(x) + "\n" for x in lines))
            got = word_batch.read_manifest(m)
            self.assertEqual({k: word_batch.verdict(v) for k, v in got.items()},
                             {"a": "OPENED", "b": "REFUSED"})


if __name__ == "__main__":
    unittest.main()
