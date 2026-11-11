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
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.report_refusals(payload)
        self.browser_run.sample(name, {'command': cmd, 'payload': payload})
        return payload

    def report_refusals(self, payload):
        observations = [row for pair in payload.get('pairs', [])
                        for arm in ('cold', 'warm')
                        for row in (pair[arm], *pair[arm].get('burst', []))
                        if 'outcome' in row]
        reasons = {}
        for row in observations:
            if row['outcome'] != 'measured':
                reason = row.get('failure_reason', 'unnamed')
                reasons[reason] = reasons.get(reason, 0) + 1
        print('B2_REFUSALS ' + json.dumps({'test': self.id(), 'total': len(observations),
                                         'refusals': sum(reasons.values()), 'reasons': reasons}), flush=True)

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
            self.report_refusals(payload)
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
        observations = [(edit['single_edit_ms'], edit),
                        *((item['edit_ms'], item) for item in edit['burst'])]
        self.assertEqual(len(observations), 4)
        for value, observation in observations:
            if value is None:
                self.assertEqual(observation.get('failure_reason'), 'witness_sparse', observation)
            else:
                self.assertGreaterEqual(value, 0, observation)
                self.assertLess(value, 33, observation)
        self.assertIn('clock_skew', edit)

    def test_delayed(self):
        p = self.probe('delayed', '--fresh-context-probe', 'false')
        edit = p['pairs'][0]['cold']
        self.assertIn('mechanism', edit)
        self.assertGreaterEqual(edit['single_edit_ms'], 50)
        self.assertIn('clock_skew', edit)

    def test_replaced_block_still_measures(self):
        # Eigenpal re-creates the edited paragraph element: an observer rooted
        # at the arm-time first match is detached and the x lands in the new
        # first-matching element (HF e2-docsplus ...-091 cell 0004-eigenpal,
        # b=0 a=1 muts=0). The lane must follow the live document, not the
        # arm-time element.
        p = self.probe('replace', '--url', self.host.url + '/?replace=1', '--fresh-context-probe', 'false')
        for arm in ('cold', 'warm'):
            edit = p['pairs'][0][arm]
            latency = edit['single_edit_ms']
            self.assertIsNotNone(latency, edit)
            self.assertEqual(edit['outcome'], 'measured', edit)
            self.assertTrue(0 <= latency < 100, edit)

    def test_decoy_frame_before_delayed_glyph_measures_the_glyph(self):
        # Superdoc on HF: a small decoy change paints right after the key, the
        # glyph's DOM mutation is delivered later (259 ms observer delivery
        # lag), so the witness frame predates the mutation stamp and the
        # delivery-time eligibility filter refused a real edit (HF e2-publish-2
        # ...-001 cell 0008-superdoc, witness 6355.9, stamps 6586.3).
        p = self.probe('decoy', '--url', self.host.url + '/?decoy=1&delay=300', '--fresh-context-probe', 'false')
        for arm in ('cold', 'warm'):
            edit = p['pairs'][0][arm]
            latency = edit['single_edit_ms']
            self.assertIsNotNone(latency, edit)
            self.assertEqual(edit['outcome'], 'measured', edit)
            self.assertGreaterEqual(latency, 300, edit)


def frame_record():
    from perf.tests.witness_records import publishable_witness_record
    return publishable_witness_record(125, 100)


