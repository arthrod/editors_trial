import unittest

from perf.schema import validate_trial, dump_trial, load_trial, validate_environment


def _trial(boundary, claim):
    return {
        "outcome": "measured",
        "boundary": boundary,
        "claims": [claim],
        "samples_ms": [1.0],
        "latency_ms": None,
    }


class BoundaryClaims(unittest.TestCase):
    def test_raf_callback_cannot_claim_visible_paint(self):
        with self.assertRaises(ValueError) as caught:
            validate_trial(_trial("raf_callback", "visible_paint"))
        self.assertIn("raf_callback cannot claim visible paint", str(caught.exception))

    def test_constructor_return_cannot_claim_usable(self):
        with self.assertRaises(ValueError) as caught:
            validate_trial(_trial("constructor_return", "usable"))
        self.assertIn("constructor_return cannot claim usable", str(caught.exception))

    def test_model_ready_cannot_claim_user_visible(self):
        with self.assertRaises(ValueError) as caught:
            validate_trial(_trial("model_ready", "user_visible"))
        self.assertIn("model_ready cannot claim user-visible latency", str(caught.exception))

    def test_paint_boundary_may_claim_visible_paint(self):
        validate_trial(_trial("first_contentful_paint", "visible_paint"))


class Outcomes(unittest.TestCase):
    def test_unsupported_rejects_zero_latency(self):
        trial = {
            "outcome": "unsupported",
            "boundary": "input_to_next_paint",
            "claims": [],
            "samples_ms": [],
            "latency_ms": 0,
        }
        with self.assertRaises(ValueError) as caught:
            validate_trial(trial)
        self.assertIn("non-measured latency must be null", str(caught.exception))

    def test_failed_rejects_samples(self):
        trial = {
            "outcome": "failed",
            "boundary": "first_usable",
            "claims": [],
            "samples_ms": [12.0],
            "latency_ms": None,
            "failure_reason": "timeout",
        }
        with self.assertRaises(ValueError) as caught:
            validate_trial(trial)
        self.assertIn("non-measured samples must be empty", str(caught.exception))

    def test_measured_zero_is_a_real_sample(self):
        validate_trial({
            "outcome": "measured",
            "boundary": "handler_duration",
            "claims": [],
            "samples_ms": [0.0],
            "latency_ms": None,
        })

    def test_unknown_outcome_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            validate_trial({
                "outcome": "skipped",
                "boundary": "handler_duration",
                "claims": [],
                "samples_ms": [],
                "latency_ms": None,
            })
        self.assertIn("unknown outcome", str(caught.exception))

    def test_not_run_is_distinct_from_failed(self):
        validate_trial({
            "outcome": "not_run",
            "boundary": "process_spawn",
            "claims": [],
            "samples_ms": [],
            "latency_ms": None,
            "failure_reason": "harness-seatbelt",
        })

    def test_scalar_samples_are_not_an_empty_list(self):
        with self.assertRaises(ValueError) as caught:
            validate_trial({
                "outcome": "unsupported",
                "boundary": "input_to_next_paint",
                "claims": [],
                "samples_ms": 0,
                "latency_ms": None,
            })
        self.assertIn("samples_ms", str(caught.exception))

    def test_failed_and_not_run_require_a_reason(self):
        for outcome in ("failed", "not_run"):
            with self.assertRaises(ValueError) as caught:
                validate_trial({
                    "outcome": outcome,
                    "boundary": "first_usable",
                    "claims": [],
                    "samples_ms": [],
                    "latency_ms": None,
                })
            self.assertIn("failure_reason", str(caught.exception))


class RoundTrip(unittest.TestCase):
    def test_dump_and_load_preserve_samples(self):
        trial = {
            "schema_version": 1,
            "editor_id": "superdoc",
            "outcome": "measured",
            "boundary": "model_ready",
            "claims": [],
            "samples_ms": [3.5, 4.0],
            "latency_ms": None,
            "criterion_id": "C02",
        }
        loaded = load_trial(dump_trial(trial))
        self.assertEqual(loaded["samples_ms"], [3.5, 4.0])
        self.assertEqual(loaded["criterion_id"], "C02")

    def test_dump_rejects_a_zero_for_unverified(self):
        trial = {
            "schema_version": 1,
            "editor_id": "wordcraft",
            "outcome": "unverified",
            "boundary": "input_to_next_paint",
            "claims": [],
            "samples_ms": [],
            "latency_ms": 0,
            "criterion_id": "C23",
        }
        with self.assertRaises(ValueError) as caught:
            dump_trial(trial)
        self.assertIn("non-measured latency must be null", str(caught.exception))


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
            validate_environment(_env(host_class="ci_coarse", execution_profile="dedicated_publish", headless=True, display_refresh_hz=None))
        self.assertIn("dedicated_publish", str(caught.exception))

    def test_ci_contract_requires_headless(self):
        with self.assertRaises(ValueError) as caught:
            validate_environment(_env(host_class="ci_coarse", execution_profile="ci_contract", headless=False))
        self.assertIn("ci_contract", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
