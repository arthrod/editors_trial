"""Immutable browser invocations; one shuffled editor pass per repetition.

The CLI adapter calls the existing measurement body with one repetition. It
never changes the probe clocks. Cell summaries and attempts remain separate;
the invocation summary indexes them instead of pooling distributions.
"""
from __future__ import annotations

import argparse
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys
import uuid

from perf.runner.order import editor_order
from perf.runner.browser_throttle import read_cpu_accounting, accounting_delta, accounting_summary

REPO = Path(__file__).resolve().parents[2]
ACTIVE = ContextVar('browser_run', default=None)
CELL = ContextVar('browser_cell', default=None)


def execution_profile(default='ci_broad'):
    run = ACTIVE.get()
    return run.execution_profile if run is not None else default


def host_class(default='ci_coarse'):
    run = ACTIVE.get()
    return run.host_class if run is not None else default


def schedule(editors, repetitions, seed):
    return [(rep, editor) for rep in range(repetitions)
            for editor in editor_order(editors, seed + rep)]


def capture(call):
    try:
        return call()
    except Exception as exc:
        return {'outcome': 'failed', 'failure_reason': f'{type(exc).__name__}: {exc}'}


def repo_roots():
    # Worktrees intentionally do not carry the editor checkouts or symlink them.
    return sorted({p.resolve() for p in (REPO / 'repos', (REPO / 'harness').resolve().parent / 'repos')
                   if p.is_dir()})


def repo_snapshot():
    result = {}
    for root in repo_roots():
        for path in sorted(root.iterdir()):
            if (path / '.git').exists():
                proc = subprocess.run(['git', '-C', str(path), 'status', '--porcelain'],
                                      capture_output=True, text=True, check=True)
                result[str(path)] = proc.stdout
    if not result:
        raise RuntimeError('no editor checkouts found for repos guard')
    return result


def repos_modified(before, after):
    return before != after


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


