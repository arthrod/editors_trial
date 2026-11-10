"""Pull HF container output over ssh or a test transport."""
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
from pathlib import Path

from . import artifacts


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
            raise TransportError(result.stderr.decode() or result.stdout.decode() or 'ssh failed')
        return result.stdout


class BashTransport(Transport):
    def __init__(self, remote_root: Path):
        self.remote_root = Path(remote_root)

    def run(self, shell_fragment: str) -> bytes:
        script = f'export REMOTE_ROOT={shlex.quote(str(self.remote_root))}; cd "$REMOTE_ROOT" && {shell_fragment}'
        result = subprocess.run(['bash', '-c', script], capture_output=True, check=False)
        if result.returncode != 0:
            raise TransportError(result.stderr.decode() or result.stdout.decode() or 'bash failed')
        return result.stdout

    def list_files(self) -> dict[str, dict]:
        rows = []
        for path in self.remote_root.rglob('*'):
            if not path.is_file():
                continue
            rel = path.relative_to(self.remote_root).as_posix()
            st = path.stat()
            rows.append({'path': rel, 'size': st.st_size, 'mtime': int(st.st_mtime),
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        return {row['path']: row for row in rows}

    def tar_paths(self, paths: list[str]) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w') as tar:
            for rel in paths:
                tar.add(self.remote_root / rel, arcname=rel)
        return buf.getvalue()


REMOTE_LIST = r"""python3 -I <<'PY'
import hashlib, json, os, sys
root = os.environ.get('REMOTE_ROOT', '.')
rows = []
for dirpath, _, filenames in os.walk(root):
    for name in filenames:
        path = os.path.join(dirpath, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        if not os.path.isfile(path):
            continue
        rel = os.path.relpath(path, root)
        with open(path, 'rb') as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        rows.append({'path': rel, 'size': st.st_size, 'mtime': int(st.st_mtime), 'sha256': digest})
print(json.dumps(rows))
PY"""

REMOTE_TAR = r"""python3 -I <<'PY'
import base64, io, json, os, sys, tarfile
root = os.environ.get('REMOTE_ROOT', '.')
paths = json.loads(base64.b64decode(sys.stdin.read().strip()))
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode='w') as tar:
    for rel in paths:
        path = os.path.join(root, rel)
        tar.add(path, arcname=rel)
sys.stdout.buffer.write(buf.getvalue())
PY"""


def list_remote(transport: Transport) -> dict[str, dict]:
    if isinstance(transport, BashTransport):
        return transport.list_files()
    raw = transport.run(REMOTE_LIST).decode()
    rows = json.loads(raw)
    return {row['path']: row for row in rows}


def fetch_tar(transport: Transport, paths: list[str]) -> bytes:
    if not paths:
        return b''
    if isinstance(transport, BashTransport):
        return transport.tar_paths(paths)
    payload = base64.b64encode(json.dumps(paths).encode()).decode()
    tar_cmd = f"printf '%s' {shlex.quote(payload)} | {REMOTE_TAR}"
    return transport.run(tar_cmd)


def extract_tar_stream(stream: bytes, dest_root: Path, expected: dict[str, dict]) -> None:
    with tarfile.open(fileobj=io.BytesIO(stream), mode='r') as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                raise VerifyError(f'missing tar member: {member.name}')
            data = extracted.read()
            meta = expected.get(member.name)
            if meta is None:
                continue
            digest = hashlib.sha256(data).hexdigest()
            if digest != meta['sha256']:
                raise VerifyError(f'sha256 mismatch for {member.name}')
            target = dest_root / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != data:
                stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
                prev = target.with_name(f'{target.name}.prev-{stamp}')
                prev.write_bytes(target.read_bytes())
            target.write_bytes(data)


def verify_job_manifest(dest_root: Path, job_prefix: str, remote_index: dict[str, dict]) -> int:
    job_done_rel = f'{job_prefix}/JOB-DONE'
    if job_done_rel not in remote_index:
        return 0
    job_dir = dest_root / job_prefix
    manifest = job_dir / 'MANIFEST.sha256'
    if not manifest.exists():
        raise VerifyError(f'missing local manifest for {job_prefix}')
    for line in manifest.read_text().splitlines():
        if not line.strip():
            continue
        digest, rel = line.split('  ', 1)
        path = job_dir / rel
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise VerifyError(f'manifest mismatch for {job_prefix}/{rel}')
    status = 0
    for line in (job_dir / 'JOB-DONE').read_text().splitlines():
        if line.startswith('exit_status='):
            status = int(line.split('=', 1)[1])
    return len([line for line in manifest.read_text().splitlines() if line.strip()])


def pull_cycle(transport: Transport, remote_root: Path, dest: Path, *, announce: set[str] | None = None) -> set[str]:
    remote_root = Path(remote_root)
    announce_path = dest / '.pull-announced.json'
    if announce is None:
        announce = set(json.loads(announce_path.read_text())) if announce_path.exists() else set()
    index = list_remote(transport)
    local_index_path = dest / '.pull-index.json'
    prior = {}
    if local_index_path.exists():
        prior = json.loads(local_index_path.read_text())
    to_fetch = [
        path for path, meta in index.items()
        if prior.get(path) != meta['sha256']
    ]
    if to_fetch:
        stream = fetch_tar(transport, to_fetch)
        subset = {path: index[path] for path in to_fetch}
        extract_tar_stream(stream, dest, subset)
    local_index_path.parent.mkdir(parents=True, exist_ok=True)
    local_index_path.write_text(json.dumps({path: meta['sha256'] for path, meta in index.items()}))
    jobs = {}
    for path in index:
        m = re.match(r'^runs/([^/]+)/([^/]+)/([^/]+)/JOB-DONE$', path)
        if m:
            jobs[f'runs/{m.group(1)}/{m.group(2)}/{m.group(3)}'] = m.group(1)
    for job_prefix, run_id in sorted(jobs.items()):
        key = f'{run_id}/{job_prefix.removeprefix(f"runs/{run_id}/")}'
        if key in announce:
            continue
        if f'{job_prefix}/JOB-DONE' not in index:
            continue
        files = verify_job_manifest(dest, job_prefix, index)
        status = 0
        job_done = dest / job_prefix / 'JOB-DONE'
        for line in job_done.read_text().splitlines():
            if line.startswith('exit_status='):
                status = int(line.split('=', 1)[1])
        print(f'JOB-DONE {key} status={status} files={files} verified', flush=True)
        announce.add(key)
    announce_path.parent.mkdir(parents=True, exist_ok=True)
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
    backoff = interval
    cycles = 0
    exit_status = 0
    while True:
        cycles += 1
        if max_cycles is not None and cycles > max_cycles:
            return exit_status
        try:
            index = list_remote(transport)
            pull_cycle(transport, remote_root, dest, announce=announced)
            run_done = index.get(f'runs/{run_id}/RUN-DONE')
            if run_done:
                done_path = dest / f'runs/{run_id}/RUN-DONE'
                if not done_path.exists() and f'runs/{run_id}/RUN-DONE' in index:
                    rel = f'runs/{run_id}/RUN-DONE'
                    stream = fetch_tar(transport, [rel])
                    extract_tar_stream(stream, dest, {rel: run_done})
                if done_path.exists():
                    for line in done_path.read_text().splitlines():
                        if line.startswith('exit_status='):
                            exit_status = int(line.split('=', 1)[1])
                    print(f'RUN-DONE {run_id} exit_status={exit_status}', flush=True)
                    return exit_status
            backoff = interval
        except (TransportError, VerifyError) as exc:
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
    parser = argparse.ArgumentParser(prog='perf.container.pull')
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
