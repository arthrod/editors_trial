"""The apryse key gate must read the same variable the trial's .env provides."""

import os
import unittest
from unittest import mock

from perf.runner.benchmark_warm_cold import _apryse_key_present


class ApryseKeyGateTest(unittest.TestCase):
    def test_env_file_variable_name_is_honoured(self):
        # The trial's .env ships APRYSE_API_KEY (the capture pipeline reads it);
        # the perf runner must not skip apryse when that variable is set.
        with mock.patch.dict(os.environ, {"APRYSE_API_KEY": "demo:key"}, clear=False):
            for name in ("APRYSE_LICENSE_KEY", "PDFTRON_LICENSE_KEY", "TRIAL_KEY"):
                os.environ.pop(name, None)
            self.assertTrue(_apryse_key_present())

    def test_absent_everywhere_is_false(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_apryse_key_present())


if __name__ == "__main__":
    unittest.main()