class SamplePolicy(unittest.TestCase):
    def test_docxodus_warm_cold_types_into_the_block_editor_not_the_read_only_render(self):
        # The render surface (#pages, convertDocxToPaginatedHtml output) is
        # static: no caret, no keyboard surface (0 contenteditable at boot).
        # The block editor (#modeEditor) mounts [data-anchor] contenteditable
        # blocks at docxodus 15.0.0 — verified live: one CDP 'x' after the
        # mount lands in #editorHost textContent (118 -> 119 x's). The
        # warm/cold target must engage that surface, or every C05/C06 cell
        # refuses expected_edit_not_confirmed without the editor ever being
        # asked (all 122 HF warm/cold attempts, every rung). The borrowing
        # lanes pass --edit-selector only (no --pre-edit-click plumbing), so
        # the shared base entry stays on the surface they resolve.
        target = runner.warm_cold_target('docxodus')
        self.assertEqual(target.get('pre_edit_click'), '#modeEditor')
        self.assertEqual(target['edit_selector'], '#editorHost [contenteditable="true"]')
        base = runner.BROWSER_TARGETS['docxodus']
        self.assertEqual(base['edit_selector'], '#pages')
        self.assertNotIn('pre_edit_click', base)

    def test_missing_frame_is_refused(self):
        row = runner.input_sample_record(
            {'edit_ms': 25, 'outcome': 'measured',
             'clock_skew': {'skew_ms': 0, 'bound_ms': 5, 'acceptable': True},
             'edit_confirmation': {'confirmed': True, 'changed_pixels': 20,
                 'visible_rects': [{'x': 10, 'y': 10, 'width': 20, 'height': 30}]}},
            'C05',
        )
        self.assertEqual(row['outcome'], 'failed')
        self.assertEqual(row['failure_reason'], 'record_not_a_mapping')
        self.assertIsNone(row['latency_ms'])

    def test_excessive_skew_is_refused(self):
        self.assertTrue(hasattr(runner, 'input_sample_record'), 'input sample policy absent')
        row = runner.input_sample_record(
            {
                'mechanism': 'cdp_screencast_changed_frame',
                'edit_ms': 25,
                'outcome': 'measured',
                'clock_skew': {'skew_ms': 7, 'bound_ms': 5, 'acceptable': False},
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
                'clock_skew': {'skew_ms': 0, 'bound_ms': 5, 'acceptable': True},
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
            readings = iter([snapshot(), snapshot(), snapshot(3, 10_050) if throttled else snapshot(2)])
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
                    'clock_skew': {'skew_ms': skew, 'bound_ms': 5, 'acceptable': abs(skew) <= 5},
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
        row = self.write(skew=7)  # lax layer: the bound is 5 ms now
        self.assertEqual(row['failure_reason'], 'clock_skew_above_bound')
        self.assertEqual(row['samples_ms'], [])
        self.assertIn('clock_skew', row)
        self.assertEqual(row['clock_skew'][0]['skew_ms'], 7)

    def test_writer_refuses_cpu_throttled(self):
        row = self.write(throttled=True)
        self.assertEqual(row['failure_reason'], 'cpu_throttled')
        self.assertEqual(row['samples_ms'], [])
        self.assertEqual(row['cpu_accounting']['delta']['nr_throttled'], 1)


class ReviewPolicy(unittest.TestCase):
    def test_f1_expected_edit_required(self):
        row = runner.input_sample_record({
            'edit_ms': 25, 'outcome': 'measured', 'witness': frame_record(),
            'clock_skew': {'skew_ms': 0, 'bound_ms': 5, 'acceptable': True},
            'edit_confirmation': {'confirmed': False},
        }, 'C05')
        self.assertEqual(row['failure_reason'], 'expected_edit_not_confirmed')
        self.assertIsNone(row['latency_ms'])

    def test_model_adapter_without_glyph_rects_is_not_applicable(self):
        row = runner.input_sample_record({
            'edit_ms': 24,
            'outcome': 'measured',
            'witness': frame_record(),
            'clock_skew': {'skew_ms': 0, 'bound_ms': 5, 'acceptable': True},
            'edit_confirmation': {
                'confirmed': True,
                'changed_pixels': 0,
                'visible_rects': [],
                'adapter': {'adapter': 'model', 'confirmed': True,
                            'before_count': 0, 'after_count': 1},
            },
        }, 'C05')
        self.assertEqual(row['outcome'], 'not_applicable')
        self.assertEqual(row['failure_reason'], runner.NO_GLYPH_GEOMETRY_REASON)
        self.assertIsNone(row['latency_ms'])
        # The evidence that the edit did land in the model travels with the row.
        self.assertEqual(row['edit_confirmation']['adapter']['after_count'], 1)

    def test_flag_adapter_without_glyph_rects_is_not_applicable(self):
        row = runner.input_sample_record({
            'edit_ms': 21,
            'outcome': 'measured',
            'witness': frame_record(),
            'clock_skew': {'skew_ms': 0, 'bound_ms': 5, 'acceptable': True},
            'edit_confirmation': {
                'confirmed': True,
                'changed_pixels': 0,
                'visible_rects': [],
                'adapter': {'adapter': 'flag', 'confirmed': True,
                            'before_count': 0, 'after_count': 1},
            },
        }, 'C06')
        self.assertEqual(row['outcome'], 'not_applicable')
        self.assertEqual(row['failure_reason'], runner.NO_GLYPH_GEOMETRY_REASON)
        self.assertIsNone(row['latency_ms'])

    def test_model_adapter_unconfirmed_is_still_a_refusal(self):
        row = runner.input_sample_record({
            'edit_ms': 24,
            'outcome': 'measured',
            'witness': frame_record(),
            'clock_skew': {'skew_ms': 0, 'bound_ms': 5, 'acceptable': True},
            'edit_confirmation': {
                'confirmed': False,
                'changed_pixels': 0,
                'visible_rects': [],
                'adapter': {'adapter': 'model', 'confirmed': False,
                            'reason': 'caret_scope_token_mismatch'},
            },
        }, 'C05')
        self.assertEqual(row['outcome'], 'failed')
        self.assertEqual(row['failure_reason'], 'expected_edit_not_confirmed')
        self.assertIsNone(row['latency_ms'])

    def test_f4_refusal_reason_survives_missing_clock(self):
        row = runner.input_sample_record({'outcome': 'failed', 'failure_reason': 'trusted_keydown_not_observed'}, 'C05')
        self.assertEqual(row['failure_reason'], 'trusted_keydown_not_observed')

    def test_boolean_clock_is_not_numeric(self):
        row = runner.input_sample_record({'clock_skew': {'skew_ms': True, 'bound_ms': 5, 'acceptable': True}}, 'C05')
        self.assertEqual(row['failure_reason'], 'clock_skew_unavailable')

    def test_glyph_geometry_refusal_is_detected_from_the_payload(self):
        observation = {
            'mechanism': 'cdp_screencast_changed_frame',
            'edit_ms': None,
            'outcome': 'not_applicable',
            'failure_reason': runner.NO_GLYPH_GEOMETRY_REASON,
            'witness': frame_record(),
            'clock_skew': {'skew_ms': 0, 'bound_ms': 2, 'acceptable': True},
            'edit_confirmation': {
                'confirmed': True,
                'changed_pixels': 0,
                'visible_rects': [],
                'adapter': {'adapter': 'model', 'confirmed': True, 'after_count': 1},
            },
        }
        payload = {'pairs': [{'cold': {'single_edit_ms': None, 'burst': [dict(observation)]},
                              'warm': {'single_edit_ms': None, 'burst': [dict(observation)]}}]}
        refusal = runner._glyph_geometry_refusal(payload)
        self.assertIsNotNone(refusal)
        self.assertEqual(refusal['reason'], runner.NO_GLYPH_GEOMETRY_REASON)
        self.assertEqual(refusal['adapters'], ['model'])
        self.assertTrue(refusal['edit_landed_in_model'])

    def test_glyph_geometry_refusal_absent_for_dom_editors(self):
        observation = {
            'mechanism': 'cdp_screencast_changed_frame',
            'edit_ms': 24,
            'outcome': 'measured',
            'witness': frame_record(),
            'clock_skew': {'skew_ms': 0, 'bound_ms': 2, 'acceptable': True},
            'edit_confirmation': {
                'confirmed': True,
                'changed_pixels': 40,
                'visible_rects': [{'x': 1, 'y': 1, 'width': 8, 'height': 18}],
                'adapter': {'adapter': 'dom', 'confirmed': True},
            },
        }
        payload = {'pairs': [{'cold': {'single_edit_ms': 24, 'burst': [dict(observation)]},
                              'warm': {'single_edit_ms': 25, 'burst': [dict(observation)]}}]}
        self.assertIsNone(runner._glyph_geometry_refusal(payload))

    def test_glyph_geometry_refusal_requires_the_edit_to_have_landed(self):
        observation = {
            'mechanism': 'cdp_screencast_changed_frame',
            'edit_ms': None,
            'outcome': 'failed',
            'failure_reason': 'expected_edit_not_confirmed',
            'witness': frame_record(),
            'clock_skew': {'skew_ms': 0, 'bound_ms': 2, 'acceptable': True},
            'edit_confirmation': {
                'confirmed': False,
                'changed_pixels': 0,
                'visible_rects': [],
                'adapter': {'adapter': 'model', 'confirmed': False},
            },
        }
        payload = {'pairs': [{'cold': {'single_edit_ms': None, 'burst': [dict(observation)]},
                              'warm': {'single_edit_ms': None, 'burst': [dict(observation)]}}]}
        self.assertIsNone(runner._glyph_geometry_refusal(payload))

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
        dirty['clock_check']['bound_ms'] = 5.0  # lax layer: the forged clean bound is the new constant
        dirty['clock_check']['page_offset_ms'] = 500_000.0
        dirty['clock_check']['skew_ms'] = 500_000.0
        dirty['clock_check']['acceptable'] = True
        row = runner.input_sample_record({
            'edit_ms': 12,
            'outcome': 'measured',
            'witness': dirty,
            'clock_skew': {'skew_ms': 0.2, 'bound_ms': 5.0, 'acceptable': True},
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
            'clock_skew': {'skew_ms': 0.2, 'bound_ms': 5.0, 'acceptable': True},
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
        # lax layer (owner 2026-11-11): the bound is 5 ms, so the sibling and
        # witness must disagree by more than that to refuse.
        shifted['clock_skew_ms'] = 4.0
        shifted['clock_check'] = copy.deepcopy(shifted['clock_check'])
        shifted['clock_check']['page_offset_ms'] = 4.0
        shifted['clock_check']['skew_ms'] = 4.0
        row = runner.input_sample_record({
            'edit_ms': 12,
            'outcome': 'measured',
            'witness': shifted,
            'clock_skew': {'skew_ms': -4.0, 'bound_ms': 5.0, 'acceptable': True},
            'edit_confirmation': proof,
        }, 'C05')
        self.assertEqual(row['failure_reason'], 'clock_disagreement')
        self.assertIsNone(row['latency_ms'])



def _real_fixture(directory):
    """The probe reads the fixture's opening text before it starts: a real package, not a name."""
    from perf.fixtures.docx_workload import workload_docx
    path = Path(directory) / 'x.docx'
    path.write_bytes(workload_docx('prose-500w')['docx'])
    return path


class ProbeBracketIntegration(unittest.TestCase):
    def test_f2_exception_restores_cell_bracket(self):
        from unittest.mock import patch
        from perf.runner.browser_run import BrowserRun, ACTIVE
        from perf.tests.test_browser_throttle import snapshot
        with tempfile.TemporaryDirectory() as tmp:
            readings = iter([snapshot(n=0), snapshot(n=0), snapshot(1, 10_050), snapshot(1, 10_050)])  # lax layer: above the tolerance
            run = BrowserRun(tmp, 'bracket', snapshot=lambda: {}, accounting_reader=lambda: next(readings))
            token = ACTIVE.set(run)
            try:
                run.begin_sample()
                # subprocess has no upstream fake: fail the process boundary only.
                with patch.object(runner.subprocess, 'run', side_effect=RuntimeError('poisoned probe')):
                    with self.assertRaisesRegex(RuntimeError, 'poisoned probe'):
                        runner._run_browser_probe(target={'url':'http://fixture', 'corpus_route':'/x', 'edit_selector':'#doc'}, corpus_path=_real_fixture(tmp), pairs=1)
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
                self.assertGreater(edit['edit_confirmation']['changed_pixels'], 0, edit)
                self.assertTrue(edit['edit_confirmation']['visible_rects'], edit)
                self.assertTrue(edit['witness']['document_scoped'])
            else:
                # The hidden span itself is never confirmable (empty rects),
                # so a refusal is expected_edit_not_confirmed. The genuinely
                # visible 150 ms insertion may also reach settlement (the
                # delivery-time eligibility filter is gone); when the blink-
                # driven frame stream is too sparse to prove its quiet
                # window, the honest refusal is witness_sparse. Both refuse;
                # neither confirms anything below the real 150 ms paint.
                self.assertIn(edit['failure_reason'],
                              ('expected_edit_not_confirmed', 'witness_sparse'), edit)

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
            self.assertIsNotNone(latency, edit)
            self.assertTrue(latency >= 150 and latency <= upper, edit)
            if latency is not None:
                self.assertEqual(edit['outcome'], 'measured', edit)

    def ink_oracle(self, edit):
        ink = edit['edit_confirmation']['fixture_ink']
        # Equivalent to the witness epoch-to-page conversion, without applying
        # page_offset_ms as a correction. The key event is on this page clock.
        page_ms = ink['page_ms'] + (ink['time_origin_ms'] - edit['witness']['time_origin_ms'])
        onset = page_ms - edit['event_timing']['event']['startTime']
        interval = edit['clock_skew']['frame_interval_ms']
        self.assertGreater(interval, 0)
        return onset, interval

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
                onset, interval = self.ink_oracle(edit)
                self.assertGreaterEqual(latency, onset, edit)
                self.assertLessEqual(latency, onset + 2 * interval + 1, edit)
            else:
                self.assertEqual(edit.get('failure_reason'), 'witness_sparse', edit)

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
        for arm in ('cold', 'warm'):
            edit = p['pairs'][0][arm]
            latency = edit['single_edit_ms']
            if latency is None:
                self.assertEqual(edit.get('failure_reason'), 'witness_sparse', edit)
            else:
                onset, interval = self.ink_oracle(edit)
                self.assertGreaterEqual(latency, onset, edit)
                self.assertLessEqual(latency, onset + 2 * interval + 1, edit)
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
            readings = iter([snapshot(n=0), snapshot(n=0), snapshot(1, 10_050), snapshot(1, 10_050), snapshot(1, 10_050)])  # lax layer: above the tolerance
            run = BrowserRun(tmp, 'bracket-success', snapshot=lambda: {}, accounting_reader=lambda: next(readings))
            token = ACTIVE.set(run)
            try:
                run.begin_sample()
                process = subprocess.CompletedProcess(['node'], 0, '{"pairs": []}', '')
                with patch.object(runner.subprocess, 'run', return_value=process):
                    runner._run_browser_probe(target={'url':'http://fixture', 'corpus_route':'/x', 'edit_selector':'#doc'}, corpus_path=_real_fixture(tmp), pairs=1)
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
            'clock_skew': {'skew_ms': 0, 'bound_ms': 5, 'acceptable': True},
            'edit_confirmation': {'confirmed': True},
        }, 'C05')
        self.assertEqual(row['outcome'], 'failed')
        self.assertEqual(row['failure_reason'], 'expected_edit_not_confirmed')
        self.assertIsNone(row['latency_ms'])

    def test_r2_no_delay_uses_several_keys(self):
        # Run the acceptance assertion with deterministic recorded latencies.
        class RecordedProbe(BrowserIntegration):
            def probe(self, *args):
                return {'pairs': [{'cold': {
                    'single_edit_ms': 200, 'edit_ms': 200, 'mechanism': 'cdp_screencast_changed_frame',
                    'clock_skew': {}, 'burst': [{'edit_ms': n} for n in (8, 12, 16)],
                }}]}
        with self.assertRaises(AssertionError):
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
                    'clock_skew': {'skew_ms': 0, 'bound_ms': 5, 'acceptable': True},
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
            readings = iter([snapshot(), snapshot(), snapshot(3, 10_050)])  # lax layer: above the max(1 ms, 1 %) tolerance
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


class SettlementIntegration(unittest.TestCase):
    def test_pure_frame_sequence_contract(self):
        result = subprocess.run(
            ['node', '--experimental-test-coverage', '--test', str(ROOT / 'perf/tests/test_b2_settle.mjs'),
             str(ROOT / 'perf/tests/test_b2_pixels.mjs')],
            capture_output=True, text=True, timeout=30,
        )
        print(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class RoundSevenOracles(unittest.TestCase):
    def no_delay(self, single, burst):
        class RecordedProbe(BrowserIntegration):
            def probe(self, *args):
                return {'pairs': [{'cold': {
                    **single, 'mechanism': 'cdp_screencast_changed_frame',
                    'clock_skew': {}, 'burst': burst,
                }}]}
        RecordedProbe('test_no_delay').test_no_delay()

    def test_sparse_no_delay_is_accepted(self):
        self.no_delay({'single_edit_ms': None, 'failure_reason': 'witness_sparse'},
                      [{'edit_ms': 8}, {'edit_ms': None, 'failure_reason': 'witness_sparse'}, {'edit_ms': 12}])

    def test_other_refusal_is_rejected(self):
        with self.assertRaises(AssertionError):
            self.no_delay({'single_edit_ms': None, 'failure_reason': 'no_frame'},
                          [{'edit_ms': 8}] * 3)

    def test_outlier_is_rejected_even_with_fast_peers(self):
        with self.assertRaises(AssertionError):
            self.no_delay({'single_edit_ms': 200}, [{'edit_ms': 8}] * 3)

    def attack(self, mode, latency, onset=830, interval=20):
        class RecordedProbe(AdversarialBrowser):
            host = type('Host', (), {'url': 'http://fixture.invalid'})()

            def probe(self, *args):
                edit = {'single_edit_ms': latency, 'outcome': 'measured',
                        'edit_confirmation': {'fixture_ink': {'page_ms': 100 + onset, 'time_origin_ms': 1000}},
                        'event_timing': {'event': {'startTime': 100}},
                        'witness': {'time_origin_ms': 1000},
                        'clock_skew': {'frame_interval_ms': interval}}
                return {'pairs': [{'cold': edit, 'warm': edit}]}
        name = ('test_nr1_late800_waits_for_delayed_ink_or_refuses' if mode == 'late800'
                else 'test_nr1_second_cover_does_not_replace_key_paint')
        getattr(RecordedProbe(name), name)()

    def test_actual_late_timer_and_calibrated_interval_are_accepted(self):
        self.attack('late800', 871)

    def test_decoy_and_late_frame_are_rejected(self):
        for latency in (20, 829, 871.01):
            with self.subTest(latency=latency), self.assertRaises(AssertionError):
                self.attack('late800', latency)

    def test_second_uses_glyph_set_and_rejects_cover(self):
        self.attack('second', 45, onset=4)
        with self.assertRaises(AssertionError):
            self.attack('second', 400, onset=4)
