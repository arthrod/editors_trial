"""Real Chromium integration and smoke coverage for issue #135 fix 5."""
import json
import subprocess
from pathlib import Path
import unittest
from perf.tests import test_b3_fix3 as helpers

class DocumentQuietHosts(unittest.TestCase):
    server = None
    corpus = None
    setUpClass = classmethod(helpers.Fix3Hosts.setUpClass.__func__)
    tearDownClass = classmethod(helpers.Fix3Hosts.tearDownClass.__func__)

    def probe(self, name, dpr=False, selector='#doc'):
        cmd = ['node']
        if dpr:
            cmd += ['--import', str(Path(__file__).parent/'fixtures/b3_fix5_dpr2.mjs')]
        cmd += [str(helpers.PROBE), '--mode', 'load', '--url', self.base_url+'/'+name,
                '--corpus', str(self.corpus), '--doc-selector', selector,
                '--usable-signal', 'screencast_ink', '--timeout-ms', '3000']
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        result = json.loads(p.stdout)
        print(name, json.dumps({k: result.get(k) for k in ['usable_ms','surface_reason','frames_total']}))
        return result

    def test_margin_animation_does_not_block_document(self):
        p = self.probe('b3_fix5_margin_anim.html')
        self.assertIsNotNone(p['usable_ms'], p)
        self.assertLess(p['usable_ms'], 200)

    def test_staged_canvas_final_half(self):
        p = self.probe('b3_fix5_half_paint.html')
        self.assertGreater(p['frames_total'], 0, p)
        self.assertIsNotNone(p['usable_ms'], p)
        self.assertGreaterEqual(p['usable_ms'], 600)
        self.assertLessEqual(p['usable_ms'], 650)

    def test_font_swap_preserves_first_matching_bitmap(self):
        p = self.probe('b3_fix5_font_swap.html')
        self.assertIsNotNone(p['usable_ms'], p)
        self.assertGreaterEqual(p['usable_ms'], 400)
        self.assertLess(p['usable_ms'], 500)

    def test_device_scale_explicit_refusal(self):
        p = self.probe('b3_fix5_margin_anim.html', dpr=True)
        self.assertIsNone(p['usable_ms'], p)
        self.assertEqual(p['surface_reason'], 'unsupported_device_scale')

    def test_caret(self):
        p = self.probe('b3_fix5_caret_editor.html')
        self.assertIsNotNone(p['usable_ms'], p)
        self.assertLess(p['usable_ms'], 200)

    def test_outside_spinner(self):
        p = self.probe('b3_spinner_outside.html', selector='.doc-paragraph')
        self.assertIsNotNone(p['usable_ms'], p)
        self.assertGreaterEqual(p['usable_ms'], 1200)
        self.assertLess(p['usable_ms'], 1300)

class HostErrorPreservation(unittest.TestCase):
    def test_host_error_only_fills_unattempted_criteria_this_launch(self):
        # Execute the actual exception body with an in-memory attempt sink.
        # Source-inspection integration test; the executed handler uses only fakes.
        import ast
        import perf.runner.benchmark_document as bd
        source = Path(bd.__file__).read_text()
        tree = ast.parse(source)
        handler = next(n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)
                       and any(isinstance(c, ast.Constant) and isinstance(c.value, str)
                               and c.value.startswith('host-error:') for c in ast.walk(n)))
        rows = [{'criterion_id': 'C12', 'editor_id': 'old-launch'},
                {'criterion_id': 'C11', 'editor_id': 'current', 'attempt_file': 'measured'}]
        writes = []
        env = dict(failures=0, exc=RuntimeError('later probe broke'),
                   criteria=['C11', 'C12'], rows=rows, launch_row_start=1,
                   editor_id='current', CRITERIA=bd.CRITERIA,
                   specs={**bd.CRITERIA, 'C12': {**bd.CRITERIA['C12'], 'workload': 'prose-500w'}},
                   fixtures={'prose-500w': {}},
                   _refuse_cell=lambda cid, fixture, reason: writes.append(cid))
        exec(compile(ast.fix_missing_locations(ast.Module(body=handler.body, type_ignores=[])),
                     bd.__file__, 'exec'), env)
        self.assertEqual(writes, ['C12'])
        self.assertEqual(rows[1]['attempt_file'], 'measured')
