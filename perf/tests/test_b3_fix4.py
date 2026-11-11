"""Real Chromium integration/smoke regressions for #135 review R3-1 through R3-6."""
import unittest
from perf.tests import test_b3_fix3 as helpers

class SettledDocumentHosts(unittest.TestCase):
    server = None
    corpus = None
    setUpClass = classmethod(helpers.Fix3Hosts.setUpClass.__func__)
    tearDownClass = classmethod(helpers.Fix3Hosts.tearDownClass.__func__)
    def probe(self, mode, host, extra):
        import subprocess, json
        from pathlib import Path
        script = Path(__file__).parent / 'fixtures/b3_fix4_prenavigation.mjs'
        result = subprocess.run(['node', '--import', str(script), str(helpers.PROBE),
            '--mode', mode, '--url', self.base_url+'/'+host, '--corpus', str(self.corpus),
            *extra], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def run_host(self, name, extra=()):
        return self.probe('load', 'b3_fix4_'+name+'.html', [
            '--doc-selector', '#doc', '--usable-signal', 'screencast_ink',
            '--wait-after-ready', '1800', '--timeout-ms', '3000', *extra])

    def test_border_only_refused(self):
        p = self.run_host('border')
        self.assertIsNone(p['usable_ms'], p)
        self.assertEqual(p['surface_reason'], 'document_surface_absent')

    def test_pure_webgl_static_ink_first_frame(self):
        p = self.run_host('gl')
        self.assertIsNotNone(p['usable_ms'], p)
        self.assertGreaterEqual(p['usable_ms'], 1000)
        self.assertLess(p['usable_ms'], 1050)

    def test_uniform_webgl_is_not_ink_under_mode_rule(self):
        p = self.run_host('uniform_gl')
        self.assertIsNone(p['usable_ms'], p)
        self.assertEqual(p['surface_reason'], 'document_surface_absent')

    def test_iframe_border_does_not_count(self):
        p = self.run_host('iframe')
        self.assertIsNotNone(p['usable_ms'], p)
        self.assertGreaterEqual(p['usable_ms'], 1000)

    def test_shadow_rect_reaches_witness(self):
        p = self.run_host('shadow', ['--document-selector', '#paper'])
        self.assertIsNotNone(p['usable_ms'], p)
        self.assertTrue(p['witness']['document_scoped'], p)

    def test_missing_selector_refuses_in_probe(self):
        p = self.run_host('shadow', ['--document-selector', '#missing'])
        self.assertIsNone(p['usable_ms'], p)
        self.assertEqual(p['surface_reason'], 'document_region_missing')
        p = self.run_host('spinner', ['--document-selector', '#missing'])
        self.assertIsNone(p['usable_ms'], p)
        self.assertEqual(p['surface_reason'], 'document_region_missing')

    def test_two_disjoint_flashes_refused(self):
        p = self.run_host('flashes')
        self.assertIsNone(p['usable_ms'], p)

    def test_inside_spinner_waits_for_content(self):
        p = self.run_host('spinner')
        self.assertIsNotNone(p['usable_ms'], p)
        self.assertGreaterEqual(p['usable_ms'], 1600)

    def test_continuous_inside_spinner_never_settles(self):
        p = self.run_host('continuous_spinner')
        self.assertIsNone(p['usable_ms'], p)
        self.assertEqual(p['surface_reason'], 'settled_frame_not_observed')

class SharedClockContract(unittest.TestCase):
    def test_conversion_and_ack_are_shared(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'runner/document_probe.mjs').read_text()
        self.assertNotIn('function convertFrameToPageMs(', source)
        self.assertNotIn('function frameAckSettled(', source)
        self.assertNotIn('pageMs === null ? await page.evaluate', source)

    def test_unknown_first_timestamp_and_disjoint_frames(self):
        import subprocess
        from pathlib import Path
        script = Path(__file__).parent / 'fixtures/b3_fix4_clock.mjs'
        result = subprocess.run(['node', str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
