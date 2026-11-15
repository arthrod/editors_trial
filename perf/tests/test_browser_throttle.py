"""CPU accounting unit tests and fake-file/bookkeeping integration tests (#129).

Removing throttle refusal, losing a boundary, or fabricating missing counters
must break these tests. Filesystem tests explicitly use temporary fake roots.
"""

import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from perf.runner.browser_run import BrowserRun


def snapshot(n=2, usec=10, ticks=100, steal=1, load=2):
    return dict(
        available=True,
        nr_periods=10 + n,
        nr_throttled=n,
        throttled_usec=usec,
        cpu_ticks=dict(total=ticks, steal=steal),
        loadavg=[load, 3.0, 4.0],
        cpu_max='800000 100000',
        cpu_count_visible=64,
        cgroup_path='/fake/cgroup',
    )


class Accounting(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec('perf.runner.browser_throttle'), 'CPU accounting reader is missing'
        )
        self.api = importlib.import_module('perf.runner.browser_throttle')

    def test_t2_macos_unavailable_is_not_zero(self):
        result = self.api.read_cpu_accounting(platform='darwin')
        self.assertEqual(set(result), {'available', 'reason'})
        self.assertFalse(result['available'])
        self.assertIn('darwin', result['reason'])

    def test_integration_fake_files_and_missing_or_malformed_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cg, proc = root / 'cg', root / 'proc'
            cg.mkdir()
            proc.mkdir()
            files = {
                cg / 'cpu.stat': 'usage_usec 90\nnr_periods 12\nnr_throttled 2\nthrottled_usec 10\n',
                cg / 'cpu.max': '800000 100000\n',
                proc / 'stat': 'cpu 10 20 30 40 0 0 0 5 90 80\ncpu0 1 2\n',
                proc / 'loadavg': '2.5 3.5 4.5 2/30 100\n',
            }
            for path, content in files.items():
                path.write_text(content)

            def read():
                return self.api.read_cpu_accounting(
                    cgroup_root=cg, proc_root=proc, platform='linux', cpu_count=lambda: 64
                )

            value = read()
            self.assertTrue(value['available'])
            self.assertEqual(value['cpu_ticks'], {'total': 105, 'steal': 5})
            self.assertEqual(value['nr_throttled'], 2)
            self.assertEqual(value['nr_periods'], 12)
            self.assertEqual(value['throttled_usec'], 10)
            self.assertEqual(value['loadavg'], [2.5, 3.5, 4.5])
            self.assertEqual(value['cpu_max'], '800000 100000')
            self.assertEqual(value['cpu_count_visible'], 64)
            for path in files:
                with self.subTest(missing=path.name):
                    path.unlink()
                    self.assertFalse(read()['available'])
                    self.assertTrue(read()['reason'])
                    path.write_text(files[path])
                with self.subTest(malformed=path.name):
                    path.write_text('invalid')
                    self.assertFalse(read()['available'])
                    path.write_text(files[path])
            for path, malformed in [
                (cg / 'cpu.stat', 'nr_periods -1\nnr_throttled 2\nthrottled_usec 10'),
                (proc / 'stat', 'cpu -1 0 0 0 0 0 0 0'),
                (proc / 'loadavg', 'nan 2 3'),
                (proc / 'loadavg', '1 2'),
            ]:
                path.write_text(malformed)
                self.assertFalse(read()['available'])
                path.write_text(files[path])
            self.assertFalse(
                self.api.read_cpu_accounting(cgroup_root=cg, proc_root=proc, platform='linux', cpu_count=lambda: None)[
                    'available'
                ]
            )
            from unittest.mock import patch

            with patch('perf.runner.host._cgroup_dirs', return_value=[str(cg)]):
                self.assertTrue(
                    self.api.read_cpu_accounting(proc_root=proc, platform='linux', cpu_count=lambda: 64)['available']
                )
            for bad in ['max 0', '-1 100000', '800000 0']:
                (cg / 'cpu.max').write_text(bad)
                self.assertFalse(read()['available'])
            (cg / 'cpu.max').write_text('max 100000')
            self.assertEqual(read()['cpu_max'], 'max 100000')

    def test_delta_and_counter_reset(self):
        result = self.api.accounting_delta(snapshot(), snapshot(3, 50, 200, 3, 8))
        self.assertEqual(
            result['delta'], dict(nr_periods=1, nr_throttled=1, throttled_usec=40, total_ticks=100, steal_ticks=2)
        )
        self.assertEqual(result['steal_percent'], 2.0)
        self.assertIsNone(self.api.accounting_delta(snapshot(), snapshot())['steal_percent'])
        for after in [snapshot(1), dict(snapshot(), cpu_max='max 100000')]:
            self.assertFalse(self.api.accounting_delta(snapshot(), after)['available'])
        unavailable = dict(available=False, reason='no cgroup v2')
        self.assertEqual(self.api.accounting_delta(unavailable, snapshot()), unavailable)
        self.assertEqual(self.api.accounting_delta(snapshot(), unavailable), unavailable)


