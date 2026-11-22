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
    checkpoint.loop(src, interval=0.01)
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
