"""Immutable browser invocations; one shuffled editor pass per repetition.

The CLI adapter calls the existing measurement body with one repetition. It
never changes the probe clocks. Cell summaries and attempts remain separate;
the invocation summary indexes them instead of pooling distributions.

Record-don't-abort: every scheduled cell is recorded, and the run-level
signal aggregates them. The one-line JSON the run prints and summary.json
carry cells_total, cells_measured, cells_refused (environmental refusals:
cpu_throttled, quota-class reasons), cells_failed and the per-reason counts
(cell_failure_reasons). run_cli exits 0 when at least one cell was measured,
3 when none was (every cell failed or was environmentally refused), and 2
for usage errors before any run directory exists.
"""
from __future__ import annotations

import argparse
from collections import Counter
from functools import partial
from contextvars import ContextVar
from contextlib import nullcontext, redirect_stderr
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
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


def capture(call, *, stderr_tail=0):
    """Run call, folding any exception into a failed row (record-don't-abort).

    With stderr_tail, stderr the call writes is buffered and replayed after
    the call, and a SystemExit carrying only an exit code (argparse's
    parser.error) additionally records the last stderr_tail lines of that
    stderr in the row: the message an operator saw on the console must
    survive in the summary, not only "SystemExit: 2".
    """
    buffer = io.StringIO() if stderr_tail else None
    try:
        if buffer is None:
            return call()
        with redirect_stderr(buffer):
            return call()
    except (Exception, SystemExit) as exc:
        from perf.runner.browser_hosts import HostBuildError
        row = {'outcome': 'failed', 'refusal_code': 'host_build' if isinstance(exc, HostBuildError) else 'crash',
               'failure_reason': f'{type(exc).__name__}: {exc}'}
        if buffer is not None and isinstance(exc, SystemExit) and isinstance(exc.code, int):
            lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
            if lines:
                row['failure_stderr_tail'] = '\n'.join(lines[-stderr_tail:])
        return row
    finally:
        if buffer is not None:
            replay = buffer.getvalue()
            if replay:
                sys.stderr.write(replay)


def _read_accounting(reader):
    """A broken accounting probe is unavailable evidence, never a lost run."""
    try:
        reading = reader()
    except Exception as exc:
        return {'available': False, 'reason': f'{type(exc).__name__}: {exc}',
                'exception': {'type': type(exc).__name__, 'message': str(exc)}}
    # The monotonic stamp carries no accounting meaning of its own; it lets
    # accounting_delta state the sample's span, which the throttle tolerance
    # is a percentage of (lax layer, owner decision 2026-11-11).
    if isinstance(reading, dict):
        return {**reading, 'monotonic_ms': time.monotonic() * 1000.0}
    return reading


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


def _under(path, root):
    try:
        Path(path).relative_to(root)
    except ValueError:
        return False
    return True


