"""Interleaved blocks: the publication campaign's layout (Arthur, 2026-11-11).

One block is one job that measures every editor, a few repetitions each, in
the seeded interleaved order. The blocks of one seed are slices of the single
30-repetition schedule, so pooled they are that schedule exactly.
"""
import json
import sys
from collections import Counter, defaultdict
from functools import partial

import pytest

from perf.container import plan, policy
from perf.runner import browser_run as api
from perf.tests.test_b7_fix2 import accounting

EDITORS = ['plate', 'docxodus', 'docen']


def _opt(options, flag):
    return options[options.index(flag) + 1] if flag in options else None


def _blocks():
    return policy.publication_jobs(EDITORS, 1, 2, 'shared_guarded', blocks=10)


def test_default_layout_is_unchanged_one_editor_per_job():
    jobs = policy.publication_jobs(EDITORS, 1, 2, 'shared_guarded')
    assert all(len(policy.job_editors(options)) == 1 for _name, options in jobs)
    assert not any('--block' in options for _name, options in jobs)


def test_every_block_job_measures_every_editor():
    for name, options in _blocks():
        if name == 'benchmark_typing':
            assert len(policy.job_editors(options)) == 1
            assert '--block' not in options
        else:
            assert policy.job_editors(options) == EDITORS, (name, options)
            assert _opt(options, '--block') is not None


def test_each_cell_has_every_block_once_and_thirty_repetitions():
    groups = defaultdict(list)
    for name, options in _blocks():
        if name == 'benchmark_typing':
            continue
        cell = (name, _opt(options, '--seed'), _opt(options, '--workload'), 'C14' in options)
        count = int(_opt(options, policy.SHAKEDOWN_COUNT_FLAG[name]))
        groups[cell].append((_opt(options, '--block'), count))
    assert groups
    for cell, rows in groups.items():
        assert sorted(block for block, _count in rows) == sorted('%d/10' % k for k in range(1, 11)), cell
        assert sum(count for _block, count in rows) == 30, cell


def test_traces_are_taken_in_the_first_block_only():
    for name, options in _blocks():
        if name == 'benchmark_typing':
            continue
        assert ('--chrome-profile' in options) == (_opt(options, '--block') == '1/10'), (name, options)


def test_blocks_must_divide_the_repetitions():
    with pytest.raises(ValueError):
        policy.publication_jobs(EDITORS, 1, 2, 'shared_guarded', blocks=7)


def test_job_key_separates_blocks_and_joins_seeds():
    keys = Counter(policy.job_key(name, options) for name, options in _blocks())
    assert set(keys.values()) == {2}


def test_planner_costs_a_block_by_its_editors_and_repetitions():
    one = ('benchmark_resources', ['--seed', '1', '--workload', 'prose-500w', '--editors', 'plate'])
    block = ('benchmark_resources', ['--seed', '1', '--workload', 'prose-500w', '--editors', *EDITORS,
                                    '--block', '1/10', '--repetitions', '3'])
    assert plan.estimate(*block) == pytest.approx(plan.estimate(*one) * 3 * 3 / 30 + plan._BUILD * 3)


def _run(tmp_path, monkeypatch, *extra, single=False):
    monkeypatch.delenv('PERF_SHAKEDOWN', raising=False)
    monkeypatch.setattr(sys, 'argv', [
        'fake', '--out-root', str(tmp_path), '--run-id', 'b', '--seed', '7',
        '--execution-profile', 'dedicated_publish', '--host-class', 'dedicated', *extra])
    code = api.run_cli(
        lambda: 0, 'fake', {name: {} for name in EDITORS}, count_flag='--pairs', single=single,
        run_factory=partial(api.BrowserRun, snapshot=lambda: {}, accounting_reader=accounting),
        facts=(lambda: {}, lambda: {}))
    return code, json.loads((tmp_path / 'fake/b/summary.json').read_text())


def test_a_block_is_a_slice_of_the_full_schedule(tmp_path, monkeypatch):
    _code, summary = _run(tmp_path, monkeypatch, '--editors', *EDITORS, '--pairs', '3', '--block', '2/10')
    full = api.schedule(EDITORS, 30, 7)
    assert [tuple(item) for item in summary['order']] == [item for item in full if 3 <= item[0] < 6]
    assert summary['block'] == {'index': 2, 'of': 10, 'repetitions': 3}
    assert summary['seed'] == 7
    assert sorted(sample['repetition'] for sample in summary['samples']) == sorted([3, 4, 5] * 3)


def test_a_block_too_small_for_thirty_is_refused(tmp_path, monkeypatch):
    with pytest.raises(SystemExit):
        _run(tmp_path, monkeypatch, '--editors', *EDITORS, '--pairs', '2', '--block', '2/10')


@pytest.mark.parametrize('block', ['0/10', '11/10', 'x', '3'])
def test_a_malformed_block_is_refused(tmp_path, monkeypatch, block):
    with pytest.raises(SystemExit):
        _run(tmp_path, monkeypatch, '--editors', *EDITORS, '--pairs', '3', '--block', block)


def test_a_one_editor_lane_takes_several_editors_in_a_block(tmp_path, monkeypatch):
    _code, summary = _run(tmp_path, monkeypatch, '--editors', *EDITORS, '--pairs', '3', '--block', '1/10', single=True)
    assert {editor for _rep, editor in summary['order']} == set(EDITORS)
    assert len(summary['samples']) == 9


def test_a_shakedown_can_rehearse_the_block_layout():
    """One repetition of every editor in a block job: the publication layout, never publishable."""
    jobs = _blocks()
    name, options = next(job for job in jobs if job[0] == 'benchmark_resources')
    cut = policy.shakedown_options(name, options, 1)
    flag = policy.SHAKEDOWN_COUNT_FLAG[name]
    # argparse keeps the last value of a repeated flag
    assert [cut[i + 1] for i, token in enumerate(cut) if token == flag][-1] == '1'
    assert policy.job_editors(cut) == EDITORS and '--block' in cut


def test_a_shakedown_block_runs_one_repetition_per_editor(tmp_path, monkeypatch):
    monkeypatch.setenv('PERF_SHAKEDOWN', '1')
    monkeypatch.setattr(sys, 'argv', [
        'fake', '--out-root', str(tmp_path), '--run-id', 'b', '--seed', '7',
        '--execution-profile', 'dedicated_publish', '--host-class', 'dedicated',
        '--editors', *EDITORS, '--pairs', '3', '--block', '1/10', '--pairs', '1'])
    api.run_cli(
        lambda: 0, 'fake', {name: {} for name in EDITORS}, count_flag='--pairs',
        run_factory=partial(api.BrowserRun, snapshot=lambda: {}, accounting_reader=accounting),
        facts=(lambda: {}, lambda: {}))
    summary = json.loads((tmp_path / 'fake/b/summary.json').read_text())
    assert len(summary['samples']) == 3 and summary['shakedown'] is True
    assert summary['publishable'] is False


def test_the_planner_costs_a_rehearsed_block():
    block = ('benchmark_resources', ['--chrome-profile', '--seed', '1', '--workload', 'prose-500w', '--editors', *EDITORS,
                                    '--block', '1/10', '--repetitions', '3'])
    one = ('benchmark_resources', ['--seed', '1', '--workload', 'prose-500w', '--editors', 'plate'])
    assert plan.estimate(*block, shakedown=1) == pytest.approx(plan.estimate(*one) * 3 * 2 / 30 + plan._BUILD * 3)
