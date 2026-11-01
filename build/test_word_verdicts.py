#!/usr/bin/env python3
"""word_verdicts.py measures either the round-trip outputs or the broken-corpus outputs, into separate files."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import word_verdicts as wv  # noqa: E402


class Sets(unittest.TestCase):
    def test_the_default_set_is_the_round_trip_outputs(self):
        s = wv.SETS["outputs"]
        self.assertEqual(s["src"], wv.ROOT / "out")
        self.assertEqual(s["json"], wv.ROOT / "out" / "word_verdicts.json")

    def test_the_broken_set_reads_out_broken_and_writes_its_own_file(self):
        s = wv.SETS["broken"]
        self.assertEqual(s["src"], wv.ROOT / "out_broken")
        self.assertEqual(s["json"], wv.ROOT / "out" / "word_verdicts_broken.json")
        self.assertNotEqual(s["work"], wv.SETS["outputs"]["work"])

    def test_targets_are_only_the_outputs_that_exist(self):
        t = wv.targets("broken")
        self.assertIn("apryse", t)
        self.assertNotIn("plate", t)   # Plate produced no output from the broken corpus
        self.assertTrue(all(p.name == "complex.docx" and p.exists() for p in t.values()))

    def test_arguments(self):
        self.assertEqual(wv.parse(["--set", "broken"]).set, "broken")
        a = wv.parse(["--reread", "/tmp/x"])
        self.assertEqual((a.set, a.reread), ("outputs", Path("/tmp/x")))


class NoWordOnImport(unittest.TestCase):
    """Importing a script that drives Word must never open Word (2026-11-01: an import ran a whole batch)."""
    def test_importing_the_word_scripts_does_not_run_the_driver(self):
        import importlib
        import word_batch
        calls = []
        real, word_batch.run = word_batch.run, lambda *a, **k: calls.append(a) or {}
        try:
            for name in ("word_verdicts", "word_render_all", "verify_deliverables"):
                sys.modules.pop(name, None)
                importlib.import_module(name)
        finally:
            word_batch.run = real
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
