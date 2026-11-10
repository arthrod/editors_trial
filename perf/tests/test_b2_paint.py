"""B2 regression units and explicitly opted-in browser integration measurers."""

import json
import os
from pathlib import Path
import subprocess
import unittest
import tempfile

from perf.layers.classify import assert_visible_evidence
from perf.runner import benchmark_warm_cold as runner
from perf.schema import validate_trial

ROOT = Path(__file__).resolve().parents[2]
LOG_ROOT = Path(os.environ.get('B2_LOG_ROOT', str(Path(tempfile.gettempdir()) / 'e2-b2-tests')))


class Evidence(unittest.TestCase):
    def test_bare_raf_is_not_evidence(self):
        with self.assertRaises(ValueError):
            assert_visible_evidence('C05', 'raf_callback')

    def test_writer_rejects_raf_before_writing(self):
        with self.assertRaises(Exception) as caught:
            runner._write_measured_attempt(
                attempt_dir=None,
                criterion_id='C05',
                layer='browser_visible',
                boundary='presented_frame',
                editor_id='plate',
                lane='browser',
                env={'repetition_unit': 'fresh_process'},
                samples_ms=[20],
                cache_state='warm_steady',
                diagnostic={'mechanism': 'raf_callback'},
            )
        self.assertIsInstance(caught.exception, ValueError)
        self.assertIn('raf_callback', str(caught.exception))

    def test_schema_rejects_raf(self):
        for criterion in ('C05', 'C06'):
            with self.subTest(criterion=criterion):
                with self.assertRaisesRegex(ValueError, 'raf_callback'):
                    validate_trial(self.trial(criterion, mechanism='raf_callback'))

    @staticmethod
    def trial(criterion, **extra):
        return {
            'criterion_id': criterion,
            'layer': 'browser_visible',
            'boundary': 'presented_frame',
            'outcome': 'measured',
            'samples_ms': [20],
            **extra,
        }

    def test_schema_rejects_missing_mechanism(self):
        for criterion in ('C05', 'C06'):
            with self.subTest(criterion=criterion):
                with self.assertRaisesRegex(ValueError, 'visible evidence'):
                    validate_trial(self.trial(criterion))

    def test_schema_accepts_visible_mechanism(self):
        for criterion in ('C05', 'C06'):
            for evidence in (
                {'mechanism': 'cdp_screencast_changed_frame'},
                {'diagnostic': {'mechanism': 'cdp_screencast_changed_frame'}},
            ):
                with self.subTest(criterion=criterion, evidence=evidence):
                    validate_trial(self.trial(criterion, **evidence))

    def test_schema_allows_refusals_without_mechanism(self):
        for criterion in ('C05', 'C06'):
            with self.subTest(criterion=criterion):
                validate_trial(self.trial(
                    criterion, outcome='failed', samples_ms=[], failure_reason='no_frame',
                ))


