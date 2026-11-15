"""_job_roots on the real campaign layout (shakedown 3): a job directory has
cells/<NNNN-editor>/summary.json, and those cells are not jobs."""
from pathlib import Path

from perf.analysis.e2_cells import _job_roots


def _real_job(root: Path) -> Path:
    job = root / 'runs' / 'r1' / 'benchmark_document' / 'r1-018'
    (job / 'samples').mkdir(parents=True)
    (job / 'summary.json').write_text('{}')
    (job / 'JOB-DONE').write_text('exit_status=0\n')
    for editor in ('canvas', 'docen', 'plate'):
        cell = job / 'cells' / f'0000-{editor}'
        cell.mkdir(parents=True)
        (cell / 'summary.json').write_text('{}')
    return job


def test_a_job_directory_is_one_job_not_its_cells(tmp_path):
    job = _real_job(tmp_path)
    assert _job_roots(job) == [job]


def test_campaign_and_space_roots_find_the_job_once(tmp_path):
    job = _real_job(tmp_path)
    assert _job_roots(tmp_path / 'runs' / 'r1') == [job]
    assert _job_roots(tmp_path) == [job]
