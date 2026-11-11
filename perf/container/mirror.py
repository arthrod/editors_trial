"""Best-effort mirror of sealed jobs to the HF persistent bucket (/data)."""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from pathlib import Path

CHUNK = 1024 * 1024
_SKIP_LOGGED: set[str] = set()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as fh:
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def mirror_root() -> Path | None:
    raw = os.environ.get('HF_MIRROR_ROOT', '/data/e2')
    root = Path(raw)
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        if str(root) not in _SKIP_LOGGED:
            _SKIP_LOGGED.add(str(root))
        return None
    if not root.is_dir():
        if str(root) not in _SKIP_LOGGED:
            _SKIP_LOGGED.add(str(root))
        return None
    if not os.access(root, os.W_OK):
        if str(root) not in _SKIP_LOGGED:
            _SKIP_LOGGED.add(str(root))
        return None
    return root


def _append_run_log(run_log: Path | None, line: str) -> None:
    if run_log is None or not run_log.parent.exists():
        return
    with run_log.open('a', encoding='utf-8') as fh:
        fh.write(line.rstrip() + '\n')
        fh.flush()
        os.fsync(fh.fileno())


def _skip_line(root: Path, run_log: Path | None) -> None:
    _append_run_log(run_log, f'mirror skip: HF_MIRROR_ROOT not writable: {root}')


def write_prev_copy(target: Path) -> None:
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    base = f'{target.name}.prev-{stamp}'
    suffix = 0
    while True:
        name = base if suffix == 0 else f'{base}-{suffix}'
        prev = target.with_name(name)
        try:
            with open(prev, 'xb') as out, target.open('rb') as inp:
                while True:
                    chunk = inp.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
            return
        except FileExistsError:
            suffix += 1


def copy_file_verified(src: Path, dst: Path, expected_digest: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and sha256_file(dst) == expected_digest:
        return
    if dst.exists() and sha256_file(dst) != expected_digest:
        write_prev_copy(dst)
    tmp = dst.with_name(f'{dst.name}.tmp-{os.getpid()}')
    try:
        with src.open('rb') as inp, tmp.open('wb') as out:
            while True:
                chunk = inp.read(CHUNK)
                if not chunk:
                    break
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        digest = sha256_file(tmp)
        if digest != expected_digest:
            tmp.unlink(missing_ok=True)
            raise ValueError(f'digest mismatch for {dst.name}')
        os.replace(tmp, dst)
        if sha256_file(dst) != expected_digest:
            raise ValueError(f'reread mismatch for {dst.name}')
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


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


def _manifest_digest_map(job_dir: Path) -> dict[str, str]:
    manifest = job_dir / 'MANIFEST.sha256'
    mapping: dict[str, str] = {}
    for line in manifest.read_text().splitlines():
        if not line.strip():
            continue
        digest, rel = line.split('  ', 1)
        mapping[rel] = digest
    return mapping


def mirror_job_directory(
    campaign_id: str,
    runner: str,
    job_id: str,
    job_dir: Path,
    run_log: Path | None,
) -> None:
    root = mirror_root()
    if root is None:
        _skip_line(Path(os.environ.get('HF_MIRROR_ROOT', '/data/e2')), run_log)
        return
    if not (job_dir / 'JOB-DONE').exists():
        _append_run_log(run_log, f'MIRROR-ERROR {job_id} missing JOB-DONE')
        return
    dest = root / campaign_id / runner / job_id
    try:
        mapping = _manifest_digest_map(job_dir)
        for rel, digest in sorted(mapping.items()):
            copy_file_verified(job_dir / rel, dest / rel, digest)
        for name in ('MANIFEST.sha256', 'JOB-DONE'):
            src = job_dir / name
            digest = sha256_file(src)
            copy_file_verified(src, dest / name, digest)
        for rel, digest in sorted(mapping.items()):
            if sha256_file(dest / rel) != digest:
                raise ValueError(f'mirror verify failed for {rel}')
        for name in ('MANIFEST.sha256', 'JOB-DONE'):
            if sha256_file(dest / name) != sha256_file(job_dir / name):
                raise ValueError(f'mirror verify failed for {name}')
        manifest_sha = sha256_file(dest / 'MANIFEST.sha256')
        mirror_ok = dest / 'MIRROR-OK'
        if mirror_ok.exists():
            write_prev_copy(mirror_ok)
        atomic_write(mirror_ok, f'manifest_sha256={manifest_sha}\n')
    except (OSError, ValueError) as exc:
        _append_run_log(run_log, f'MIRROR-ERROR {job_id} {exc}')


def mirror_campaign_tail(campaign_root: Path, campaign_id: str, run_log: Path | None) -> None:
    root = mirror_root()
    if root is None:
        return
    dest = root / campaign_id
    try:
        for name in ('RUN-DONE', 'RUN.log'):
            src = campaign_root / name
            if not src.is_file():
                continue
            digest = sha256_file(src)
            copy_file_verified(src, dest / name, digest)
    except (OSError, ValueError) as exc:
        _append_run_log(run_log, f'MIRROR-ERROR campaign {exc}')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='mirror')
    sub = parser.add_subparsers(dest='command', required=True)
    job = sub.add_parser('job')
    job.add_argument('campaign_id')
    job.add_argument('runner')
    job.add_argument('job_id')
    job.add_argument('job_dir', type=Path)
    job.add_argument('run_log', type=Path)
    tail = sub.add_parser('tail')
    tail.add_argument('campaign_root', type=Path)
    tail.add_argument('campaign_id')
    tail.add_argument('run_log', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'job':
        mirror_job_directory(
            args.campaign_id,
            args.runner,
            args.job_id,
            args.job_dir,
            args.run_log,
        )
    else:
        mirror_campaign_tail(args.campaign_root, args.campaign_id, args.run_log)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
