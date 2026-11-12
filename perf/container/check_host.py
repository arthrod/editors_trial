"""Call the existing host gate, retaining its refusal rather than bypassing it.

A bucket copy is expected on a Hugging Face Space. Dev Mode ssh often does
not export SPACE_ID or the Space secret, so both are read from PID 1's
environment, the same fallback the mirror uses for the token. Set
HF_BUCKET_REQUIRED=1 to demand a copy when SPACE_ID is unset. A value of
0 does not waive the check once SPACE_ID is set: skipping it would let a
campaign measure with no bucket copy.
"""
import importlib
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


def _hub_version() -> str | None:
    try:
        module = importlib.import_module('huggingface_hub')
    except ImportError:
        return None
    version = getattr(module, '__version__', None)
    if isinstance(version, str) and version.strip():
        return version.strip()
    try:
        return importlib.metadata.version('huggingface_hub')
    except importlib.metadata.PackageNotFoundError:
        return None


def bucket_status() -> dict:
    expected = bucket_expected()
    version = _hub_version()
    # Status word only. The token value is not stored on the report.
    token = 'present' if mirror._bucket_token() else 'absent'
    hub = version if version is not None else 'missing'
    ready = version == mirror.HUGGINGFACE_HUB_VERSION and token == 'present'
    blocking = []
    if expected and not ready:
        if version is None:
            blocking.append('no_huggingface_hub')
        elif version != mirror.HUGGINGFACE_HUB_VERSION:
            blocking.append(
                f'huggingface_hub_version {version} != {mirror.HUGGINGFACE_HUB_VERSION}'
            )
        if token == 'absent':
            blocking.append('no_token')
    return {
        'expected': expected,
        'ready': ready,
        'huggingface_hub': hub,
        'token': token,
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
