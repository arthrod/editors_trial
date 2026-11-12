"""Best-effort mirror of sealed jobs to the HF persistent bucket (/data).

Each sealed job is also uploaded to the private HF Storage Bucket so a Space
restart loses at most the job in progress (#162). Bucket layout mirrors the
campaign directory: `runs/<space>/<run id>/<runner>/<job>/...` for job files
and `runs/<space>/<run id>/...` for campaign-level files (RUN.log, RUN-DONE).
Only generated measurement data is uploaded: BUCKET_EXCLUDES drops editor
builds, dependency trees, fixture copies and the .docx inputs.
"""
from __future__ import annotations

import argparse
import contextlib
import fnmatch
import hashlib
import os
import signal
import socket
import sys
import time
from pathlib import Path

CHUNK = 1024 * 1024
_SKIP_LOGGED: set[str] = set()

BUCKET_ID_DEFAULT = 'arthrod/editors-trial-e2-runs'
# The image pip line carries the same pin. Spaces are not rebuilt from that
# image during the campaign; setup.sh installs this spec into the venv the
# mirror imports under (sys.executable -I with that venv on PATH).
HUGGINGFACE_HUB_VERSION = '2.4.0'
RUNTIME_PIP = '/home/user/python-runtime/bin/pip'
# The bucket gets generated data only. Editor builds, dependency trees, job
# fixture copies and .docx inputs never leave the Space.
BUCKET_EXCLUDES: tuple[str, ...] = (
    'builds/*', '*/builds/*',
    'dist/*', '*/dist/*',
    'node_modules/*', '*/node_modules/*',
    'fixtures/*', '*/fixtures/*',
    'repos/*', '*/repos/*',
    '*.docx',
)
# Tests inject a fake client here: callable(token) -> client with
# list_bucket_tree / batch_bucket_files. None means the real HfApi.
BUCKET_CLIENT_FACTORY = None
# Runs are started over Dev Mode ssh, whose session may not carry the Space's
# secrets; the Space's own process environment is the fallback.
PROC1_ENVIRON = '/proc/1/environ'


def bucket_excluded(rel: str) -> bool:
    return any(fnmatch.fnmatchcase(rel, pattern) for pattern in BUCKET_EXCLUDES)


def _bucket_id() -> str:
    return os.environ.get('HF_BUCKET_ID', BUCKET_ID_DEFAULT)


def _space_name() -> str:
    space = os.environ.get('SPACE_ID', '').strip().strip('/')
    return space or socket.gethostname()


def _bucket_token() -> str | None:
    token = os.environ.get('HF_BUCKET_TOKEN')
    if token:
        return token
    prefix = b'HF_BUCKET_TOKEN='
    try:
        raw = Path(PROC1_ENVIRON).read_bytes()
    except OSError:
        return None
    for field in raw.split(b'\0'):
        if field.startswith(prefix):
            value = field[len(prefix):].decode('utf-8', 'replace')
            return value or None
    return None


def _bucket_client(token: str):
    if BUCKET_CLIENT_FACTORY is not None:
        return BUCKET_CLIENT_FACTORY(token)
    from huggingface_hub import HfApi

    return HfApi(token=token)


def _safe_reason(exc: BaseException, token: str | None) -> str:
    text = str(exc) or type(exc).__name__
    if token:
        text = text.replace(token, '<redacted>')
    text = ' '.join(text.split())
    return text[:160] or 'error'


def _log_skip_once(run_log: Path | None, line: str) -> None:
    if run_log is not None and run_log.is_file():
        try:
            if line in run_log.read_text(encoding='utf-8', errors='replace'):
                return
        except OSError:
            pass
    _append_run_log(run_log, line)


class _BucketDeadline(BaseException):
    """SIGALRM deadline for the bucket sync; BaseException so generic error
    handlers never swallow it and keep uploading past the budget."""


def _raise_bucket_deadline(signum, frame):
    raise _BucketDeadline('bucket timeout')


