"""B2 regression units and explicitly opted-in browser integration measurers."""

import json
import os
from pathlib import Path
import subprocess
import unittest
import tempfile
import statistics

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
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
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
                if row['outcome'] == 'measured':
                    self.assertGreaterEqual(row['latency_ms'], 0)
                else:
                    # A loaded recorder may lack a proven quiet window. The
                    # accounting contract must preserve that safe refusal.
                    self.assertEqual(row['outcome'], 'failed', row)
                    self.assertEqual(row['failure_reason'], 'witness_sparse', row)
                    self.assertIsNone(row['latency_ms'], row)
                    self.assertIsNone(row['edit_ms'], row)
                    self.assertIsNone(row['paint_ms'], row)
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
        values = [edit['single_edit_ms'], *(item['edit_ms'] for item in edit['burst'])]
        self.assertEqual(len(values), 4)
        self.assertTrue(all(value is not None for value in values), edit)
        self.assertLess(statistics.median(values), 33, edit)
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
        'clock_check': {
            'kind': 'clock_skew', 'acceptable': True, 'reason': None,
            'method': 'page_clock_offset+pixel_anchor', 'timestamp_kind': 'epoch_seconds',
            'timestamp_field': 'timestamp', 'bound_ms': 2, 'page_offset_ms': 0,
            'page_offset_samples': [0] * 9, 'page_offset_spread_ms': 0, 'skew_ms': 0,
            'time_origin_ms': 1700000000000, 'change_page_ms': 100,
            'frame_page_ms': 116, 'frame_lag_ms': 16, 'frame_monotonic_ms': None,
            'frames_total': 2, 'anchor_pixel_checked': True, 'anchor_diff_ratio': 1,
            'anchor_probe_region_px': {'x': 0, 'y': 0, 'width': 8, 'height': 8},
            'frame_interval_ms': 16.667, 'frame_interval_source': 'raf_delta',
            'frame_interval_samples': 60, 'lag_bound_ms': 100,
            'lag_bound_rule': 'max(3 frame intervals, 100 ms)',
            'conversion': {'formula': 'page_ms = timestamp * 1000 - performance.timeOrigin',
                           'error_lower_ms': -2, 'error_upper_ms': 100,
                           'published': '[-2 ms, +100 ms] (never ±2 ms)'},
            'caret_masked': True, 'caret_mask_error': None,
            'checks': {key: True for key in (
                'timestamp_kind_known', 'page_offset_within_bound',
                'page_offset_spread_within_bound', 'anchor_found', 'anchor_pixel_checked',
                'anchor_converted', 'anchor_causality', 'anchor_lag_within_bound')},
        },
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
                'edit_confirmation': {'confirmed': True, 'changed_pixels': 20,
                    'visible_rects': [{'x': 10, 'y': 10, 'width': 20, 'height': 30}]},
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
                'edit_confirmation': {'confirmed': True, 'changed_pixels': 20,
                    'visible_rects': [{'x': 10, 'y': 10, 'width': 20, 'height': 30}]},
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

    def test_n3_clock_bound_is_validator_constant_not_record(self):
        proof = {
            'confirmed': True,
            'changed_pixels': 20,
            'visible_rects': [{'x': 10, 'y': 10, 'width': 20, 'height': 30}],
        }
        row = runner.input_sample_record({
            'edit_ms': 12,
            'outcome': 'measured',
            'witness': frame_record(),
            'clock_skew': {'skew_ms': 0.2, 'bound_ms': 1_000_000.0, 'acceptable': True},
            'edit_confirmation': proof,
        }, 'C05')
        self.assertEqual(row['failure_reason'], 'clock_skew_bound_not_constant')
        self.assertIsNone(row['latency_ms'])

    def test_n3_forged_skew_cannot_carry_inflated_bound(self):
        proof = {
            'confirmed': True,
            'changed_pixels': 20,
            'visible_rects': [{'x': 10, 'y': 10, 'width': 20, 'height': 30}],
        }
        row = runner.input_sample_record({
            'edit_ms': 12,
            'outcome': 'measured',
            'witness': frame_record(),
            'clock_skew': {'skew_ms': 500_000.0, 'bound_ms': 1_000_000.0, 'acceptable': True},
            'edit_confirmation': proof,
        }, 'C05')
        self.assertEqual(row['failure_reason'], 'clock_skew_bound_not_constant')
        self.assertIsNone(row['latency_ms'])

    def test_n4_forged_witness_skew_not_replaced_by_clean_sibling(self):
        import copy

        proof = {
            'confirmed': True,
            'changed_pixels': 20,
            'visible_rects': [{'x': 10, 'y': 10, 'width': 20, 'height': 30}],
        }
        dirty = frame_record()
        dirty['clock_skew_ms'] = 500_000.0
        dirty['clock_check'] = copy.deepcopy(dirty['clock_check'])
        dirty['clock_check']['bound_ms'] = 2.0
        dirty['clock_check']['page_offset_ms'] = 500_000.0
        dirty['clock_check']['skew_ms'] = 500_000.0
        dirty['clock_check']['acceptable'] = True
        row = runner.input_sample_record({
            'edit_ms': 12,
            'outcome': 'measured',
            'witness': dirty,
            'clock_skew': {'skew_ms': 0.2, 'bound_ms': 2.0, 'acceptable': True},
            'edit_confirmation': proof,
        }, 'C05')
        self.assertEqual(row['failure_reason'], 'clock_skew_above_bound')
        self.assertIsNone(row['latency_ms'])

    def test_n4_witness_declared_bound_must_match_constant(self):
        import copy

        proof = {
            'confirmed': True,
            'changed_pixels': 20,
            'visible_rects': [{'x': 10, 'y': 10, 'width': 20, 'height': 30}],
        }
        mild = frame_record()
        mild['clock_check'] = copy.deepcopy(mild['clock_check'])
        mild['clock_check']['bound_ms'] = 1_000_000.0
        row = runner.input_sample_record({
            'edit_ms': 12,
            'outcome': 'measured',
            'witness': mild,
            'clock_skew': {'skew_ms': 0.2, 'bound_ms': 2.0, 'acceptable': True},
            'edit_confirmation': proof,
        }, 'C05')
        self.assertEqual(row['failure_reason'], 'clock_bound_mismatch')
        self.assertIsNone(row['latency_ms'])

    def test_n4_sibling_and_witness_skew_must_agree(self):
        import copy

        proof = {
            'confirmed': True,
            'changed_pixels': 20,
            'visible_rects': [{'x': 10, 'y': 10, 'width': 20, 'height': 30}],
        }
        shifted = frame_record()
        shifted['clock_skew_ms'] = 2.0
        shifted['clock_check'] = copy.deepcopy(shifted['clock_check'])
        shifted['clock_check']['page_offset_ms'] = 2.0
        shifted['clock_check']['skew_ms'] = 2.0
        row = runner.input_sample_record({
            'edit_ms': 12,
            'outcome': 'measured',
            'witness': shifted,
            'clock_skew': {'skew_ms': -2.0, 'bound_ms': 2.0, 'acceptable': True},
            'edit_confirmation': proof,
        }, 'C05')
        self.assertEqual(row['failure_reason'], 'clock_disagreement')
        self.assertIsNone(row['latency_ms'])


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

    def test_r1_hidden_span_cannot_confirm_caret_frame(self):
        p = self.probe('hidden', '--url', self.host.url + '/hidden.html', '--fresh-context-probe', 'false')
        for arm in ('cold', 'warm'):
            edit = p['pairs'][0][arm]
            self.assertTrue(edit['single_edit_ms'] is None or edit['single_edit_ms'] >= 150, edit)
            if edit['single_edit_ms'] is not None:
                self.assertGreater(edit['edit_confirmation']['changed_pixels'], 0)
                self.assertTrue(edit['edit_confirmation']['visible_rects'])
            else:
                self.assertEqual(edit['failure_reason'], 'expected_edit_not_confirmed', edit)

    def test_r1_invisible_geometry_and_unrelated_damage_are_refused(self):
        for mode in ('none', 'zero', 'clipped', 'offregion', 'transparent', 'clip'):
            with self.subTest(mode=mode):
                p = self.probe(mode, '--url', self.host.url + '/hidden.html?mode=' + mode,
                               '--fresh-context-probe', 'false')
                for arm in ('cold', 'warm'):
                    edit = p['pairs'][0][arm]
                    self.assertIsNone(edit['single_edit_ms'], edit)
                    self.assertEqual(edit['failure_reason'], 'expected_edit_not_confirmed', edit)

    def test_r1_visibility_must_survive_until_confirmation(self):
        p = self.probe('microtask', '--url', self.host.url + '/hidden.html?mode=microtask',
                       '--fresh-context-probe', 'false')
        for arm in ('cold', 'warm'):
            edit = p['pairs'][0][arm]
            self.assertIsNone(edit['single_edit_ms'], edit)
            self.assertEqual(edit['failure_reason'], 'expected_edit_not_confirmed', edit)

    def test_f3_poisoned_edit_keeps_c03(self):
        p = self.probe('poison', '--url', self.host.url + '/?poison=1', '--fresh-context-probe', 'false')
        for arm in ('cold', 'warm'):
            edit = p['pairs'][0][arm]
            self.assertGreaterEqual(edit['first_usable_ms'], 0)
            self.assertEqual(edit['outcome'], 'failed')
            self.assertIsNone(edit['single_edit_ms'])
            self.assertIn('failure_reason', edit)

    def test_nr1_bgdecoy_delayed_measures_settled_glyph(self):
        p = self.probe(
            'bgdecoy_delayed',
            '--url',
            self.host.url + '/bgdecoy_delayed.html',
            '--fresh-context-probe',
            'false',
        )
        interval = float(p['pairs'][0]['cold'].get('witness', {}).get('frame_interval_ms') or 16.667)
        upper = 150 + 2 * interval
        for arm in ('cold', 'warm'):
            edit = p['pairs'][0][arm]
            latency = edit['single_edit_ms']
            self.assertTrue(latency is None or (latency >= 150 and latency <= upper), edit)
            if latency is not None:
                self.assertEqual(edit['outcome'], 'measured', edit)

    def test_nr1_late800_waits_for_delayed_ink_or_refuses(self):
        p = self.probe(
            'late800',
            '--url',
            self.host.url + '/attack.html?mode=late800',
            '--edit-selector',
            '#doc',
            '--fresh-context-probe',
            'false',
        )
        for arm in ('cold', 'warm'):
            edit = p['pairs'][0][arm]
            latency = edit['single_edit_ms']
            if latency is not None:
                self.assertGreaterEqual(latency, 800, edit)
            else:
                self.assertIn(edit.get('failure_reason'), ('settle_not_reached', 'expected_edit_not_confirmed'), edit)

    def test_nr1_second_cover_does_not_replace_key_paint(self):
        p = self.probe(
            'second',
            '--url',
            self.host.url + '/attack.html?mode=second',
            '--edit-selector',
            '#doc',
            '--fresh-context-probe',
            'false',
        )
        interval = float(p['pairs'][0]['cold'].get('witness', {}).get('frame_interval_ms') or 16.667)
        bound = 2 * interval + 2
        for arm in ('cold', 'warm'):
            edit = p['pairs'][0][arm]
            latency = edit['single_edit_ms']
            self.assertIsNotNone(latency, edit)
            self.assertLessEqual(latency, bound, edit)
            self.assertEqual(edit['outcome'], 'measured', edit)

    def test_nr1_bgdecoy_immediate_stays_within_one_frame(self):
        p = self.probe(
            'bgdecoy',
            '--url',
            self.host.url + '/bgdecoy.html',
            '--fresh-context-probe',
            'false',
        )
        edit = p['pairs'][0]['cold']
        self.assertIsNotNone(edit.get('single_edit_ms'), edit)
        self.assertLess(edit['single_edit_ms'], 33, edit)


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


