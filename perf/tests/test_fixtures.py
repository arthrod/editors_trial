import unittest

from perf.fixtures.generate import build_workload


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


if __name__ == "__main__":
    unittest.main()
