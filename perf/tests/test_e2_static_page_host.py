"""OnlyOffice's host page is served unbuilt (browser_hosts.STATIC_PAGES).

harness/ui/onlyoffice is plain files plus OnlyOffice's release archives under
vendor/ (fetched, SHA-512 pinned). It has no Vite config to build. start_host
serves it as it stands, hashes the page files and each vendor tree for
provenance, and allows the vendor trees as extra roots (vendor/ may be a
symlink to a shared copy). Every other editor keeps its build path, and a
StaticHost given no extra roots refuses a symlink escape as before.
"""
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from perf.runner import browser_hosts as hosts
from perf.runner.browser_run import ACTIVE, BrowserRun


class StaticPageHost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.page = root / 'onlyoffice'
        self.page.mkdir()
        for name in ('index.html', 'main.js', 'x2t_worker.js'):
            (self.page / name).write_text(f'// {name}')
        shared = root / 'shared-vendor'
        (shared / 'editor').mkdir(parents=True)
        (shared / 'x2t').mkdir()
        (shared / 'editor' / 'api.js').write_text('editor')
        (shared / 'x2t' / 'x2t.wasm').write_bytes(b'\0asm')
        (self.page / 'vendor').symlink_to(shared)

    def test_symlinked_vendor_is_served_only_as_a_named_extra_root(self):
        bare = hosts.StaticHost(self.page)
        try:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(bare.url + '/vendor/x2t/x2t.wasm')
            self.assertEqual(caught.exception.code, 404)
            caught.exception.close()
        finally:
            bare.stop()
        named = hosts.StaticHost(self.page, extra_roots=[self.page / 'vendor' / 'x2t'])
        try:
            with urllib.request.urlopen(named.url + '/vendor/x2t/x2t.wasm') as response:
                self.assertEqual(response.headers.get_content_type(), 'application/wasm')
                self.assertEqual(response.read(), b'\0asm')
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(named.url + '/vendor/editor/api.js')
            caught.exception.close()
        finally:
            named.stop()

    def test_onlyoffice_is_served_unbuilt_with_hashed_provenance(self):
        run = BrowserRun(Path(self.tmp.name), 'static', snapshot=lambda: {})
        fixture = run.fixture('prose', b'docx bytes')
        token = ACTIVE.set(run)
        self.addCleanup(ACTIVE.reset, token)
        target = {'cwd': self.page, 'url': 'http://127.0.0.1:0/', 'corpus_route': '/sample.docx'}
        server = hosts.start_host('onlyoffice', target, lambda *a: self.fail('legacy start used'))
        try:
            with urllib.request.urlopen(server.url + '/vendor/editor/api.js') as response:
                self.assertEqual(response.read(), b'editor')
            with urllib.request.urlopen(server.url + '/sample.docx') as response:
                self.assertEqual(response.read(), b'docx bytes')
        finally:
            server.stop()
        meta = run.hosts['onlyoffice']
        self.assertEqual(meta['adapter'], 'static_page')
        self.assertTrue(meta['publishable'])
        self.assertEqual(set(meta['tree_parts']), {'index.html', 'main.js', 'x2t_worker.js', 'vendor/editor', 'vendor/x2t'})
        self.assertEqual(meta['tree_parts']['vendor/x2t'], hosts.tree_hash(self.page / 'vendor' / 'x2t'))
        self.assertFalse((Path(self.tmp.name) / 'builds').exists())
        before = meta['tree_sha256']
        (self.page / 'vendor' / 'x2t' / 'x2t.wasm').write_bytes(b'changed')
        self.assertNotEqual(hosts.static_page_meta('onlyoffice', target, hosts.host_policy('onlyoffice'))['tree_sha256'], before)

    def test_missing_vendor_tree_fails_the_host_by_name(self):
        (self.page / 'vendor').unlink()
        with self.assertRaisesRegex(FileNotFoundError, 'fetch script'):
            hosts.static_page_meta('onlyoffice', {'cwd': self.page}, hosts.host_policy('onlyoffice'))

    def test_a_host_that_fails_validation_is_recorded_unpublishable(self):
        # CodeRabbit on #283 (2026-11-23): start_host stored the publishable
        # production policy first; a missing vendor tree raised past it and the
        # run still listed the host as publishable.
        (self.page / 'vendor').unlink()
        run = BrowserRun(Path(self.tmp.name), 'static', snapshot=lambda: {})
        token = ACTIVE.set(run)
        self.addCleanup(ACTIVE.reset, token)
        target = {'cwd': self.page, 'url': 'http://127.0.0.1:0/'}
        with self.assertRaises(FileNotFoundError):
            hosts.start_host('onlyoffice', target, lambda *a: self.fail('legacy start used'))
        meta = run.hosts['onlyoffice']
        self.assertIs(meta['publishable'], False)
        self.assertEqual(meta['outcome'], 'failed')
        self.assertIn('fetch script', meta['publication_block_reason'])

    def test_a_host_tree_that_changes_during_the_run_blocks_publication(self):
        # CodeRabbit on #283 (2026-11-23): the hash taken at start was published
        # even if the served files changed before the run ended.
        for change in (False, True):
            with self.subTest(changed=change):
                run = BrowserRun(Path(self.tmp.name), 'static', snapshot=lambda: {},
                                 accounting_reader=lambda: {'available': False, 'reason': 'fake'})
                token = ACTIVE.set(run)
                target = {'cwd': self.page, 'url': 'http://127.0.0.1:0/'}
                try:
                    hosts.start_host('onlyoffice', target, lambda *a: self.fail('legacy start used')).stop()
                finally:
                    ACTIVE.reset(token)
                if change:
                    (self.page / 'vendor' / 'x2t' / 'x2t.wasm').write_bytes(b'changed during the run')
                result = run.finish({'outcome': 'ok', 'publishable': True})
                if change:
                    self.assertIs(result['publishable'], False)
                    self.assertIn('host_tree_changed_during_run: onlyoffice', result['publication_block_reason'])
                    self.assertIn('tree_sha256_at_finish', run.hosts['onlyoffice'])
                else:
                    self.assertNotIn('host_tree_changed', str(result.get('publication_block_reason')))

    def test_only_onlyoffice_is_a_static_page(self):
        self.assertEqual(set(hosts.STATIC_PAGES), {'onlyoffice'})


