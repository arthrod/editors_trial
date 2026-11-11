"""Issue #139 fix round 3: F1 run-level cell accounting, F2 force-close
counting, F3 moved skip paths, F7 baseline-ref error handling."""

import json
from functools import partial
from pathlib import Path
import subprocess
import sys

from perf.runner import browser_run as api

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]


def reading(n):
    return dict(available=True, nr_periods=10, nr_throttled=n, throttled_usec=n * 10000,  # lax layer (owner 2026-11-11): above the max(1 ms, 1 %) tolerance
                cpu_ticks=dict(total=100, steal=0), loadavg=[0, 0, 0],
                cpu_max='100 100', cpu_count_visible=1, cgroup_path='/fake')


def invoke(tmp_path, main, editors=('a', 'b'), **kwargs):
    argv = sys.argv
    try:
        sys.argv = ['fake', '--out-root', str(tmp_path)]
        kwargs.setdefault('facts', (lambda: {}, lambda: {}))
        kwargs.setdefault(
            'run_factory',
            partial(api.BrowserRun, snapshot=lambda: {},
                    accounting_reader=lambda: {'available': False, 'reason': 'fake'}))
        return api.run_cli(main, 'fake', {name: {} for name in editors}, **kwargs)
    finally:
        sys.argv = argv


def summary_of(root):
    return json.loads(next(Path(root).rglob('summary.json')).read_text())


def run_line(out):
    lines = [line for line in out.splitlines() if line.startswith('{')]
    return json.loads(lines[-1])


# --------------------------------------------------------------------------- #
# F1: run-level cell accounting and exit codes
# --------------------------------------------------------------------------- #


def test_f1_all_cells_failed_exits_three_and_counts_reasons(tmp_path, capsys):
    def main():
        raise SystemExit('unsupported criterion id(s): C99')

    assert invoke(tmp_path, main) == 3
    summary = summary_of(tmp_path)
    assert summary['cells_total'] == 2
    assert summary['cells_measured'] == 0
    assert summary['cells_refused'] == 0
    assert summary['cells_failed'] == 2
    assert summary['cell_failure_reasons'] == {'SystemExit: unsupported criterion id(s): C99': 2}
    line = run_line(capsys.readouterr().out)
    assert line['cells_total'] == 2
    assert line['cells_measured'] == 0
    assert line['cells_refused'] == 0
    assert line['cells_failed'] == 2
    assert line['cell_failure_reasons'] == {'SystemExit: unsupported criterion id(s): C99': 2}


def test_f1_mixed_run_exits_zero_and_systemexit_records_stderr_tail(tmp_path, capsys):
    def main():
        editor = sys.argv[sys.argv.index('--editors') + 1]
        if editor == 'a':
            api.write_json(Path(sys.argv[sys.argv.index('--out-root') + 1]) / 'summary.json',
                           {'outcome': 'ok'})
            return 0
        print('usage: fake [-h]', file=sys.stderr)
        print('fake: error: unrecognized arguments: --repetitions 0', file=sys.stderr)
        raise SystemExit(2)

    assert invoke(tmp_path, main) == 0
    summary = summary_of(tmp_path)
    assert summary['cells_total'] == 2
    assert summary['cells_measured'] == 1
    assert summary['cells_failed'] == 1
    rows = {row['editor_id']: row for row in summary['samples']}
    assert rows['a']['outcome'] == 'ok'
    assert rows['b']['failure_reason'] == 'SystemExit: 2'
    assert 'unrecognized arguments: --repetitions 0' in rows['b']['failure_stderr_tail']
    assert summary['cell_failure_reasons'] == {'SystemExit: 2': 1}


def test_f1_all_cells_refused_exits_three_and_counts_environmental(tmp_path):
    state = [reading(0)]

    def main():
        state[0] = reading(state[0]['nr_throttled'] + 5)
        return 0

    assert invoke(tmp_path, main, editors=('a',),
                  run_factory=partial(api.BrowserRun, snapshot=lambda: {},
                                      accounting_reader=lambda: state[0])) == 3
    summary = summary_of(tmp_path)
    assert summary['cells_total'] == 1
    assert summary['cells_measured'] == 0
    assert summary['cells_refused'] == 1
    assert summary['cells_failed'] == 0
    assert summary['cell_failure_reasons'] == {'cpu_throttled': 1}


def test_f1_real_c99_criteria_exits_three(tmp_path):
    proc = subprocess.run([sys.executable, '-m', 'perf.runner.benchmark_document',
                           '--criteria', 'C99', '--out-root', str(tmp_path)],
                          capture_output=True, text=True, cwd=REPO, timeout=600)
    assert proc.returncode == 3, proc.stderr[-2000:]
    summary = summary_of(tmp_path)
    assert summary['cells_total'] >= 1
    assert summary['cells_measured'] == 0
    assert summary['cells_total'] == summary['cells_failed'] + summary['cells_refused']
    assert sum(summary['cell_failure_reasons'].values()) == summary['cells_total']
    assert all('C99' in reason for reason in summary['cell_failure_reasons'])
    line = run_line(proc.stdout)
    assert line['cells_measured'] == 0 and line['cells_total'] == summary['cells_total']


