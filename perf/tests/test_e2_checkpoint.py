"""Every 5 minutes, the campaign's in-progress files go to the bucket (owner, 2026-11-22).

run.py mirrors a job only once it is sealed, so a Space lost mid-job lost that
job. checkpoint.py copies whatever changed since its last pass into
<mirror root>/partial/<space>/<campaign>/, every interval, at the lowest CPU
and I/O priority. When RUN-DONE appears it makes a separate, whole duplicate in
<mirror root>/final/<space>/<campaign>/, checked by sha256 with a MANIFEST, and
leaves the partial copy as it was (owner: "a duplicate copy so it doesn't bother
the first"). It never writes to the sealed-job mirror's prefix.
"""
import os
import time
from pathlib import Path

from perf.container import checkpoint


def _tree(root: Path, files: dict) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def test_copies_new_and_changed_files_only(tmp_path):
    src, dest = tmp_path / 'campaign', tmp_path / 'mirror'
    _tree(src, {'RUN.log': 'a', 'benchmark_input/r1/attempts/1.json': '{}'})
    state = {}
    assert checkpoint.sync_once(src, dest, state) == 2
    assert (dest / 'benchmark_input/r1/attempts/1.json').read_text() == '{}'
    assert checkpoint.sync_once(src, dest, state) == 0
    time.sleep(0.01)
    (src / 'RUN.log').write_text('ab')
    assert checkpoint.sync_once(src, dest, state) == 1
    assert (dest / 'RUN.log').read_text() == 'ab'


def test_skips_what_the_bucket_mirror_excludes(tmp_path):
    src, dest = tmp_path / 'campaign', tmp_path / 'mirror'
    _tree(src, {'benchmark_input/r1/builds/x/dist/big.js': 'x', 'RUN.log': 'a'})
    checkpoint.sync_once(src, dest, {})
    assert (dest / 'RUN.log').exists()
    assert not (dest / 'benchmark_input/r1/builds/x/dist/big.js').exists()


def test_destination_is_the_partial_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv('HF_MIRROR_ROOT', str(tmp_path / 'data'))
    monkeypatch.setenv('SPACE_ID', 'arthrod/e2-publish')
    dest = checkpoint.destination(Path('/app/perf/container/out/runs/20261122T160000Z'))
    assert dest == tmp_path / 'data' / 'partial' / 'arthrod/e2-publish' / '20261122T160000Z'


def test_at_run_done_a_separate_verified_duplicate_and_partial_untouched(tmp_path, monkeypatch):
    monkeypatch.setenv('HF_MIRROR_ROOT', str(tmp_path / 'data'))
    monkeypatch.setenv('SPACE_ID', 's')
    src = tmp_path / 'runs' / 'C1'
    _tree(src, {'RUN.log': 'a', 'benchmark_input/r1/attempts/1.json': '{}'})
    partial = tmp_path / 'data/partial/s/C1'
    checkpoint.sync_once(src, partial, {})
    before = {p.relative_to(partial): p.stat().st_mtime_ns for p in partial.rglob('*') if p.is_file()}
    (src / 'RUN.log').write_text('ab')
    (src / 'RUN-DONE').write_text('exit_status=0\n')
    assert checkpoint.loop(src, interval=0.01) is True
    final = tmp_path / 'data/final/s/C1'
    assert (final / 'RUN-DONE').exists()
    assert (final / 'RUN.log').read_text() == 'ab'
    manifest = (final / 'MANIFEST.sha256').read_text()
    assert 'benchmark_input/r1/attempts/1.json' in manifest and 'RUN.log' in manifest
    after = {p.relative_to(partial): p.stat().st_mtime_ns for p in partial.rglob('*') if p.is_file()}
    assert after == before  # the first copy is not touched at the end


def test_stops_when_the_campaign_process_is_gone(tmp_path, monkeypatch):
    monkeypatch.setenv('HF_MIRROR_ROOT', str(tmp_path / 'data'))
    monkeypatch.setenv('SPACE_ID', 's')
    src = tmp_path / 'runs' / 'C2'
    _tree(src, {'RUN.log': 'a'})
    import subprocess, sys
    dead = subprocess.Popen([sys.executable, '-c', 'pass']); dead.wait()
    checkpoint.loop(src, interval=0.01, parent_pid=dead.pid)
    assert (tmp_path / 'data/final/s/C2/RUN.log').exists()