if __name__ == '__main__':
    unittest.main()


def test_a_restart_on_a_changed_tree_keeps_the_first_hash_and_blocks(tmp_path):
    """CodeRabbit on #287: a second start of OpenDoc (or WordCraft) in one run
    replaced the first tree hash, so samples served from the first tree were
    published under the second's hash and the end-of-run check passed."""
    webapp = tmp_path / 'repos' / 'opendoc' / 'webapp'
    webapp.mkdir(parents=True)
    (webapp / 'index.html').write_text('first')
    host_dir = tmp_path / 'host'
    host_dir.mkdir()
    (host_dir / 'host.mjs').write_text('// host')
    target = {'cwd': host_dir, 'url': 'http://127.0.0.1:0/', 'repos_root': str(tmp_path / 'repos')}
    run = BrowserRun(tmp_path / 'out', 'static', snapshot=lambda: {},
                     accounting_reader=lambda: {'available': False, 'reason': 'fake'})
    token = ACTIVE.set(run)
    try:
        hosts.start_host('opendoc', dict(target), lambda *a: None)
        first = run.hosts['opendoc']['tree_sha256']
        (webapp / 'index.html').write_text('second')
        hosts.start_host('opendoc', dict(target), lambda *a: None)
    finally:
        ACTIVE.reset(token)
    meta = run.hosts['opendoc']
    assert meta['tree_sha256'] == first
    assert meta['tree_sha256_at_restart'] != first
    result = run.finish({'outcome': 'ok', 'publishable': True})
    assert result['publishable'] is False
    assert 'host_tree_changed_during_run: opendoc' in result['publication_block_reason']


def test_a_restart_on_the_same_tree_stays_publishable(tmp_path):
    """The control: two starts on unchanged bytes publish as before."""
    webapp = tmp_path / 'repos' / 'opendoc' / 'webapp'
    webapp.mkdir(parents=True)
    (webapp / 'index.html').write_text('same')
    host_dir = tmp_path / 'host'
    host_dir.mkdir()
    target = {'cwd': host_dir, 'url': 'http://127.0.0.1:0/', 'repos_root': str(tmp_path / 'repos')}
    run = BrowserRun(tmp_path / 'out', 'static', snapshot=lambda: {},
                     accounting_reader=lambda: {'available': False, 'reason': 'fake'})
    token = ACTIVE.set(run)
    try:
        hosts.start_host('opendoc', dict(target), lambda *a: None)
        hosts.start_host('opendoc', dict(target), lambda *a: None)
    finally:
        ACTIVE.reset(token)
    assert 'tree_sha256_at_restart' not in run.hosts['opendoc']
    result = run.finish({'outcome': 'ok', 'publishable': True})
    assert 'host_tree_changed' not in str(result.get('publication_block_reason'))


def test_a_tree_changed_and_put_back_during_the_run_still_blocks(tmp_path):
    """CodeRabbit on #287 (follow-up): A, then a restart on B, then a restart
    back on A. The bytes at the end match the first hash, but samples were
    served from B in between, so the run must not publish; and the third start
    must not erase the record of B."""
    webapp = tmp_path / 'repos' / 'opendoc' / 'webapp'
    webapp.mkdir(parents=True)
    (webapp / 'index.html').write_text('A')
    host_dir = tmp_path / 'host'
    host_dir.mkdir()
    target = {'cwd': host_dir, 'url': 'http://127.0.0.1:0/', 'repos_root': str(tmp_path / 'repos')}
    run = BrowserRun(tmp_path / 'out', 'static', snapshot=lambda: {},
                     accounting_reader=lambda: {'available': False, 'reason': 'fake'})
    token = ACTIVE.set(run)
    try:
        hosts.start_host('opendoc', dict(target), lambda *a: None)
        first = run.hosts['opendoc']['tree_sha256']
        (webapp / 'index.html').write_text('B')
        hosts.start_host('opendoc', dict(target), lambda *a: None)
        (webapp / 'index.html').write_text('A')
        hosts.start_host('opendoc', dict(target), lambda *a: None)
    finally:
        ACTIVE.reset(token)
    meta = run.hosts['opendoc']
    assert meta['tree_sha256'] == first
    assert meta.get('tree_sha256_at_restart'), 'the restart on B was forgotten'
    result = run.finish({'outcome': 'ok', 'publishable': True})
    assert result['publishable'] is False
    assert 'host_tree_changed_during_run: opendoc' in result['publication_block_reason']