def test_f1_real_forwarded_bad_flag_keeps_argparse_text(tmp_path):
    proc = subprocess.run([sys.executable, '-m', 'perf.runner.benchmark_document',
                           '--repetitions', '0', '--out-root', str(tmp_path)],
                          capture_output=True, text=True, cwd=REPO, timeout=600)
    assert proc.returncode == 3, proc.stderr[-2000:]
    summary = summary_of(tmp_path)
    assert summary['cells_measured'] == 0
    assert summary['cells_total'] == summary['cells_failed'] + summary['cells_refused']
    rows = summary['samples']
    assert rows and all(row.get('failure_reason') == 'SystemExit: 2' for row in rows)
    assert any('unrecognized arguments' in (row.get('failure_stderr_tail') or '') for row in rows)
    assert summary['cell_failure_reasons'].get('SystemExit: 2') == summary['cells_total']


# --------------------------------------------------------------------------- #
# F2: forced bracket closures counted per run and per cell
# --------------------------------------------------------------------------- #


def test_f2_shared_diagnostic_cannot_hide_a_leaked_bracket(tmp_path):
    state = [reading(1)]
    run = api.BrowserRun(tmp_path, 'fake', snapshot=lambda: {}, accounting_reader=lambda: state[0])
    token = api.CELL.set(dict(repetition=0, editor_id='a'))
    try:
        run.begin_sample()
        state[0] = reading(4)

        def leak():
            run.begin_sample()
            raise ValueError('probe crashed')

        api.capture(leak)
        run.sample('saturation-0-a', dict(outcome='failed', failure_reason='warm_cold_identical'))
        run.sample('0000-a', dict(outcome='ok'))
    finally:
        api.CELL.reset(token)
    saturation, cell = run.samples[-2], run.samples[-1]
    assert saturation.get('brackets_force_closed', 0) >= 1
    assert cell.get('brackets_force_closed', 0) >= 1
    assert cell['outcome'] == 'failed' and cell['failure_reason'] == 'cpu_throttled'
    assert cell['cpu_accounting']['delta']['nr_throttled'] == 3
    result = run.finish({})
    assert result['brackets_force_closed'] >= 1


def test_f2_clean_run_reports_zero_forced_closures(tmp_path):
    state = [reading(0)]
    run = api.BrowserRun(tmp_path, 'fake', snapshot=lambda: {}, accounting_reader=lambda: state[0])
    token = api.CELL.set(dict(repetition=0, editor_id='a'))
    try:
        run.begin_sample()
        run.sample('0000-a', dict(outcome='ok'))
    finally:
        api.CELL.reset(token)
    assert 'brackets_force_closed' not in run.samples[0]
    assert run.finish({})['brackets_force_closed'] == 0


# --------------------------------------------------------------------------- #
# F3: skip listing paths survive the rejected-evidence move
# --------------------------------------------------------------------------- #


def test_f3_skip_listing_points_at_moved_file(tmp_path):
    state = [reading(0)]
    run = api.BrowserRun(tmp_path, 'fake', snapshot=lambda: {}, accounting_reader=lambda: state[0])
    cell_dir = run.directory / 'cells' / '0000-a'
    api.write_json(cell_dir / 'skip.json', {'outcome': 'not_run', 'failure_reason': 'unsupported'})
    token = api.CELL.set(dict(repetition=0, editor_id='a'))
    try:
        run.begin_sample()
        state[0] = reading(2)
        run.sample('0000-a', dict(outcome='ok', cell_directory=str(cell_dir),
                                  non_failure_outcomes=[dict(file=str(cell_dir / 'skip.json'),
                                                             outcome='not_run',
                                                             failure_reason='unsupported')]))
    finally:
        api.CELL.reset(token)
    row = run.samples[0]
    assert row['outcome'] == 'failed' and row['failure_reason'] == 'cpu_throttled'
    listing = row['non_failure_outcomes'][0]
    moved = Path(row['rejected_evidence_directory']) / 'cell' / 'skip.json'
    assert listing['file'] == str(moved)
    assert Path(listing['file']).exists()


# --------------------------------------------------------------------------- #
# F7: --baseline-ref error path and the real baseline mechanism
# --------------------------------------------------------------------------- #


def smoke(*options, timeout=300):
    return subprocess.run([sys.executable, '-I', str(ROOT / 'tests' / 'b1a_smoke.py'), *options],
                          capture_output=True, text=True, cwd=REPO, timeout=timeout)


def test_f7_bogus_baseline_ref_exits_two_with_one_line(tmp_path):
    proc = smoke('--baseline-ref', 'no-such-ref-zzz', '--out-root', str(tmp_path), timeout=120)
    assert proc.returncode == 2
    assert 'Traceback' not in proc.stderr
    lines = [line for line in proc.stderr.splitlines() if line.strip()]
    assert len(lines) == 1, proc.stderr
    assert 'no-such-ref-zzz' in lines[0]


def test_f7_baseline_ref_head_runs_the_real_smoke(tmp_path):
    proc = smoke('--baseline-ref', 'HEAD', '--out-root', str(tmp_path))
    assert proc.returncode == 0, proc.stderr[-2000:]
    summary = summary_of(tmp_path)
    assert summary['runner'] == 'b1a-smoke'
    assert summary['samples'][0]['outcome'] == 'ok'
