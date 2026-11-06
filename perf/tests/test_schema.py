import unittest

from perf.schema import validate_trial


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


if __name__ == "__main__":
    unittest.main()