def test_a_bad_duplicate_is_refused(tmp_path):
    src, dest = tmp_path / 'campaign', tmp_path / 'final'
    _tree(src, {'RUN.log': 'a'})
    checkpoint.duplicate(src, dest)
    (dest / 'RUN.log').write_text('corrupt')
    import pytest
    with pytest.raises(ValueError):
        checkpoint.verify(src, dest)


def test_run_py_starts_it_at_lowest_priority_every_300_seconds():
    src = Path('perf/container/run.py').read_text()
    assert "'nice', '-n', '19', 'ionice', '-c3'" in src
    assert 'perf.container.checkpoint' in src
    assert checkpoint.INTERVAL_S == 300


def test_excluded_directories_are_never_walked(tmp_path, monkeypatch):
    src = tmp_path / 'campaign'
    _tree(src, {'builds/x/dist/a.js': 'x', 'benchmark_input/r1/builds/y/node_modules/b.js': 'y', 'RUN.log': 'a'})
    walked = []
    real = os.walk
    def spy(top, *a, **k):
        for entry in real(top, *a, **k):
            walked.append(Path(entry[0]).relative_to(src).as_posix())
            yield entry
    monkeypatch.setattr(checkpoint.os, 'walk', spy)
    assert [rel for rel, _ in checkpoint._files(src)] == ['RUN.log']
    assert not any('builds' in w for w in walked), walked


def test_a_source_that_changes_while_copied_keeps_the_previous_copy(tmp_path, monkeypatch):
    src, dest = tmp_path / 'campaign', tmp_path / 'mirror'
    _tree(src, {'RUN.log': 'good'})
    state = {}
    assert checkpoint.sync_once(src, dest, state) == 1
    time.sleep(0.01)
    (src / 'RUN.log').write_text('torn and longer')
    real = checkpoint.shutil.copyfile
    def racing(a, b):
        real(a, b)
        Path(a).write_text('changed again during the copy')
    monkeypatch.setattr(checkpoint.shutil, 'copyfile', racing)
    assert checkpoint.sync_once(src, dest, state) == 0
    assert (dest / 'RUN.log').read_text() == 'good'
    assert not list(dest.glob('*.ckpt-tmp'))


def test_the_final_duplicate_waits_for_the_campaign_process_and_skips_its_own_log(tmp_path, monkeypatch):
    monkeypatch.setenv('HF_MIRROR_ROOT', str(tmp_path / 'data'))
    monkeypatch.setenv('SPACE_ID', 's')
    monkeypatch.setattr(checkpoint, 'POLL_S', 0.05)
    src = tmp_path / 'runs' / 'C3'
    _tree(src, {'RUN.log': 'a', 'RUN-DONE': 'exit_status=0\n', 'checkpoint.log': 'mine'})
    import subprocess, sys
    # The campaign process appends to RUN.log after RUN-DONE, then exits.
    proc = subprocess.Popen([sys.executable, '-c',
                             'import time,sys;time.sleep(0.5);open(sys.argv[1],"a").write("tail");'
                             , str(src / 'RUN.log')])
    import threading
    threading.Thread(target=proc.wait, daemon=True).start()  # reaped as run.py's parent reaps it
    started = time.monotonic()
    assert checkpoint.loop(src, interval=0.01, parent_pid=proc.pid, parent_exit_wait=30) is True
    assert time.monotonic() - started < 10  # it waited for the exit, not for the limit
    final = tmp_path / 'data/final/s/C3'
    assert (final / 'RUN.log').read_text() == 'atail'
    assert not (final / 'checkpoint.log').exists()
    assert 'checkpoint.log' not in (final / 'MANIFEST.sha256').read_text()


