#!/usr/bin/env python3
"""The protection level is not the safety field."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protection


class ProtectionTest(unittest.TestCase):
    def test_a_named_ceiling_is_not_the_safety_word(self):
        self.assertEqual(
            protection.classify("refused", "bounded-reject", "limit-exceeded: DOCX exceeds maxEntryBytes"),
            "bounded-refusal",
        )
        self.assertEqual(
            protection.classify("refused", "bounded-reject", "limit exceeded: XML nesting too deep"),
            "bounded-refusal",
        )
        self.assertEqual(
            protection.classify("refused", "bounded-reject", "INPUT_LIMIT: entry count"),
            "bounded-refusal",
        )
        self.assertEqual(
            protection.classify(
                "refused",
                "bounded-reject",
                "INVALID_XML: element <w:p>: element exceeds 1024 attributes",
            ),
            "bounded-refusal",
        )

    def test_stack_overflow_is_not_a_ceiling(self):
        self.assertEqual(
            protection.classify("refused", "bounded-reject", "RangeError: Maximum call stack size exceeded"),
            "stack-exhaustion",
        )

    def test_a_parse_refusal_is_erroring(self):
        self.assertEqual(
            protection.classify("refused", "bounded-reject", "invalid-package: DOCX XML must not contain a document type declaration"),
            "erroring",
        )
        self.assertEqual(
            protection.classify("refused", "bounded-reject", "External entities are not supported"),
            "erroring",
        )

    def test_a_clean_drop_is_sanitation_and_a_kept_weapon_is_not(self):
        self.assertEqual(protection.classify("dropped", "ok", ""), "sanitation")
        self.assertEqual(protection.classify("preserved", "ok", ""), "preserved")
        self.assertEqual(
            protection.classify("preserved", "bounded-reject", "still there"),
            "errored-but-preserved",
        )

    def test_hang_crash_leak_and_a_silent_miss_stay_distinct(self):
        self.assertEqual(protection.classify("refused", "hang", ""), "hang")
        self.assertEqual(protection.classify("preserved", "crash", ""), "crash")
        self.assertEqual(protection.classify("dropped", "leak", ""), "leak")
        self.assertEqual(
            protection.classify("refused", "ok", "Error: source file could not be loaded"),
            "failed-load-exit-zero",
        )

    def test_a_markdown_view_that_cannot_carry_the_weapon_is_not_sanitation(self):
        self.assertEqual(protection.classify("not-in-view", "ok", ""), "not-in-view")
        self.assertEqual(protection.classify("not-run", "not-run", ""), "not-run")

    def test_unexpanded_entity_references_are_not_sanitation(self):
        self.assertEqual(
            protection.classify("preserved", "ok", "BOMB_BODY_OK\n&lol6;&xxe;&canary;"),
            "unexpanded-kept",
        )
        self.assertEqual(
            protection.classify("preserved", "ok", "BOMB_LOL &lol6;"),
            "preserved",
        )
        self.assertIn("unexpanded-kept", protection.LEVELS)
        self.assertIn("bounded-delivery", protection.LEVELS)


if __name__ == "__main__":
    unittest.main()


class DocxodusCeilingTest(unittest.TestCase):
    """Docxodus 15 names its ceilings as snake_case error codes."""

    def test_depth_code_is_a_named_ceiling(self):
        ev = "Error: xml_depth_limit_exceeded: /word/document.xml nests deeper than the 128 level safety limit."
        self.assertEqual(protection.classify("refused", "bounded-reject", ev), "bounded-refusal")

    def test_ratio_code_is_a_named_ceiling(self):
        ev = "Error: compression_ratio_limit_exceeded: measuring /word/document.xml for the XML depth limit would pass the package limits."
        self.assertEqual(protection.classify("refused", "bounded-reject", ev), "bounded-refusal")

    def test_label_phrases_name_the_ceiling(self):
        import label_protection as L
        self.assertEqual(L.phrase_for("Error: compression_ratio_limit_exceeded: x", "bounded-refusal"),
                         "named ceiling on compression ratio")
        self.assertEqual(L.phrase_for("Error: xml_depth_limit_exceeded: x", "bounded-refusal"),
                         "named ceiling on element depth")


class DocxodusDtdTest(unittest.TestCase):
    def test_dtd_prohibited_is_named(self):
        import label_protection as L
        self.assertEqual(protection.classify("refused", "bounded-reject", "Error: Xml_DtdIsProhibitedEx"), "erroring")
        self.assertEqual(L.phrase_for("Error: Xml_DtdIsProhibitedEx", "erroring"), "rejected a document type declaration")
