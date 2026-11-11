"""Chromium integration: settled pixels must carry the loaded corpus text."""
import json
import subprocess
import unittest
from perf.tests import test_b3_fix5 as helpers

class ContentHosts(helpers.DocumentQuietHosts):
    def check(self, host, expected='REAL DOCUMENT CONTENT', selector='#doc'):
        cmd = ['node', str(helpers.helpers.PROBE), '--mode', 'load', '--url', self.base_url+'/'+host,
               '--corpus', str(self.corpus), '--doc-selector', selector, '--usable-signal', 'screencast_ink',
               '--timeout-ms', '3500', '--expected-opening-text', expected]
        if selector == '#host':
            cmd += ['--document-selector', '#doc']
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_empty_dom(self):
        p = self.check('b3_fix7_ruler_empty.html')
        self.assertIsNone(p['usable_ms'], p)
        self.assertEqual(p['surface_reason'], 'document_content_absent')

    def test_wrong_dom(self):
        p = self.check('b3_fix5_caret_editor.html')
        self.assertIsNone(p['usable_ms'], p)
        self.assertEqual(p['surface_reason'], 'document_content_mismatch')

    def test_matching_dom(self):
        p = self.check('b3_fix7_text.html')
        self.assertIsNotNone(p['usable_ms'], p)
        self.assertTrue(p['content_verified'])
        self.assertIn('REAL DOCUMENT CONTENT', p['document_text'])

    def test_runner_refuses_absent_and_wrong_corpus(self):
        from perf.runner import benchmark_document as bd
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / 'corpus.docx'
            corpus.write_bytes(bd.docx_paragraph_bytes(b'REAL DOCUMENT CONTENT\n'))
            cfg = dict(doc_selector='#doc', edit_selector='#doc', page_model='continuous_flow',
                       usable_signal='screencast_ink')
            for host, reason in [('b3_fix7_ruler_empty.html', 'document_content_absent'),
                                 ('b3_fix5_caret_editor.html', 'document_content_mismatch')]:
                target = dict(url=self.base_url+'/'+host, corpus_route='/corpus.docx')
                with self.subTest(host=host), self.assertRaisesRegex(bd.ProbeRefusal, reason):
                    bd._run_load_samples(editor_id='fixture', target=target, cfg=cfg,
                                         fixture_path=corpus, count=1)

    def test_matching_iframe(self):
        p = self.check('b3_fix4_iframe.html', expected='Delayed iframe document content')
        self.assertIsNotNone(p['usable_ms'], p)
        self.assertTrue(p['content_verified'])

    def test_matching_shadow(self):
        p = self.check('b3_fix7_shadow.html', selector='#host')
        self.assertIsNotNone(p['usable_ms'], p)
        self.assertTrue(p['content_verified'])

    def test_canvas_without_model_refuses_unverifiable(self):
        p = self.check('b3_fix7_ruler_canvas.html')
        self.assertFalse(p['content_verified'], p)
        self.assertEqual(p['surface_reason'], 'document_content_unverifiable', p)
        self.assertIsNone(p['usable_ms'], p)

class CorpusOpeningIntegration(unittest.TestCase):
    def test_expected_uses_shared_docx_extractor(self):
        import tempfile
        from pathlib import Path
        from perf.runner import benchmark_document as bd
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / 'corpus.docx'
            corpus.write_bytes(bd.docx_paragraph_bytes(b'   \nOne two three four five six seven eight nine\n'))
            self.assertEqual(bd.corpus_opening_text(corpus), 'One two three four five six seven eight')
            corpus.write_bytes(bd.docx_paragraph_bytes(b'   \n'))
            self.assertEqual(bd.corpus_opening_text(corpus), '')

    def test_trial_persists_all_sample_content_verification(self):
        import tempfile
        from pathlib import Path
        from perf.runner import benchmark_document as bd
        from perf.tests.test_document_criteria import _env
        for checks, expected in [([True, True], True), ([True, False], False), ([], False)]:
            with self.subTest(checks=checks), tempfile.TemporaryDirectory() as tmp:
                path, trial = bd._write_measured(
                    attempt_dir=Path(tmp), criterion_id='C11', editor_id='plate',
                    lane='browser_slate', env=_env(), samples=[56., 61.],
                    diagnostic={'samples': [{'content_verified': c} for c in checks],
                                'frame_interval_ms': 16.7})
                self.assertIs(trial['content_verified'], expected)
                self.assertIs(json.loads(path.read_text())['content_verified'], expected)