class BrowserRun:
    def __init__(self, out_root, runner, *, seed=None, run_id=None, snapshot=repo_snapshot,
                 accounting_reader=read_cpu_accounting):
        self.seed = seed if seed is not None else secrets.randbits(32)
        self.run_id = run_id or (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex)
        for name in (runner, self.run_id):
            if Path(name).name != name or name in ('.', '..'):
                raise ValueError('invalid run path component')
        self.out_root = Path(out_root).resolve()
        self.directory = self.out_root / runner / self.run_id
        self.directory.mkdir(parents=True, exist_ok=False)
        self.snapshot = snapshot
        self.before = snapshot()
        self.hosts = {}
        self.fixtures = {}
        self.samples = []
        self.execution_profile = 'ci_broad'
        self.host_class = 'ci_coarse'
        self.accounting_reader = accounting_reader
        self.accounting_start = accounting_reader()
        self.sample_start = None

    def fixture(self, workload, data):
        if Path(workload).name != workload or workload in ('.', '..'):
            raise ValueError('invalid workload')
        sha = hashlib.sha256(data).hexdigest()
        key = (workload, sha)
        if key in self.fixtures:
            return self.fixtures[key]
        path = self.directory / 'fixtures' / f'{workload}-{sha[:16]}.docx'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        self.fixtures[key] = path
        return path

    def begin_sample(self):
        """Bracket the measurement, including any nested diagnostic samples."""
        self.sample_start = self.accounting_reader()

    def sample(self, name, row):
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('invalid sample name')
        before = self.sample_start or {'available': False, 'reason': 'before-sample accounting not captured'}
        accounting = accounting_delta(before, self.accounting_reader())
        value = {**row, 'run_id': self.run_id, 'seed': self.seed, 'cpu_accounting': accounting}
        if accounting['available'] and accounting['delta']['nr_throttled'] > 0:
            # The underlying cell/probe files remain raw evidence, not accepted times.
            value = {key: val for key, val in value.items() if not key.endswith('_ms')}
            value.update(outcome='failed', failure_reason='cpu_throttled', publishable=False)
            if value.get('cell_directory'):
                source = Path(value.pop('cell_directory'))
                destination = self.directory / 'rejected-evidence' / name
                if source.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    source.rename(destination)
                    value['rejected_evidence_directory'] = str(destination)
        path = self.directory / 'samples' / (name + '.json')
        write_json(path, value)
        self.samples.append(value)
        return path

    def finish(self, summary):
        accounting = accounting_summary(self.accounting_start, self.accounting_reader(), self.samples)
        after = self.snapshot()
        result = {**summary, 'run_id': self.run_id, 'seed': self.seed,
                  'samples': self.samples, 'hosts': self.hosts, 'cpu_accounting': accounting,
                  'execution_profile': self.execution_profile, 'host_class': self.host_class,
                  'repos_before': self.before, 'repos_after': after,
                  'fixtures': [str(p) for p in self.fixtures.values()]}
        host = result.get('host', {})
        if accounting['cpu_count_visible'] is None:
            accounting['cpu_count_visible'] = host.get('cpu_cores_logical')
        if host.get('container') and host.get('cpu_quota') and not accounting['available']:
            result.update(publishable=False, publication_block_reason='cpu_accounting_unavailable')
        from perf.runner.speed_headless import _dirty_verdict
        allowed, refused = {}, {}
        for checkout, porcelain in self.before.items():
            if not porcelain:
                continue
            rows = [[line[:2].strip()[:1], line[3:]]
                    for line in porcelain.splitlines() if len(line) > 3]
            ok, reason = _dirty_verdict('repos/' + Path(checkout).name, rows)
            if ok:
                allowed[checkout] = reason
            else:
                refused[checkout] = {'reason': reason, 'paths': [row[1] for row in rows]}
        result.update(repos_dirty_allowed=allowed, repos_dirty_at_start=refused,
                      repos_unchanged=not repos_modified(self.before, after))
        if refused:
            result.update(failure_reason='repos_dirty_at_start', publishable=False)
        if repos_modified(self.before, after):
            result.update(outcome='failed', failure_reason='repos_modified', publishable=False)
        write_json(self.directory / 'summary.json', result)
        return result


def fixture_path(workload, data, fallback):
    run = ACTIVE.get()
    if run is not None:
        return run.fixture(workload, data)
    path = Path(fallback).with_name(f'{workload}-{hashlib.sha256(data).hexdigest()[:16]}.docx')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise
    return path



def failure_reasons(value):
    if isinstance(value, dict):
        own = [value['failure_reason']] if value.get('outcome') == 'failed' and value.get('failure_reason') else []
        return own + [reason for key, child in value.items() if key != 'failure_reason'
                      for reason in failure_reasons(child)]
    if isinstance(value, list):
        return [reason for child in value for reason in failure_reasons(child)]
    return []


def non_failure_outcomes(value):
    """Retain skipped/refused rows without treating them as cell failures."""
    if isinstance(value, dict):
        own = [value] if value.get('outcome') in ('not_run', 'refused', 'not_applicable', 'unsupported', 'unverified') else []
        return own + [row for child in value.values() for row in non_failure_outcomes(child)]
    if isinstance(value, list):
        return [row for child in value for row in non_failure_outcomes(child)]
    return []


def has_failure(value):
    if isinstance(value, dict):
        return value.get('outcome') == 'failed' or any(has_failure(child) for child in value.values())
    if isinstance(value, list):
        return any(has_failure(child) for child in value)
    return False


def record_process(proc):
    """Keep the original probe response and stderr before parsing or refusing."""
    run = ACTIVE.get()
    if run is not None:
        write_json(run.directory / 'evidence' / (uuid.uuid4().hex + '.json'), {
            'run_id': run.run_id, **(CELL.get() or {}), 'command': proc.args,
            'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr,
        })