def test_run_done_is_noticed_within_seconds_not_at_the_next_pass(tmp_path, monkeypatch):
    monkeypatch.setenv('HF_MIRROR_ROOT', str(tmp_path / 'data'))
    monkeypatch.setenv('SPACE_ID', 's')
    monkeypatch.setattr(checkpoint, 'POLL_S', 0.05)
    src = tmp_path / 'runs' / 'C4'
    _tree(src, {'RUN.log': 'a'})
    import threading
    threading.Timer(0.3, lambda: (src / 'RUN-DONE').write_text('exit_status=0\n')).start()
    started = time.monotonic()
    assert checkpoint.loop(src, interval=300, parent_pid=None) is True
    assert time.monotonic() - started < 10


def test_the_module_exits_non_zero_when_the_duplicate_cannot_be_verified():
    src = Path('perf/container/checkpoint.py').read_text()
    assert 'sys.exit(0 if ok else 1)' in src


def test_a_zombie_campaign_process_counts_as_exited(tmp_path, monkeypatch):
    # 2026-11-22 test run on e2-publish: run.py exited, PID 1 never reaped it, and the
    # final duplicate waited its whole limit for a process that was already gone.
    proc = tmp_path / 'proc'
    (proc / '4242').mkdir(parents=True)
    (proc / '4242' / 'stat').write_text('4242 (python3 (x)) Z 1 4242 4242 0 -1\n')
    (proc / '4343').mkdir(parents=True)
    (proc / '4343' / 'stat').write_text('4343 (python3) S 1 4343 4343 0 -1\n')
    monkeypatch.setattr(checkpoint, 'PROC', proc, raising=False)
    monkeypatch.setattr(checkpoint.os, 'kill', lambda pid, sig: None)
    assert checkpoint._alive(4242) is False
    assert checkpoint._alive(4343) is True


def test_a_file_that_changes_once_during_the_final_duplicate_is_copied_on_a_retry(tmp_path, monkeypatch):
    # Gitar review on #285: one busy file used to fail the whole attempt.
    src, dest = tmp_path / 'campaign', tmp_path / 'final'
    _tree(src, {'A.log': 'a', 'B.json': 'b', 'C.json': 'c'})
    monkeypatch.setattr(checkpoint, 'RETRY_S', 0)
    real, calls = checkpoint._copy, {'n': 0}
    def once_busy(path, target):
        if path.name == 'A.log' and calls['n'] == 0:
            calls['n'] += 1
            return False
        return real(path, target)
    monkeypatch.setattr(checkpoint, '_copy', once_busy)
    checkpoint.duplicate(src, dest)
    assert sorted(p.name for p in dest.iterdir()) == ['A.log', 'B.json', 'C.json']


def test_a_file_that_keeps_changing_does_not_stop_the_files_after_it(tmp_path, monkeypatch):
    src, dest = tmp_path / 'campaign', tmp_path / 'final'
    _tree(src, {'A.log': 'a', 'B.json': 'b', 'C.json': 'c'})
    monkeypatch.setattr(checkpoint, 'RETRY_S', 0)
    real = checkpoint._copy
    monkeypatch.setattr(checkpoint, '_copy', lambda p, t: False if p.name == 'A.log' else real(p, t))
    try:
        checkpoint.duplicate(src, dest)
    except ValueError as exc:
        assert 'A.log' in str(exc)
    else:
        raise AssertionError('a file that never settled must make the duplicate fail')
    assert sorted(p.name for p in dest.iterdir()) == ['B.json', 'C.json']


def test_a_checkpoint_that_cannot_start_is_a_failure_line_not_a_stopped_campaign(tmp_path, monkeypatch, capsys):
    # CodeRabbit on #283 (2026-11-23): Popen raising (no `nice`, no interpreter)
    # or the log failing to open ended the campaign before its first job, with
    # no RUN-DONE. It is now a line in RUN-DONE's failures and the run goes on.
    from perf.container import run

    def refuse(*a, **k):
        raise OSError('nice: not found')

    monkeypatch.setattr(run.subprocess, 'Popen', refuse)
    failures = []
    assert run.start_checkpoint(tmp_path, failures) is False
    assert failures == ['checkpoint: not started: nice: not found']
    assert 'CHECKPOINT-NOT-STARTED' in capsys.readouterr().out
    # A log that cannot be opened is the same failure.
    monkeypatch.undo()
    failures = []
    assert run.start_checkpoint(tmp_path / 'missing-dir', failures) is False
    assert failures and failures[0].startswith('checkpoint: not started:')
