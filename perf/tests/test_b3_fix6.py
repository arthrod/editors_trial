"""Real Chromium integration regressions for issue #135: settled ink is mandatory."""
import unittest
from perf.tests import test_b3_fix5 as helpers

class SettledInkHosts(unittest.TestCase):
    server = None
    corpus = None
    setUpClass = classmethod(helpers.DocumentQuietHosts.setUpClass.__func__)
    tearDownClass = classmethod(helpers.DocumentQuietHosts.tearDownClass.__func__)
    probe = helpers.DocumentQuietHosts.probe

    def assert_refused(self, name):
        result = self.probe('b3_fix6_' + name + '.html')
        self.assertGreater(result['frames_total'], 0, result)
        self.assertIsNone(result['usable_ms'], result)
        self.assertEqual(result['surface_reason'], 'document_surface_absent')

    def test_stripe_to_uniform(self):
        self.assert_refused('stripe_to_uniform')

    def test_pattern_then_blank(self):
        self.assert_refused('pattern_then_blank')

    def test_flash_then_uniform(self):
        self.assert_refused('flash_then_uniform')

    def test_uniform_half_paint(self):
        self.assert_refused('uniform_half_paint')