@unittest.skipUnless(os.environ.get('B2_BROWSER'), 'opt-in browser integration')
class BrowserIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from perf.runner.browser_hosts import StaticHost
        from perf.runner.browser_run import BrowserRun

        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        cls.host = StaticHost(ROOT / 'perf/tests/fixtures/hosts/b2_input')
        cls.browser_run = BrowserRun(LOG_ROOT, os.environ.get('B2_PHASE', 'probe'), snapshot=lambda: {})
        cls.fixture = cls.browser_run.fixture('b2', b'fake host does not import a document')

    @classmethod
    def tearDownClass(cls):
        cls.host.stop()
        cls.browser_run.finish({'integration': True})

    def probe(self, name, *extra):
        self.browser_run.begin_sample()
        cmd = [
            'node',
            str(ROOT / 'perf/runner/warm_cold_browser.mjs'),
            '--url',
            self.host.url + '/?delay=' + ('50' if name == 'delayed' else '0'),
            '--corpus',
            str(self.fixture),
            '--pairs',
            '1',
            *extra,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.browser_run.sample(name, {'command': cmd, 'payload': payload})
        return payload

    def test_accounted_production_probe(self):
        from perf.runner.browser_run import ACTIVE

        token = ACTIVE.set(self.browser_run)
        try:
            target = {
                'url': self.host.url,
                'driver': 'playwright',
                'corpus_route': '/corpus.docx',
                'ready_selector': '.status-ok',
                'edit_selector': '[contenteditable="true"]',
            }
            payload = runner._run_browser_probe(target=target, corpus_path=self.fixture, pairs=1)
            rows = [r for r in self.browser_run.samples if r.get('criterion_id') in ('C05', 'C06')]
            self.assertEqual(len(rows), 8)
            for row in rows:
                self.assertIn('cpu_accounting', row)
                self.assertIn('clock_skew', row)
                self.assertEqual(row['outcome'], 'measured', row)
                self.assertGreaterEqual(row['latency_ms'], 0)
            self.assertTrue(payload['pairs'][0]['server_cold'])
        finally:
            ACTIVE.reset(token)

    def test_settle_pair_and_fresh(self):
        p = self.probe('settle', '--skip-edit', 'true', '--wait-after-ready', '1000')
        cold = p['pairs'][0]['cold']
        self.assertLess(cold['first_usable_ms'], 1000)
        self.assertGreaterEqual(cold.get('settle_ms', 0), 950)
        fresh = p['fresh_context_load_ms'][0]
        self.assertIsInstance(fresh, dict)
        self.assertLess(fresh['first_usable_ms'], 1000)
        self.assertGreaterEqual(fresh['settle_ms'], 950)

    def test_settle_criteria(self):
        p = self.probe('criteria', '--criteria', 'C04', '--wait-after-ready', '1000')
        self.assertLess(p['ready']['ready_ms'], 1000)
        self.assertGreaterEqual(p['ready'].get('settle_ms', 0), 950)

    def test_no_delay(self):
        p = self.probe('instant', '--fresh-context-probe', 'false')
        edit = p['pairs'][0]['cold']
        self.assertIn('mechanism', edit)
        self.assertTrue(edit['single_edit_ms'] < 33, edit)
        self.assertIn('clock_skew', edit)

    def test_delayed(self):
        p = self.probe('delayed', '--fresh-context-probe', 'false')
        edit = p['pairs'][0]['cold']
        self.assertIn('mechanism', edit)
        self.assertGreaterEqual(edit['single_edit_ms'], 50)
        self.assertIn('clock_skew', edit)


def frame_record():
    return {
        'outcome': 'witnessed',
        'frame_page_ms': 125,
        'frames_total': 2,
        'frames_after': 1,
        'diff_ratio': 0.01,
        'threshold': 0.00001,
        'caret_masked': True,
        'document_scoped': True,
        'changed_pixels': 100,
        'clock_check': {'acceptable': True, 'page_offset_ms': 0},
    }


class SamplePolicy(unittest.TestCase):
    def test_missing_frame_is_refused(self):
        row = runner.input_sample_record(
            {'edit_ms': 25, 'outcome': 'measured', 'clock_skew': {'skew_ms': 0, 'bound_ms': 2, 'acceptable': True}},
            'C05',
        )
        self.assertEqual(row['outcome'], 'failed')
        self.assertIsNone(row['latency_ms'])

    def test_excessive_skew_is_refused(self):
        self.assertTrue(hasattr(runner, 'input_sample_record'), 'input sample policy absent')
        row = runner.input_sample_record(
            {
                'mechanism': 'cdp_screencast_changed_frame',
                'edit_ms': 25,
                'outcome': 'measured',
                'clock_skew': {'skew_ms': 3, 'bound_ms': 2, 'acceptable': False},
            },
            'C05',
        )
        self.assertEqual(row['failure_reason'], 'clock_skew_above_bound')
        self.assertIsNone(row['latency_ms'])

    def test_censor_does_not_create_numeric_duration(self):
        self.assertTrue(hasattr(runner, 'input_sample_record'), 'input sample policy absent')
        row = runner.input_sample_record(
            {
                'mechanism': 'cdp_screencast_changed_frame',
                'edit_ms': 25,
                'outcome': 'measured',
                'clock_skew': {'skew_ms': 0, 'bound_ms': 2, 'acceptable': True},
                'witness': frame_record(),
                'edit_confirmation': {'confirmed': True},
                'event_timing': {'outcome': 'censored_below_16_ms', 'entries': []},
            },
            'C06',
        )
        self.assertEqual(row['event_timing']['outcome'], 'censored_below_16_ms')
        self.assertEqual(row['event_timing']['samples_ms'], [])
        self.assertEqual(row['latency_ms'], 25)


class WriterIntegration(unittest.TestCase):
    def write(self, *, skew=0, throttled=False, criterion="C05"):
        from perf.runner.browser_run import BrowserRun, ACTIVE
        from perf.tests.test_browser_throttle import snapshot
        from perf.tests.test_schema import _env
        import tempfile

        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=LOG_ROOT) as tmp:
            readings = iter([snapshot(), snapshot(), snapshot(n=3 if throttled else 2)])
            run = BrowserRun(tmp, 'writer', snapshot=lambda: {}, accounting_reader=lambda: next(readings))
            token = ACTIVE.set(run)
            try:
                run.begin_sample()
                obs = {
                    'mechanism': 'cdp_screencast_changed_frame',
                    'edit_ms': 25,
                    'outcome': 'measured',
                    'witness': frame_record(),
                'edit_confirmation': {'confirmed': True},
                    'clock_skew': {'skew_ms': skew, 'bound_ms': 2, 'acceptable': abs(skew) <= 2},
                }
                path = runner._write_measured_attempt(
                    attempt_dir=Path(tmp) / 'attempts',
                    criterion_id=criterion,
                    layer='browser_visible',
                    boundary='presented_frame',
                    editor_id='plate',
                    lane='browser',
                    env=_env(),
                    samples_ms=[25],
                    cache_state='process_cold_fs_warm',
                    diagnostic={'mechanism': 'cdp_screencast_changed_frame', 'observations': [obs]},
                )
                return json.loads(path.read_text())
            finally:
                ACTIVE.reset(token)

    def test_writer_preserves_accounting_and_skew(self):
        row = self.write()
        self.assertIn('cpu_accounting', row)
        self.assertEqual(row['clock_skew'][0]['skew_ms'], 0)
        self.assertEqual(row['samples_ms'], [25])

    def test_writer_refuses_skew_with_evidence(self):
        row = self.write(skew=3)
        self.assertEqual(row['failure_reason'], 'clock_skew_above_bound')
        self.assertEqual(row['samples_ms'], [])
        self.assertIn('clock_skew', row)
        self.assertEqual(row['clock_skew'][0]['skew_ms'], 3)

    def test_writer_refuses_cpu_throttled(self):
        row = self.write(throttled=True)
        self.assertEqual(row['failure_reason'], 'cpu_throttled')
        self.assertEqual(row['samples_ms'], [])
        self.assertEqual(row['cpu_accounting']['delta']['nr_throttled'], 1)


