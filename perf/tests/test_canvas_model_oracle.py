"""Canvas editors: __PERF_MODEL_TEXT__ gates C11 load and C03 ready (#146)."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from perf.tests import test_b3_fix5 as helpers
from perf.tests.test_b3_fix3 import PROBE, REPO
from perf.runner import benchmark_document as bd


class CanvasModelOracleHosts(helpers.DocumentQuietHosts):
    def load_probe(self, host: str, expected: str, *, extra: str = ''):
        cmd = [
            'node',
            str(PROBE),
            '--mode',
            'load',
            '--url',
            self.base_url + '/' + host,
            '--corpus',
            str(self.corpus),
            '--doc-selector',
            '#doc',
            '--usable-signal',
            'screencast_ink',
            '--timeout-ms',
            '4000',
            '--expected-opening-text',
            expected,
        ]
        if extra:
            cmd.append(extra)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)


class CanvasModelOracle(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    CanvasModelOracleHosts.setUpClass()

  @classmethod
  def tearDownClass(cls):
    CanvasModelOracleHosts.tearDownClass()

  def setUp(self):
    self.hosts = CanvasModelOracleHosts()

  def test_canvas_model_hook_verifies_opening(self):
    payload = self.hosts.load_probe(
        'b3_canvas_model_ok.html',
        'REAL DOCUMENT CONTENT',
    )
    self.assertTrue(payload['content_verified'], payload)
    self.assertIn('real document content', payload['document_text'].lower())

  def test_canvas_without_model_payload_is_unverifiable(self):
    p = self.hosts.load_probe('b3_fix7_ruler_canvas.html', 'REAL DOCUMENT CONTENT')
    self.assertFalse(p['content_verified'], p)
    self.assertEqual(p['surface_reason'], 'document_content_unverifiable', p)

  def test_canvas_model_mismatch_payload_refuses(self):
    p = self.hosts.load_probe('b3_canvas_model_wrong.html', 'REAL DOCUMENT CONTENT')
    self.assertFalse(p['content_verified'], p)
    self.assertEqual(p['surface_reason'], 'document_content_mismatch', p)

  def test_runner_raises_on_unverifiable_probe_payload(self):
    payload = {
        'content_verified': False,
        'surface_reason': 'document_content_unverifiable',
        'editor_error': 'TypeError: model read failed',
        'content_text_accessible': False,
    }
    originals = (bd._run_probe,)
    bd._run_probe = lambda *a, **k: payload
    try:
      with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp) / 'corpus.docx'
        corpus.write_bytes(bd.docx_paragraph_bytes(b'REAL DOCUMENT CONTENT\n'))
        cfg = dict(doc_selector='#doc', edit_selector='#doc', page_model='continuous_flow', usable_signal='screencast_ink')
        target = dict(url='http://fixture/b3_canvas.html', corpus_route='/corpus.docx')
        with self.assertRaisesRegex(
            bd.ProbeRefusal,
            r'document_content_unverifiable: TypeError: model read failed',
        ):
          bd._run_load_samples(editor_id='fixture', target=target, cfg=cfg, fixture_path=corpus, count=1)
    finally:
      bd._run_probe = originals[0]

  def test_warm_cold_probe_accepts_expected_opening_flag(self):
    source = (REPO / 'perf/runner/warm_cold_browser.mjs').read_text(encoding='utf-8')
    self.assertIn("expected-opening-text", source)
    self.assertIn('verifyCanvasOpening', source)
    source_py = (REPO / 'perf/runner/benchmark_warm_cold.py').read_text(encoding='utf-8')
    self.assertIn('corpus_opening_text', source_py)
    self.assertIn('expected-opening-text', source_py)

  def test_hosts_declare_perf_model_text(self):
    docen = (REPO / 'harness/ui/docen-host/src/main.ts').read_text(encoding='utf-8')
    canvas = (REPO / 'harness/ui/canvas/src/main.ts').read_text(encoding='utf-8')
    self.assertIn('__PERF_MODEL_TEXT__', docen)
    self.assertIn('__PERF_MODEL_TEXT__', canvas)