class RoundThreePolicy(unittest.TestCase):
    def test_r1_boolean_confirmation_without_visible_pixels_is_refused(self):
        row = runner.input_sample_record({
            'edit_ms': 25, 'outcome': 'measured', 'witness': frame_record(),
            'clock_skew': {'skew_ms': 0, 'bound_ms': 2, 'acceptable': True},
            'edit_confirmation': {'confirmed': True},
        }, 'C05')
        self.assertEqual(row['outcome'], 'failed')
        self.assertIsNone(row['latency_ms'])

    def test_r2_no_delay_uses_several_keys(self):
        # Run the acceptance assertion with deterministic recorded latencies.
        class RecordedProbe(BrowserIntegration):
            def probe(self, *args):
                return {'pairs': [{'cold': {
                    'single_edit_ms': 200, 'edit_ms': 200, 'mechanism': 'cdp_screencast_changed_frame',
                    'clock_skew': {}, 'burst': [{'edit_ms': n} for n in (8, 12, 16)],
                }}]}
        RecordedProbe('test_no_delay').test_no_delay()

    def test_all_refusal_reasons_are_published(self):
        from perf.tests.test_schema import _env
        with tempfile.TemporaryDirectory() as tmp:
            path = runner._write_input_refusal(
                attempt_dir=Path(tmp), criterion_id='C06', layer='browser_visible',
                boundary='input_to_next_paint', editor_id='plate', lane='browser', env=_env(),
                failure_reason='missing_input_latency', observations=[
                    {'failure_reason': r, 'outcome': 'failed'}
                    for r in ('no_frame', 'expected_edit_not_confirmed', 'no_frame')],
            )
            row = json.loads(path.read_text())
            self.assertEqual(row.get('failure_reasons'), ['expected_edit_not_confirmed', 'no_frame'])

    def test_r2_no_delay_keeps_median_bound(self):
        class RecordedProbe(BrowserIntegration):
            def probe(self, *args):
                return {'pairs': [{'cold': {
                    'single_edit_ms': 8, 'mechanism': 'cdp_screencast_changed_frame',
                    'clock_skew': {}, 'burst': [{'edit_ms': n} for n in (40, 40, 40)],
                }}]}
        with self.assertRaises(AssertionError):
            RecordedProbe('test_no_delay').test_no_delay()

    def test_visible_proof_rejects_empty_or_invalid_geometry(self):
        for pixels, rects in ((0, [{'x': 0, 'y': 0, 'width': 10, 'height': 10}]),
                              (True, []), (float('nan'), []), (4, []),
                              (4, [{'x': 0, 'y': 0, 'width': 0, 'height': 10}])):
            with self.subTest(pixels=pixels, rects=rects):
                row = runner.input_sample_record({
                    'edit_ms': 25, 'outcome': 'measured', 'witness': frame_record(),
                    'clock_skew': {'skew_ms': 0, 'bound_ms': 2, 'acceptable': True},
                    'edit_confirmation': {'confirmed': True, 'changed_pixels': pixels, 'visible_rects': rects},
                }, 'C05')
                self.assertEqual(row['failure_reason'], 'expected_edit_not_confirmed')

    def test_measured_writer_preserves_all_refusals(self):
        from perf.tests.test_schema import _env
        with tempfile.TemporaryDirectory() as tmp:
            path = runner._write_measured_attempt(
                attempt_dir=Path(tmp), criterion_id='C05', layer='browser_visible',
                boundary='input_to_next_paint', editor_id='plate', lane='browser', env=_env(),
                samples_ms=[20], cache_state='warm_steady',
                diagnostic={'mechanism': 'cdp_screencast_changed_frame', 'observations': [
                    {'failure_reason': r, 'outcome': 'failed'} for r in ('no_frame', 'expected_edit_not_confirmed')]},
            )
            row = json.loads(path.read_text())
            self.assertEqual(row['failure_reasons'], ['expected_edit_not_confirmed', 'no_frame'])

    def test_throttled_refusal_keeps_all_reasons(self):
        from perf.runner.browser_run import BrowserRun, ACTIVE
        from perf.tests.test_browser_throttle import snapshot
        from perf.tests.test_schema import _env
        with tempfile.TemporaryDirectory() as tmp:
            readings = iter([snapshot(), snapshot(), snapshot(n=3)])
            run = BrowserRun(tmp, 'refused', snapshot=lambda: {}, accounting_reader=lambda: next(readings))
            token = ACTIVE.set(run)
            try:
                run.begin_sample()
                path = runner._write_input_refusal(
                    attempt_dir=Path(tmp)/'attempts', criterion_id='C06', layer='browser_visible',
                    boundary='input_to_next_paint', editor_id='plate', lane='browser', env=_env(),
                    failure_reason='missing_input_latency', observations=[
                        {'failure_reason': r, 'outcome': 'failed'}
                        for r in ('no_frame', 'expected_edit_not_confirmed')],
                )
                row = json.loads(path.read_text())
                self.assertEqual(row.get('failure_reasons'), ['cpu_throttled', 'expected_edit_not_confirmed', 'no_frame'])
                self.assertEqual(row['samples_ms'], [])
                self.assertFalse(row['publishable'])
            finally:
                ACTIVE.reset(token)
