"""Re-run only the lanes and editors a fix touched (#129, fix round 2026-11-11).

--runners and --editors select jobs from the publication job list; a job keeps
its global index whatever selects it; with no flag every job runs.
"""
import pytest

from perf.container import run

BASE = ['--publish', '--dry-run', '--host-class', 'shared_guarded', '--seed', '1', '--seed2', '2']


def _jobs(capsys, *extra):
    assert run.main([*BASE, *extra]) in (0, None)
    return [line for line in capsys.readouterr().out.splitlines() if '--run-id DRY-RUN-' in line]


def test_no_filter_keeps_all_jobs(capsys):
    assert len(_jobs(capsys)) == 594


def test_runners_filter_keeps_only_those_runners(capsys):
    lines = _jobs(capsys, '--runners', 'benchmark_memory', 'benchmark_input')
    assert len(lines) == 2 * 2 * 5 * 9  # two runners, two seeds, five rungs, nine editors
    assert all('perf.runner.benchmark_memory ' in line or 'perf.runner.benchmark_input ' in line for line in lines)


def test_editors_filter_narrows_every_job(capsys):
    lines = _jobs(capsys, '--runners', 'benchmark_typing', 'adversarial_c10_scroll', '--editors', 'wordcraft')
    # typing: 2 seeds x 2 kinds; C10: 2 seeds x 5 rungs; one editor each
    assert len(lines) == 4 + 10
    for line in lines:
        assert 'wordcraft' in line
        assert 'plate' not in line and 'folio' not in line


def test_filters_then_shard_partition_the_filtered_jobs(capsys):
    full = _jobs(capsys, '--runners', 'benchmark_document', '--editors', 'canvas', 'folio', 'superdoc')
    assert len(full) == 3 * 12  # three editors, (five rungs + C14) x two seeds
    parts = [_jobs(capsys, '--runners', 'benchmark_document', '--editors', 'canvas', 'folio', 'superdoc',
                   '--shard', f'{i}/4') for i in range(4)]
    assert sorted(sum(parts, [])) == sorted(full)
    assert len(sum(parts, [])) == len(set(sum(parts, [])))


@pytest.mark.parametrize('extra', [['--runners', 'benchmark_nope'], ['--editors', 'apryse'], ['--editors', 'nobody']])
def test_unknown_runner_or_editor_is_refused(capsys, extra):
    with pytest.raises(SystemExit):
        run.main([*BASE, *extra])
