"""Production host policy, build wrappers and the shared HTTP server seam.

Config audit (2026-11-09); 'candidate' requires a successful build at runtime.
No successful build is silently replaced by a development server.

| Host | Static build | Config / reason |
| --- | --- | --- |
| plate | Vite candidate | vite.config.ts; React and source aliases survive build |
| docxodus | Vite candidate | vite.config.ts; copy raw dist and WASM dev middleware assets |
| superdoc | Vite candidate | vite.config.ts; package imports, no server middleware |
| genoffice | No (dev_server) | vite.config.mjs changes root to Electron renderer; host has no index.html; desktop-stub is dev middleware |
| canvas | Vite candidate | vite.config.mjs; source aliases, normal HTML entry |
| docen | Vite candidate | docen-host/vite.config.mjs; source aliases, normal HTML entry |
| docsplus | No (dev_server) | host/start.sh runs Next dev, REST stub and route-injecting proxy |
| fidus | No (app_server) | fidus-host/proxy.mjs needs Django session/import API |
| wordcraft | Existing production | wordcraft-host/server.mjs serves Trunk dist/web; hash dist and host |
| apryse | Vite candidate | vite.perf.config.mjs; perf.html entry, public lib and COOP/COEP headers |
| eigenpal | Vite candidate | examples/vite/vite.config.ts; source aliases and emitted fixtures |
| folio | Vite candidate | packages/playground/vite.config.ts; corpus middleware replaced by fixture route |

Non-static hosts are attached to an already running service: starting their
original commands can write Next/Django caches inside read-only checkouts.
Their measurements are never publishable. Wordcraft's existing read-only
Trunk server may be launched and is stopped through the existing process seam.
"""
from __future__ import annotations

from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import subprocess
import threading
from urllib.parse import urlsplit, unquote
import urllib.request
import uuid

from perf.runner.browser_run import ACTIVE, REPO

WRAPPER = Path(__file__).parent / 'hosts' / 'vite.config.mjs'
NONSTATIC = {
    'docsplus': ('dev_server', 'Next dev and REST proxy require an existing app service'),
    'fidus': ('app_server', 'Django session/import API requires an existing app service'),
    'genoffice': ('dev_server', 'Electron renderer root and desktop-stub dev middleware; no host HTML entry'),
}


def host_policy(editor):
    if editor in NONSTATIC:
        kind, reason = NONSTATIC[editor]
        return {'host_build': kind, 'publishable': False, 'publication_block_reason': reason}
    return {'host_build': 'production', 'publishable': True, 'publication_block_reason': None}


def tree_hash(root):
    """Length-framed (UTF-8 relative path, file bytes), sorted by relative path."""
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(root)
    digest = hashlib.sha256()
    for path in sorted((p for p in root.rglob('*') if p.is_file()), key=lambda p: p.relative_to(root).as_posix()):
        name = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(name).to_bytes(8, 'big'))
        digest.update(name)
        digest.update(len(data).to_bytes(8, 'big'))
        digest.update(data)
    return digest.hexdigest()


class StaticHost:
    def __init__(self, root, *, port=0, corpus_route='/corpus.docx', fixture=None, headers=None):
        root = Path(root).resolve()
        self.fixture = fixture
        host = self
        class Handler(SimpleHTTPRequestHandler):
            extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                '.wasm': 'application/wasm', '.mjs': 'text/javascript', '.js': 'text/javascript',
                '.css': 'text/css', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}

            def translate_path(self, path):
                if unquote(urlsplit(path).path) == corpus_route and host.fixture is not None:
                    return str(host.fixture)
                resolved = Path(super().translate_path(path)).resolve()
                if not resolved.is_relative_to(root):
                    return str(root / '__forbidden__')
                return str(resolved)

            def end_headers(self):
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                super().end_headers()

            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', port), partial(Handler, directory=str(root)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:%d' % self.server.server_port

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class AttachedHost:
    def stop(self):
        # The attached service belongs to somebody else.
        pass


def vite_paths(cwd):
    for base in (cwd, *cwd.parents, (REPO / 'harness/ui/plate').resolve()):
        vite = base / 'node_modules/vite'
        if (vite / 'bin/vite.js').is_file():
            return vite.resolve()
    raise FileNotFoundError('Vite is not installed; no install performed')


