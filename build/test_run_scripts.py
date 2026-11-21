"""Static checks on the shell scripts that drive the measurement."""
import re
import unittest
from pathlib import Path

BUILD = Path(__file__).resolve().parent


class SecondPassEvidenceTest(unittest.TestCase):
    def test_docsplus_second_pass_keeps_its_own_evidence(self):
        # The docs.plus harness writes evidence.json (import warnings, revision
        # hits) next to itself unless EVIDENCE_DIR says otherwise. The second
        # pass feeds it its own output, so without a separate directory the
        # second pass overwrites the first pass's evidence with that of a
        # different input.
        text = (BUILD / "run_second_pass.sh").read_text()
        block = text[text.index("second docsplus"):]
        block = block[: block.index("\n\n")] if "\n\n" in block else block
        self.assertRegex(block, r"EVIDENCE_DIR=\S*out/docsplus/second/evidence")


class BrokenCorpusInputTest(unittest.TestCase):
    """run_broken.sh must hand every editor the broken corpus and an out_broken/ path (2026-11-01:
    Plate got an unset $IN_BROKEN and canvas the clean fixture by default)."""
    def setUp(self):
        self.text = (BUILD / "run_broken.sh").read_text()

    def line(self, name):
        return next(l for l in self.text.splitlines() if l.startswith(f"run {name} "))

    def test_every_variable_the_script_uses_is_set_in_it(self):
        used = set(re.findall(r"\$\{?([A-Z_][A-Z0-9_]*)", self.text))
        set_here = set(re.findall(r"^\s*([A-Z_][A-Z0-9_]*)=", self.text, re.M))
        # TRIAL_ROOT is the one variable a runner reads from outside: where the checkout is.
        self.assertEqual(used - set_here, {"TRIAL_ROOT"})

    def test_every_editor_reads_the_broken_corpus(self):
        for l in self.text.splitlines():
            if l.startswith("run "):
                self.assertIn("$IN", l, l.split()[1])

    def test_canvas_is_told_its_input_and_output(self):
        l = self.line("canvas")
        self.assertIn("IN_DOCX=$IN", l)
        self.assertIn("OUT_DIR=$OUTROOT/canvas", l)

    def test_libreoffice_output_is_named_like_every_other_editors(self):
        # soffice names its output after the input (complex_broken.docx); the scan reads complex.docx.
        lo = self.text[self.text.index("soffice"):self.text.index("run plate")]
        self.assertIn('mv "$OUTROOT/lo_baseline/complex_broken.docx" "$OUTROOT/lo_baseline/complex.docx"', lo)

    def test_docsplus_keeps_its_broken_corpus_evidence_apart(self):
        # Without EVIDENCE_DIR the docs.plus harness overwrites the round trip's
        # harness/docsplus/evidence with the broken corpus's (2026-11-01).
        self.assertIn("EVIDENCE_DIR=$OUTROOT/docsplus/evidence", self.line("docsplus"))

    def test_the_output_root_can_be_a_scratch_directory(self):
        self.assertIn("OUTROOT=${OUTROOT:-", self.text)


class CheckoutRootTest(unittest.TestCase):
    """The runners measure the checkout they are in. They once named one path on one machine,
    so a run from a worktree read and wrote another checkout (2026-11-21); the release
    checklist's own advice, to run a frozen copy, needs TRIAL_ROOT for the same reason."""
    RUNNERS = ("run_all.sh", "run_second_pass.sh", "run_broken.sh")
    IDIOM = 'BASE="${TRIAL_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"'

    def test_every_runner_finds_its_checkout_the_same_way(self):
        for name in self.RUNNERS:
            lines = [l for l in (BUILD / name).read_text().splitlines() if re.match(r"\s*BASE=", l)]
            self.assertEqual(lines, [self.IDIOM], name)

    def test_no_runner_or_scorer_names_a_checkout_path(self):
        for name in self.RUNNERS + ("score_all.py", "score_extra.py"):
            self.assertNotIn("/Users/", (BUILD / name).read_text(), name)

    def test_a_runner_copied_out_of_the_checkout_is_told_where_it_is(self):
        # release_broken.sh runs a frozen copy of run_broken.sh from its work folder.
        text = (BUILD / "release_broken.sh").read_text()
        self.assertIn('TRIAL_ROOT="$B" OUTROOT="$L/broken$i" bash "$L/run_broken.copy.sh"', text)

    def test_the_scorers_take_the_same_override(self):
        for name in ("score_all.py", "score_extra.py"):
            self.assertIn('os.environ.get("TRIAL_ROOT")', (BUILD / name).read_text(), name)


if __name__ == "__main__":
    unittest.main()
