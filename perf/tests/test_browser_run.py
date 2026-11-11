"""Bookkeeping unit tests and isolated filesystem integration tests."""
import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


class BrowserRun(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('perf.runner.browser_run'),
                             'B1 browser run bookkeeping is missing')
        self.api = importlib.import_module('perf.runner.browser_run')

    def test_schedule_interleaves_and_replays(self):
        schedule = self.api.schedule(['a', 'b', 'c'], 4, 42)
        self.assertEqual(schedule, self.api.schedule(['a', 'b', 'c'], 4, 42))
        for rep in range(4):
            self.assertEqual(sorted(e for r, e in schedule if r == rep), ['a', 'b', 'c'])
        self.assertNotEqual(schedule, self.api.schedule(['a', 'b', 'c'], 4, 43))

    def test_failure_is_data(self):
        def bad():
            raise AssertionError('saturated')
        row = self.api.capture(bad)
        self.assertEqual(row['outcome'], 'failed')
        self.assertIn('saturated', row['failure_reason'])
        self.assertEqual(self.api.capture(lambda: {'outcome': 'ok'})['outcome'], 'ok')

    def test_repos_guard_detects_dirty_and_changed(self):
        self.assertFalse(self.api.repos_modified({'a': ''}, {'a': ''}))
        self.assertTrue(self.api.repos_modified({'a': ''}, {'a': ' M x'}))
        self.assertFalse(self.api.repos_modified({'a': ' M x'}, {'a': ' M x'}))

    def test_integration_unique_immutable_files_and_fixture_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.api.BrowserRun(Path(tmp), 'fake', seed=42, snapshot=lambda: {'a': ''})
            fixture = run.fixture('micro', b'first')
            self.assertIn('micro-a7937b64', fixture.name)
            run.sample('one', {'outcome': 'ok'})
            run.finish({'test': True})
            before = {p.relative_to(run.directory): p.read_bytes() for p in run.directory.rglob('*') if p.is_file()}
            second = self.api.BrowserRun(Path(tmp), 'fake', seed=43, snapshot=lambda: {'a': ''})
            second.finish({})
            self.assertNotEqual(run.run_id, second.run_id)
            self.assertEqual(before, {p.relative_to(run.directory): p.read_bytes() for p in run.directory.rglob('*') if p.is_file()})
            with self.assertRaises(FileExistsError):
                self.api.BrowserRun(Path(tmp), 'fake', run_id=run.run_id, snapshot=lambda: {})
            with self.assertRaises(FileExistsError):
                run.sample('one', {})
            summary = json.loads((run.directory / 'summary.json').read_text())
            self.assertEqual(summary['seed'], 42)
            self.assertEqual(summary['run_id'], run.run_id)

    def test_integration_guard_marks_summary(self):
        snapshots = iter([{'a': ''}, {'a': '?? changed'}])
        with tempfile.TemporaryDirectory() as tmp:
            run = self.api.BrowserRun(Path(tmp), 'fake', snapshot=lambda: next(snapshots))
            result = run.finish({})
            self.assertEqual(result['failure_reason'], 'repos_modified')
            self.assertFalse(result['publishable'])


