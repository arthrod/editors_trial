"""#245, end to end on a real record: Docen's probe payload (local run, 16 Nov 2026, prose-5kw) goes through
the harness's trial writer and the report's reader, and comes out a measured, labelled typing trial."""
import json
import tempfile
import unittest
from pathlib import Path

from perf.analysis import e2_cells as cells
from perf.runner import benchmark_warm_cold as runner
from perf.tests.test_b2_paint import LOG_ROOT

PAYLOAD = json.loads((Path(__file__).parent / 'fixtures' / 'docen_settled_probe.json').read_text())


def write(criterion, arm, mutate=None):
    from perf.runner.browser_run import ACTIVE, BrowserRun
    from perf.tests.test_browser_throttle import snapshot
    from perf.tests.test_schema import _env

    data = json.loads(json.dumps(PAYLOAD[arm]))
    if mutate:
        mutate(data)
    if criterion == 'C05':
        observations, samples = [data['single']], [data['single_edit_ms']]
    else:
        observations, samples = [data['burst']], [data['sustained_typing_median_ms']]
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=LOG_ROOT) as tmp:
        readings = iter([snapshot(), snapshot(), snapshot(2)])
        run = BrowserRun(tmp, 'writer', snapshot=lambda: {}, accounting_reader=lambda: next(readings))
        token = ACTIVE.set(run)
        try:
            run.begin_sample()
            path = runner._write_measured_attempt(
                attempt_dir=Path(tmp) / 'attempts', criterion_id=criterion, layer='browser_visible',
                boundary='presented_frame' if criterion == 'C05' else 'input_to_next_paint',
                editor_id='docen', lane='editor', env=_env(), samples_ms=samples,
                cache_state='process_cold_fs_warm' if arm == 'cold' else 'warm_steady',
                diagnostic={'mechanism': 'cdp_screencast_changed_frame', 'observations': observations})
            return json.loads(path.read_text())
        finally:
            ACTIVE.reset(token)


class SettledPixelTrial(unittest.TestCase):
    def test_the_payload_is_not_the_glyph_refusal(self):
        payload = {'pairs': [{arm: {**PAYLOAD[arm]['single'], 'burst': PAYLOAD[arm]['burst']} for arm in ('cold', 'warm')}]}
        self.assertIsNone(runner._glyph_geometry_refusal(payload))

    def test_both_criteria_and_both_arms_are_measured_and_say_their_witness(self):
        for criterion in ('C05', 'C06'):
            for arm in ('cold', 'warm'):
                trial = write(criterion, arm)
                self.assertEqual(trial['outcome'], 'measured', (criterion, arm, trial.get('failure_reason')))
                self.assertEqual(trial['witness'], 'settled_pixels')
                self.assertEqual(len(trial['samples_ms']), 1)
                read = cells.settled_pixel_typing(trial)
                self.assertEqual(read['outcome'], 'measured', (criterion, arm))
                self.assertEqual(read['pixel_witness']['issue'], 245)
                self.assertEqual(read['pixel_witness']['keystrokes'], 1 if criterion == 'C05' else 3)
                # Docen's "x" with its caret's two columns left out.
                self.assertEqual(read['pixel_witness']['least_changed_pixels'], 34)

    def test_a_key_press_that_did_not_settle_refuses_the_trial_by_name(self):
        def unsettle(data):
            data['burst'][1]['edit_confirmation']['pixel_settle']['failure_reason'] = 'not_settled'
        trial = write('C06', 'warm', unsettle)
        self.assertEqual(trial['outcome'], 'failed')
        self.assertEqual(trial['failure_reason'], 'not_settled')
        self.assertEqual(trial['refusal_code'], 'paint_witness_unavailable')
        self.assertEqual(trial['samples_ms'], [])


if __name__ == '__main__':
    unittest.main()


def test_the_written_trial_becomes_a_report_cell_marked_by_pixels(tmp_path):
    from perf.tests.test_e2_reader_pixel_typing import ENV
    run = tmp_path / 'campaign'
    for arm, measure in (('cold', 'process_cold_fs_warm'), ('warm', 'warm_steady')):
        trial = write('C05', arm)
        trial.update(measure=measure, environment=dict(ENV, editor_id='docen', cache_state=measure),
                     host_provenance={'host_build': 'production', 'publishable': True, 'tree_sha256': 'tree-a'})
        job = run / 'benchmark_warm_cold' / 'run-001'
        path = job / 'cells' / '0000-docen' / 'attempts' / f'c05-{arm}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(trial))
        (job / 'summary.json').write_text(json.dumps(dict(
            run_id='run-001', seed=1, execution_profile='dedicated_publish', order=[[0, 'docen']])))
    for arm, measure in (('cold', 'process_cold_fs_warm'), ('warm', 'warm_steady')):
        cell = cells.build_run_cell(run, 'docen', 'C05', measure=measure)
        assert cell['refusals'] == {}, (measure, cell['refusals'], cell.get('failure_reasons'))
        assert cell['kept_ms'] == [PAYLOAD[arm]['single_edit_ms']]
        assert cell['witness'] == 'settled_pixels' and cell['least_changed_pixels'] == 34
