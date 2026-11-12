"""Call the existing host gate, retaining its refusal rather than bypassing it.

A bucket copy is expected on a Hugging Face Space: the Storage Bucket is
attached as a volume at /data and every sealed job is copied, verified, to
HF_MIRROR_ROOT (default /data/e2). No HF token belongs in the container
(issue #164). Dev Mode ssh often does not export SPACE_ID, so it is also
read from PID 1's environment. Set HF_BUCKET_REQUIRED=1 to demand the mount
when SPACE_ID is unset. A value of 0 does not waive the check once SPACE_ID
is set: skipping it would let a campaign measure with no bucket copy.
"""
import json
import os
from pathlib import Path

from perf.container import mirror
from perf.runner.host import host_record, quiet_machine_check


def _proc1_value(name: str) -> str | None:
    prefix = f'{name}='.encode()
    try:
        raw = Path(mirror.PROC1_ENVIRON).read_bytes()
    except OSError:
        return None
    for field in raw.split(b'\0'):
        if field.startswith(prefix):
            value = field[len(prefix):].decode('utf-8', 'replace').strip()
            return value or None
    return None


def bucket_expected() -> bool:
    if os.environ.get('SPACE_ID', '').strip():
        return True
    if _proc1_value('SPACE_ID'):
        return True
    return os.environ.get('HF_BUCKET_REQUIRED') == '1'


def bucket_status() -> dict:
    """The bucket copy is the verified HF_MIRROR_ROOT copy onto the Storage
    Bucket attached to the Space as a volume (issue #164). No token is read
    or required: none belongs in the container."""
    expected = bucket_expected()
    mount = mirror.mirror_mount_status()
    ready = mount == 'mounted'
    blocking = ['no_bucket_mount'] if expected and not ready else []
    return {
        'expected': expected,
        'ready': ready,
        'mirror_root': os.environ.get('HF_MIRROR_ROOT', '/data/e2'),
        'mount': mount,
        'blocking': blocking,
    }


def main():
    record = host_record()
    verdict = quiet_machine_check()
    bucket = bucket_status()
    if bucket['blocking']:
        verdict['reasons'] = list(bucket['blocking']) + list(verdict['reasons'])
        verdict['quiet'] = False
    print(json.dumps({'host': record, 'quiet_machine_check': verdict, 'bucket': bucket}, indent=2))
    if not verdict['quiet']:
        if bucket['blocking']:
            raise SystemExit('host check refused: ' + ', '.join(bucket['blocking']))
        raise SystemExit('host check refused; do not start browser runners')


if __name__ == '__main__':
    main()
