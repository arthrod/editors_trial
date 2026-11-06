import unittest

from perf.fixtures.generate import build_workload, correctness_fixtures


SHORT = {
    "workload_id": "short-paragraphs",
    "paragraphs": 3,
    "paragraph_chars": 5,
    "unicode_class": "ascii",
    "match_count": 0,
    "seed": 1,
}


class BuildWorkload(unittest.TestCase):
    def test_same_profile_same_hash(self):
        first = build_workload(SHORT)
        second = build_workload(SHORT)
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(len(first["sha256"]), 64)
        self.assertEqual(first["body"].count(b"\n"), 3)

    def test_more_paragraphs_change_the_hash(self):
        other = dict(SHORT, paragraphs=4)
        self.assertNotEqual(build_workload(SHORT)["sha256"], build_workload(other)["sha256"])


class CorrectnessFixtures(unittest.TestCase):
    def test_unicode_keeps_a_combining_mark_and_a_non_bmp_scalar(self):
        body = correctness_fixtures()["unicode"].decode("utf-8")
        self.assertIn("e\u0301", body)
        self.assertIn("𠀋", body)

    def test_emoji_fixture_contains_zwj_family_and_skin_tone(self):
        body = correctness_fixtures()["emoji"].decode("utf-8")
        self.assertIn("👨‍👩‍👧‍👦", body)
        self.assertIn("👍🏻", body)

    def test_bidi_fixture_keeps_logical_order(self):
        body = correctness_fixtures()["bidi"].decode("utf-8")
        self.assertLess(body.index("Hello"), body.index("مرحبا"))

    def test_ime_fixture_is_the_committed_string_only(self):
        body = correctness_fixtures()["ime_committed"].decode("utf-8")
        self.assertEqual(body, "地\n")
        self.assertNotIn("di", body)


if __name__ == "__main__":
    unittest.main()
