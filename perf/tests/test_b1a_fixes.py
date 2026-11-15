"""Issue #132 regressions; filesystem/host calls are isolated integration tests."""

import argparse
import ast
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
import unittest

from perf.runner import browser_run as api
from perf.runner.benchmark_ci_contract import _host_base
from perf.schema import validate_environment


class BookkeepingIntegration(unittest.TestCase):
    def invoke(self, root, main, *options, **kwargs):
        original = sys.argv
        try:
            sys.argv = ['fake', '--out-root', str(root), '--seed', '1', *options]
            return api.run_cli(
                main,
                'fake',
                {'a': {}},
                run_factory=partial(api.BrowserRun, snapshot=lambda: {}),
                facts=(lambda: {}, lambda: {}),
                **kwargs,
            )
        finally:
            sys.argv = original

    def test_skips_are_listed_without_failing_healthy_cell(self):
        with tempfile.TemporaryDirectory() as tmp:

            def main():
                root = Path(sys.argv[sys.argv.index('--out-root') + 1])
                for outcome in ('not_run', 'refused', 'not_applicable', 'unsupported', 'unverified'):
                    api.write_json(
                        root / (outcome + '.json'), {'outcome': outcome, 'failure_reason': outcome + ' reason'}
                    )
                return 0

            self.invoke(tmp, main)
            row = json.loads(next(Path(tmp).glob('fake/*/summary.json')).read_text())['samples'][0]
            self.assertEqual(row['outcome'], 'ok')
            self.assertIsNone(row['failure_reason'])
            self.assertEqual(
                {r['outcome'] for r in row['non_failure_outcomes']},
                {'not_run', 'refused', 'not_applicable', 'unsupported', 'unverified'},
            )

    def test_explicit_failure_and_exit_status_still_fail(self):
        for status in (0, 3):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:

                def main():
                    root = Path(sys.argv[sys.argv.index('--out-root') + 1])
                    api.write_json(root / 'attempt.json', {'outcome': 'failed', 'failure_reason': 'readiness'})
                    return status

                self.invoke(tmp, main)
                row = json.loads(next(Path(tmp).glob('fake/*/summary.json')).read_text())['samples'][0]
                self.assertEqual(row['outcome'], 'failed')
                self.assertIn('readiness', row['failure_reason'])

    def test_selected_profile_controls_total_budget(self):
        from perf.schema import sample_budget_for_profile

        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            try:
                self.invoke(
                    tmp,
                    lambda: calls.append(1) or 0,
                    '--execution-profile',
                    'dedicated_publish',
                    '--host-class',
                    'dedicated',
                    '--samples',
                    '30',
                    count_flag='--samples',
                    max_repetitions=lambda profile: sample_budget_for_profile(profile, 'fresh_process'),
                )
            except TypeError as exc:
                self.fail('profile-specific budget is not resolved: ' + str(exc))
            self.assertEqual(len(calls), 30)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as caught:
                self.invoke(
                    tmp,
                    lambda: self.fail('over-budget cell must not run'),
                    '--samples',
                    '6',
                    count_flag='--samples',
                    max_repetitions=lambda profile: sample_budget_for_profile(profile, 'fresh_process'),
                )
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_nonzero_exit_without_failure_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.invoke(tmp, lambda: 7)
            row = json.loads(next(Path(tmp).glob('fake/*/summary.json')).read_text())['samples'][0]
            self.assertEqual(row['outcome'], 'failed')
            self.assertEqual(row['failure_reason'], 'exit 7')

    def test_short_help_creates_no_run(self):
        with tempfile.TemporaryDirectory() as tmp:

            def main():
                raise SystemExit(0)

            with self.assertRaises(SystemExit) as caught:
                self.invoke(tmp, main, '-h')
            self.assertEqual(caught.exception.code, 0)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_fallback_accepts_identical_and_refuses_corrupt_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fallback = Path(tmp) / 'fixture.docx'
            first = api.fixture_path('micro', b'same', fallback)
            try:
                second = api.fixture_path('micro', b'same', fallback)
            except FileExistsError:
                self.fail('identical fallback fixture must be reusable')
            self.assertEqual(first, second)
            first.write_bytes(b'corrupt')
            with self.assertRaises(FileExistsError):
                api.fixture_path('micro', b'same', fallback)
            self.assertEqual(first.read_bytes(), b'corrupt')

    def test_profile_and_host_reach_environment_and_summary(self):
        for host_class in ('dedicated', 'ci_coarse'):
            with self.subTest(host_class=host_class), tempfile.TemporaryDirectory() as tmp:

                def main():
                    parser = argparse.ArgumentParser()
                    parser.add_argument('--out-root', type=Path)
                    parser.add_argument('--editors', nargs='+')
                    args, unknown = parser.parse_known_args()
                    self.assertEqual(unknown, [], 'bookkeeping flags leaked to cell parser')
                    env = _host_base(
                        editor_id='fake',
                        editor_version='1',
                        execution_profile='ci_broad',
                        fixture_sha256='a' * 64,
                        workload_row=dict(
                            workload_id='micro-paragraphs', paragraphs=1, unicode_class='ascii', match_count=0
                        ),
                        docx_size=1,
                        cache_state='warm_steady',
                        repetition_unit='fresh_process',
                        run_kind='timing',
                        feature_profile_name='P0',
                    )
                    api.write_json(args.out_root / 'trial.json', {'environment': env})
                    return 0

                self.invoke(tmp, main, '--execution-profile', 'dedicated_publish', '--host-class', host_class)
                summary = json.loads(next(Path(tmp).glob('fake/*/summary.json')).read_text())
                self.assertEqual(summary.get('execution_profile'), 'dedicated_publish')
                self.assertEqual(summary.get('host_class'), host_class)
                cell = summary['samples'][0]
                if host_class == 'dedicated':
                    env = json.loads((Path(cell['cell_directory']) / 'trial.json').read_text())['environment']
                    self.assertEqual(env['execution_profile'], 'dedicated_publish')
                    self.assertEqual(env['host_class'], host_class)
                    validate_environment(env)
                    self.assertEqual(cell['outcome'], 'ok')
                else:
                    self.assertEqual(cell['outcome'], 'failed')
                    self.assertIn('dedicated_publish requires', cell['failure_reason'])


