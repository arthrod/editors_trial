"""setup.py's harness manifest walk: which package.json files it installs.

A manifest with dependencies and no lockfile is still refused (missing_lockfile).
A manifest that declares no dependency has nothing to install or pin and is
skipped (harness/onlyoffice: it only says its scripts are ES modules). The
fetched OnlyOffice vendor trees are vendored release builds, never install
targets: their package.json files (x2t's module-type marker, Monaco's own
manifests inside the editor build) are not walked.
"""
import json
import sys

import pytest

from perf.tests.test_bucket_upload import _setup_facts


def _tree(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def _dry_run(monkeypatch, tmp_path):
    from perf.container import setup
    facts = _setup_facts(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(setup.subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(AssertionError('ran')))
    monkeypatch.setattr(sys, 'argv', ['setup', '--dry-run', '--facts', str(facts)])
    setup.main()


DEPS = json.dumps({'name': 'x', 'dependencies': {'left-pad': '1.3.0'}})


def test_dependency_free_manifest_and_vendor_trees_are_not_installed(monkeypatch, capsys, tmp_path):
    _tree(tmp_path, {
        'harness/ui/package.json': DEPS,
        'harness/ui/pnpm-lock.yaml': 'lockfileVersion: 9.0\n',
        'harness/onlyoffice/package.json': json.dumps({'name': 'onlyoffice-harness', 'private': True, 'type': 'module'}),
        'harness/onlyoffice/vendor/x2t/package.json': '{ "type": "commonjs" }\n',
        'harness/ui/onlyoffice/vendor/editor/web-apps/vendor/monaco/monaco/package.json': DEPS,
        'harness/ui/onlyoffice/vendor/editor/web-apps/vendor/monaco/monaco-for-ie/package.json': DEPS,
    })
    _dry_run(monkeypatch, tmp_path)
    out = capsys.readouterr().out
    assert '(cd harness/ui && pnpm install --frozen-lockfile)' in out
    assert 'skip harness/onlyoffice: package.json declares no dependency' in out
    assert '(cd harness/onlyoffice &&' not in out
    assert 'vendor/x2t' not in out
    assert 'monaco' not in out


def test_lockless_manifest_with_dependencies_is_still_refused(monkeypatch, tmp_path):
    _tree(tmp_path, {'harness/other/package.json': DEPS})
    with pytest.raises(ValueError, match='missing_lockfile'):
        _dry_run(monkeypatch, tmp_path)


def test_a_vendor_directory_elsewhere_is_still_walked(monkeypatch, tmp_path):
    # The rule names OnlyOffice's two fetched trees, not every directory called vendor.
    _tree(tmp_path, {'harness/other/vendor/package.json': DEPS})
    with pytest.raises(ValueError, match='missing_lockfile'):
        _dry_run(monkeypatch, tmp_path)


def test_dev_or_peer_dependencies_count_as_dependencies(monkeypatch, tmp_path):
    for key in ('devDependencies', 'optionalDependencies', 'peerDependencies'):
        _tree(tmp_path, {'harness/other/package.json': json.dumps({key: {'a': '1.0.0'}})})
        with pytest.raises(ValueError, match='missing_lockfile'):
            _dry_run(monkeypatch, tmp_path)
