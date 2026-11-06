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


from perf.fixtures.profiles import feature_profile, with_fallback


class FeatureProfiles(unittest.TestCase):
    def test_p0_has_no_optional_features(self):
        profile = feature_profile("P0")
        self.assertEqual(profile["collaboration"], "off")
        self.assertEqual(profile["ai_panel"], "off")
        self.assertEqual(profile["proofing"], "off")

    def test_p3_names_a_busy_panel(self):
        profile = feature_profile("P3")
        self.assertEqual(profile["busy_panel"], "on")
        self.assertEqual(profile["proofing"], "on")

    def test_fallback_keeps_the_requested_name_and_lists_what_dropped(self):
        dropped = with_fallback(feature_profile("P2"), ["proofing"])
        self.assertEqual(dropped["name"], "P2")
        self.assertEqual(dropped["disabled_features"], ["proofing"])
        self.assertEqual(dropped["proofing"], "off")

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            feature_profile("P9")
        self.assertIn("feature profile", str(caught.exception))

    def test_fallback_rejects_metadata_keys(self):
        with self.assertRaises(ValueError) as caught:
            with_fallback(feature_profile("P2"), ["name"])
        self.assertIn("unknown feature", str(caught.exception))
        self.assertEqual(feature_profile("P2")["name"], "P2")


if __name__ == "__main__":
    unittest.main()
