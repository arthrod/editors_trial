"""An editor-scoped re-run: ``--only-editors`` narrows each picked job (#185).

canvas-editor's C11 and C14 timed its empty page. Re-measuring them must not
re-run the other eight editors of each interleaved block job, so a picked
job keeps its global index and its options, with its editor list narrowed
to the named editors. A picked job that measures none of them is refused.
"""
import pytest

from perf.container import run

BASE = ['--publish', '--dry-run', '--host-class', 'shared_guarded', '--seed', '1', '--seed2', '2', '--blocks', '2']


def _jobs(capsys, *extra):
    assert run.main([*BASE, *extra]) in (0, None)
    return [line for line in capsys.readouterr().out.splitlines() if '--run-id DRY-RUN-' in line]


def _editors(line):
    tokens = line.split()
    start = tokens.index('--editors') + 1
    names = []
    for token in tokens[start:]:
        if token.startswith('--'):
            break
        names.append(token)
    return names


def test_picked_jobs_keep_their_index_and_measure_only_the_named_editor(capsys):
    lines = _jobs(capsys, '--jobs', '10,20,101', '--only-editors', 'canvas')
    assert [line.split('--run-id DRY-RUN-')[1].split()[0] for line in lines] == ['010', '020', '101']
    assert [_editors(line) for line in lines] == [['canvas'], ['canvas'], ['canvas']]
    assert '--criteria C11 C12 C15 --block 1/2' in lines[0]
    assert '--criteria C14 --block 1/2' in lines[1]
    assert '--seed 2' in lines[2] and '--criteria C14 --block 2/2' in lines[2]


def test_without_the_flag_a_job_measures_every_editor(capsys):
    lines = _jobs(capsys, '--jobs', '10')
    assert len(_editors(lines[0])) == 9


def test_a_picked_job_without_the_editor_is_refused(capsys):
    # Job 130 is a one-editor typing job (canvas is not its editor).
    jobs = _jobs(capsys, '--runners', 'benchmark_typing', '--editors', 'plate')
    index = jobs[0].split('--run-id DRY-RUN-')[1].split()[0]
    with pytest.raises(SystemExit):
        run.main([*BASE, '--jobs', str(int(index)), '--only-editors', 'canvas'])


@pytest.mark.parametrize('extra', [['--only-editors', 'apryse'], ['--only-editors', 'nobody']])
def test_unknown_editor_is_refused(capsys, extra):
    with pytest.raises(SystemExit):
        run.main([*BASE, '--jobs', '10', *extra])


def test_only_editors_needs_publish():
    with pytest.raises(SystemExit):
        run.main(['--dry-run', '--only-editors', 'canvas'])
