"""OnlyOffice's edit and text surfaces: model 'onlyoffice', read through its host page.

The readers run in OnlyOffice's editor frame (editor_frame.mjs) or the host page
and ask the host page's window.__host.text() / caretParagraphText()
(harness/ui/onlyoffice/main.js). Only OnlyOffice's surfaces name this model, and
the input lane's OnlyOffice branch is guarded by it, so no other editor's
readers change.
"""
import json
import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REPRO = REPO / 'perf' / 'tests' / 'e2_onlyoffice_surface_repro.mjs'


class OnlyOfficeSurface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(['node', str(REPRO)], cwd=str(REPO), capture_output=True, text=True, timeout=30)
        if proc.returncode:
            raise AssertionError(proc.stderr)
        cls.out = json.loads(proc.stdout)

    def test_reads_the_host_page_from_the_frame_and_from_the_page(self):
        self.assertEqual(self.out['frame_text']['text'], 'Article 1\n\U0002000b body')
        self.assertEqual(self.out['frame_text']['oracle'], 'perf_model')
        self.assertEqual(self.out['frame_text']['source'], 'onlyoffice_model')
        self.assertEqual(self.out['frame_caret'], '\U0002000b body')
        self.assertEqual(self.out['frame_model'], {'text': 'Article 1\n\U0002000b body', 'absorbed_items': []})
        self.assertEqual(self.out['page_text'], 'Article 1\n\U0002000b body')

    def test_no_reader_is_absent_not_empty(self):
        self.assertEqual(self.out['absent']['oracle'], 'absent')
        self.assertTrue(self.out['absent']['error'])

    def test_only_onlyoffice_names_the_model(self):
        self.assertEqual([k for k, v in self.out['models'].items() if v == 'onlyoffice'], ['onlyoffice'])
        self.assertEqual([k for k, v in self.out['text_models'].items() if v == 'onlyoffice'], ['onlyoffice'])

    def test_input_lane_branch_is_guarded_by_the_model(self):
        source = (REPO / 'perf/runner/criteria_input.mjs').read_text()
        self.assertEqual(len(re.findall(r"model === 'onlyoffice'", source)), 1)
        self.assertIn("if (spec.kind === 'model' && spec.model === 'onlyoffice') {", source)

    def test_host_page_exposes_the_reader(self):
        main = (REPO / 'harness/ui/onlyoffice/main.js').read_text()
        self.assertIn('text, caretParagraphText };', main)
        self.assertIn('S.fromCodePoint(codes[0])', main)
        self.assertIn('S.fromCharCode = narrow;', main)


if __name__ == '__main__':
    unittest.main()