class ReviewPolicy(unittest.TestCase):
    def test_f1_expected_edit_required(self):
        row = runner.input_sample_record({
            'edit_ms': 25, 'outcome': 'measured', 'witness': frame_record(),
            'clock_skew': {'skew_ms': 0, 'bound_ms': 2, 'acceptable': True},
            'edit_confirmation': {'confirmed': False},
        }, 'C05')
        self.assertEqual(row['failure_reason'], 'expected_edit_not_confirmed')
        self.assertIsNone(row['latency_ms'])

    def test_f4_refusal_reason_survives_missing_clock(self):
        row = runner.input_sample_record({'outcome': 'failed', 'failure_reason': 'trusted_keydown_not_observed'}, 'C05')
        self.assertEqual(row['failure_reason'], 'trusted_keydown_not_observed')

    def test_boolean_clock_is_not_numeric(self):
        row = runner.input_sample_record({'clock_skew': {'skew_ms': True, 'bound_ms': 2, 'acceptable': True}}, 'C05')
        self.assertEqual(row['failure_reason'], 'clock_skew_unavailable')


class ProbeBracketIntegration(unittest.TestCase):
    def test_f2_exception_restores_cell_bracket(self):
        from unittest.mock import patch
        from perf.runner.browser_run import BrowserRun, ACTIVE
        from perf.tests.test_browser_throttle import snapshot
        with tempfile.TemporaryDirectory() as tmp:
            readings = iter([snapshot(n=0), snapshot(n=0), snapshot(n=1), snapshot(n=1)])
            run = BrowserRun(tmp, 'bracket', snapshot=lambda: {}, accounting_reader=lambda: next(readings))
            token = ACTIVE.set(run)
            try:
                run.begin_sample()
                # subprocess has no upstream fake: fail the process boundary only.
                with patch.object(runner.subprocess, 'run', side_effect=RuntimeError('poisoned probe')):
                    with self.assertRaisesRegex(RuntimeError, 'poisoned probe'):
                        runner._run_browser_probe(target={'url':'http://fixture', 'corpus_route':'/x', 'edit_selector':'#doc'}, corpus_path=Path(tmp)/'x', pairs=1)
                path = run.sample('cell', {'outcome':'ok'})
                self.assertEqual(json.loads(path.read_text())['outcome'], 'failed')
            finally:
                ACTIVE.reset(token)