def build_host(editor, target, out_root):
    cwd = Path(target['cwd']).resolve()
    config_name = target.get('config')
    if not config_name:
        command = target.get('command', [])
        if '--config' in command:
            config_name = command[command.index('--config') + 1]
    configs = [cwd / config_name] if config_name else [cwd / ('vite.config.' + ext) for ext in ('ts', 'mjs', 'js', 'mts')]
    config = next((p for p in configs if p.is_file()), None)
    if config is None:
        raise FileNotFoundError(f'no Vite config for {editor}')
    build_root = Path(out_root).resolve() / 'builds' / editor / uuid.uuid4().hex
    for forbidden in ((REPO / 'harness').resolve(), REPO / 'repos', (REPO / 'harness').resolve().parent / 'repos'):
        if build_root.is_relative_to(forbidden.resolve()):
            raise ValueError('build output must be outside harness/ and repos/')
    build_root.mkdir(parents=True)
    vite = vite_paths(cwd)
    env = {**os.environ, **target.get('env', {}),
           'B1_HOST_ROOT': str(cwd), 'B1_HOST_CONFIG': str(config),
           'B1_BUILD_ROOT': str(build_root), 'B1_VITE_MODULE': str(vite / 'dist/node/index.js'),
           'B1_HOST_ID': editor}
    command = ['node', str(vite / 'bin/vite.js'), 'build', '--config', str(WRAPPER.resolve()), '--configLoader', 'native']
    proc = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=600)
    with (build_root / 'build.log').open('x', encoding='utf-8') as log:
        log.write(proc.stdout + proc.stderr)
    if proc.returncode:
        raise RuntimeError(f'{editor} production build failed ({proc.returncode}); log: {build_root / "build.log"}')
    dist = build_root / 'dist'
    if editor == 'docxodus':
        source = cwd / 'node_modules/docxodus/dist'
        shutil.copytree(source, dist / 'docxodus-dist', dirs_exist_ok=True)
        # Preserve /wasm/ fallback to dist as well as the .NET runtime subtree.
        shutil.copytree(source, dist / 'wasm', dirs_exist_ok=True)
        if (source / 'wasm').is_dir():
            shutil.copytree(source / 'wasm', dist / 'wasm', dirs_exist_ok=True)
    return {'host_build': 'production', 'tree_sha256': tree_hash(dist),
            'build_directory': str(dist), 'build_log': str(build_root / 'build.log'),
            'command': command, 'publishable': True, 'publication_block_reason': None}


def start_host(editor, target, legacy_start):
    run = ACTIVE.get()
    policy = host_policy(editor)
    if run is not None:
        run.hosts.setdefault(editor, policy)
    if editor in NONSTATIC:
        # Do not start commands that write into repos/ or harness/.
        with urllib.request.urlopen(target['url'], timeout=5) as response:
            if response.status != 200:
                raise RuntimeError('existing app service is not ready')
        return AttachedHost()
    if editor == 'wordcraft':
        root = (REPO / 'harness').resolve().parent / 'repos/wordcraft/dist/web'
        meta = {**policy, 'tree_sha256': tree_hash(root),
                'host_tree_sha256': tree_hash(Path(target['cwd']).resolve())}
        if run is not None:
            run.hosts[editor] = meta
        return legacy_start(editor, target)
    if run is None:
        raise RuntimeError('production host requires a BrowserRun context')
    meta = run.hosts.get(editor, {})
    if not meta.get('build_directory'):
        try:
            meta = build_host(editor, target, run.out_root)
        except Exception as exc:
            run.hosts[editor] = {'host_build': 'build_failed', 'publishable': False,
                                 'publication_block_reason': f'production build failed: {exc}'}
            raise
        run.hosts[editor] = meta
    fixture = target.get('fixture')
    if fixture is None and run.fixtures:
        fixture = next(iter(run.fixtures.values()))
    headers = {'Cross-Origin-Opener-Policy': 'same-origin', 'Cross-Origin-Embedder-Policy': 'require-corp'} if editor == 'apryse' else {}
    server = StaticHost(meta['build_directory'], port=urlsplit(target['url']).port,
                        corpus_route=target.get('corpus_route', '/corpus.docx'), fixture=fixture, headers=headers)
    target["_static_server"] = server
    return server


def select_fixture(target, fixture):
    """Switch the corpus route between document workloads, before navigation."""
    target['fixture'] = fixture
    server = target.get('_static_server')
    if server is not None:
        server.fixture = fixture