class SummaryGuard(unittest.TestCase):
    @staticmethod
    def write_violations(tree):
        """Reject mutable/unknown writes; exclusive opens must be statically evident."""
        violations = []
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        def exclusive(call):
            mode = next((k.value for k in call.keywords if k.arg == 'mode'), None)
            if mode is None and len(call.args) > (1 if isinstance(call.func, ast.Name) else 0):
                mode = call.args[1 if isinstance(call.func, ast.Name) else 0]
            return isinstance(mode, ast.Constant) and isinstance(mode.value, str) and 'x' in mode.value
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            if name.endswith(('.write_text', '.write_bytes')):
                violations.append(node)
            elif name == 'os.open':
                flags = node.args[1] if len(node.args) > 1 else ast.Constant(None)
                if isinstance(flags, ast.Name):
                    assignments = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
                                   and any(isinstance(t, ast.Name) and t.id == flags.id for t in n.targets)]
                    flags = assignments[0] if len(assignments) == 1 else flags
                text = ast.unparse(flags)
                if 'os.O_EXCL' not in text or 'os.O_CREAT' not in text or 'os.O_TRUNC' in text:
                    violations.append(node)
            elif name == 'open' or name.endswith('.open'):
                if not exclusive(node):
                    # Read-only literal modes (including omitted mode) are allowed.
                    offset = 1 if isinstance(node.func, ast.Name) else 0
                    mode = next((k.value for k in node.keywords if k.arg == 'mode'),
                                node.args[offset] if len(node.args) > offset else ast.Constant('r'))
                    if not isinstance(mode, ast.Constant) or mode.value not in ('r', 'rb', 'rt'):
                        violations.append(node)
            elif name == 'json.dump':
                parent = parents.get(node)
                safe = False
                while parent is not None:
                    if isinstance(parent, ast.With):
                        safe = any(isinstance(item.context_expr, ast.Call) and exclusive(item.context_expr)
                                   and len(node.args) > 1 and ast.unparse(item.optional_vars) == ast.unparse(node.args[1])
                                   for item in parent.items if item.optional_vars is not None)
                        if safe:
                            break
                    parent = parents.get(parent)
                if not safe:
                    violations.append(node)
        return violations

    def test_summary_modules_have_no_duplicate_keys_or_mutable_writes(self):
        for name in (
            'browser_run',
            'browser_hosts',
            'benchmark_warm_cold',
            'benchmark_document',
            'benchmark_input',
            'adversarial_c10_scroll',
            'criteria_input_io',
            'benchmark_ci_contract',
            'artifacts',
        ):
            with self.subTest(module=name):
                tree = ast.parse((Path(__file__).parents[1] / 'runner' / (name + '.py')).read_text())
                # Exact legacy exceptions: these are the non-browser CI CLI's
                # fixture bytes and summary, outside B1 ownership. No new writer
                # in these modules is exempt, including browser environment code.
                legacy = {
                    "indocx.write_bytes(docx_body)",
                    "summary_path.write_text(json.dumps(payload, indent=2) + '\\n', encoding='utf-8')",
                } if name == 'benchmark_ci_contract' else (
                    # 61518eec (2026-11-10, "Pass input-lane expected body via
                    # file instead of env b64"): the expected-body sidecar is
                    # probe input written once per editor before launch, not a
                    # mutable summary or fixture of record.
                    {"body_path.write_text(body, encoding='utf-8')"}
                    if name == 'benchmark_input' else set()
                )
                for node in self.write_violations(tree):
                    self.assertIn(ast.unparse(node), legacy)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Dict):
                        keys = [key.value for key in node.keys if isinstance(key, ast.Constant)]
                        self.assertEqual(len(keys), len(set(keys)))
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        # the same adjudicated exemptions as the legacy set
                        # above (61518eec's expected-body sidecar).
                        if name != 'benchmark_ci_contract' and ast.unparse(node) not in legacy:
                            self.assertNotIn(node.func.attr, ('write_text', 'write_bytes'))
