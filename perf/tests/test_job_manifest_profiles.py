"""A browser's own profile folder is not evidence (shakedown 2026-11-11).

Chrome deletes its write-ahead logs after the manifest is written, so the
pull waited for files that no longer existed; and the profiles were 7 of the
10 GB pulled.
"""
from perf.container.artifacts import finalize_job


def _write(path, text='x'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_browser_profiles_are_removed_before_the_manifest(tmp_path):
    job = tmp_path / 'benchmark_typing-001'
    _write(job / 'cells/0000-plate/browser-profile/Default/DIPS-wal')
    _write(job / 'profiles/superdoc/abc123/Default/DIPS-wal')
    _write(job / 'cells/0000-plate/attempts/typing.json', '{}')
    _write(job / 'cells/0000-plate/profile/trace.json', '{}')  # a Chromium trace is evidence
    finalize_job(job, 0)
    manifest = (job / 'MANIFEST.sha256').read_text()
    assert 'browser-profile' not in manifest and 'profiles/' not in manifest
    assert not (job / 'cells/0000-plate/browser-profile').exists()
    assert not (job / 'profiles').exists()
    assert 'cells/0000-plate/attempts/typing.json' in manifest
    assert 'cells/0000-plate/profile/trace.json' in manifest
