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


class Watchdog(unittest.TestCase):
    """Every driver run is bracketed by the bench's word_watchdog.sh, as the bench runs it:
    a modal dialog blocks the driver's own timeouts, and the watchdog's kill makes the driver recycle Word."""
    def test_the_watchdog_watches_the_driver_output_and_log_and_is_stopped_after(self):
        from unittest import mock
        events = []

        class Proc:
            def __init__(self, argv, **kw):
                events.append(("start", argv))
            def terminate(self):
                events.append(("stop",))
            def wait(self, timeout=None):
                return 0

        def run(cmd, **kw):
            events.append(("driver", cmd))
            return mock.Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "a.docx"
            src.write_bytes(b"x")
            out = Path(tmp) / "out"
            with mock.patch.object(word_batch.subprocess, "Popen", Proc), \
                 mock.patch.object(word_batch.subprocess, "run", run):
                word_batch.run({"a": src}, out)
        self.assertEqual([e[0] for e in events], ["start", "driver", "stop"])
        argv = events[0][1]
        self.assertEqual(argv[0], str(word_batch.WATCHDOG))
        work = events[1][1][events[1][1].index("--out") + 1]
        self.assertIn(work, argv)
        self.assertIn(str(out / "word_driver.log"), argv)

    def test_the_watchdog_is_vendored_beside_the_driver(self):
        self.assertTrue(word_batch.WATCHDOG.exists())
        self.assertEqual(word_batch.WATCHDOG.parent, word_batch.DRIVER.parent)


if __name__ == "__main__":
    unittest.main()