def _bucket_budget_s() -> float:
    # The bucket phase must stay inside the existing mirror child budget
    # (HF_MIRROR_TIMEOUT_S): default 90% of it, HF_BUCKET_TIMEOUT_S overrides.
    try:
        return max(0.0, float(os.environ['HF_BUCKET_TIMEOUT_S']))
    except (KeyError, ValueError):
        pass
    try:
        return max(1.0, 0.9 * float(os.environ.get('HF_MIRROR_TIMEOUT_S', '300')))
    except ValueError:
        return 270.0


@contextlib.contextmanager
def _bucket_deadline(seconds: float):
    if seconds <= 0 or not hasattr(signal, 'setitimer'):
        yield
        return
    try:
        previous_handler = signal.signal(signal.SIGALRM, _raise_bucket_deadline)
    except (ValueError, OSError):
        yield
        return
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


def _local_sizes(root: Path) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if bucket_excluded(rel):
            continue
        sizes[rel] = path.stat().st_size
    return sizes


def _sealed_job_dirs(campaign_root: Path) -> dict[str, Path]:
    jobs: dict[str, Path] = {}
    for done in sorted(campaign_root.glob('*/*/JOB-DONE')):
        job_dir = done.parent
        jobs[job_dir.relative_to(campaign_root).as_posix()] = job_dir
    return jobs


def _campaign_file_sizes(campaign_root: Path) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for path in sorted(campaign_root.rglob('*')):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(campaign_root).as_posix()
        if bucket_excluded(rel):
            continue
        parts = rel.split('/')
        if len(parts) >= 3 and (campaign_root / parts[0] / parts[1]).is_dir():
            continue
        sizes[rel] = path.stat().st_size
    return sizes


def _remote_sizes(client, bucket: str, prefix: str, token: str) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for item in client.list_bucket_tree(bucket, prefix=prefix, recursive=True, token=token):
        if getattr(item, 'type', None) == 'file':
            sizes[item.path] = int(item.size)
    return sizes


def _bucket_sync(campaign_root: Path, campaign_id: str, run_log: Path | None, *, audit_all: bool = False) -> None:
    try:
        token = _bucket_token()
    except Exception:
        token = None
    try:
        with _bucket_deadline(_bucket_budget_s()):
            _bucket_sync_inner(campaign_root, campaign_id, run_log, audit_all=audit_all, token=token)
    except _BucketDeadline:
        _append_run_log(run_log, 'BUCKET-ERROR campaign bucket timeout')
    except Exception as exc:
        _append_run_log(run_log, f'BUCKET-ERROR campaign {_safe_reason(exc, token)}')


def _sync_job_to_bucket(client, bucket: str, run_prefix: str, rel: str, job_dir: Path,
                        expected: dict[str, int], remote: dict[str, int], token: str) -> str:
    """Upload missing bytes and verify the remote listing; return the RUN.log line."""
    prefix = f'{run_prefix}/{rel}'
    need = sorted(r for r, s in expected.items() if remote.get(f'{prefix}/{r}') != s)
    expected_full = {f'{prefix}/{r}': s for r, s in expected.items()}
    if not need:
        view = {p: s for p, s in remote.items() if p.startswith(prefix + '/')}
        extra = sorted(p for p in view if p not in expected_full)
        if extra:
            return f'BUCKET-ERROR {rel} remote mismatch missing=0 extra={len(extra)}'
        return f'BUCKET-OK {rel} {len(expected)} {sum(expected.values())}'
    try:
        client.batch_bucket_files(
            bucket,
            add=[(job_dir / r, f'{prefix}/{r}') for r in need],
            token=token,
        )
    except Exception as exc:
        return f'BUCKET-ERROR {rel} {_safe_reason(exc, token)}'
    try:
        view = _remote_sizes(client, bucket, prefix + '/', token)
    except Exception as exc:
        return f'BUCKET-ERROR {rel} verify: {_safe_reason(exc, token)}'
    missing = sorted(p for p, s in expected_full.items() if view.get(p) != s)
    extra = sorted(p for p in view if p not in expected_full)
    if missing or extra:
        return f'BUCKET-ERROR {rel} remote mismatch missing={len(missing)} extra={len(extra)}'
    return f'BUCKET-OK {rel} {len(expected)} {sum(expected.values())}'