def rendering_facts():
    proc = subprocess.run(['node', str(Path(__file__).with_name('browser_environment.mjs'))],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    return json.loads(proc.stdout)


def run_cli(main, runner, targets, *, count_flag=None, default_count=1, single=False, run_factory=BrowserRun, max_repetitions=None, facts=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--out-root', type=Path, default=REPO / 'perf' / 'out')
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--run-id', default=None)
    parser.add_argument('--execution-profile', choices=('ci_contract', 'ci_broad', 'dedicated_publish'), default='ci_broad')
    parser.add_argument('--host-class', choices=('ci_coarse', 'dedicated'), default='ci_coarse')
    parser.add_argument('--editor' if single else '--editors', nargs=None if single else '+',
                        default='plate' if single else list(targets), dest='editors')
    if count_flag:
        parser.add_argument(count_flag, type=int, default=default_count, dest='repetitions')
    else:
        parser.add_argument('--repetitions', type=int, default=1)
    args, rest = parser.parse_known_args()
    if '--help' in rest or '-h' in rest:
        print('Bookkeeping options: --seed INT --run-id ID --out-root PATH --repetitions INT (input only) --execution-profile {ci_contract,ci_broad,dedicated_publish} --host-class {ci_coarse,dedicated}')
        return main()
    if '--list-support' in rest:
        return main()
    editors = [args.editors] if single else args.editors
    if args.repetitions < 1 or any(editor not in targets for editor in editors):
        parser.error('positive repetitions and known editors required')
    if callable(max_repetitions):
        max_repetitions = max_repetitions(args.execution_profile)
    if max_repetitions is not None and args.repetitions > max_repetitions:
        parser.error(f'repetitions exceed profile budget ({max_repetitions})')
    run = run_factory(args.out_root, runner, seed=args.seed, run_id=args.run_id)
    run.execution_profile = args.execution_profile
    run.host_class = args.host_class
    token = ACTIVE.set(run)
    original = sys.argv
    order = schedule(editors, args.repetitions, run.seed)
    from perf.runner.host import host_record
    host_probe, renderer_probe = facts or (host_record, rendering_facts)
    host = capture(host_probe)
    rendering = capture(renderer_probe)
    try:
        for rep, editor in order:
            name = f'{rep:04d}-{editor}'
            directory = run.directory / 'cells' / name
            cell_token = CELL.set({'repetition': rep, 'editor_id': editor})
            sys.argv = [original[0], *rest, '--out-root', str(directory),
                        '--editor' if single else '--editors', editor]
            if count_flag:
                sys.argv += [count_flag, '1']
            def invoke():
                status = main()
                reasons = []
                skipped = []
                failed = bool(status)
                for path in sorted(directory.rglob('*.json')):
                    value = json.loads(path.read_text())
                    reasons.extend(failure_reasons(value))
                    failed = failed or has_failure(value)
                    skipped.extend({'file': str(path), **row} for row in non_failure_outcomes(value))
                return {'outcome': 'failed' if failed else 'ok',
                        'non_failure_outcomes': skipped,
                        'failure_reason': '; '.join(dict.fromkeys(reasons)) or (f'exit {status}' if status else None),
                        'exit_code': status, 'cell_directory': str(directory)}
            try:
                run.begin_sample()
                row = capture(invoke)
                row.update(repetition=rep, editor_id=editor, cell_directory=str(directory))
                run.sample(name, row)
            finally:
                CELL.reset(cell_token)
        result = run.finish({'runner': runner, 'order': order, 'publishable': False,
                             'host': host, 'headless': True, 'rendering': rendering})
        print(json.dumps({'run_id': run.run_id, 'summary': str(run.directory / 'summary.json'),
                          'samples': len(run.samples), 'failure_reason': result.get('failure_reason')}))
        return 0
    finally:
        sys.argv = original
        ACTIVE.reset(token)
