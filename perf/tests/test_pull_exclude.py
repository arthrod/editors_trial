"""pull --exclude: large reproducible artifacts and already-verified runs stay on the Space."""
from __future__ import annotations

from pathlib import Path

from perf.tests.test_hf_data import write_job_tree


def _remote(tmp_path: Path) -> Path:
    root = tmp_path / 'remote'
    new, old = '20261111T041145Z-1', '20261111T005304Z-2'
    write_job_tree(root, new, 'benchmark_document', f'{new}-000', files={'summary.json': '{}'}, job_done=True)
    write_job_tree(root, old, 'benchmark_document', f'{old}-000', files={'summary.json': '{}'}, job_done=True)
    dist = root / 'runs' / new / 'builds' / 'plate' / 'abc' / 'dist' / 'assets'
    dist.mkdir(parents=True)
    (dist / 'index.js').write_text('x' * 1000)
    (root / 'runs' / new / 'builds' / 'plate' / 'abc' / 'build.json').write_text('{"tree_sha256": "t"}')
    return root


def test_exclude_skips_matching_paths_and_keeps_the_rest(tmp_path):
    from perf.container import pull as pull_mod

    root = _remote(tmp_path)
    dest = tmp_path / 'dest'
    rc = pull_mod.main([
        '--target', 'bash -c', '--remote', str(root), '--dest', str(dest),
        '--exclude', 'runs/*/builds/*/dist/*', '--exclude', 'runs/20261111T00*',
    ])
    assert rc == 0
    new = dest / 'runs' / '20261111T041145Z-1'
    assert (new / 'benchmark_document' / '20261111T041145Z-1-000' / 'summary.json').is_file()
    assert (new / 'builds' / 'plate' / 'abc' / 'build.json').is_file()
    assert not (new / 'builds' / 'plate' / 'abc' / 'dist').exists()
    assert not (dest / 'runs' / '20261111T005304Z-2').exists()


def test_excluded_paths_do_not_block_final_verification(tmp_path):
    from perf.container import pull as pull_mod

    root = _remote(tmp_path)
    dest = tmp_path / 'dest'
    pull_mod.EXCLUDE = ('runs/*/builds/*/dist/*',)
    try:
        pull_mod.pull_cycle(pull_mod.BashTransport(root), root, dest)
        index = pull_mod.list_remote(pull_mod.BashTransport(root))
        assert not any('/dist/' in p for p in index)
        assert pull_mod.local_bytes_match_listing(dest, index)
        assert pull_mod.all_jobs_manifest_verified(dest, index)
    finally:
        pull_mod.EXCLUDE = ()


def test_no_exclude_pulls_everything(tmp_path):
    from perf.container import pull as pull_mod

    root = _remote(tmp_path)
    dest = tmp_path / 'dest'
    assert pull_mod.main(['--target', 'bash -c', '--remote', str(root), '--dest', str(dest)]) == 0
    assert (dest / 'runs' / '20261111T041145Z-1' / 'builds' / 'plate' / 'abc' / 'dist' / 'assets' / 'index.js').is_file()
    assert (dest / 'runs' / '20261111T005304Z-2').is_dir()