def _bucket_sync_inner(campaign_root: Path, campaign_id: str, run_log: Path | None,
                       *, audit_all: bool, token: str | None) -> None:
    if not token:
        # The normal state (issue #164): the bucket is a volume mounted at
        # /data and the verified HF_MIRROR_ROOT copy is the bucket write. No
        # token belongs in the container, so its absence is not logged.
        return
    try:
        client = _bucket_client(token)
    except Exception:
        _log_skip_once(run_log, 'BUCKET-SKIP no_huggingface_hub')
        return
    if client is None:
        _log_skip_once(run_log, 'BUCKET-SKIP no_huggingface_hub')
        return
    bucket = _bucket_id()
    run_prefix = f'runs/{_space_name()}/{campaign_id}'
    try:
        remote = _remote_sizes(client, bucket, run_prefix + '/', token)
    except Exception as exc:
        _append_run_log(run_log, f'BUCKET-ERROR campaign {_safe_reason(exc, token)}')
        return
    jobs = _sealed_job_dirs(campaign_root)
    for rel, job_dir in sorted(jobs.items()):
        try:
            expected = _local_sizes(job_dir)
            prefix = f'{run_prefix}/{rel}'
            untouched = all(remote.get(f'{prefix}/{r}') == s for r, s in expected.items())
            line = _sync_job_to_bucket(client, bucket, run_prefix, rel, job_dir,
                                       expected, remote, token)
        except _BucketDeadline:
            _append_run_log(run_log, f'BUCKET-ERROR {rel} bucket timeout')
            return
        except Exception as exc:
            _append_run_log(run_log, f'BUCKET-ERROR {rel} {_safe_reason(exc, token)}')
            continue
        if untouched and not audit_all and line.startswith('BUCKET-OK '):
            continue
        _append_run_log(run_log, line)
    campaign_files = _campaign_file_sizes(campaign_root)
    need = sorted(r for r, s in campaign_files.items() if remote.get(f'{run_prefix}/{r}') != s)
    if need:
        try:
            client.batch_bucket_files(
                bucket,
                add=[(campaign_root / r, f'{run_prefix}/{r}') for r in need],
                token=token,
            )
        except Exception as exc:
            _append_run_log(run_log, f'BUCKET-ERROR campaign {_safe_reason(exc, token)}')


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


def _is_mount(path: Path) -> bool:
    return os.path.ismount(path)


def mirror_mount_status() -> str:
    """'mounted' when HF_MIRROR_ROOT is writable and lies on a mounted
    filesystem other than '/' (the bucket volume); else 'not_mounted' or
    'not_writable'."""
    root = mirror_root()
    if root is None:
        return 'not_writable'
    for path in (root, *root.parents):
        if str(path) == '/':
            break
        if _is_mount(path):
            return 'mounted'
    return 'not_mounted'


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
    elif not (job_dir / 'JOB-DONE').exists():
        _append_run_log(run_log, f'MIRROR-ERROR {job_id} missing JOB-DONE')
    else:
        dest = root / campaign_id / runner / job_id
        try:
            # Generated data only: builds, dependency trees, fixtures and
            # .docx files stay on the Space (the mirror root is the bucket).
            mapping = {rel: digest for rel, digest in _manifest_digest_map(job_dir).items()
                       if not bucket_excluded(rel)}
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
    _bucket_sync(Path(job_dir).parent.parent, campaign_id, run_log)


def mirror_campaign_tail(campaign_root: Path, campaign_id: str, run_log: Path | None) -> None:
    root = mirror_root()
    if root is not None:
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
    _bucket_sync(campaign_root, campaign_id, run_log, audit_all=True)


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
    try:
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
    except Exception as exc:
        try:
            token = _bucket_token()
        except Exception:
            token = None
        print(_safe_reason(exc, token), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
