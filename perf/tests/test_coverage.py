"""Campaign coverage across Spaces (review-shake #5): FINAL-VERIFIED on each Space does not
prove the campaign ran every job. coverage unions every RUN-DONE's selected_jobs."""
from __future__ import annotations

from pathlib import Path

from perf.container import coverage


def _done(root: Path, space: str, rid: str, jobs: str, total: int = 6, status: int = 0, shakedown: int | None = None):
    run = root / space / 'runs' / rid
    run.mkdir(parents=True)
    lines = [f'exit_status={status}', f'selected_jobs={jobs}', f'total_jobs={total}']
    if shakedown is not None:
        lines.append(f'shakedown={shakedown}')
    (run / 'RUN-DONE').write_text('\n'.join(lines) + '\n')


def test_complete_campaign_is_covered(tmp_path):
    _done(tmp_path, 'a', 'r1', '0,1,2')
    _done(tmp_path, 'b', 'r2', '3,4,5')
    report = coverage.check([tmp_path / 'a', tmp_path / 'b'])
    assert report['missing'] == [] and report['ok']


def test_a_space_that_never_finished_leaves_jobs_missing(tmp_path):
    _done(tmp_path, 'a', 'r1', '0,1,2')
    (tmp_path / 'b' / 'runs' / 'r2').mkdir(parents=True)  # no RUN-DONE
    report = coverage.check([tmp_path / 'a', tmp_path / 'b'])
    assert report['missing'] == [3, 4, 5]
    assert report['unfinished'] == ['b/runs/r2']
    assert not report['ok']


def test_mixed_shakedown_and_publication_or_totals_refuse(tmp_path):
    _done(tmp_path, 'a', 'r1', '0,1,2', shakedown=2)
    _done(tmp_path, 'b', 'r2', '3,4,5')
    report = coverage.check([tmp_path / 'a', tmp_path / 'b'])
    assert not report['ok'] and 'mixed shakedown' in ' '.join(report['problems'])
    _done(tmp_path, 'c', 'r3', '0', total=7)
    assert 'total_jobs' in ' '.join(coverage.check([tmp_path / 'b', tmp_path / 'c'])['problems'])


def test_failed_exit_and_duplicates_are_reported(tmp_path):
    _done(tmp_path, 'a', 'r1', '0,1,2,3', status=1)
    _done(tmp_path, 'b', 'r2', '3,4,5')
    report = coverage.check([tmp_path / 'a', tmp_path / 'b'])
    assert report['duplicates'] == [3]
    assert report['failed_runs'] == ['a/runs/r1']
    assert report['missing'] == [] and not report['ok']


def test_only_runs_named_are_read(tmp_path):
    _done(tmp_path, 'a', 'old', '0,1,2,3,4,5')
    _done(tmp_path, 'a', 'new', '0,1,2')
    report = coverage.check([tmp_path / 'a'], runs=['new'])
    assert report['missing'] == [3, 4, 5]


def test_cli_exit_status(tmp_path, capsys):
    _done(tmp_path, 'a', 'r1', '0,1,2')
    assert coverage.main([str(tmp_path / 'a')]) == 1
    assert 'missing 3' in capsys.readouterr().out