class EntryPoints(unittest.TestCase):
    def test_all_four_entrypoints_use_run_cli_and_write_once(self):
        import ast
        for name in ['benchmark_warm_cold', 'benchmark_document', 'benchmark_input', 'adversarial_c10_scroll']:
            with self.subTest(runner=name):
                source = (Path(__file__).parents[1] / 'runner' / (name + '.py')).read_text()
                tree = ast.parse(source)
                self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                                    and n.func.id == 'run_cli' for n in ast.walk(tree)), 'entrypoint bypasses B1')
                for node in ast.walk(tree):
                    if isinstance(node, ast.Dict):
                        keys = [n.value for n in node.keys if isinstance(n, ast.Constant)]
                        self.assertEqual(len(keys), len(set(keys)), 'duplicate dictionary key')
                self.assertNotIn('.write_text(', source, 'mutable summary')
                self.assertNotIn('.write_bytes(', source, 'mutable fixture')

    def test_integration_cli_interleaves_continues_and_indexes_failures(self):
        import sys
        from functools import partial
        from perf.runner.browser_run import BrowserRun, run_cli, write_json
        import inspect
        self.assertIn('run_factory', inspect.signature(run_cli).parameters, 'missing injectable run factory')
        calls = []
        def main():
            import argparse
            parser = argparse.ArgumentParser()
            parser.add_argument('--out-root', type=Path)
            parser.add_argument('--editors', nargs='+')
            parser.add_argument('--samples', type=int)
            args = parser.parse_args()
            calls.append(args.editors[0])
            self.assertEqual(args.samples, 1)
            if len(calls) == 1:
                raise AssertionError('readiness failed')
            write_json(args.out_root / 'summary.json', {'outcome': 'ok'})
            return 0
        original = sys.argv
        with tempfile.TemporaryDirectory() as tmp:
            try:
                sys.argv = ['fake', '--out-root', tmp, '--samples', '2', '--seed', '42']
                code = run_cli(main, 'fake', {'a': {}, 'b': {}}, count_flag='--samples',
                               run_factory=partial(BrowserRun, snapshot=lambda: {'a': ''}),
                               facts=(lambda: {'container': False}, lambda: {'renderer': 'fake'}))
                self.assertEqual(code, 0)
                summary = json.loads(next(Path(tmp).glob('fake/*/summary.json')).read_text())
                self.assertEqual(len(summary['samples']), 4)
                self.assertIn('readiness failed', summary['samples'][0]['failure_reason'])
                self.assertEqual(sorted(calls[:2]), ['a', 'b'])
                self.assertEqual(sorted(calls[2:]), ['a', 'b'])
            finally:
                sys.argv = original

    def test_caught_probe_failures_are_indexed(self):
        from perf.runner import browser_run
        self.assertTrue(hasattr(browser_run, 'failure_reasons'), 'missing nested failure indexing')
        self.assertEqual(browser_run.failure_reasons({'support': [
            {'outcome': 'failed', 'failure_reason': 'not ready'},
            {'outcome': 'measured', 'failure_reason': None}]}), ['not ready'])

    def test_integration_invalid_paths_refused_and_fixtures_reused(self):
        from perf.runner.browser_run import BrowserRun
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                BrowserRun(tmp, '../escape', snapshot=lambda: {})
            run = BrowserRun(tmp, 'fake', snapshot=lambda: {})
            one = run.fixture('micro', b'one')
            self.assertEqual(one, run.fixture('micro', b'one'))
            self.assertNotEqual(one, run.fixture('micro', b'two'))
            with self.assertRaises(ValueError):
                run.fixture('../escape', b'bad')
            with self.assertRaises(ValueError):
                run.sample('../escape', {})

    def test_cli_rejects_total_budget_before_running(self):
        import sys
        import contextlib
        import io
        from perf.runner.browser_run import run_cli
        original = sys.argv
        try:
            sys.argv = ['fake', '--samples', '6']
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                run_cli(lambda: self.fail('must not run'), 'fake', {'a': {}},
                        count_flag='--samples', max_repetitions=5)
            self.assertEqual(caught.exception.code, 2)
        finally:
            sys.argv = original

    def test_integration_fallback_fixture_and_probe_evidence(self):
        from perf.runner.browser_run import ACTIVE, CELL, BrowserRun, fixture_path, record_process
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = fixture_path('micro', b'data', root / 'old.docx')
            self.assertEqual(path.read_bytes(), b'data')
            run = BrowserRun(root, 'evidence', snapshot=lambda: {})
            active = ACTIVE.set(run)
            cell = CELL.set({'editor_id': 'fake', 'repetition': 0})
            try:
                self.assertTrue(fixture_path('micro', b'other', path).is_relative_to(run.directory))
                record_process(subprocess.CompletedProcess(['node', 'probe'], 1, 'raw', 'not ready'))
                record = json.loads(next((run.directory / 'evidence').glob('*.json')).read_text())
                self.assertEqual(record['stderr'], 'not ready')
                self.assertEqual(record['returncode'], 1)
            finally:
                ACTIVE.reset(active)
                CELL.reset(cell)
            record_process(subprocess.CompletedProcess([], 0, '', ''))

    def test_cli_help_list_and_invalid_arguments(self):
        import contextlib
        import io
        import sys
        import contextlib
        import io
        from perf.runner.browser_run import run_cli
        original = sys.argv
        try:
            for flag in ['--help', '--list-support']:
                sys.argv = ['fake', flag]
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(run_cli(lambda: 7, 'fake', {'a': {}}), 7)
            for args in [['--repetitions', '0'], ['--editors', 'unknown']]:
                sys.argv = ['fake', *args]
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    run_cli(lambda: self.fail('must not run'), 'fake', {'a': {}})
        finally:
            sys.argv = original

    def test_integration_attempts_carry_run_and_host_provenance(self):
        from perf.runner.artifacts import write_attempt
        from perf.runner.browser_run import ACTIVE, CELL, BrowserRun
        with tempfile.TemporaryDirectory() as tmp:
            run = BrowserRun(tmp, 'fake', snapshot=lambda: {})
            run.hosts['fake'] = {'host_build': 'app_server', 'publishable': False,
                                 'publication_block_reason': 'needs backend'}
            token = ACTIVE.set(run)
            cell = CELL.set({'editor_id': 'fake', 'repetition': 1})
            try:
                path = write_attempt(run.directory / 'attempts', 'failed', {
                    'outcome': 'failed', 'failure_reason': 'readiness', 'boundary': 'model_ready',
                    'samples_ms': [], 'editor_id': 'fake'})
                row = json.loads(path.read_text())
                self.assertEqual(row['run_id'], run.run_id)
                self.assertEqual(row['repetition'], 1)
                self.assertEqual(row['host_build'], 'app_server')
                self.assertFalse(row['publishable'])
                self.assertEqual(row['publication_block_reason'], 'needs backend')
            finally:
                CELL.reset(cell)
                ACTIVE.reset(token)


