import unittest

import tempfile
from pathlib import Path

from perf.fixtures.generate import build_workload, correctness_fixtures
from perf.fixtures.profiles import (
    allowed_workloads,
    assert_not_hostile,
    assert_workload_allowed,
    feature_profile,
    size_ladder,
    with_fallback,
)


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


class Ladder(unittest.TestCase):
    def test_ladder_ids_are_unique_and_named(self):
        rows = size_ladder()
        ids = [row["workload_id"] for row in rows]
        self.assertEqual(ids, [
            "micro-paragraphs",
            "micro-search",
            "short-paragraphs",
            "long-paragraphs",
            "one-paragraph",
            "mixed-utf8",
            "search-dense",
            "paginated-equivalent",
        ])
        self.assertEqual(len(set(ids)), len(ids))

    def test_search_profile_bytes_contain_the_declared_matches(self):
        search = [row for row in size_ladder() if row["workload_id"] == "search-dense"][0]
        built = build_workload(search)
        self.assertEqual(built["body"].count(b"NEEDLE"), 1000)
        self.assertEqual(built["match_count"], 1000)

    def test_mixed_utf8_profile_builds(self):
        mixed = [row for row in size_ladder() if row["workload_id"] == "mixed-utf8"][0]
        built = build_workload(mixed)
        text = built["body"].decode("utf-8")
        self.assertIn("e\u0301", text)
        self.assertIn("\U0002000b", text)

    def test_shapes_are_not_treated_as_one_workload(self):
        rows = {row["workload_id"]: row for row in size_ladder()}
        self.assertGreater(rows["long-paragraphs"]["paragraph_chars"], rows["short-paragraphs"]["paragraph_chars"])
        self.assertEqual(rows["one-paragraph"]["paragraphs"], 1)
        self.assertEqual(rows["paginated-equivalent"]["shape"], "pages")

    def test_hostile_corpus_is_the_resolved_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "hostile"
            inside = root / "bombs"
            inside.mkdir(parents=True)
            target = inside / "input.docx"
            target.write_bytes(b"x")
            link = Path(tmp) / "outside.docx"
            link.symlink_to(target)
            with self.assertRaises(ValueError) as caught:
                assert_not_hostile(link, root)
            self.assertIn("hostile", str(caught.exception))
            named = Path(tmp) / "notes-about-bombs.txt"
            named.write_text("bombs", encoding="utf-8")
            assert_not_hostile(named, root)


class WorkloadCaps(unittest.TestCase):
    def test_contract_allows_micro_only(self):
        allowed = allowed_workloads("ci_contract")
        self.assertEqual(allowed, frozenset({"micro-paragraphs", "micro-search"}))
        assert_workload_allowed("ci_contract", "micro-paragraphs")
        with self.assertRaises(ValueError) as caught:
            assert_workload_allowed("ci_contract", "short-paragraphs")
        self.assertIn("workload cap", str(caught.exception))

    def test_dedicated_allows_the_full_ladder(self):
        ladder_ids = {row["workload_id"] for row in size_ladder()}
        self.assertEqual(allowed_workloads("dedicated_publish"), frozenset(ladder_ids))


if __name__ == "__main__":
    unittest.main()
