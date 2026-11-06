import unittest

from perf.analysis.publication_gate import trial_publishable_flags


def _env(**kw):
    base = {
        "host_class": "ci_coarse",
        "execution_profile": "ci_contract",
        "run_kind": "timing",
        "repetition_unit": "fresh_process",
    }
    base.update(kw)
    return base


class Gate(unittest.TestCase):
    def test_ci_model_may_publish_subject_to_sample_count(self):
        pub, reason = trial_publishable_flags(_env(), "model", 1)
        self.assertFalse(pub)
        self.assertIn("n>=2", reason)
        pub2, _ = trial_publishable_flags(_env(), "model", 2)
        self.assertTrue(pub2)

    def test_visible_blocked_on_ci(self):
        pub, reason = trial_publishable_flags(_env(), "browser_visible", 30)
        self.assertFalse(pub)
        self.assertIn("ci_coarse", reason)


if __name__ == "__main__":
    unittest.main()
