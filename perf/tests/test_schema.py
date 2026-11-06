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


if __name__ == "__main__":
    unittest.main()
