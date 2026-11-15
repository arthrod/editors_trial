"""Pure host policy tests and local HTTP/filesystem integration tests."""
import importlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import urllib.request

FIXTURES = Path(__file__).parent / 'fixtures' / 'hosts'


class BrowserHosts(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('perf.runner.browser_hosts'),
                             'B1 production host support is missing')
        self.api = importlib.import_module('perf.runner.browser_hosts')

    def test_application_hosts_are_explicitly_not_publishable(self):
        for host in ['docsplus', 'fidus']:
            meta = self.api.host_policy(host)
            self.assertFalse(meta['publishable'])
            self.assertTrue(meta['publication_block_reason'])
            self.assertIn(meta['host_build'], ['dev_server', 'app_server'])
        self.assertEqual(self.api.host_policy('plate')['host_build'], 'production')

    def test_integration_tree_hash_covers_names_and_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'a').write_bytes(b'hello')
            first = self.api.tree_hash(root)
            self.assertEqual(first, self.api.tree_hash(root))
            (root / 'a').rename(root / 'b')
            self.assertNotEqual(first, self.api.tree_hash(root))
            second = self.api.tree_hash(root)
            (root / 'b').write_bytes(b'changed')
            self.assertNotEqual(second, self.api.tree_hash(root))

    def test_integration_static_routes_and_mime(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / 'micro.docx'
            fixture.write_bytes(b'run fixture')
            server = self.api.StaticHost(FIXTURES / 'static', port=0,
                                         corpus_route='/corpus.docx', fixture=fixture)
            try:
                for route, mime, body in [('/', 'text/html', b'ready'),
                    ('/module.mjs', 'text/javascript', b'export'),
                    ('/code.js', 'text/javascript', b'console'),
                    ('/style.css', 'text/css', b'body'),
                    ('/module.wasm', 'application/wasm', b'wasm'),
                    ('/corpus.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', b'run fixture')]:
                    with urllib.request.urlopen(server.url + route) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.headers.get_content_type(), mime)
                        self.assertIn(body, response.read())
            finally:
                server.stop()

    def test_wrapper_overrides_paths_and_loads_host_config(self):
        source = self.api.WRAPPER.read_text()
        self.assertIn('B1_HOST_CONFIG', source)
        self.assertIn('B1_HOST_ROOT', source)
        self.assertIn('B1_BUILD_ROOT', source)
        self.assertIn('cacheDir', source)
        self.assertIn('outDir', source)
        self.assertIn('loadConfigFromFile', source)

    def test_integration_fixture_switch_follows_current_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / 'a.docx', Path(tmp) / 'b.docx'
            first.write_bytes(b'first')
            second.write_bytes(b'second')
            server = self.api.StaticHost(FIXTURES / 'static', fixture=first)
            try:
                server.fixture = second
                with urllib.request.urlopen(server.url + '/corpus.docx') as response:
                    self.assertEqual(response.read(), b'second')
            finally:
                server.stop()

    def test_integration_real_vite_wrapper_preserves_plugin_and_relocates_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = self.api.build_host('fake', {'cwd': FIXTURES / 'vite'}, Path(tmp))
            dist = Path(meta['build_directory'])
            self.assertTrue(dist.is_relative_to(Path(tmp).resolve() / 'builds/fake'))
            self.assertIn('production-config-preserved', (dist / 'index.html').read_text())
            self.assertEqual(meta['tree_sha256'], self.api.tree_hash(dist))
            self.assertFalse((FIXTURES / 'vite/node_modules').exists())
            self.assertFalse((FIXTURES / 'vite/dist').exists())

    def test_integration_failed_build_is_not_attested_as_production(self):
        from perf.runner.browser_run import ACTIVE
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        class FakeRun:
            hosts = {}
            fixtures = {}
            out_root = Path(tmp.name)
        token = ACTIVE.set(FakeRun())
        try:
            with self.assertRaises(self.api.HostBuildError):
                self.api.start_host('missing', {'cwd': FIXTURES / 'absent'}, lambda *a: None)
            self.assertFalse(ACTIVE.get().hosts['missing']['publishable'])
            self.assertIn('build', ACTIVE.get().hosts['missing']['publication_block_reason'])
        finally:
            ACTIVE.reset(token)

    def test_integration_start_seam_reuses_build_and_attaches_apps(self):
        from perf.runner.browser_run import ACTIVE, BrowserRun
        with tempfile.TemporaryDirectory() as tmp:
            run = BrowserRun(tmp, 'seam', snapshot=lambda: {})
            fixture = run.fixture('micro', b'fixture bytes')
            token = ACTIVE.set(run)
            target = {'cwd': FIXTURES / 'vite', 'url': 'http://127.0.0.1:0/', 'corpus_route': '/corpus.docx'}
            try:
                for _ in range(2):
                    server = self.api.start_host('fake', target, lambda *a: None)
                    try:
                        self.api.select_fixture(target, fixture)
                        with urllib.request.urlopen(server.url + '/corpus.docx') as response:
                            self.assertEqual(response.read(), b'fixture bytes')
                        attached = self.api.start_host('docsplus', {'url': server.url}, lambda *a: None)
                        attached.stop()
                        self.assertFalse(run.hosts['docsplus']['publishable'])
                    finally:
                        server.stop()
                self.assertEqual(len(list((Path(tmp) / 'builds/fake').iterdir())), 1)
            finally:
                ACTIVE.reset(token)
        with self.assertRaisesRegex(RuntimeError, 'BrowserRun'):
            self.api.start_host('plate', {}, lambda *a: None)

    def test_integration_static_headers_and_symlink_escape(self):
        import urllib.error
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'public'
            root.mkdir()
            (Path(tmp) / 'secret').write_text('outside')
            (root / 'link').symlink_to(Path(tmp) / 'secret')
            server = self.api.StaticHost(root, headers={'Cross-Origin-Opener-Policy': 'same-origin'})
            try:
                with urllib.request.urlopen(server.url) as response:
                    self.assertEqual(response.headers['Cross-Origin-Opener-Policy'], 'same-origin')
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(server.url + '/link')
                self.assertEqual(caught.exception.code, 404)
                caught.exception.close()
            finally:
                server.stop()
            with self.assertRaises(FileNotFoundError):
                self.api.tree_hash(root / 'absent')
