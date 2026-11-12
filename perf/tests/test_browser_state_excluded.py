"""Browser user-data folders are state, not evidence (shakedown 3).

Chrome keeps writing into a job's browser-profile while it shuts down, so a
file can appear after the job is sealed and vanish again. Such files must
never enter a manifest, never block pull verification, never be pulled and
never reach the bucket. Evidence files with similar names (cells/*/profile/
trace-*.json.gz) stay.
"""
from __future__ import annotations

from pathlib import Path

from perf.container import artifacts, mirror, pull


def _job(tmp_path: Path) -> Path:
    job = tmp_path / 'runs' / 'r1' / 'benchmark_typing' / 'r1-127'
    for rel, text in {
        'summary.json': '{}',
        'cells/0000-superdoc/resources.json': '{}',
        'cells/0000-superdoc/browser-profile/Default/Cache/Cache_Data/a_0': 'x',
        'cells/0000-superdoc/profile-invoke/browser-profile/Default/Local Storage/b': 'y',
        'profiles/genoffice/abc/Default/DIPS-wal': 'z',
        'cells/0000-genoffice/profile/trace-warm_cold.json.gz': 'trace',
    }.items():
        path = job / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return job


def test_browser_state_paths_are_recognised():
    assert artifacts.is_browser_state('cells/0000-superdoc/browser-profile/Default/x')
    assert artifacts.is_browser_state('cells/0000-superdoc/profile-invoke/browser-profile/Default/x')
    assert artifacts.is_browser_state('profiles/genoffice/abc/Default/DIPS-wal')
    assert not artifacts.is_browser_state('cells/0000-genoffice/profile/trace-warm_cold.json.gz')
    assert not artifacts.is_browser_state('summary.json')


def test_manifest_never_names_browser_state_even_if_rewritten_during_seal(tmp_path, monkeypatch):
    job = _job(tmp_path)
    real_remove = artifacts.remove_browser_profiles

    def remove_then_chrome_writes_again(job_dir):
        real_remove(job_dir)
        late = job_dir / 'cells/0000-superdoc/browser-profile/Default/Cache/Cache_Data/late_0'
        late.parent.mkdir(parents=True, exist_ok=True)
        late.write_text('late')

    monkeypatch.setattr(artifacts, 'remove_browser_profiles', remove_then_chrome_writes_again)
    artifacts.finalize_job(job, 0)
    body = (job / 'MANIFEST.sha256').read_text()
    assert 'browser-profile' not in body and 'profiles/' not in body.replace('cells/0000-genoffice/profile/', '')
    assert 'cells/0000-genoffice/profile/trace-warm_cold.json.gz' in body
    assert 'summary.json' in body


def test_nested_profiles_are_removed_at_seal(tmp_path):
    job = _job(tmp_path)
    artifacts.finalize_job(job, 0)
    assert not (job / 'cells/0000-superdoc/profile-invoke/browser-profile').exists()
    assert not (job / 'cells/0000-superdoc/browser-profile').exists()
    assert not (job / 'profiles').exists()
    assert (job / 'cells/0000-genoffice/profile/trace-warm_cold.json.gz').is_file()


def test_pull_verification_ignores_stale_browser_state(tmp_path):
    dest = tmp_path / 'dest'
    job = _job(dest)
    # An old seal: the manifest names only evidence, but a profile file pulled
    # earlier is still on disk (Chrome recreated it after the seal).
    lines = [line for line in artifacts.build_manifest_lines(job)
             if not artifacts.is_browser_state(line.split('  ', 1)[1])]
    (job / 'MANIFEST.sha256').write_text('\n'.join(lines) + '\n')
    manifest_sha = artifacts.sha256_bytes((job / 'MANIFEST.sha256').read_bytes())
    (job / 'JOB-DONE').write_text(f'exit_status=0\nmanifest_sha256={manifest_sha}\n')
    prefix = 'runs/r1/benchmark_typing/r1-127'
    index = {f'{prefix}/JOB-DONE': {'sha256': 'x', 'size': 1}}
    pull.verify_job_manifest_impl(dest, prefix, index)


def test_pull_listing_never_includes_browser_state():
    import json
    rows = [
        'runs/r1/benchmark_typing/r1-127/cells/0000-superdoc/browser-profile/Default/a',
        'runs/r1/benchmark_resources/r1-074/profiles/wordcraft/h/Default/Code Cache/b',
        'runs/r1/benchmark_warm_cold/r1-008/cells/0000-genoffice/profile/trace-warm_cold.json.gz',
        'runs/r1/benchmark_typing/r1-127/summary.json',
    ]
    raw = '\n'.join(json.dumps({'path': p, 'sha256': 's', 'size': 1}) for p in rows)
    index = pull.parse_listing(raw)
    assert sorted(index) == sorted(rows[2:])


def test_bucket_copy_excludes_browser_state():
    assert mirror.bucket_excluded('cells/0000-superdoc/browser-profile/Default/a')
    assert mirror.bucket_excluded('profiles/wordcraft/h/Default/b')
    assert not mirror.bucket_excluded('cells/0000-genoffice/profile/trace-warm_cold.json.gz')
