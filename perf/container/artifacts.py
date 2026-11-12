"""Atomic job manifests for HF container runs."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

SKIP_NAMES = frozenset({'MANIFEST.sha256', 'JOB-DONE'})


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    tmp.write_text(content)
    fd = os.open(tmp, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def build_manifest_lines(job_dir: Path) -> list[str]:
    lines = []
    for path in sorted(job_dir.rglob('*')):
        if path.name in SKIP_NAMES:
            continue
        rel = path.relative_to(job_dir).as_posix()
        if is_browser_state(rel):
            continue
        if path.is_symlink():
            raise ValueError(f'symlink not allowed in manifest: {path}')
        if not path.is_file():
            continue
        if '\n' in rel or '\0' in rel:
            raise ValueError(f'newline in manifest path: {rel!r}')
        digest = sha256_bytes(path.read_bytes())
        lines.append(f'{digest}  {rel}')
    return lines


def is_browser_state(rel: str) -> bool:
    """A job-relative path inside a browser's own user-data folder: a
    ``browser-profile`` folder at any depth, or the top ``profiles`` folder.
    State, not evidence (``cells/*/profile/trace-*`` is evidence)."""
    parts = rel.split('/')
    return 'browser-profile' in parts or parts[0] == 'profiles'


def remove_browser_profiles(job_dir: Path) -> None:
    """Delete the browsers' own user-data folders: state, not evidence.

    Chrome keeps rewriting and deleting files there after a launch ends, so a
    manifest that names them cannot be verified, and they dwarf the evidence.
    Chrome may still recreate files while it shuts down, so the manifest also
    skips these paths (is_browser_state).
    """
    import shutil
    targets = [job_dir / 'profiles', *sorted(job_dir.rglob('browser-profile'))]
    for target in targets:
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target, ignore_errors=True)


def finalize_job(job_dir: Path, exit_status: int) -> None:
    remove_browser_profiles(job_dir)
    lines = build_manifest_lines(job_dir)
    manifest_body = '\n'.join(lines) + ('\n' if lines else '')
    manifest_path = job_dir / 'MANIFEST.sha256'
    atomic_write(manifest_path, manifest_body)
    manifest_sha = sha256_bytes(manifest_path.read_bytes())
    job_done = f'exit_status={exit_status}\nmanifest_sha256={manifest_sha}\n'
    atomic_write(job_dir / 'JOB-DONE', job_done)