class RunIntegration(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(BrowserRun, 'begin_sample'), 'before-sample boundary is missing')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.current = snapshot()
        self.run = BrowserRun(
            self.tmp.name,
            'fake',
            seed=42,
            run_id='test',
            snapshot=lambda: {},
            accounting_reader=lambda: dict(self.current),
        )

    def test_t1_rising_throttle_refuses_time_unchanged_keeps_it(self):
        self.run.begin_sample()
        self.current = snapshot(3, 10_050, 200, 3, 8)
        path = self.run.sample('throttled', dict(outcome='measured', samples_ms=[12], duration_ms=12))
        row = json.loads(path.read_text())
        self.assertEqual((row['outcome'], row['failure_reason']), ('failed', 'cpu_throttled'))
        self.assertNotIn('duration_ms', row)
        self.assertNotIn('samples_ms', row)
        self.assertEqual(row['cpu_accounting']['before']['nr_throttled'], 2)
        self.assertEqual(row['cpu_accounting']['after']['nr_throttled'], 3)
        self.assertEqual(row['cpu_accounting']['delta']['throttled_usec'], 10_040)
        self.run.begin_sample()
        self.run.sample('kept', dict(outcome='measured', samples_ms=[9]))
        self.assertEqual(self.run.samples[1]['samples_ms'], [9])
        # every kept sample records its tolerated throttling (lax layer).
        self.assertEqual(self.run.samples[1]['throttled_usec'], 0)
        result = self.run.finish({'publishable': True})['cpu_accounting']
        self.assertEqual(result['samples_refused'], 1)
        self.assertEqual(result['samples_total'], 2)
        self.assertEqual(result['throttled_usec'], 10_040)
        self.assertEqual(result['steal_percent'], 2.0)
        self.assertEqual(result['loadavg_range'], [[2, 8], [3, 3], [4, 4]])
        self.assertEqual(result['cpu_max'], '800000 100000')
        self.assertEqual(result['cpu_count_visible'], 64)

    def test_p2_straddling_throttle_is_refused(self):
        self.run.begin_sample()
        self.current = snapshot(usec=94010)
        row = json.loads(self.run.sample('straddling', dict(outcome='measured', samples_ms=[42])).read_text())
        self.assertEqual(row['outcome'], 'failed')
        self.assertEqual(row['failure_reason'], 'cpu_throttled')
        self.assertNotIn('samples_ms', row)

    def test_p5_refusal_removes_nested_measurements(self):
        self.run.begin_sample()
        self.current = snapshot(3, 10_050)
        original = dict(
            outcome='measured',
            probe={'latency_ms': 10},
            timings_ms_like=[1],
            arbitrary_measurement={'value': 42, 'unit': 'ms'},
        )
        row = json.loads(self.run.sample('nested-timing', original).read_text())
        self.assertNotIn('probe', row)
        self.assertNotIn('timings_ms_like', row)
        self.assertNotIn('arbitrary_measurement', row)
        raw = json.loads((Path(row['rejected_evidence_directory']) / 'sample.json').read_text())
        self.assertEqual(raw, original)
        self.assertEqual(original['probe']['latency_ms'], 10)

    def test_nested_brackets_restore_outer_and_count_diagnostics_separately(self):
        self.run.begin_sample()
        self.current = snapshot(3, 10_050)
        self.run.begin_sample()
        self.run.sample('inner', dict(outcome='measured', samples_ms=[10]))
        self.run.sample('outer', dict(outcome='measured', samples_ms=[20]))
        inner, outer = self.run.samples
        self.assertEqual(outer['cpu_accounting']['before']['nr_throttled'], 2)
        self.assertEqual(inner['outcome'], 'measured')
        self.assertEqual(outer['failure_reason'], 'cpu_throttled')
        totals = self.run.finish({})['cpu_accounting']
        self.assertEqual((totals['samples_total'], totals['samples_refused']), (1, 1))
        self.assertEqual(totals['diagnostics_total'], 1)
        self.assertEqual(totals['diagnostics_refused'], 0)

    def test_legacy_saturation_does_not_consume_cell_bracket(self):
        from perf.runner.browser_run import CELL

        token = CELL.set({'repetition': 0, 'editor_id': 'fake'})
        try:
            self.run.begin_sample()
            self.current = snapshot(3, 10_050)
            self.run.sample('saturation-0-fake', dict(outcome='failed', failure_reason='warm_cold_identical'))
            self.run.sample('0000-fake', dict(outcome='ok'))
        finally:
            CELL.reset(token)
        totals = self.run.finish({})['cpu_accounting']
        self.assertEqual(totals['samples_total'], 1)
        self.assertEqual(totals['samples_refused'], 1)
        self.assertEqual(totals['diagnostics_refused'], 1)
        self.assertEqual(self.run.samples[-1]['cpu_accounting']['before']['nr_throttled'], 2)

    def test_quarantine_preserves_cell_named_sample_json(self):
        cell = self.run.directory / 'cells' / 'cell'
        cell.mkdir(parents=True)
        (cell / 'sample.json').write_text('{"duration_ms": 42}')
        self.run.begin_sample()
        self.current = snapshot(3, 10_050)
        error = None
        try:
            self.run.sample('cell', dict(outcome='ok', cell_directory=str(cell)))
        except FileExistsError as exc:
            error = exc
        self.assertIsNone(error, 'raw row must not collide with existing cell evidence')
        rejected = Path(self.run.samples[0]['rejected_evidence_directory'])
        self.assertEqual((rejected / 'cell' / 'sample.json').read_text(), '{"duration_ms": 42}')
        self.assertEqual(json.loads((rejected / 'sample.json').read_text())['outcome'], 'ok')

    def test_context_bracket_restores_after_exception(self):
        self.run.begin_sample()
        self.current = snapshot(3, 50)
        bracket = self.run.begin_sample()
        self.assertTrue(hasattr(bracket, '__enter__'), 'bracket needs exception-safe context management')
        with self.assertRaisesRegex(ValueError, 'probe failed'):
            with bracket:
                raise ValueError('probe failed')
        self.run.sample('outer', dict(outcome='ok'))
        self.assertEqual(self.run.samples[0]['cpu_accounting']['before']['nr_throttled'], 2)

    def test_missing_accounting_blocks_quota_container_only(self):
        self.current = dict(available=False, reason='no cgroup v2')
        self.run.begin_sample()
        self.run.sample('unknown', dict(outcome='ok'))
        self.assertEqual(self.run.samples[0]['cpu_accounting'], self.current)
        result = self.run.finish(dict(publishable=True, host={'container': True, 'cpu_quota': 8}))
        self.assertFalse(result['publishable'])
        self.assertFalse(result['cpu_accounting']['available'])
        self.assertEqual(result['cpu_accounting']['samples_unavailable'], 1)
        self.assertIsNone(result['cpu_accounting']['throttled_usec'])

    def test_missing_begin_never_claims_measured_accounting(self):
        self.run.sample('unbracketed', dict(outcome='ok'))
        self.assertFalse(self.run.samples[0]['cpu_accounting']['available'])
        self.assertIn('before', self.run.samples[0]['cpu_accounting']['reason'])

    def test_partial_outage_cannot_be_hidden_by_run_endpoints(self):
        self.current = dict(available=False, reason='permission denied')
        self.run.begin_sample()
        self.current = snapshot(3, 50, 200, 3)
        self.run.sample('partial', dict(outcome='ok'))
        result = self.run.finish(dict(publishable=True, host={'container': True, 'cpu_quota': 8}))
        self.assertFalse(result['publishable'])
        self.assertFalse(result['cpu_accounting']['available'])

    def test_noncontainer_unavailable_is_disclosed(self):
        self.current = dict(available=False, reason='darwin has no cgroup v2')
        result = self.run.finish(dict(publishable=True, host={'container': False, 'cpu_quota': None}))
        self.assertTrue(result['publishable'])
        self.assertFalse(result['cpu_accounting']['available'])