class DirtyStartIntegration(unittest.TestCase):
    def test_unaccepted_dirt_blocks_publication_without_claiming_modification(self):
        from perf.runner.browser_run import BrowserRun
        dirty = {'/elsewhere/repos/docen': ' M source.ts\n?? new.ts\n'}
        with tempfile.TemporaryDirectory() as tmp:
            result = BrowserRun(tmp, 'dirty', snapshot=lambda: dirty).finish({'publishable': True})
        self.assertEqual(result.get('failure_reason'), 'repos_dirty_at_start')
        self.assertFalse(result['publishable'])
        self.assertEqual(result.get('publication_block_reason'), 'repos_dirty_at_start')
        self.assertIn('/elsewhere/repos/docen', result['repos_dirty_at_start'])
        self.assertIn('source.ts', str(result['repos_dirty_at_start']))

    def test_dirty_start_sample_carries_publication_block_reason(self):
        from perf.runner.browser_run import ACTIVE, BrowserRun
        dirty = {'/elsewhere/repos/docen': ' M source.ts\n'}
        with tempfile.TemporaryDirectory() as tmp:
            run = BrowserRun(tmp, 'dirty', snapshot=lambda: dirty)
            token = ACTIVE.set(run)
            try:
                path = run.sample('0000-plate', {'editor_id': 'plate', 'repetition': 0, 'outcome': 'not_run'})
                row = json.loads(path.read_text())
            finally:
                ACTIVE.reset(token)
        self.assertEqual(row.get('publication_block_reason'), 'repos_dirty_at_start')
        self.assertFalse(row['publishable'])

    def test_cpu_accounting_unavailable_sample_carries_publication_block_reason(self):
        from perf.runner.browser_run import ACTIVE, BrowserRun
        with tempfile.TemporaryDirectory() as tmp:
            run = BrowserRun(tmp, 'acct', snapshot=lambda: {}, accounting_reader=lambda: {'available': False})
            token = ACTIVE.set(run)
            try:
                path = run.sample('0000-plate', {'editor_id': 'plate', 'repetition': 0, 'outcome': 'ok'})
                row = json.loads(path.read_text())
            finally:
                ACTIVE.reset(token)
        self.assertEqual(row.get('publication_block_reason'), 'cpu_accounting_unavailable')

    def test_allowed_report_e_deletions_keep_reason(self):
        from perf.runner.browser_run import BrowserRun
        dirty = {'/elsewhere/repos/office-open': ' D scripts/coverage/a.py\n'}
        with tempfile.TemporaryDirectory() as tmp:
            result = BrowserRun(tmp, 'allowed', snapshot=lambda: dirty).finish({'publishable': True})
        self.assertTrue(result['publishable'])
        self.assertIn('27 coverage scripts deleted', result['repos_dirty_allowed']['/elsewhere/repos/office-open'])
        self.assertTrue(result['repos_unchanged'])