class BrowserRun:
    def __init__(self, out_root, runner, *, seed=None, run_id=None, snapshot=repo_snapshot,
                 accounting_reader=read_cpu_accounting):
        self.seed = seed if seed is not None else secrets.randbits(32)
        self.run_id = run_id or (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex)
        for name in (runner, self.run_id):
            if Path(name).name != name or name in ('.', '..'):
                raise ValueError('invalid run path component')
        self.out_root = (REPO / out_root).resolve()
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
        self.accounting_start = _read_accounting(accounting_reader)
        self.sample_start = None
        self._sample_parents = []
        self.brackets_force_closed = 0
        self._cell_force_closed = {}

    def publication_block_from_environment(self) -> str | None:
        """Run-wide refusal when an editor checkout was dirty before measurement."""
        from perf.runner.speed_headless import _dirty_verdict

        for checkout, porcelain in self.before.items():
            if not porcelain:
                continue
            rows = [[line[:2].strip()[:1], line[3:]] for line in porcelain.splitlines() if len(line) > 3]
            ok, _reason = _dirty_verdict("repos/" + Path(checkout).name, rows)
            if not ok:
                return "repos_dirty_at_start"
        return None

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
        """Open a nested bracket; optionally use as a context for exception cleanup.

        sample() closes the innermost bracket. The context also closes an
        unfinished bracket when a probe raises, restoring its enclosing cell.
        A bracket left open and later popped by another row is counted as a
        forced closure (per run in brackets_force_closed, and per cell on the
        cell row's marker), never silently absorbed.
        """
        from contextlib import contextmanager

        self._sample_parents.append(self.sample_start)
        self.sample_start = _read_accounting(self.accounting_reader)
        depth = len(self._sample_parents)

        @contextmanager
        def bracket():
            try:
                yield self
            finally:
                while len(self._sample_parents) >= depth:
                    self.sample_start = self._sample_parents.pop()

        return bracket()

    def sample(self, name, row):
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('invalid sample name')
        cell = CELL.get()
        cell_name = f'{cell["repetition"]:04d}-{cell["editor_id"]}' if cell else None
        # The cell owns depth one. Unfinished bare inner brackets must not
        # replace its CPU window or poison subsequent cells' accounting.
        closed = 0
        if cell and name == cell_name:
            while len(self._sample_parents) > 1:
                self.sample_start = self._sample_parents.pop()
                closed += 1
            self.brackets_force_closed += closed
            # Forced closures that earlier rows already counted for this cell
            # still surface on the cell's own row, not only on the row that
            # consumed them, so a shared diagnostic cannot hide the leak.
            closed += self._cell_force_closed.pop((cell['repetition'], cell['editor_id']), 0)
        # Legacy saturation diagnostics share the cell bracket without opening
        # one themselves. Do not consume that bracket or count the row as a cell.
        shared_diagnostic = bool(
            cell and len(self._sample_parents) == 1 and name != cell_name
        )
        # A non-cell row written above depth one consumes a leaked inner
        # bracket it did not open. The CPU accounting stays correct, but the
        # closure is forced: count it per run and attribute it to the
        # enclosing cell instead of silently absorbing the leak.
        consumed_leak = bool(cell and name != cell_name and len(self._sample_parents) > 1)
        if consumed_leak:
            self.brackets_force_closed += 1
            key = (cell['repetition'], cell['editor_id'])
            self._cell_force_closed[key] = self._cell_force_closed.get(key, 0) + 1
            closed += 1
        row = {**(cell or {}), **row}
        if closed:
            row = {**row, 'brackets_force_closed': closed}
        diagnostic = shared_diagnostic or len(self._sample_parents) > 1
        before = self.sample_start or {'available': False, 'reason': 'before-sample accounting not captured'}
        after = _read_accounting(self.accounting_reader)
        accounting = accounting_delta(before, after)
        if 'exception' in before or 'exception' in after:
            # Keep raised errors even when delta reports only the first outage.
            accounting.update(before=before, after=after)
        if self.host_class == 'shared_guarded' and not accounting['available']:
            destination = self.directory / 'rejected-evidence' / name
            source = Path(row['cell_directory']) if row.get('cell_directory') else None
            if source is not None and source.exists():
                destination.mkdir(parents=True, exist_ok=True)
                source.rename(destination / 'cell')
            refusal_row = {
                **{key: row[key] for key in ('run_id', 'seed', 'editor_id', 'repetition', 'exit_code') if key in row},
                'outcome': 'failed',
                'failure_reason': 'cpu_accounting_unavailable',
                'refusal_code': 'cpu_accounting_unavailable',
                'publishable': False,
                'rejected_evidence_directory': str(destination),
                'cpu_accounting': accounting,
                'accounting_scope': 'diagnostic' if diagnostic else 'sample',
            }
            write_json(destination / 'sample.json', refusal_row)
            write_json(self.directory / 'samples' / (name + '.json'), refusal_row)
            self.samples.append(refusal_row)
            if not shared_diagnostic and self._sample_parents:
                self.sample_start = self._sample_parents.pop()
            return self.directory / 'samples' / (name + '.json')
        from perf.runner.refusals import refusal_code
        value = {
            **row,
            'refusal_code': refusal_code(row),
            'run_id': self.run_id,
            'seed': self.seed,
            'cpu_accounting': accounting,
            'accounting_scope': 'diagnostic' if diagnostic else 'sample',
        }
        env_block = self.publication_block_from_environment()
        if env_block:
            value.update(publishable=False, publication_block_reason=env_block)
        from perf.runner.browser_throttle import throttled_within_tolerance
        _delta = accounting.get('delta') or {}
        _throttled_usec = _delta.get('throttled_usec')
        _throttled_usec = _throttled_usec if isinstance(_throttled_usec, (int, float)) and not isinstance(_throttled_usec, bool) else 0
        if accounting['available'] and not throttled_within_tolerance(_delta, accounting.get('span_ms')):
            # Keep arbitrary raw measurements only as forensic evidence. An
            # allowlist avoids leaking nested or differently named timing fields.
            destination = self.directory / 'rejected-evidence' / name
            source = Path(row['cell_directory']) if row.get('cell_directory') else None
            if source is not None and source.exists():
                destination.mkdir(parents=True, exist_ok=True)
                moved = destination / 'cell'
                source.rename(moved)
                # The skip listing must point at where the evidence now lives;
                # the pre-move path is gone the moment the refusal moves it.
                row['non_failure_outcomes'] = [
                    {**item, 'file': str(moved / Path(item['file']).relative_to(source))}
                    if item.get('file') and _under(item['file'], source) else item
                    for item in row.get('non_failure_outcomes', [])
                ]
            write_json(destination / 'sample.json', row)
            value = {
                key: value[key]
                for key in (
                    'run_id',
                    'seed',
                    'cpu_accounting',
                    'accounting_scope',
                    'editor_id',
                    'repetition',
                    'exit_code',
                    'brackets_force_closed',
                )
                if key in value
            }
            # Skip metadata survives refusal; arbitrary nested measurements do not.
            if 'non_failure_outcomes' in row:
                value['non_failure_outcomes'] = [
                    {key: item[key] for key in ('file', 'outcome', 'failure_reason',
                                               'criterion_id', 'editor_id', 'repetition') if key in item}
                    for item in row['non_failure_outcomes']
                ]
            value.update(
                outcome='failed',
                failure_reason='cpu_throttled',
                refusal_code='cpu_throttled',
                publishable=False,
                publication_block_reason='cpu_throttled',
                rejected_evidence_directory=str(destination),
            )
        elif not accounting['available'] and not value.get('publication_block_reason'):
            # The row keeps its measurements (unavailable accounting is not
            # throttling), stays unpublishable, and names why.
            value.update(
                refusal_code='cpu_accounting_unavailable',
                publishable=False,
                publication_block_reason='cpu_accounting_unavailable',
            )
        elif accounting['available']:
            # Lax layer (owner decision 2026-11-11): throttling within
            # max(1 ms, 1 % of the sample's span) keeps the sample, with the
            # throttled microseconds recorded on the row so the trial and the
            # report can disclose what was tolerated.
            _events = _delta.get('nr_throttled')
            value['throttled_usec'] = int(_throttled_usec)
            value['nr_throttled'] = int(_events) if isinstance(_events, (int, float)) and not isinstance(_events, bool) else 0
        path = self.directory / 'samples' / (name + '.json')
        write_json(path, value)
        self.samples.append(value)
        if not shared_diagnostic and self._sample_parents:
            self.sample_start = self._sample_parents.pop()
        return path

    def finish(self, summary):
        accounting = accounting_summary(self.accounting_start, _read_accounting(self.accounting_reader), self.samples)
        tally, reasons = cell_tally(self.samples)
        after = self.snapshot()
        result = {**summary, 'run_id': self.run_id, 'seed': self.seed,
                  'samples': self.samples, 'hosts': self.hosts, 'cpu_accounting': accounting,
                  'cpu_steal_percent': accounting.get('steal_percent'),
                  'cpu_throttle_refused_samples': accounting.get('samples_refused'),
                  'execution_profile': self.execution_profile, 'host_class': self.host_class,
                  'brackets_force_closed': self.brackets_force_closed,
                  **tally, 'cell_failure_reasons': reasons,
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
            result.update(
                failure_reason='repos_dirty_at_start',
                publishable=False,
                publication_block_reason='repos_dirty_at_start',
            )
        if repos_modified(self.before, after):
            result.update(outcome='failed', failure_reason='repos_modified', publishable=False)
        if getattr(self, 'block', None):
            result['block'] = self.block
        if getattr(self, 'shakedown', False):
            result.update(shakedown=True, publishable=False,
                          publication_block_reason='shakedown: few repetitions to find bugs; never a publication run')
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



ENVIRONMENTAL_REFUSAL_REASONS = frozenset({'cpu_throttled'})


def cell_tally(samples):
    """Classify recorded cell rows for the run-level signal.

    Diagnostic rows (saturation diagnostics, nested probes) are not cells.
    A refused cell lost its sample to the environment (ENVIRONMENTAL_REFUSAL_
    REASONS; quota-class reasons join that set when introduced); every other
    failed cell row counts as failed. A run where nothing was measured
    (cells_measured == 0) exits 3 instead of signalling success.
    """
    cells = [row for row in samples if row.get('accounting_scope') != 'diagnostic']
    tally = {'cells_total': len(cells), 'cells_measured': 0, 'cells_refused': 0, 'cells_failed': 0}
    reasons = {}
    for row in cells:
        if row.get('outcome') != 'failed':
            tally['cells_measured'] += 1
            continue
        reason = row.get('failure_reason') or 'failed'
        reasons[reason] = reasons.get(reason, 0) + 1
        if reason in ENVIRONMENTAL_REFUSAL_REASONS:
            tally['cells_refused'] += 1
        else:
            tally['cells_failed'] += 1
    return tally, reasons


def failure_reasons(value):
    if isinstance(value, dict):
        own = [value['failure_reason']] if value.get('outcome') == 'failed' and value.get('failure_reason') else []
        return own + [reason for key, child in value.items() if key != 'failure_reason'
                      for reason in failure_reasons(child)]
    if isinstance(value, list):
        return [reason for child in value for reason in failure_reasons(child)]
    return []


def non_failure_outcomes(value):
    """Retain skipped/refused rows without treating them as cell failures.

    Each retained entry carries its evidence `file` path; when a refusal
    quarantines the cell into rejected-evidence/, the path is repointed at
    the moved file so the listing stays resolvable.
    """
    if isinstance(value, dict):
        own = [value] if value.get('outcome') in ('not_run', 'refused', 'not_applicable', 'unsupported', 'unverified') else []
        return own + [row for child in value.values() for row in non_failure_outcomes(child)]
    if isinstance(value, list):
        return [row for child in value for row in non_failure_outcomes(child)]
    return []


def aggregate_cell_refusal_code(directory, failed: bool):
    """Do not stamp ``crash`` when every failing attempt is a named refusal."""
    if not failed:
        return None
    codes = set()
    for path in directory.rglob('attempts/*.json'):
        if 'profile-invoke' in path.parts:
            continue
        trial = json.loads(path.read_text())
        if trial.get('outcome') in ('failed', 'unverified', 'refused', 'not_applicable', 'unsupported'):
            code = trial.get('refusal_code') or trial.get('outcome')
            if code:
                codes.add(code)
    if codes == {'unverified'}:
        return 'unverified'
    if len(codes) == 1 and codes & {'unverified', 'editor_load_failed', 'paint_witness_unavailable'}:
        return next(iter(codes))
    return 'crash'


def has_failure(value):
    """Explicit failures, including warm_cold_identical, fail the cell.

    Saturation invalidates the claimed cold/warm distinction, so B1 keeps the
    producer's failure verdict. Routine not_run/refused rows remain non-failures.
    B1 must not silently reinterpret a lane's explicit failed measurement.
    """
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


PUBLICATION_REPETITIONS = 30
TYPING_PUBLICATION_SESSIONS = 12
TYPING_PUBLICATION_MIN_KEPT = 10

TEXT_CORRECTNESS_ORACLES = frozenset({'dom_document_text', 'model_document_text'})


def typing_session_kept(value, session_kind):
    """One typing attempt counts toward the kept-session gate.

    Only a text oracle can prove what was typed: a session on a flag or
    missing oracle is unverified evidence — it is recorded, never kept
    ("no unverified timings are published").
    """
    from perf.runner.refusals import refusal_code
    if refusal_code(value) is not None:
        return False
    if value.get('correctness_oracle') not in TEXT_CORRECTNESS_ORACLES:
        return False
    return (value.get('outcome') == 'measured' and not value.get('failure_reason')
            and value.get('session_kind') == session_kind
            and (value.get('throughput_chars_s') is not None if session_kind == 'throughput'
                 else value.get('load_ms') is not None
                 and (value.get('key_to_paint') or {}).get('median_ms') is not None))

RUNNER_PROFILE_CRITERION = {
    'benchmark_warm_cold': 'B1',
    'benchmark_document': 'C11',
    'benchmark_input': 'C07',
    'adversarial_c10_scroll': 'C10',
    'benchmark_memory': 'C17',
    'benchmark_resources': 'C18',
    'benchmark_typing': 'TYPING',
}


def _attempt_counts_excluded(row: dict) -> bool:
    return row.get('outcome') == 'profiled' or row.get('accounting_scope') == 'diagnostic'


def _run_chrome_profile_pass(main, runner, *, directory, editor, rep, rest, single, count_flag, original_argv):
    import os
    from perf.runner.artifacts import write_attempt
    from perf.runner.chrome_profile import record_profile_traces

    profile_dir = directory / 'profile'
    profile_dir.mkdir(parents=True, exist_ok=True)
    invoke_root = directory / 'profile-invoke'
    invoke_root.mkdir(parents=True, exist_ok=True)
    saved = {key: os.environ.get(key) for key in (
        'PERF_CHROME_PROFILE', 'PERF_CHROME_PROFILE_DIR', 'PERF_CHROME_TRACE_PATH',
        'PERF_CHROME_PROFILE_BUDGET_S')}
    os.environ['PERF_CHROME_PROFILE'] = '1'
    os.environ['PERF_CHROME_PROFILE_DIR'] = str(profile_dir)
    os.environ.pop('PERF_CHROME_TRACE_PATH', None)
    if runner == 'benchmark_typing':
        os.environ['PERF_CHROME_PROFILE_BUDGET_S'] = '60'
    sys.argv = [
        original_argv[0],
        *rest,
        '--out-root',
        str(invoke_root),
        '--editor' if single else '--editors',
        editor,
    ]
    if count_flag:
        sys.argv += [count_flag, '1']
    run = ACTIVE.get()
    try:
        bracket = run.begin_sample() if run is not None else nullcontext()
        with bracket:
            capture(main, stderr_tail=5)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    capture(
        lambda: record_profile_traces(
            directory, editor, RUNNER_PROFILE_CRITERION.get(runner, 'PROFILE'), write_fn=write_attempt
        ),
        stderr_tail=5,
    )


def run_cli(main, runner, targets, *, count_flag=None, default_count=1, single=False, run_factory=BrowserRun, max_repetitions=None, facts=None):
    """Drive one measurement body per scheduled cell, record-don't-abort.

    Every cell is recorded; the run-level one-line JSON and summary.json
    aggregate them (cells_total, cells_measured, cells_refused, cells_failed,
    cell_failure_reasons). Returns 0 when at least one cell was measured, 3
    when none was (all failed or environmentally refused), and 2 for usage
    errors raised before any run directory exists. A SystemExit carrying
    only an exit code keeps the producing call's stderr tail in the row.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--out-root', type=Path, default=REPO / 'perf' / 'out')
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--run-id', default=None)
    parser.add_argument('--execution-profile', choices=('ci_contract', 'ci_broad', 'dedicated_publish'), default='ci_broad')
    parser.add_argument('--host-class', choices=('ci_coarse', 'dedicated', 'shared_guarded'), default='ci_coarse')
    parser.add_argument('--editor' if single else '--editors', nargs=None if single else '+',
                        default='plate' if single else list(targets), dest='editors')
    if count_flag:
        parser.add_argument(count_flag, type=int, default=default_count, dest='repetitions')
    else:
        parser.add_argument('--repetitions', type=int, default=1)
    if runner == 'benchmark_typing':
        parser.add_argument('--session-kind', choices=('throughput', 'latency'), default='throughput')
    parser.add_argument('--chrome-profile', action='store_true',
                        help='after each cell, run one traced diagnostic repetition')
    # A block is one of N jobs that together make one seed's schedule: every
    # editor, a few repetitions each, on one machine (interleaved blocks).
    parser.add_argument('--block', default=None, metavar='K/N')
    if single:
        parser.add_argument('--editors', nargs='+', default=None, dest='block_editors')
    argv = list(sys.argv)
    args, rest = parser.parse_known_args()
    if '--help' in rest or '-h' in rest:
        print('Bookkeeping options: --seed INT --run-id ID --out-root PATH --repetitions INT (input only) --execution-profile {ci_contract,ci_broad,dedicated_publish} --host-class {ci_coarse,dedicated,shared_guarded}')
        return main()
    if '--list-support' in rest:
        return main()
    if runner == 'benchmark_typing':
        rest += ['--session-kind', args.session_kind]
    editors = [args.editors] if single else args.editors
    if single and args.block_editors:
        editors = args.block_editors
    block = None
    if args.block is not None:
        try:
            index, total = (int(value) for value in args.block.split('/'))
        except ValueError:
            parser.error('--block must be K/N')
        if total < 1 or not 1 <= index <= total:
            parser.error('--block must be K/N with 1 <= K <= N')
        block = (index, total)
    minimum_repetitions = TYPING_PUBLICATION_SESSIONS if runner == 'benchmark_typing' else PUBLICATION_REPETITIONS
    def _count_flag_explicit(tokens, flag):
        if flag:
            for token in tokens:
                if token == flag or token.startswith(flag + '='):
                    return True
        for token in tokens:
            if token == '--repetitions' or token.startswith('--repetitions='):
                return True
        return False

    count_explicit = _count_flag_explicit(argv, count_flag)
    if args.execution_profile == 'dedicated_publish' and not count_explicit:
        args.repetitions = minimum_repetitions
    # Shakedown (run.py --shakedown): every rung, few repetitions, never publishable.
    shakedown = os.environ.get('PERF_SHAKEDOWN') == '1'
    planned = args.repetitions * (block[1] if block else 1)
    if args.execution_profile == 'dedicated_publish' and planned < minimum_repetitions and not shakedown:
        parser.error(
            f'#136: dedicated_publish requires at least {minimum_repetitions} repetitions per editor, got {planned}'
        )
    if args.execution_profile == 'dedicated_publish' and args.host_class == 'shared_guarded':
        reader = read_cpu_accounting
        if isinstance(run_factory, partial) and run_factory.keywords.get('accounting_reader'):
            reader = run_factory.keywords['accounting_reader']
        accounting = _read_accounting(reader)
        if not accounting.get('available'):
            parser.error('shared_guarded dedicated_publish requires readable cgroup v2 cpu accounting')
        cpu_max = (accounting.get('cpu_max') or '').split()
        if len(cpu_max) >= 1 and cpu_max[0] == 'max':
            parser.error('shared_guarded dedicated_publish requires a cgroup CPU quota (cpu.max is unlimited)')
    if args.repetitions < 1 or any(editor not in targets for editor in editors):
        parser.error('positive repetitions and known editors required')
    if callable(max_repetitions):
        max_repetitions = max_repetitions(args.execution_profile)
    if max_repetitions is not None and args.repetitions > max_repetitions:
        parser.error(f'repetitions exceed profile budget ({max_repetitions})')
    run = run_factory(args.out_root, runner, seed=args.seed, run_id=args.run_id)
    run.execution_profile = args.execution_profile
    run.host_class = args.host_class
    run.shakedown = shakedown
    token = ACTIVE.set(run)
    original = sys.argv
    order = schedule(editors, args.repetitions, run.seed)
    if block:
        # The blocks of a seed are consecutive slices of its one schedule, so
        # pooled they are that schedule and no launch name repeats.
        first = (block[0] - 1) * args.repetitions
        order = [item for item in schedule(editors, block[1] * args.repetitions, run.seed)
                 if first <= item[0] < first + args.repetitions]
        run.block = {'index': block[0], 'of': block[1], 'repetitions': args.repetitions}
    typing_kept_by_editor = {editor: 0 for editor in editors}
    typing_remaining_by_editor = Counter(editor for _, editor in order)
    from perf.runner.host import host_record
    host_probe, renderer_probe = facts or (host_record, rendering_facts)
    host = capture(host_probe)
    rendering = capture(renderer_probe)
    try:
        for rep, editor in order:
            name = f'{rep:04d}-{editor}'
            directory = run.directory / 'cells' / name
            cell_token = CELL.set({'repetition': rep, 'editor_id': editor})
            skip_unreachable = (
                runner == 'benchmark_typing'
                and args.execution_profile == 'dedicated_publish'
                and not shakedown
                and planned >= TYPING_PUBLICATION_SESSIONS
                and typing_kept_by_editor[editor] + typing_remaining_by_editor[editor]
                < TYPING_PUBLICATION_MIN_KEPT
            )
            typing_remaining_by_editor[editor] -= 1
            if skip_unreachable:
                directory.mkdir(parents=True, exist_ok=True)
                (directory / 'attempts').mkdir(parents=True, exist_ok=True)
                write_json(directory / 'attempts' / 'typing.json', {
                    'schema': 'perf.typing/2',
                    'criterion_id': 'TYPING',
                    'session_kind': args.session_kind,
                    'editor_id': editor,
                    'run_id': run.run_id,
                    'seed': run.seed,
                    'repetition': rep,
                    'outcome': 'not_run',
                    'failure_reason': 'typing_sessions_unreachable',
                    'refusal_code': 'not_run',
                    'publishable': False,
                })
                run.begin_sample()
                row = {
                    'outcome': 'not_run',
                    'failure_reason': 'typing_sessions_unreachable',
                    'refusal_code': 'not_run',
                    'typing_session_kept': False,
                    'session_kind': args.session_kind,
                    'repetition': rep,
                    'editor_id': editor,
                    'cell_directory': str(directory),
                    'exit_code': 0,
                    'non_failure_outcomes': [],
                }
                row.update(repetition=rep, editor_id=editor, cell_directory=str(directory))
                run.sample(name, row)
                CELL.reset(cell_token)
                continue
            sys.argv = [
                original[0],
                *rest,
                '--out-root',
                str(directory),
                '--editor' if single else '--editors',
                editor,
            ]
            if count_flag:
                sys.argv += [count_flag, '1']
            def invoke():
                status = main()
                reasons = []
                skipped = []
                failed = bool(status)
                typing_kept = False
                attempts = {}
                for path in sorted(directory.rglob('*.json')):
                    if 'profile-invoke' in path.parts:
                        continue
                    value = json.loads(path.read_text())
                    if isinstance(value, dict) and _attempt_counts_excluded(value):
                        continue
                    if path.parent.name == 'attempts' and isinstance(value, dict):
                        criterion = value.get('criterion_id')
                        if criterion:
                            diagnostic = value.get('diagnostic') or {}
                            measure = value.get('measure') or diagnostic.get('size_rung') or diagnostic.get('measurement') or ''
                            phase = value.get('measurement_phase') or ''
                            # 72cec1e8 (#151) publishes each size rung under
                            # its own measurement name, so one launch can carry
                            # the same (criterion, measure) for several rungs;
                            # the rung is part of the attempt's identity.
                            rung = diagnostic.get('size_rung') or ''
                            identity = (criterion, str(measure), str(phase), str(rung))
                            attempts[identity] = attempts.get(identity, 0) + 1
                    if runner == 'benchmark_typing' and isinstance(value, dict) and value.get('criterion_id') == 'TYPING':
                        typing_kept = typing_session_kept(value, args.session_kind)
                    reasons.extend(failure_reasons(value))
                    failed = failed or has_failure(value)
                    skipped.extend({'file': str(path), **row} for row in non_failure_outcomes(value))
                if any(count > 1 for count in attempts.values()):
                    # A launch contributes at most one attempt per criterion/measure.
                    # Remove invalid attempts from the measured tree but retain
                    # the complete cell for diagnosis, as with throttle refusals.
                    destination = run.directory / 'rejected-evidence' / name
                    destination.mkdir(parents=True, exist_ok=True)
                    directory.rename(destination / 'cell')
                    return {**({'typing_session_kept': typing_kept, 'session_kind': args.session_kind} if runner == 'benchmark_typing' else {}),
                        'outcome': 'failed', 'publishable': False,
                            'failure_reason': 'multiple_attempts_per_launch',
                            'exit_code': status,
                            'rejected_evidence_directory': str(destination)}
                return {**({'typing_session_kept': typing_kept, 'session_kind': args.session_kind} if runner == 'benchmark_typing' else {}),
                        'outcome': 'failed' if failed else 'ok',
                        'refusal_code': aggregate_cell_refusal_code(directory, failed),
                        'non_failure_outcomes': skipped,
                        'failure_reason': '; '.join(dict.fromkeys(reasons)) or (f'exit {status}' if status else None),
                        'exit_code': status, 'cell_directory': str(directory)}
            try:
                run.begin_sample()
                row = capture(invoke, stderr_tail=5)
                row.update(repetition=rep, editor_id=editor, cell_directory=str(directory))
                run.sample(name, row)
                if runner == 'benchmark_typing' and row.get('typing_session_kept'):
                    typing_kept_by_editor[editor] += 1
                if args.chrome_profile:
                    _run_chrome_profile_pass(
                        main, runner, directory=directory, editor=editor, rep=rep,
                        rest=rest, single=single, count_flag=count_flag, original_argv=original)
            finally:
                CELL.reset(cell_token)
        typing_gate = {}
        if runner == 'benchmark_typing' and args.execution_profile == 'dedicated_publish':
            kept = {editor:{args.session_kind:sum(row.get('editor_id') == editor and row.get('outcome') == 'ok'
                               and not row.get('failure_reason') and row.get('typing_session_kept', False)
                               for row in run.samples)} for editor in editors}
            typing_gate = {'typing_sessions_kept':kept, 'typing_minimum_kept':TYPING_PUBLICATION_MIN_KEPT,
                           'typing_session_isolation':'fresh_process', 'session_kind':args.session_kind}
            if any(group[args.session_kind] < TYPING_PUBLICATION_MIN_KEPT for group in kept.values()):
                typing_gate['failure_reason'] = 'insufficient_typing_sessions'
        result = run.finish({
            **typing_gate,
            'runner': runner,
            'order': order,
            'publishable': False,
            'host': host,
            'headless': True,
            'rendering': rendering,
        })
        line = {key: result.get(key) for key in (
            'cells_total', 'cells_measured', 'cells_refused', 'cells_failed', 'cell_failure_reasons')}
        print(json.dumps({'run_id': run.run_id, 'summary': str(run.directory / 'summary.json'),
                          'samples': len(run.samples), 'failure_reason': result.get('failure_reason'),
                          **line}))
        return 3 if result['cells_measured'] == 0 else 0
    finally:
        sys.argv = original
        ACTIVE.reset(token)
