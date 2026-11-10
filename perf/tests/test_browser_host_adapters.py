"""Build/HTTP integration tests using real Vite and isolated miniature hosts.

No editor checkout is changed. Pure policy tests need no I/O doubles.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.request
from perf.runner import browser_hosts as hosts
from perf.runner.browser_run import ACTIVE, BrowserRun


class HostAdapters(unittest.TestCase):
    def test_docsplus_is_app_server(self):
        self.assertEqual(hosts.host_policy('docsplus')['host_build'], 'app_server')
        self.assertFalse(hosts.host_policy('docsplus')['publishable'])

    def test_genoffice_attempts_production(self):
        self.assertEqual(hosts.host_policy('genoffice')['host_build'], 'production')

    def test_fidus_requires_app_service(self):
        self.assertEqual(hosts.host_policy('fidus')['host_build'], 'app_server')
        self.assertTrue(hosts.host_policy('fidus')['publication_block_reason'])


class BuildIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.host = self.root / 'host'
        self.host.mkdir()
        self.repos = self.root / 'repos'
        self.repos.mkdir()
        (self.host / 'index.html').write_text('<html><body><script type="module" src="/main.js"></script></body></html>')
        (self.host / 'main.js').write_text('document.body.dataset.ready="yes"')
        self.config = self.host / 'vite.config.mjs'
        self.config.write_text('export default {}')
        self.target = {'cwd': self.host, 'repos_root': self.repos, 'url': 'http://127.0.0.1:0/'}

    def build(self, editor):
        return hosts.build_host(editor, self.target, self.root / 'outputs')

    def test_plate_relocates_aliases_to_supplied_checkout(self):
        source = self.repos / 'plate/packages/platejs/src'
        source.mkdir(parents=True)
        (source / 'index.js').write_text('export default "relocated-plate"')
        self.config.write_text('export default {resolve:{alias:[{find:/^platejs$/,replacement:"/absent/workspace/repos/plate/packages/platejs/src/index.js"}]}}')
        (self.host / 'main.js').write_text('import x from "platejs";document.body.textContent=x')
        try:
            meta = self.build('plate')
        except Exception as exc:
            self.fail('Plate aliases did not relocate: ' + str(exc))
        self.assertIn('relocated-plate', ''.join(p.read_text() for p in Path(meta['build_directory']).rglob('*.js')))

    def test_docxodus_copies_raw_dist_and_wasm_precedence(self):
        dist = self.host / 'node_modules/docxodus/dist'
        (dist / 'wasm').mkdir(parents=True)
        (dist / 'library.js').write_bytes(b'raw bytes')
        (dist / 'runtime.js').write_bytes(b'fallback')
        (dist / 'wasm/runtime.js').write_bytes(b'preferred')
        meta = self.build('docxodus')
        out = Path(meta['build_directory'])
        self.assertEqual((out / 'docxodus-dist/library.js').read_bytes(), b'raw bytes')
        self.assertEqual((out / 'wasm/runtime.js').read_bytes(), b'preferred')
        server = hosts.StaticHost(out)
        self.addCleanup(server.stop)
        # The dev middleware also accepts node_modules-style URLs.
        try:
            with urllib.request.urlopen(server.url + '/node_modules/docxodus/dist/library.js') as response:
                self.assertEqual(response.read(), b'raw bytes')
        except Exception as exc:
            self.fail('raw dist URL was lost: ' + str(exc))

    def test_genoffice_preserves_renderer_root_and_emits_stub(self):
        renderer = self.repos / 'genoffice/apps/docs/src/renderer'
        renderer.mkdir(parents=True)
        (renderer / 'index.html').write_text('<script type="module" src="./main.tsx"></script>')
        (renderer / 'main.tsx').write_text('document.body.textContent="real-renderer"')
        (self.host / 'desktop-stub.js').write_text('window.desktop={ready:true}')
        self.config.write_text('export default {root:process.env.GENOFFICE_REPO+"/apps/docs/src/renderer"}')
        meta = self.build('genoffice')
        out = Path(meta['build_directory'])
        self.assertTrue((out / 'desktop-stub.js').is_file(), 'desktop bridge missing')
        self.assertIn('real-renderer', ''.join(p.read_text() for p in out.rglob('*.js')))

    def test_genoffice_synthesizes_missing_renderer_entry(self):
        renderer = self.repos / 'genoffice/apps/docs/src/renderer'
        renderer.mkdir(parents=True)
        (renderer / 'main.tsx').write_text('document.getElementById("root").textContent="generated-entry"')
        (self.host / 'desktop-stub.js').write_text('window.desktop={}')
        self.config.write_text('export default {root:process.env.GENOFFICE_REPO+"/apps/docs/src/renderer"}')
        meta = self.build('genoffice')
        out = Path(meta['build_directory'])
        self.assertIn('id="root"', (out / 'index.html').read_text())
        self.assertIn('generated-entry', ''.join(p.read_text() for p in out.rglob('*.js')))
        self.assertFalse((renderer / 'index.html').exists())

    def test_apryse_absent_key_refuses_before_config_load(self):
        # Empty target env cannot supply a secret; only the real process env may.
        prior = os.environ.pop('APRYSE_API_KEY', None)
        self.addCleanup(lambda: os.environ.update({'APRYSE_API_KEY': prior}) if prior is not None else None)
        self.config.write_text('throw new Error("config must not load")')
        run = BrowserRun(self.root, 'apryse', snapshot=lambda: {})
        token = ACTIVE.set(run)
        self.addCleanup(ACTIVE.reset, token)
        with self.assertRaises(Exception):
            hosts.start_host('apryse', self.target, lambda *a: self.fail('fallback'))
        meta = run.hosts['apryse']
        self.assertEqual(meta.get('reason'), 'apryse_key_absent')
        self.assertIs(meta.get('key_present'), False)
        self.assertEqual(meta.get('failure_reason'), 'host_build')

    def test_apryse_static_isolation_headers(self):
        run = BrowserRun(self.root, 'headers', snapshot=lambda: {})
        run.hosts['apryse'] = {'build_directory': str(self.host)}
        token = ACTIVE.set(run)
        self.addCleanup(ACTIVE.reset, token)
        server = hosts.start_host('apryse', self.target, lambda *a: self.fail('fallback'))
        self.addCleanup(server.stop)
        with urllib.request.urlopen(server.url) as response:
            self.assertEqual(response.headers['Cross-Origin-Opener-Policy'], 'same-origin')
            self.assertEqual(response.headers['Cross-Origin-Embedder-Policy'], 'require-corp')

    def test_broken_config_records_failed_build_log_without_fallback(self):
        self.config.write_text('throw new Error("deliberately broken host")')
        run = BrowserRun(self.root, 'broken', snapshot=lambda: {})
        token = ACTIVE.set(run)
        self.addCleanup(ACTIVE.reset, token)
        with self.assertRaises(Exception):
            hosts.start_host('fake', self.target, lambda *a: self.fail('fallback'))
        meta = run.hosts['fake']
        self.assertEqual(meta.get('failure_reason'), 'host_build')
        self.assertEqual(meta.get('outcome'), 'failed')
        self.assertIn('deliberately broken host', Path(meta['build_log']).read_text())
        self.assertFalse(meta['publishable'])

    def _plain(self, editor):
        meta = self.build(editor)
        out = Path(meta['build_directory'])
        self.assertTrue((out / 'index.html').is_file())
        self.assertTrue(out.is_relative_to(self.root / 'outputs'))
        self.assertFalse((self.host / 'node_modules').exists())
        self.assertEqual(meta['tree_sha256'], hosts.tree_hash(out))

    def test_superdoc_wrapper(self): self._plain('superdoc')
    def test_canvas_wrapper(self): self._plain('canvas')
    def test_docen_wrapper(self): self._plain('docen')
    def test_eigenpal_wrapper(self): self._plain('eigenpal')

    def test_folio_query_loads_fixture_from_static_route(self):
        self._plain('folio')
        fixture = self.root / 'fixture.docx'
        fixture.write_bytes(b'folio fixture')
        server = hosts.StaticHost(self.host, corpus_route='/fixtures/corpus.docx', fixture=fixture)
        self.addCleanup(server.stop)
        with urllib.request.urlopen(server.url + '/?file=corpus.docx') as response:
            self.assertEqual(response.status, 200)
        with urllib.request.urlopen(server.url + '/fixtures/corpus.docx') as response:
            self.assertEqual(response.read(), b'folio fixture')

    def test_wordcraft_hashes_supplied_existing_release_without_build(self):
        release = self.repos / 'wordcraft/dist/web'
        release.mkdir(parents=True)
        (release / 'index.html').write_text('existing release')
        run = BrowserRun(self.root, 'release', snapshot=lambda: {})
        token = ACTIVE.set(run)
        self.addCleanup(ACTIVE.reset, token)
        sentinel = object()
        launched = []
        def launch(editor, target):
            launched.append(target)
            return sentinel
        try:
            result = hosts.start_host('wordcraft', self.target, launch)
        except Exception as exc:
            self.fail('explicit repo root not used: ' + str(exc))
        self.assertIs(result, sentinel)
        self.assertEqual(launched[0].get('env', {}).get('WC_DIST'), str(release))
        self.assertEqual(run.hosts['wordcraft']['tree_sha256'], hosts.tree_hash(release))

    def test_apryse_key_present_ignores_dotenv_and_redacts_failure(self):
        prior = os.environ.get('APRYSE_API_KEY')
        os.environ['APRYSE_API_KEY'] = 'test-only-sentinel'
        self.addCleanup(lambda: os.environ.pop('APRYSE_API_KEY', None) if prior is None else os.environ.update(APRYSE_API_KEY=prior))
        (self.host / 'perf.html').write_text('<script type="module" src="/main.js"></script>')
        (self.root / '.env').write_text('APRYSE_FORBIDDEN=from-dotenv\n')
        (self.host / 'main.js').write_text('document.body.textContent=import.meta.env.APRYSE_FORBIDDEN||"env-isolated"')
        self.config.write_text('export default {envDir:"..",envPrefix:"APRYSE_"}')
        meta = self.build('apryse')
        self.assertIs(meta['key_present'], True)
        scripts = ''.join(p.read_text() for p in Path(meta['build_directory']).rglob('*.js'))
        self.assertIn('env-isolated', scripts)
        self.assertNotIn('from-dotenv', scripts)
        self.config.write_text('throw new Error(process.env.APRYSE_API_KEY)')
        with self.assertRaises(hosts.HostBuildError) as caught:
            self.build('apryse')
        self.assertNotIn('test-only-sentinel', str(caught.exception))
        self.assertNotIn('test-only-sentinel', Path(caught.exception.metadata['build_log']).read_text())


    def test_docxodus_materializer_stays_external_and_byte_identical(self):
        dist = self.host / 'node_modules/docxodus/dist'
        dist.mkdir(parents=True)
        materializer = b'export const materializer = import.meta.url; // attested bytes'
        (dist / 'export-browser.bundle.js').write_bytes(materializer)
        (dist.parent / 'package.json').write_text(json.dumps({'name':'docxodus', 'type':'module', 'exports':{'./export-browser':'./dist/export-browser.bundle.js'}}))
        (self.host / 'main.js').write_text('import {materializer} from "docxodus/export-browser";document.body.textContent=materializer')
        meta = self.build('docxodus')
        out = Path(meta['build_directory'])
        js = ''.join(p.read_text() for p in (out / 'assets').glob('*.js'))
        self.assertIn('/docxodus-dist/export-browser.bundle.js', js)
        self.assertEqual((out / 'docxodus-dist/export-browser.bundle.js').read_bytes(), materializer)

    def test_eigenpal_commonjs_config_directory_is_preserved_in_memory(self):
        self.config.write_text('export default {define:{__CONFIG_ROOT__:JSON.stringify(__dirname)}}')
        (self.host / 'main.js').write_text('document.body.textContent=__CONFIG_ROOT__')
        try:
            meta = self.build('eigenpal')
        except Exception as exc:
            self.fail('config directory unavailable: ' + str(exc))
        self.assertIn(str(self.host), ''.join(p.read_text() for p in Path(meta['build_directory']).rglob('*.js')))

    def test_warm_cold_missing_key_records_host_failure(self):
        import sys
        from perf.runner.benchmark_warm_cold import _main
        previous = sys.argv
        self.addCleanup(setattr, sys, 'argv', previous)
        removed = {name: os.environ.pop(name) for name in
                   ('APRYSE_API_KEY', 'APRYSE_LICENSE_KEY', 'PDFTRON_LICENSE_KEY', 'TRIAL_KEY') if name in os.environ}
        self.addCleanup(os.environ.update, removed)
        run = BrowserRun(self.root, 'entry', snapshot=lambda: {})
        token = ACTIVE.set(run)
        self.addCleanup(ACTIVE.reset, token)
        sys.argv = ['benchmark_warm_cold', '--editors', 'apryse', '--pairs', '1', '--out-root', str(self.root / 'cell')]
        _main()
        self.assertEqual(run.hosts.get('apryse', {}).get('failure_reason'), 'host_build')
        self.assertEqual(run.hosts['apryse']['reason'], 'apryse_key_absent')
