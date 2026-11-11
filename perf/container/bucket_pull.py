#!/usr/bin/env python3
"""Download one run (or every run of a Space) from the HF Storage Bucket.

Usage:
    python3 -I perf/container/bucket_pull.py --dest DIR --space arthrod/e2-publish --run 20261115T120000Z
    python3 -I perf/container/bucket_pull.py --dest DIR --space arthrod/e2-publish

`--run` limits the pull to one campaign run id; without it every run stored
under `runs/<space>/` is fetched. Files land under `<dest>/runs/<space>/...`
mirroring the bucket layout. Every sealed job (dirs with MANIFEST.sha256 and
JOB-DONE) is verified against its manifest — sha256 of each listed file, no
unlisted files, manifest_sha256 recorded in JOB-DONE — the same checks
pull.py applies to the ssh pull. Verified files are then installed; a file
that would overwrite different local content is preserved as
`<name>.prev-<stamp>` first, and files of a job that fails verification stay
quarantined under `<dest>/.bucket-staging/`. Nothing local is ever deleted.

The token is read from HF_BUCKET_TOKEN (a read token is enough), falling back
to /proc/1/environ when a Dev Mode ssh session does not carry the Space
secrets. The value is used in memory only and never printed. Exit status is
non-zero on any mismatch, missing file, transport error, or missing token;
the last stdout line is the one-line summary
`BUCKET-PULL <scope> files=<n> bytes=<n> ok=<jobs> failed=<jobs>`.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import time
from pathlib import Path

BUCKET_ID_DEFAULT = 'arthrod/editors-trial-e2-runs'
# Tests inject a fake client here: callable(token) -> client with
# list_bucket_tree / download_bucket_files. None means the real HfApi.
CLIENT_FACTORY = None
PROC1_ENVIRON = '/proc/1/environ'
STREAM_CHUNK = 1024 * 1024


class PullError(RuntimeError):
    pass


def _token() -> str | None:
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


def _client(token: str):
    if CLIENT_FACTORY is not None:
        return CLIENT_FACTORY(token)
    from huggingface_hub import HfApi

    return HfApi(token=token)


def _safe_reason(exc: BaseException, token: str | None) -> str:
    text = str(exc) or type(exc).__name__
    if token:
        text = text.replace(token, '<redacted>')
    text = ' '.join(text.split())
    return text[:160] or 'error'


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as fh:
        while True:
            chunk = fh.read(STREAM_CHUNK)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _write_prev_copy(target: Path) -> None:
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    base = f'{target.name}.prev-{stamp}'
    suffix = 0
    while True:
        name = base if suffix == 0 else f'{base}-{suffix}'
        prev = target.with_name(name)
        try:
            with open(prev, 'xb') as out, target.open('rb') as inp:
                while True:
                    chunk = inp.read(STREAM_CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
            return
        except FileExistsError:
            suffix += 1


def _quarantine_stale_staging(dest: Path) -> None:
    staging = dest / '.bucket-staging'
    if not staging.is_dir():
        return
    try:
        next(staging.iterdir())
    except StopIteration:
        return
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    for suffix in range(1000):
        candidate = dest / (f'.bucket-staging.stale-{stamp}' if suffix == 0
                            else f'.bucket-staging.stale-{stamp}-{suffix}')
        try:
            staging.rename(candidate)
            return
        except FileExistsError:
            continue
        except OSError:
            return


def _remote_listing(client, bucket: str, prefix: str, token: str) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for item in client.list_bucket_tree(bucket, prefix=prefix, recursive=True, token=token):
        if getattr(item, 'type', None) == 'file':
            sizes[item.path] = int(item.size)
    return sizes


def _job_prefixes(remote_paths: dict[str, int]) -> list[str]:
    return sorted(
        path.rsplit('/', 1)[0]
        for path in remote_paths
        if path.endswith('/MANIFEST.sha256')
    )


def _verify_staged_job(staging: Path, prefix: str) -> int:
    """Same checks pull.py applies; returns the manifest file count."""
    job = staging / prefix
    manifest = job / 'MANIFEST.sha256'
    job_done = job / 'JOB-DONE'
    if not manifest.is_file() or not job_done.is_file():
        raise PullError(f'missing local job artifacts for {prefix}')
    manifest_body = manifest.read_bytes()
    listed: dict[str, str] = {}
    for line in manifest_body.decode('utf-8', 'replace').splitlines():
        if not line.strip():
            continue
        digest, rel = line.split('  ', 1)
        listed[rel] = digest
    for rel, digest in sorted(listed.items()):
        path = job / rel
        if not path.is_file():
            raise PullError(f'manifest lists missing file {prefix}/{rel}')
        if sha256_file(path) != digest:
            raise PullError(f'manifest mismatch for {prefix}/{rel}')
    for path in sorted(job.rglob('*')):
        if not path.is_file() or path.name in ('MANIFEST.sha256', 'JOB-DONE'):
            continue
        if '.prev-' in path.name:
            continue
        rel = path.relative_to(job).as_posix()
        if rel not in listed:
            raise PullError(f'manifest missing file {prefix}/{rel}')
    recorded = ''
    for line in job_done.read_text().splitlines():
        if line.startswith('manifest_sha256='):
            recorded = line.split('=', 1)[1].strip()
    if recorded != hashlib.sha256(manifest_body).hexdigest():
        raise PullError(f'manifest_sha256 mismatch for {prefix}')
    return len(listed)


def _install(staged: Path, dest_root: Path, rel: str) -> None:
    target = dest_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and sha256_file(target) != sha256_file(staged):
        _write_prev_copy(target)
    os.replace(staged, target)


def pull_bucket(client, bucket: str, prefix: str, dest: Path, token: str) -> dict:
    """Download `prefix` into dest, verify staged jobs, install verified files."""
    remote = _remote_listing(client, bucket, prefix, token)
    if not remote:
        raise PullError(f'nothing under {prefix}')
    _quarantine_stale_staging(dest)
    staging = dest / '.bucket-staging'
    jobs = set(_job_prefixes(remote))
    try:
        client.download_bucket_files(
            bucket,
            files=[(path, staging / path) for path in sorted(remote)],
            token=token,
        )
    except Exception as exc:
        raise PullError(f'download: {_safe_reason(exc, token)}') from exc
    listed_sizes = {
        path: (staging / path).stat().st_size
        for path in remote
        if (staging / path).is_file()
    }
    missing_downloads = sorted(set(remote) - set(listed_sizes))
    if missing_downloads:
        raise PullError(f'download missing files: {missing_downloads[:3]}')
    wrong_size = sorted(p for p, s in listed_sizes.items() if s != remote[p])
    if wrong_size:
        raise PullError(f'download size mismatch: {wrong_size[:3]}')
    failed: dict[str, str] = {}
    ok_files = 0
    for prefix_job in sorted(jobs):
        try:
            ok_files += _verify_staged_job(staging, prefix_job)
        except PullError as exc:
            failed[prefix_job] = str(exc)
    verified: list[str] = []
    for path in sorted(remote):
        owner = next((j for j in jobs if path.startswith(j + '/')), None)
        if owner in failed:
            continue
        verified.append(path)
    for rel in verified:
        _install(staging / rel, dest, rel)
    return {
        'files': len(verified),
        'bytes': sum(remote[p] for p in verified),
        'ok': len(jobs) - len(failed),
        'failed': failed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='bucket_pull')
    parser.add_argument('--dest', type=Path, required=True)
    parser.add_argument('--space', required=True, help='Space id used in runs/<space>/')
    parser.add_argument('--run', default=None, help='campaign run id; all runs when omitted')
    parser.add_argument('--bucket', default=os.environ.get('HF_BUCKET_ID', BUCKET_ID_DEFAULT))
    args = parser.parse_args(argv)
    try:
        token = _token()
    except Exception:
        token = None
    scope = f'{args.space}/{args.run}' if args.run else args.space
    if not token:
        print(f'BUCKET-PULL-ERROR {scope} no_token', flush=True)
        return 1
    try:
        client = _client(token)
    except Exception as exc:
        print(f'BUCKET-PULL-ERROR {scope} {_safe_reason(exc, token)}', flush=True)
        return 1
    prefix = f"runs/{args.space.strip('/')}/{args.run}/" if args.run else f"runs/{args.space.strip('/')}/"
    args.dest.mkdir(parents=True, exist_ok=True)
    try:
        result = pull_bucket(client, args.bucket, prefix, args.dest, token)
    except Exception as exc:
        print(f'BUCKET-PULL-ERROR {scope} {_safe_reason(exc, token)}', flush=True)
        return 1
    failed = result['failed']
    for job in sorted(failed):
        print(f'BUCKET-PULL-ERROR {job} {failed[job]}', flush=True)
    print(
        f"BUCKET-PULL {scope} files={result['files']} bytes={result['bytes']} "
        f"ok={result['ok']} failed={len(failed)}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
