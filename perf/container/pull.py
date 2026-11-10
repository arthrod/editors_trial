#!/usr/bin/env python3
"""Pull HF container output over ssh or a test transport (stdlib-only)."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath

BATCH_MAX_BYTES = 64 * 1024 * 1024
BATCH_MAX_FILES = 500

REMOTE_LIST = (
    "python3 -I -c "
    + shlex.quote(
        "import hashlib,json,os,stat,sys\n"
        "root=os.environ.get('REMOTE_ROOT','.')\n"
        "sys.stdout.write('\\n');sys.stdout.flush()\n"
        "for dp,_,fns in os.walk(root):\n"
        "  for fn in fns:\n"
        "    p=os.path.join(dp,fn)\n"
        "    try: st=os.lstat(p)\n"
        "    except OSError: continue\n"
        "    rel=os.path.relpath(p,root).replace(os.sep,'/')\n"
        "    if stat.S_ISLNK(st.st_mode):\n"
        "      print(f'PULL-WARN {rel} not a regular file',flush=True); continue\n"
        "    if not stat.S_ISREG(st.st_mode):\n"
        "      print(f'PULL-WARN {rel} not a regular file',flush=True); continue\n"
        "    if '\\n' in rel:\n"
        "      print(f'PULL-WARN {rel} not a regular file',flush=True); continue\n"
        "    with open(p,'rb') as fh: digest=hashlib.sha256(fh.read()).hexdigest()\n"
        "    print(json.dumps({'path':rel,'size':st.st_size,'mtime':int(st.st_mtime),"
        "'sha256':digest}),flush=True)\n"
    )
)

REMOTE_TAR_SCRIPT = (
    "import base64,json,os,sys,tarfile\n"
    "root=os.environ.get('REMOTE_ROOT','.')\n"
    "paths=json.loads(base64.b64decode(sys.argv[1]))\n"
    "sys.stdout.buffer.flush()\n"
    "with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as tar:\n"
    "  for rel in paths:\n"
    "    path=os.path.join(root,rel)\n"
    "    if not os.path.isfile(path): continue\n"
    "    tar.add(path,arcname=rel,recursive=False)\n"
)


class TransportError(RuntimeError):
    pass


class VerifyError(RuntimeError):
    pass


class Transport:
    def run(self, shell_fragment: str) -> bytes:
        raise NotImplementedError


class SshTransport(Transport):
    def __init__(self, target: str, remote_root: str):
        self.target = target
        self.remote_root = remote_root

    def run(self, shell_fragment: str) -> bytes:
        command = f'cd {shlex.quote(self.remote_root)} && {shell_fragment}'
        result = subprocess.run(
            ['ssh', self.target, command],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            text = result.stderr.decode() or result.stdout.decode() or 'ssh failed'
            raise TransportError(text.strip())
        return result.stdout


class BashTransport(Transport):
    """Runs the same shell fragments as SshTransport via bash -c."""

    def __init__(self, remote_root: Path):
        self.remote_root = Path(remote_root)
        self.call_log: list[str] = []

    def run(self, shell_fragment: str) -> bytes:
        self.call_log.append(shell_fragment)
        script = (
            f'export REMOTE_ROOT={shlex.quote(str(self.remote_root))}; '
            f'cd "$REMOTE_ROOT" && {shell_fragment}'
        )
        result = subprocess.run(['bash', '-c', script], capture_output=True, check=False)
        if result.returncode != 0:
            text = result.stderr.decode() or result.stdout.decode() or 'bash failed'
            raise TransportError(text.strip())
        return result.stdout


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_tar_member(name: str) -> None:
    pure = PurePosixPath(name)
    if pure.is_absolute() or '..' in pure.parts or name.endswith('/'):
        raise VerifyError(f'tar jail rejected member: {name}')
    if '\n' in name or '\0' in name:
        raise VerifyError(f'tar jail rejected member: {name!r}')


def list_remote(transport: Transport) -> dict[str, dict]:
    raw = transport.run(REMOTE_LIST).decode()
    index: dict[str, dict] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('PULL-WARN'):
            print(line, flush=True)
            continue
        row = json.loads(line)
        index[row['path']] = row
    return index


def fetch_tar_command(paths: list[str]) -> str:
    payload = base64.b64encode(json.dumps(paths).encode()).decode()
    return f"python3 -I -c {shlex.quote(REMOTE_TAR_SCRIPT)} {shlex.quote(payload)}"


def fetch_tar(transport: Transport, paths: list[str]) -> bytes:
    if not paths:
        return b''
    return transport.run(fetch_tar_command(paths))


def make_batches(paths: list[str], index: dict[str, dict]) -> list[list[str]]:
    batches: list[list[str]] = []
    batch: list[str] = []
    batch_bytes = 0
    for path in paths:
        size = int(index[path]['size'])
        if batch and (
            len(batch) >= BATCH_MAX_FILES
            or batch_bytes + size > BATCH_MAX_BYTES
        ):
            batches.append(batch)
            batch = []
            batch_bytes = 0
        batch.append(path)
        batch_bytes += size
    if batch:
        batches.append(batch)
    return batches


def write_prev_copy(target: Path) -> None:
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    base = f'{target.name}.prev-{stamp}'
    data = target.read_bytes()
    for suffix in range(1000):
        name = base if suffix == 0 else f'{base}-{suffix}'
        prev = target.with_name(name)
        try:
            with open(prev, 'xb') as fh:
                fh.write(data)
            return
        except FileExistsError:
            continue
    raise OSError(f'could not allocate prev name for {target}')


def extract_tar_stream(stream: bytes, dest_root: Path, expected: dict[str, dict]) -> set[str]:
    satisfied: set[str] = set()
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
                data = extracted.read()
                digest = sha256_bytes(data)
                if digest != expected[member.name]['sha256']:
                    raise VerifyError(f'sha256 mismatch for {member.name}')
                target = dest_root / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and target.read_bytes() != data:
                    write_prev_copy(target)
                target.write_bytes(data)
                satisfied.add(member.name)
    except tarfile.TarError as exc:
        raise VerifyError(f'tar read error: {exc}') from exc
    missing = set(expected) - satisfied
    if missing:
        raise VerifyError(f'tar missing members: {sorted(missing)[:3]}')
    return satisfied


def fetch_tar_batches(
    transport: Transport,
    paths: list[str],
    index: dict[str, dict],
    dest: Path,
) -> set[str]:
    verified: set[str] = set()
    for batch in make_batches(paths, index):
        stream = fetch_tar(transport, batch)
        subset = {path: index[path] for path in batch}
        verified |= extract_tar_stream(stream, dest, subset)
    return verified


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def verify_job_manifest(dest_root: Path, job_prefix: str, remote_index: dict[str, dict]) -> int:
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
        if sha256_bytes(path.read_bytes()) != digest:
            raise VerifyError(f'manifest mismatch for {job_prefix}/{rel}')
    for path in sorted(job_dir.rglob('*')):
        if not path.is_file() or path.name in ('MANIFEST.sha256', 'JOB-DONE'):
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


def pull_cycle(
    transport: Transport,
    remote_root: Path,
    dest: Path,
    *,
    announce: set[str] | None = None,
    verified_jobs: set[str] | None = None,
) -> set[str]:
    dest = Path(dest)
    announce_path = dest / '.pull-announced.json'
    if announce is None:
        announce = set(json.loads(announce_path.read_text())) if announce_path.exists() else set()
    if verified_jobs is None:
        verified_jobs = set()
    index = list_remote(transport)
    local_index_path = dest / '.pull-index.json'
    prior = load_json(local_index_path)
    to_fetch = [path for path, meta in index.items() if prior.get(path) != meta['sha256']]
    verified_paths: dict[str, str] = {}
    if to_fetch:
        batches = make_batches(to_fetch, index)

        def run_batch(batch: list[str]) -> set[str]:
            stream = fetch_tar(transport, batch)
            subset = {path: index[path] for path in batch}
            return extract_tar_stream(stream, dest, subset)

        for batch in batches:
            satisfied = run_batch(batch)
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
    dest.mkdir(parents=True, exist_ok=True)
    local_index_path.write_text(json.dumps(dict(sorted(new_index.items()))) + '\n')
    jobs: dict[str, str] = {}
    for path in index:
        m = re.match(r'^runs/([^/]+)/([^/]+)/([^/]+)/JOB-DONE$', path)
        if m:
            jobs[f'runs/{m.group(1)}/{m.group(2)}/{m.group(3)}'] = m.group(1)
    for job_prefix, run_id in sorted(jobs.items()):
        key = f'{run_id}/{job_prefix.removeprefix(f"runs/{run_id}/")}'
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
        verified_jobs.add(key)
    announce_path.write_text(json.dumps(sorted(announce)) + '\n')
    return announce


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
    verified_jobs: set[str] = set()
    backoff = interval
    cycles = 0
    exit_status = 0
    while True:
        cycles += 1
        if max_cycles is not None and cycles > max_cycles:
            return exit_status
        try:
            pull_cycle(transport, remote_root, dest, announce=announced, verified_jobs=verified_jobs)
            index = list_remote(transport)
            run_done_rel = f'runs/{run_id}/RUN-DONE'
            run_done = index.get(run_done_rel)
            if run_done:
                done_path = dest / run_done_rel
                idx = load_json(dest / '.pull-index.json')
                if idx.get(run_done_rel) != run_done['sha256']:
                    stream = fetch_tar(transport, [run_done_rel])
                    extract_tar_stream(stream, dest, {run_done_rel: run_done})
                    idx[run_done_rel] = run_done['sha256']
                    (dest / '.pull-index.json').write_text(json.dumps(dict(sorted(idx.items()))) + '\n')
                if done_path.exists():
                    for line in done_path.read_text().splitlines():
                        if line.startswith('exit_status='):
                            exit_status = int(line.split('=', 1)[1])
                    print(f'RUN-DONE {run_id} exit_status={exit_status}', flush=True)
                    return exit_status
            backoff = interval
        except (TransportError, VerifyError, tarfile.TarError, OSError, ValueError) as exc:
            print(f'PULL-ERROR {exc}', flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
        if max_cycles is None:
            time.sleep(interval)
    return exit_status


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
    args = parser.parse_args(argv)
    transport = build_transport(args.target, args.remote)
    args.dest.mkdir(parents=True, exist_ok=True)
    if args.until_run:
        return pull_until(transport, Path(args.remote), args.dest, args.until_run, interval=args.interval)
    pull_cycle(transport, Path(args.remote), args.dest)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
