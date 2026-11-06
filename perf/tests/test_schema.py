import unittest

from perf.schema import sample_budget_for_profile, validate_environment, validate_sample_budget


def _env(**overrides):
    env = {
        "host_class": "dedicated",
        "execution_profile": "dedicated_publish",
        "cpu_model": "unspecified-test-cpu",
        "os": "linux",
        "arch": "x86_64",
        "ram_bytes": 16 * 1024 ** 3,
        "power_source": "ac",
        "editor_id": "plate",
        "editor_version": "60c7f5530",
        "fixture_sha256": "a" * 64,
        "cache_state": "process_cold_fs_warm",
        "feature_profile": "P0",
        "workload_id": "flow-short-1mb",
        "repetition_unit": "fresh_process",
        "run_kind": "timing",
        "headless": False,
        "display_refresh_hz": 60,
    }
    env.update(overrides)
    return env


class Environment(unittest.TestCase):
    def test_accepts_a_dedicated_timing_environment(self):
        validate_environment(_env())

    def test_rejects_a_short_fixture_hash(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(fixture_sha256="abc"))
        self.assertIn("fixture_sha256", str(caught.exception))

    def test_headless_allows_a_null_refresh(self):
        validate_environment(_env(headless=True, display_refresh_hz=None))

    def test_headed_run_needs_a_refresh(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(display_refresh_hz=None))
        self.assertIn("display_refresh_hz", str(caught.exception))

    def test_ci_cannot_pretend_to_be_os_cache_cold(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(host_class="ci_coarse", cache_state="os_cache_cold"))
        self.assertIn("os_cache_cold", str(caught.exception))

    def test_hash_must_be_sixty_four_hex_characters_and_nothing_else(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(fixture_sha256=("a" * 64) + "\n"))
        self.assertIn("fixture_sha256", str(caught.exception))

    def test_headless_must_be_a_boolean(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(headless="false"))
        self.assertIn("headless", str(caught.exception))

    def test_refresh_rejects_nan(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(display_refresh_hz=float("nan")))
        self.assertIn("display_refresh_hz", str(caught.exception))

    def test_os_cache_cold_requires_a_recorded_page_cache_drop(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(cache_state="os_cache_cold"))
        self.assertIn("page_cache_dropped", str(caught.exception))
        validate_environment(_env(cache_state="os_cache_cold", page_cache_dropped=True))

    def test_dedicated_publish_cannot_run_on_ci_coarse(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(
                _env(
                    host_class="ci_coarse",
                    execution_profile="dedicated_publish",
                    headless=True,
                    display_refresh_hz=None,
                )
            )
        self.assertIn("dedicated_publish", str(caught.exception))

    def test_ci_contract_requires_headless(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(
                _env(host_class="ci_coarse", execution_profile="ci_contract", headless=False)
            )
        self.assertIn("ci_contract", str(caught.exception))


class SampleBudget(unittest.TestCase):
    def test_contract_uses_one_fresh_process(self):
        self.assertEqual(sample_budget_for_profile("ci_contract", "fresh_process"), 1)

    def test_dedicated_wasm_uses_five_hundred_iterations(self):
        self.assertEqual(
            sample_budget_for_profile("dedicated_publish", "in_process_iteration"), 500
        )

    def test_ci_broad_rejects_an_extra_attempt(self):
        env = _env(
            host_class="ci_coarse",
            execution_profile="ci_broad",
            headless=False,
            display_refresh_hz=60,
        )
        with self.assertRaises(ValueError) as caught:
            validate_sample_budget(env, 6)
        self.assertIn("sample budget", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
