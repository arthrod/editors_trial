"""editor_frame.mjs: OnlyOffice's document calls go to its editor frame; every other editor's page is untouched.

OnlyOffice's application is a same-origin iframe of its host page. The lanes'
page-context work (listeners, event timing, the model, the caret) must run in
that frame. ``editorPage`` returns the very same page object for every other
browser target, so no published editor's driver changes.
"""
import json
import subprocess
import unittest
from pathlib import Path

from perf.runner.benchmark_warm_cold import BROWSER_TARGETS

REPO = Path(__file__).resolve().parents[2]
REPRO = REPO / 'perf' / 'tests' / 'e2_editor_frame_repro.mjs'


class EditorFrame(unittest.TestCase):
    def setUp(self):
        proc = subprocess.run(['node', str(REPRO), *sorted(BROWSER_TARGETS)], cwd=str(REPO),
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.out = json.loads(proc.stdout)

    def test_every_other_editor_gets_the_same_page_object(self):
        self.assertIn('onlyoffice', BROWSER_TARGETS)
        self.assertTrue(self.out['others_same_object'])
        self.assertTrue(self.out['null_editor_same_object'])
        self.assertEqual(self.out['listed'], ['onlyoffice'])

    def test_onlyoffice_document_calls_reach_its_frame(self):
        self.assertEqual(self.out['before_frame'], 'main:evaluate')
        self.assertEqual(self.out['evaluate'], 'editor:evaluate')
        self.assertEqual(self.out['waitForFunction'], 'editor:waitForFunction')
        self.assertEqual(self.out['locator'], 'editor:locator:#id_viewer')

    def test_onlyoffice_devices_and_navigation_stay_on_the_page(self):
        self.assertEqual(self.out['mouse'], 'page:mouse')
        self.assertEqual(self.out['reload'], 'page:reload')
        self.assertEqual(self.out['viewport'], 1280)
        self.assertTrue(self.out['raw'])

    def test_frame_clock_offset_is_zero_without_a_call_for_other_editors(self):
        self.assertTrue(self.out['offsets_others'])
        self.assertEqual(set(self.out['offsets_others']), {0})
        self.assertEqual(self.out['offset_onlyoffice'], 107.7)

    def test_document_lane_rules_name_only_onlyoffice(self):
        # C12 not applicable: the canvas/docen ruling, plus OnlyOffice.
        self.assertEqual(self.out['c12_no_geometry'], ['canvas', 'docen', 'onlyoffice'])
        probe = (REPO / 'perf/runner/document_probe.mjs').read_text()
        # C15's interval rule is armed for OnlyOffice only.
        self.assertIn("intervalReplies: editorId === 'onlyoffice',", probe)
        self.assertIn('if (intervalReplies) {', probe)
        # C11's clock move is the offset, 0 for every other editor.
        self.assertIn('const originOffset = await frameClockOffsetMs(ctx.page, editorId);', probe)

    def test_every_lane_driver_wraps_its_page(self):
        # Each driver's page is editorPage(page, editor): the page itself for
        # every editor but OnlyOffice (test_other_editors_get_their_page_back).
        wraps = {
            'warm_cold_browser.mjs': 'editorPage(await ',
            'document_probe.mjs': 'editorPage(await context.newPage(), editorId)',
            'adversarial_c10_scroll.mjs': 'editorPage(await context.newPage(), editorId)',
            'memory_probe.mjs': 'editorPage(await context.newPage(), editorId)',
            'resources_session.mjs': "page = editorPage(browserPage, opts.editorId || '')",
            'typing_session.mjs': "page = editorPage(browserPage, command.editor_id || '')",
        }
        for name, needle in wraps.items():
            self.assertIn(needle, (REPO / 'perf/runner' / name).read_text(), name)
        typing = (REPO / 'perf/runner/benchmark_typing.py').read_text()
        self.assertIn("offset = load.get('frame_clock_offset_ms') or 0", typing)

    def test_host_page_lays_the_frame_out_at_the_origin(self):
        # Coordinates are not translated between the frame and the page: the
        # host page must keep the frame at (0, 0), full size, borderless.
        html = (REPO / 'harness/ui/onlyoffice/index.html').read_text()
        self.assertIn('html, body { margin: 0; height: 100%; }', html)
        self.assertIn('#root { height: 100vh; }', html)
        self.assertIn('<div id="root"><div id="oo-holder"></div></div>', html)


if __name__ == '__main__':
    unittest.main()