class BoundaryIntegration(unittest.TestCase):
    def test_t1_cli_fake_files_quarantines_refused_cell(self):
        import sys
        from functools import partial
        from perf.runner.browser_run import run_cli, write_json
        from perf.runner.browser_throttle import read_cpu_accounting

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cg, proc = root / 'cg', root / 'proc'
            cg.mkdir()
            proc.mkdir()
            (cg / 'cpu.max').write_text('800000 100000')
            (proc / 'stat').write_text('cpu 10 0 0 90 0 0 0 0')
            (proc / 'loadavg').write_text('2 3 4 1/2 42')

            def counters(n):
                # 20 ms of throttled time per event: above the max(1 ms, 1 %)
                # tolerance (lax layer, owner 2026-11-11), so the sample refuses.
                (cg / 'cpu.stat').write_text(f'nr_periods {10 + n}\nnr_throttled {n}\nthrottled_usec {n * 20000}\n')

            counters(0)
            calls = []

            def main():
                directory = Path(sys.argv[sys.argv.index('--out-root') + 1])
                calls.append(directory)
                write_json(directory / 'summary.json', dict(outcome='measured', samples_ms=[12]))
                counters(1)  # first sample changes; second remains unchanged
                return 0

            argv = sys.argv
            try:
                sys.argv = ['fake', '--out-root', str(root / 'runs'), '--repetitions', '2']
                run_cli(
                    main,
                    'fake',
                    {'a': {}},
                    facts=(lambda: {'container': True, 'cpu_quota': 8}, lambda: {}),
                    run_factory=partial(
                        BrowserRun,
                        snapshot=lambda: {},
                        accounting_reader=partial(
                            read_cpu_accounting, cgroup_root=cg, proc_root=proc, platform='linux', cpu_count=lambda: 64
                        ),
                    ),
                )
            finally:
                sys.argv = argv
            summary = json.loads(next((root / 'runs').glob('fake/*/summary.json')).read_text())
            refused, kept = summary['samples']
            self.assertEqual(refused['failure_reason'], 'cpu_throttled')
            self.assertEqual(refused['cpu_accounting']['delta']['nr_throttled'], 1)
            self.assertFalse(calls[0].exists(), 'refused timing must leave the accepted cells tree')
            self.assertNotIn('cell_directory', refused)
            self.assertTrue(Path(refused['rejected_evidence_directory']).is_dir())
            self.assertEqual(kept['outcome'], 'ok')
            self.assertEqual(kept['cpu_accounting']['delta']['nr_throttled'], 0)
            self.assertTrue(calls[1].exists())

    def test_v1_reason_reaches_summary(self):
        from perf.runner.browser_throttle import read_cpu_accounting

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'cpu.cfs_quota_us').write_text('800000')
            (root / 'cpu.cfs_period_us').write_text('100000')

            def read():
                return read_cpu_accounting(cgroup_root=root, platform='linux')

            run = BrowserRun(root, 'v1', seed=1, run_id='v1', snapshot=lambda: {}, accounting_reader=read)
            result = run.finish({'host': {'container': True, 'cpu_quota': 8}})
            self.assertIn('cgroup v1', result['cpu_accounting']['reason'])
            self.assertIn('refusal unavailable', result['cpu_accounting']['reason'])
            self.assertFalse(result['publishable'])

    def test_macos_summary_retains_known_host_cpu_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = BrowserRun(
                tmp, 'fake', snapshot=lambda: {}, accounting_reader=lambda: {'available': False, 'reason': 'darwin'}
            )
            result = run.finish({'host': {'cpu_cores_logical': 12}})
            self.assertEqual(result['cpu_accounting']['cpu_count_visible'], 12)

    def test_multiple_quota_ancestors_are_not_silently_ignored(self):
        from unittest.mock import patch
        from perf.runner.browser_throttle import read_cpu_accounting

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, quota in [('parent', 800000), ('child', 1600000)]:
                cg = root / name
                cg.mkdir()
                (cg / 'cpu.max').write_text(f'{quota} 100000')
                (cg / 'cpu.stat').write_text('nr_periods 10\nnr_throttled 0\nthrottled_usec 0')
            (root / 'stat').write_text('cpu 10 0 0 90 0 0 0 0')
            (root / 'loadavg').write_text('2 3 4')
            # Only replace mount/membership discovery; real parsers read fake files.
            with patch('perf.runner.host._cgroup_dirs', return_value=[str(root / 'child'), str(root / 'parent')]):
                result = read_cpu_accounting(proc_root=root, platform='linux')
            self.assertFalse(result['available'], 'multiple quota sources cannot silently collapse to one')
            self.assertIn('multiple', result['reason'])


class MissingOutputIntegration(unittest.TestCase):
    def test_failed_cli_without_files_still_records_throttling(self):
        import sys
        from functools import partial
        from perf.runner.browser_run import run_cli

        current = [snapshot()]

        def main():
            current[0] = snapshot(3, 50_000, 200, 3)
            return 1

        with tempfile.TemporaryDirectory() as tmp:
            argv = sys.argv
            error = None
            try:
                sys.argv = ['fake', '--out-root', tmp]
                run_cli(
                    main,
                    'fake',
                    {'a': {}},
                    facts=(lambda: {}, lambda: {}),
                    run_factory=partial(BrowserRun, snapshot=lambda: {}, accounting_reader=lambda: current[0]),
                )
            except Exception as exc:
                error = exc
            finally:
                sys.argv = argv
            self.assertIsNone(error, 'missing cell output must not abort accounting')
            summary = json.loads(next(Path(tmp).glob('fake/*/summary.json')).read_text())
            row = summary['samples'][0]
            self.assertEqual(row['failure_reason'], 'cpu_throttled')
            self.assertEqual(row['exit_code'], 1)
            self.assertEqual(row['cpu_accounting']['delta']['nr_throttled'], 1)


if __name__ == '__main__':
    unittest.main()
