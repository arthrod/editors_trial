#!/usr/bin/env python3
"""Pull HF container output over ssh or a test transport (stdlib-only)."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath

BATCH_MAX_BYTES = 64 * 1024 * 1024
BATCH_MAX_FILES = 500
BATCH_MAX_PATH_BYTES = 32 * 1024
STREAM_CHUNK = 65536
PREV_COPY_CHUNK = 1024 * 1024
LISTED_SIZE_CAP = 3

TAR_STDIN_MARKER = "sys.stdin.buffer.read()"

REMOTE_LIST = (
    "python3 -I -c "
    + shlex.quote(
        "import hashlib,json,os,stat,sys\n"
        "root='.'\n"
        "def warn(path,reason):\n"
        "  print(json.dumps({'pull_warn':reason,'path':path},ensure_ascii=True),flush=True)\n"
        "def good_name(path):\n"
        "  if '\\n' in path or '\\0' in path:\n"
        "    warn(path,'not a regular file');return False\n"
        "  try: path.encode('utf-8')\n"
        "  except UnicodeEncodeError:\n"
        "    warn(path,'not a regular file');return False\n"
        "  return True\n"
        "for dp,dns,fns in os.walk(root):\n"
        "  for dn in dns:\n"
        "    p=os.path.join(dp,dn)\n"
        "    try: st=os.lstat(p)\n"
        "    except OSError: continue\n"
        "    if stat.S_ISLNK(st.st_mode):\n"
        "      try:\n"
        "        if stat.S_ISDIR(os.stat(p).st_mode):\n"
        "          rel=os.path.relpath(p,root).replace(os.sep,'/')\n"
        "          warn(rel,'directory symlink')\n"
        "      except OSError: pass\n"
        "  for fn in fns:\n"
        "    p=os.path.join(dp,fn)\n"
        "    try: st=os.lstat(p)\n"
        "    except OSError: continue\n"
        "    rel=os.path.relpath(p,root).replace(os.sep,'/')\n"
        "    if not good_name(rel): continue\n"
        "    if stat.S_ISLNK(st.st_mode):\n"
        "      try: mode=os.stat(p).st_mode\n"
        "      except OSError: warn(rel,'not a regular file');continue\n"
        "      if stat.S_ISDIR(mode):\n"
        "        warn(rel,'directory symlink');continue\n"
        "      warn(rel,'not a regular file');continue\n"
        "    if not stat.S_ISREG(st.st_mode):\n"
        "      warn(rel,'not a regular file');continue\n"
        "    with open(p,'rb') as fh: digest=hashlib.sha256(fh.read()).hexdigest()\n"
        "    print(json.dumps({'path':rel,'size':st.st_size,'mtime':int(st.st_mtime),"
        "'sha256':digest},ensure_ascii=True),flush=True)\n"
    )
)

REMOTE_TAR_SCRIPT = (
    "import io,os,stat,sys,tarfile\n"
    "raw=sys.stdin.buffer.read()\n"
    "paths=[p.decode() for p in raw.split(b'\\0') if p]\n"
    "sys.stdout.buffer.flush()\n"
    "with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as tar:\n"
    "  for rel in paths:\n"
    "    path=os.path.join('.',rel)\n"
    "    if not os.path.isfile(path): continue\n"
    "    st=os.lstat(path)\n"
    "    if stat.S_ISREG(st.st_mode) and st.st_nlink>1:\n"
    "      with open(path,'rb') as fh: data=fh.read()\n"
    "      info=tarfile.TarInfo(name=rel)\n"
    "      info.size=len(data)\n"
    "      tar.addfile(info,io.BytesIO(data))\n"
    "    else:\n"
    "      tar.add(path,arcname=rel,recursive=False)\n"
)


class TransportError(RuntimeError):
    pass


class VerifyError(RuntimeError):
    pass


class Transport:
    def run(self, shell_fragment: str, *, stdin: bytes | None = None) -> bytes:
        raise NotImplementedError


def format_command_error(result: subprocess.CompletedProcess[bytes]) -> str:
    raw = (result.stderr or result.stdout or b'command failed')[:500]
    text = raw.decode('utf-8', 'replace')
    text = ''.join(ch if ch.isprintable() or ch in '\n\t' else '?' for ch in text)
    return text.strip()


class SshTransport(Transport):
    def __init__(self, target: str, remote_root: str):
        self.target = target
        self.remote_root = remote_root

    def run(self, shell_fragment: str, *, stdin: bytes | None = None) -> bytes:
        command = f'cd {shlex.quote(self.remote_root)} && unset REMOTE_ROOT && {shell_fragment}'
        result = subprocess.run(
            ['ssh', self.target, command],
            capture_output=True,
            check=False,
            input=stdin,
        )
        if result.returncode != 0:
            raise TransportError(format_command_error(result))
        return result.stdout


class BashTransport(Transport):
    """Runs the same shell fragments as SshTransport via bash -c."""

    def __init__(self, remote_root: Path):
        self.remote_root = Path(remote_root)
        self.call_log: list[str] = []

    def run(self, shell_fragment: str, *, stdin: bytes | None = None) -> bytes:
        self.call_log.append(shell_fragment)
        script = (
            f'export REMOTE_ROOT={shlex.quote(str(self.remote_root))}; '
            f'cd "$REMOTE_ROOT" && unset REMOTE_ROOT && {shell_fragment}'
        )
        result = subprocess.run(
            ['bash', '-c', script],
            capture_output=True,
            check=False,
            input=stdin,
        )
        if result.returncode != 0:
            raise TransportError(format_command_error(result))
        return result.stdout


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as fh:
        while True:
            chunk = fh.read(STREAM_CHUNK)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def safe_tar_member(name: str) -> None:
    pure = PurePosixPath(name)
    if pure.is_absolute() or '..' in pure.parts or name.endswith('/'):
        raise VerifyError(f'tar jail rejected member: {name}')
    if '\n' in name or '\0' in name:
        raise VerifyError(f'tar jail rejected member: {name!r}')


EXCLUDE: tuple[str, ...] = ()


def parse_listing(raw: str) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if 'pull_warn' in row:
            print(f"PULL-WARN {row['path']} {row['pull_warn']}", flush=True)
            continue
        if any(fnmatch.fnmatchcase(row['path'], pattern) for pattern in EXCLUDE):
            continue
        index[row['path']] = row
    return index


def list_remote(transport: Transport) -> dict[str, dict]:
    raw = transport.run(REMOTE_LIST).decode()
    return parse_listing(raw)


def fetch_tar_command() -> str:
    return f"python3 -I -c {shlex.quote(REMOTE_TAR_SCRIPT)}"


def fetch_tar(transport: Transport, paths: list[str]) -> bytes:
    if not paths:
        return b''
    payload = '\0'.join(paths).encode()
    return transport.run(fetch_tar_command(), stdin=payload)


def make_batches(paths: list[str], index: dict[str, dict]) -> list[list[str]]:
    batches: list[list[str]] = []
    batch: list[str] = []
    batch_bytes = 0
    batch_path_bytes = 0
    for path in paths:
        size = int(index[path]['size'])
        path_len = len(path.encode())
        if batch and (
            len(batch) >= BATCH_MAX_FILES
            or batch_bytes + size > BATCH_MAX_BYTES
            or batch_path_bytes + path_len > BATCH_MAX_PATH_BYTES
        ):
            batches.append(batch)
            batch = []
            batch_bytes = 0
            batch_path_bytes = 0
        batch.append(path)
        batch_bytes += size
        batch_path_bytes += path_len
    if batch:
        batches.append(batch)
    return batches


def _pull_meta_skip(rel: str, name: str) -> bool:
    if name.startswith('.pull-'):
        return True
    if rel.startswith('.pull-staging/') or '/.pull-staging/' in rel:
        return True
    if rel.startswith('.pull-staging.stale-') or '/.pull-staging.stale-' in rel:
        return True
    return False


def quarantine_stale_pull_staging(dest: Path) -> None:
    staging = dest / '.pull-staging'
    if not staging.is_dir():
        return
    try:
        next(staging.iterdir())
    except StopIteration:
        return
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    stale = dest / f'.pull-staging.stale-{stamp}'
    for suffix in range(1000):
        candidate = stale if suffix == 0 else Path(f'{stale}-{suffix}')
        try:
            staging.rename(candidate)
            return
        except FileExistsError:
            continue
        except OSError:
            return


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
                    chunk = inp.read(PREV_COPY_CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
            return
        except FileExistsError:
            suffix += 1


def _new_staging_dir(dest_root: Path) -> Path:
    for _ in range(100):
        stamp = f'{os.getpid()}-{time.time_ns()}'
        staging = dest_root / '.pull-staging' / stamp
        try:
            staging.mkdir(parents=True, exist_ok=False)
            return staging
        except FileExistsError:
            continue
    raise OSError('could not allocate pull staging directory')


def _stream_member_to_staging(
    extracted: io.BufferedReader,
    staging_path: Path,
    listed_size: int,
    expected_digest: str,
    member_name: str,
) -> None:
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    cap = max(int(listed_size), 1) * LISTED_SIZE_CAP
    hasher = hashlib.sha256()
    total = 0
    tmp = staging_path.with_name(f'{staging_path.name}.part-{os.getpid()}')
    try:
        with tmp.open('wb') as out:
            while True:
                chunk = extracted.read(STREAM_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > cap:
                    raise VerifyError(f'listed size cap exceeded for {member_name}')
                hasher.update(chunk)
                out.write(chunk)
        digest = hasher.hexdigest()
        if digest != expected_digest:
            raise VerifyError(f'sha256 mismatch for {member_name}')
        os.replace(tmp, staging_path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def extract_tar_stream(stream: bytes, dest_root: Path, expected: dict[str, dict]) -> set[str]:
    staging = _new_staging_dir(dest_root)
    staged: dict[str, Path] = {}
    try:
        data = stream.lstrip(b'\n\r')
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as tar:
            for member in tar:
                if member.isdir() or member.issym() or member.ischr() or member.isblk() or member.isfifo():
                    continue
                if not member.isreg():
                    raise VerifyError(f'tar member not a regular file: {member.name}')
                safe_tar_member(member.name)
                if member.name not in expected:
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    raise VerifyError(f'missing tar member: {member.name}')
                staging_path = staging / member.name
                meta = expected[member.name]
                _stream_member_to_staging(
                    extracted,
                    staging_path,
                    int(meta.get('size', 0)),
                    meta['sha256'],
                    member.name,
                )
                staged[member.name] = staging_path
        missing = set(expected) - set(staged)
        if missing:
            raise VerifyError(f'tar missing members: {sorted(missing)[:3]}')
        satisfied: set[str] = set()
        for rel, staging_path in staged.items():
            target = dest_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and sha256_file(target) != sha256_file(staging_path):
                write_prev_copy(target)
            os.replace(staging_path, target)
            satisfied.add(rel)
        return satisfied
    except tarfile.TarError as exc:
        raise VerifyError(f'tar read error: {exc}') from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def atomic_write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    tmp.write_text(json.dumps(payload, sort_keys=True) + '\n')
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


def rebuild_local_index(dest: Path) -> dict[str, str]:
    digest_by_path: dict[str, str] = {}
    for path in dest.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(dest).as_posix()
        if _pull_meta_skip(rel, path.name) or '.pull-index.json.corrupt-' in path.name:
            continue
        digest_by_path[rel] = sha256_file(path)
    return digest_by_path


def load_gone_index(dest: Path) -> dict[str, str]:
    path = dest / '.pull-index-gone.json'
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def prune_index_to_listing(
    index_map: dict[str, str],
    listing: dict[str, dict],
    dest: Path,
) -> dict[str, str]:
    pruned = {path: digest for path, digest in index_map.items() if path in listing}
    gone = load_gone_index(dest)
    for path, digest in index_map.items():
        if path not in listing:
            gone[path] = digest
    if gone:
        atomic_write_json(dest / '.pull-index-gone.json', gone)
    return pruned


def load_json_state(path: Path, dest: Path) -> dict | list:
    empty: dict | list = [] if path.name == '.pull-announced.json' else {}
    if not path.exists():
        return empty
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        print('PULL-WARN index unreadable; rebuilding', flush=True)
        for suffix in range(1000):
            corrupt = path.with_name(
                f'{path.name}.corrupt-{stamp}' if suffix == 0 else f'{path.name}.corrupt-{stamp}-{suffix}'
            )
            try:
                with open(corrupt, 'xb') as fh:
                    fh.write(path.read_bytes())
                break
            except FileExistsError:
                continue
        if path.name == '.pull-index.json':
            return rebuild_local_index(dest)
        return empty


def verify_job_manifest_impl(dest_root: Path, job_prefix: str, remote_index: dict[str, dict]) -> int:
    job_done_rel = f'{job_prefix}/JOB-DONE'
    if job_done_rel not in remote_index:
        return 0
    job_dir = dest_root / job_prefix
    manifest = job_dir / 'MANIFEST.sha256'
    job_done = job_dir / 'JOB-DONE'
    if not manifest.exists() or not job_done.exists():
        raise VerifyError(f'missing local job artifacts for {job_prefix}')
    manifest_body = manifest.read_bytes()
    manifest_lines = [line for line in manifest.read_text().splitlines() if line.strip()]
    listed: set[str] = set()
    for line in manifest_lines:
        digest, rel = line.split('  ', 1)
        listed.add(rel)
        path = job_dir / rel
        if not path.is_file():
            raise VerifyError(f'manifest lists missing file {job_prefix}/{rel}')
        if sha256_file(path) != digest:
            raise VerifyError(f'manifest mismatch for {job_prefix}/{rel}')
    for path in sorted(job_dir.rglob('*')):
        if not path.is_file() or path.name in ('MANIFEST.sha256', 'JOB-DONE'):
            continue
        if '.prev-' in path.name:
            continue
        rel = path.relative_to(job_dir).as_posix()
        if rel not in listed:
            raise VerifyError(f'manifest missing file {job_prefix}/{rel}')
    job_done_lines = job_done.read_text().splitlines()
    recorded = ''
    status = 0
    for line in job_done_lines:
        if line.startswith('exit_status='):
            status = int(line.split('=', 1)[1])
        if line.startswith('manifest_sha256='):
            recorded = line.split('=', 1)[1].strip()
    manifest_sha = sha256_bytes(manifest_body)
    if recorded != manifest_sha:
        raise VerifyError(f'manifest_sha256 mismatch for {job_prefix}')
    return len(listed)


def verify_job_manifest(dest_root: Path, job_prefix: str, remote_index: dict[str, dict]) -> int:
    return verify_job_manifest_impl(dest_root, job_prefix, remote_index)


def run_done_candidates(run_id: str) -> list[str]:
    return [f'runs/{run_id}/RUN-DONE', f'{run_id}/RUN-DONE']


def find_run_done(index: dict[str, dict], run_id: str) -> tuple[str | None, dict | None]:
    for rel in run_done_candidates(run_id):
        meta = index.get(rel)
        if meta:
            return rel, meta
    return None, None


def iter_job_prefixes(index: dict[str, dict]) -> list[str]:
    prefixes: list[str] = []
    seen: set[str] = set()
    for path in index:
        m = re.match(r'^(runs/[^/]+/[^/]+/[^/]+)/JOB-DONE$', path)
        if not m:
            m2 = re.match(r'^([^/]+)/([^/]+)/([^/]+)/JOB-DONE$', path)
            if m2:
                prefix = f'{m2.group(1)}/{m2.group(2)}/{m2.group(3)}'
                if prefix not in seen:
                    seen.add(prefix)
                    prefixes.append(prefix)
            continue
        prefix = m.group(1)
        if prefix not in seen:
            seen.add(prefix)
            prefixes.append(prefix)
    return sorted(set(prefixes))


def paths_needing_fetch(dest: Path, index: dict[str, dict], prior: dict[str, str]) -> list[str]:
    to_fetch: list[str] = []
    for path, meta in index.items():
        if prior.get(path) != meta['sha256']:
            to_fetch.append(path)
            continue
        local = dest / path
        if not local.is_file():
            to_fetch.append(path)
            continue
        if sha256_file(local) != meta['sha256']:
            to_fetch.append(path)
    return to_fetch


def local_bytes_match_listing(dest: Path, index: dict[str, dict]) -> bool:
    local_index = load_json_state(dest / '.pull-index.json', dest)
    if not isinstance(local_index, dict):
        return False
    for path, meta in index.items():
        if local_index.get(path) != meta['sha256']:
            return False
        local = dest / path
        if not local.is_file():
            return False
        if sha256_file(local) != meta['sha256']:
            return False
    return True


def index_fully_synced(dest: Path, index: dict[str, dict]) -> bool:
    return local_bytes_match_listing(dest, index)


def all_jobs_manifest_verified(dest: Path, index: dict[str, dict]) -> bool:
    for job_prefix in iter_job_prefixes(index):
        job_done_rel = f'{job_prefix}/JOB-DONE'
        if job_done_rel not in index:
            continue
        local_index = load_json_state(dest / '.pull-index.json', dest)
        if not isinstance(local_index, dict):
            return False
        if local_index.get(job_done_rel) != index[job_done_rel]['sha256']:
            return False
        try:
            verify_job_manifest_impl(dest, job_prefix, index)
        except VerifyError:
            return False
    return True


def pull_cycle(
    transport: Transport,
    remote_root: Path,
    dest: Path,
    *,
    announce: set[str] | None = None,
) -> tuple[set[str], int]:
    dest = Path(dest)
    quarantine_stale_pull_staging(dest)
    announce_path = dest / '.pull-announced.json'
    if announce is None:
        raw = load_json_state(announce_path, dest)
        announce = set(raw) if isinstance(raw, list) else set()
    index = list_remote(transport)
    local_index_path = dest / '.pull-index.json'
    prior = load_json_state(local_index_path, dest)
    if not isinstance(prior, dict):
        prior = {}
    to_fetch = paths_needing_fetch(dest, index, prior)
    verified_paths: dict[str, str] = {}
    if to_fetch:
        for batch in make_batches(to_fetch, index):
            stream = fetch_tar(transport, batch)
            subset = {path: index[path] for path in batch}
            satisfied = extract_tar_stream(stream, dest, subset)
            for path in satisfied:
                verified_paths[path] = index[path]['sha256']
    new_index = dict(prior)
    for path, digest in verified_paths.items():
        new_index[path] = digest
    for path, meta in index.items():
        if path in verified_paths:
            continue
        if prior.get(path) == meta['sha256']:
            new_index[path] = meta['sha256']
    new_index = prune_index_to_listing(new_index, index, dest)
    dest.mkdir(parents=True, exist_ok=True)
    atomic_write_json(local_index_path, new_index)
    jobs: dict[str, str] = {}
    for path in index:
        m = re.match(r'^runs/([^/]+)/([^/]+)/([^/]+)/JOB-DONE$', path)
        if m:
            jobs[f'runs/{m.group(1)}/{m.group(2)}/{m.group(3)}'] = m.group(1)
        m2 = re.match(r'^([^/]+)/([^/]+)/([^/]+)/JOB-DONE$', path)
        if m2:
            jobs[f'{m2.group(1)}/{m2.group(2)}/{m2.group(3)}'] = m2.group(1)
    for job_prefix, run_id in sorted(jobs.items()):
        key = f'{run_id}/{job_prefix.removeprefix(f"runs/{run_id}/")}' if job_prefix.startswith('runs/') else job_prefix
        job_dir = dest / job_prefix
        if key in announce:
            manifest = job_dir / 'MANIFEST.sha256'
            if manifest.exists():
                listed = {
                    line.split('  ', 1)[1]
                    for line in manifest.read_text().splitlines()
                    if line.strip()
                }
                for path in sorted(job_dir.rglob('*')):
                    if not path.is_file() or path.name in ('MANIFEST.sha256', 'JOB-DONE'):
                        continue
                    if '.prev-' in path.name:
                        continue
                    rel = path.relative_to(job_dir).as_posix()
                    if rel not in listed:
                        print(f'JOB-CHANGED {key} path={rel}', flush=True)
            continue
        if f'{job_prefix}/JOB-DONE' not in index:
            continue
        if f'{job_prefix}/JOB-DONE' not in new_index:
            continue
        try:
            files = verify_job_manifest(dest, job_prefix, index)
        except VerifyError:
            continue
        status = 0
        for line in (job_dir / 'JOB-DONE').read_text().splitlines():
            if line.startswith('exit_status='):
                status = int(line.split('=', 1)[1])
        print(f'JOB-DONE {key} status={status} files={files} verified', flush=True)
        announce.add(key)
    atomic_write_json(announce_path, sorted(announce))
    return announce, len(verified_paths)


def ensure_run_done_local(
    transport: Transport,
    dest: Path,
    index: dict[str, dict],
    run_done_rel: str,
    meta: dict,
) -> None:
    idx = load_json_state(dest / '.pull-index.json', dest)
    if not isinstance(idx, dict):
        idx = {}
    if idx.get(run_done_rel) != meta['sha256']:
        stream = fetch_tar(transport, [run_done_rel])
        extract_tar_stream(stream, dest, {run_done_rel: meta})
        idx[run_done_rel] = meta['sha256']
        atomic_write_json(dest / '.pull-index.json', idx)


def pull_until(
    transport: Transport,
    remote_root: Path,
    dest: Path,
    run_id: str,
    *,
    interval: float = 60,
    max_cycles: int | None = None,
) -> int:
    announced: set[str] = set()
    backoff = interval
    cycles = 0
    exit_status = 0
    run_done_seen = False
    final_verified = False
    while True:
        cycles += 1
        if max_cycles is not None and cycles > max_cycles:
            return 0 if final_verified else 1
        try:
            announced, fetched = pull_cycle(transport, remote_root, dest, announce=announced)
            index = list_remote(transport)
            run_done_rel, run_done = find_run_done(index, run_id)
            if run_done and run_done_rel:
                ensure_run_done_local(transport, dest, index, run_done_rel, run_done)
                done_path = dest / run_done_rel
                if done_path.exists():
                    for line in done_path.read_text().splitlines():
                        if line.startswith('exit_status='):
                            exit_status = int(line.split('=', 1)[1])
                    print(f'RUN-DONE {run_id} exit_status={exit_status}', flush=True)
                if not run_done_seen:
                    run_done_seen = True
                    backoff = interval
                    if max_cycles is None:
                        time.sleep(interval)
                    continue
            if run_done_seen and local_bytes_match_listing(dest, index) and all_jobs_manifest_verified(dest, index):
                local_index = load_json_state(dest / '.pull-index.json', dest)
                rel, meta = find_run_done(index, run_id)
                if meta and isinstance(local_index, dict) and local_index.get(rel) == meta['sha256']:
                    local_done = dest / rel
                    if local_done.is_file() and sha256_file(local_done) == meta['sha256']:
                        print(
                            f'FINAL-VERIFIED {run_id} files={len(index)} '
                            f'jobs={len(announced)} run_exit={exit_status}',
                            flush=True,
                        )
                        final_verified = True
                        return 0
            backoff = interval
        except (TransportError, VerifyError, tarfile.TarError, OSError, ValueError) as exc:
            print(f'PULL-ERROR {exc}', flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
        if max_cycles is None:
            time.sleep(interval)
    return 0 if final_verified else 1


def build_transport(target: str, remote: str) -> Transport:
    if target == 'bash -c':
        return BashTransport(Path(remote))
    return SshTransport(target, remote)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='pull')
    parser.add_argument('--target', required=True)
    parser.add_argument('--remote', required=True)
    parser.add_argument('--dest', type=Path, required=True)
    parser.add_argument('--interval', type=float, default=60)
    parser.add_argument('--until-run')
    parser.add_argument('--exclude', action='append', default=[], help='glob of remote paths never pulled')
    args = parser.parse_args(argv)
    global EXCLUDE
    EXCLUDE = tuple(args.exclude)
    transport = build_transport(args.target, args.remote)
    args.dest.mkdir(parents=True, exist_ok=True)
    if args.until_run:
        return pull_until(transport, Path(args.remote), args.dest, args.until_run, interval=args.interval)
    pull_cycle(transport, Path(args.remote), args.dest)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
