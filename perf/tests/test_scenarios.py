import unittest

from perf.scenarios.catalog import scenarios


class Catalog(unittest.TestCase):
    def test_ids_are_exactly_the_twenty_four_criteria(self):
        ids = [row["id"] for row in scenarios()]
        self.assertEqual(ids, ["C%02d" % n for n in range(1, 25)])

    def test_startup_keeps_three_cache_states(self):
        startup = scenarios()[0]
        self.assertEqual(startup["id"], "C01")
        self.assertEqual(startup["cache_states"], [
            "process_cold_fs_warm",
            "os_cache_cold",
            "warm_steady",
        ])
        self.assertEqual(startup["repetition_unit"], "fresh_process")

    def test_visible_scenarios_do_not_use_a_raf_callback(self):
        for row in scenarios():
            if row["layer"] == "browser_visible":
                forbidden = {"raf_callback", "constructor_return", "model_ready"}
                for field in ("boundary", "evidence"):
                    self.assertNotIn(row[field], forbidden)


if __name__ == "__main__":
    unittest.main()
