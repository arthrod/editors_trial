"""Every five minutes, copy the running campaign's changed files to the bucket.

Owner's request (2026-11-22). run.py mirrors a job to the bucket only once the
job is sealed (mirror.py), so a Space lost mid-job lost that job's evidence.
This process copies whatever changed since its last pass into
<mirror root>/partial/<space>/<campaign>/ every INTERVAL_S. When RUN-DONE
appears it makes a separate whole duplicate in
<mirror root>/final/<space>/<campaign>/, verified file by file by sha256 and
listed in MANIFEST.sha256, and leaves the partial copy as it was. It never
writes to the sealed-job mirror's prefix.

The copy shares the Space with timed samples, so run.py starts it under
`nice -n 19 ionice -c3` and each pass copies only new or changed files, using
the same exclusions as the bucket mirror (editor builds are not evidence).

usage: python3 -m perf.container.checkpoint <campaign_root> [<campaign pid>]
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import time
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from perf.container.mirror import bucket_excluded, mirror_root, _space_name  # noqa: E402
else:
    from .mirror import bucket_excluded, mirror_root, _space_name

INTERVAL_S = 300
# How often the loop looks for RUN-DONE between passes, so the final duplicate
# starts within seconds of the campaign's end (Codex review 2026-11-22).
POLL_S = 5
# After RUN-DONE, run.py still writes (tail mirroring into RUN.log): the final
# duplicate waits for it to exit, at most this long.
PARENT_EXIT_WAIT_S = 1800
# The checkpoint's own log keeps changing while it works: never part of a copy.
OWN_LOG = 'checkpoint.log'


def destination(campaign_root: Path, kind: str = 'partial') -> Path | None:
    root = mirror_root()
    if root is None:
        return None
    return root / kind / _space_name() / Path(campaign_root).name


def _files(src: Path):
    """Files to copy, in a stable order. Excluded directories (editor builds and
    their dependency trees) are pruned, never walked (Codex review 2026-11-22)."""
    for directory, dirs, files in os.walk(src):
        here = Path(directory)
        rel_dir = here.relative_to(src).as_posix()
        prefix = '' if rel_dir == '.' else rel_dir + '/'
        dirs[:] = sorted(d for d in dirs if not bucket_excluded(prefix + d + '/_')
                         and not (here / d).is_symlink())
        for name in sorted(files):
            rel = prefix + name
            path = here / name
            if rel == OWN_LOG or path.is_symlink() or bucket_excluded(rel):
                continue
            yield rel, path


def _copy(path: Path, target: Path) -> bool:
    """Copy through a temporary file. A source that changed while it was read is
    not installed (the previous good copy stays) and is retried next pass."""
    before = path.stat()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + '.ckpt-tmp')
    shutil.copyfile(path, tmp)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        tmp.unlink(missing_ok=True)
        return False
    os.replace(tmp, target)
    return True


def sync_once(src: Path, dest: Path, state: dict) -> int:
    """Copy files new or changed (size, mtime) since the last pass; return how many."""
    copied = 0
    for rel, path in _files(src):
        try:
            st = path.stat()
        except FileNotFoundError:
            continue  # removed between listing and copying
        key = (st.st_size, st.st_mtime_ns)
        if state.get(rel) == key:
            continue
        try:
            if not _copy(path, dest / rel):
                continue  # changed while copied: next pass
        except FileNotFoundError:
            continue
        state[rel] = key
        copied += 1
    return copied


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def duplicate(src: Path, dest: Path) -> None:
    for rel, path in _files(src):
        if not _copy(path, dest / rel):
            raise ValueError(f'source changed while duplicated: {rel}')


def verify(src: Path, dest: Path) -> str:
    """Every source file is in dest with the same sha256; returns the manifest text."""
    lines = []
    for rel, path in _files(src):
        digest = _sha256(path)
        copy = dest / rel
        if not copy.is_file() or _sha256(copy) != digest:
            raise ValueError(f'duplicate differs from the source: {rel}')
        lines.append(f'{digest}  {rel}')
    return '\n'.join(lines) + '\n'


def _alive(pid: int | None) -> bool:
    if pid is None:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait(seconds: float, campaign_root: Path, parent_pid: int | None) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if (campaign_root / 'RUN-DONE').exists() or not _alive(parent_pid):
            return
        time.sleep(min(POLL_S, max(0.0, end - time.monotonic())))


def loop(campaign_root: Path, interval: float = INTERVAL_S, parent_pid: int | None = None,
         parent_exit_wait: float = PARENT_EXIT_WAIT_S) -> bool:
    """Copy every `interval` until RUN-DONE (or the campaign process is gone), then
    wait for the campaign process to exit and make the final duplicate. Returns
    True only when the duplicate was verified and its MANIFEST written."""
    campaign_root = Path(campaign_root)
    partial = destination(campaign_root, 'partial')
    if partial is None:
        print('checkpoint: no writable mirror root; nothing to do', flush=True)
        return False
    state: dict = {}
    while not (campaign_root / 'RUN-DONE').exists() and _alive(parent_pid):
        try:
            n = sync_once(campaign_root, partial, state)
            print(f'{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} checkpoint {n} file(s) -> {partial}', flush=True)
        except OSError as exc:  # a bad pass never stops the campaign or the next pass
            print(f'checkpoint error: {exc}', flush=True)
        _wait(interval, campaign_root, parent_pid)
    # run.py still writes after RUN-DONE (tail mirroring): copy only once it has exited.
    end = time.monotonic() + parent_exit_wait
    while _alive(parent_pid) and parent_pid is not None and time.monotonic() < end:
        time.sleep(min(POLL_S, parent_exit_wait))
    final = destination(campaign_root, 'final')
    for attempt in range(1, 4):
        try:
            duplicate(campaign_root, final)
            manifest = verify(campaign_root, final)
            (final / 'MANIFEST.sha256').write_text(manifest)
            print(f'checkpoint final duplicate verified ({manifest.count(chr(10))} files) -> {final}', flush=True)
            return True
        except (OSError, ValueError) as exc:
            print(f'checkpoint final duplicate attempt {attempt} failed: {exc}', flush=True)
            time.sleep(POLL_S)
    return False


if __name__ == '__main__':
    ok = loop(Path(sys.argv[1]), parent_pid=int(sys.argv[2]) if len(sys.argv) > 2 else None)
    sys.exit(0 if ok else 1)