@unittest.skipUnless(os.environ.get('B2_BROWSER'), 'opt-in browser integration')
class AdversarialBrowser(BrowserIntegration):
    def test_f1_custom_caret_does_not_prove_edit(self):
        p = self.probe('caret', '--url', self.host.url + '/?delay=150&caret=1', '--fresh-context-probe', 'false')
        for arm in ('cold', 'warm'):
            edit = p['pairs'][0][arm]
            self.assertTrue(edit['single_edit_ms'] is None or edit['single_edit_ms'] >= 150, edit)
            if edit['single_edit_ms'] is not None:
                self.assertTrue(edit['witness']['document_scoped'])

    def test_f3_poisoned_edit_keeps_c03(self):
        p = self.probe('poison', '--url', self.host.url + '/?poison=1', '--fresh-context-probe', 'false')
        for arm in ('cold', 'warm'):
            edit = p['pairs'][0][arm]
            self.assertGreaterEqual(edit['first_usable_ms'], 0)
            self.assertEqual(edit['outcome'], 'failed')
            self.assertIsNone(edit['single_edit_ms'])
            self.assertIn('failure_reason', edit)


class ReviewArtifactIntegration(WriterIntegration):
    def test_f8_c06_records_isolation(self):
        row = self.write(criterion='C06')
        self.assertEqual(row['diagnostic'].get('keys'), 3)
        self.assertIs(row['diagnostic'].get('isolated'), True)

    def test_f5_recorder_stop_precedes_reload_clock(self):
        source = (ROOT / 'perf/runner/warm_cold_browser.mjs').read_text()
        start = source.index('  const reloadT0 =')
        end = source.index('  const documentReloadSameContextMs', start)
        self.assertNotIn('stopRecorder', source[start:end])

    def test_f4_count_gate_writes_failure_with_evidence(self):
        from perf.tests.test_schema import _env
        with tempfile.TemporaryDirectory() as tmp:
            path = runner._write_input_refusal(
                attempt_dir=Path(tmp), criterion_id='C06', layer='browser_visible',
                boundary='input_to_next_paint', editor_id='plate', lane='browser', env=_env(),
                failure_reason='missing_input_latency',
                observations=[{'outcome':'failed', 'failure_reason':'no_frame', 'witness':{'outcome':'no_frame'}}],
            )
            row = json.loads(path.read_text())
            self.assertEqual(row['outcome'], 'failed')
            self.assertEqual(row['failure_reason'], 'no_frame')
            self.assertEqual(row['diagnostic']['observations'][0]['witness']['outcome'], 'no_frame')


class AllReadyAttempts(unittest.TestCase):
    def test_f9_checks_every_c03_not_only_last(self):
        self.assertTrue(hasattr(runner, 'validate_ready_attempts'))
        rows = [
            {'editor_id':'plate', 'criterion_id':'C02', 'outcome':'measured', 'boundary':'model_ready_browser', 'samples_ms':[10]},
            {'editor_id':'plate', 'criterion_id':'C03', 'outcome':'measured', 'boundary':'first_usable', 'samples_ms':[10]},
            {'editor_id':'plate', 'criterion_id':'C03', 'outcome':'measured', 'boundary':'first_usable', 'samples_ms':[20]},
        ]
        with self.assertRaisesRegex(ValueError, 'identical'):
            runner.validate_ready_attempts(rows)
        runner.validate_ready_attempts([rows[0], rows[2]])


class SuccessfulProbeBracketIntegration(unittest.TestCase):
    def test_build_throttle_survives_successful_inner_probe(self):
        from unittest.mock import patch
        from perf.runner.browser_run import BrowserRun, ACTIVE
        from perf.tests.test_browser_throttle import snapshot
        with tempfile.TemporaryDirectory() as tmp:
            readings = iter([snapshot(n=0), snapshot(n=0), snapshot(n=1), snapshot(n=1), snapshot(n=1)])
            run = BrowserRun(tmp, 'bracket-success', snapshot=lambda: {}, accounting_reader=lambda: next(readings))
            token = ACTIVE.set(run)
            try:
                run.begin_sample()
                process = subprocess.CompletedProcess(['node'], 0, '{"pairs": []}', '')
                with patch.object(runner.subprocess, 'run', return_value=process):
                    runner._run_browser_probe(target={'url':'http://fixture', 'corpus_route':'/x', 'edit_selector':'#doc'}, corpus_path=Path(tmp)/'x', pairs=1)
                path = run.sample('cell', {'outcome':'ok'})
                row = json.loads(path.read_text())
                self.assertEqual(row['failure_reason'], 'cpu_throttled')
                self.assertEqual(row['cpu_accounting']['delta']['nr_throttled'], 1)
            finally:
                ACTIVE.reset(token)
