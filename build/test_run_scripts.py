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


if __name__ == "__main__":
    unittest.main()
