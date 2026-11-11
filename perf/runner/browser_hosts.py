"""Production host policy, build wrappers and the shared HTTP server seam.

Each Vite host has an explicit adapter; a failed build is never a dev server.

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
    'docsplus': ('app_server', 'Next and REST proxy require an existing app service; next build/start descoped by #128'),
    'fidus': ('app_server', 'Django session/import API requires an existing app service'),
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
                # Match docxodus-raw-dist's alternate package URL, without exposing
                # the checkout's node_modules or permitting traversal outside dist.
                pathname = unquote(urlsplit(path).path)
                marker = '/docxodus/dist/'
                if marker in pathname:
                    path = '/docxodus-dist/' + pathname.split(marker, 1)[1]
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


# Explicit adapter inventory. Wrapper-only adapters still own an attested build.
ADAPTERS = {
    'plate': 'plate_aliases', 'docxodus': 'docxodus_assets',
    'genoffice': 'genoffice_renderer', 'apryse': 'apryse_licensed',
    'superdoc': 'wrapper', 'canvas': 'wrapper', 'docen': 'wrapper',
    'eigenpal': 'eigenpal_config', 'folio': 'wrapper',
}


class HostBuildError(RuntimeError):
    def __init__(self, metadata):
        self.metadata = metadata
        super().__init__(f"host_build: {metadata['reason']}; log: {metadata['build_log']}")


def build_host(editor, target, out_root, *, repos_root=None):
    cwd = Path(target['cwd']).resolve()
    repos = Path(repos_root or target.get('repos_root') or
                 (REPO / 'harness').resolve().parent / 'repos').resolve()
    build_root = Path(out_root).resolve() / 'builds' / editor / uuid.uuid4().hex
    for forbidden in ((REPO / 'harness').resolve(), REPO / 'repos', repos,
                      (REPO / 'harness').resolve().parent / 'repos'):
        if build_root.is_relative_to(forbidden.resolve()):
            raise ValueError('build output must be outside harness/ and repos/')
    build_root.mkdir(parents=True)
    log_path = build_root / 'build.log'
    key = os.environ.get('APRYSE_API_KEY', '').strip() if editor == 'apryse' else ''
    metadata = {'host_build': 'build_failed', 'outcome': 'failed',
                'failure_reason': 'host_build', 'publishable': False,
                'build_log': str(log_path), 'adapter': ADAPTERS.get(editor, 'wrapper')}
    if editor == 'apryse':
        metadata['key_present'] = bool(key)
    def redact(text):
        return text.replace(key, '[REDACTED]') if key else text
    build_log = ''
    try:
        if editor == 'apryse' and not key:
            raise RuntimeError('apryse_key_absent')
        config_name = target.get('config')
        command = target.get('command', [])
        if not config_name and '--config' in command:
            config_name = command[command.index('--config') + 1]
        configs = [cwd / config_name] if config_name else [cwd / ('vite.config.' + ext) for ext in ('ts', 'mjs', 'js', 'mts')]
        config = next((p for p in configs if p.is_file()), None)
        if config is None:
            raise FileNotFoundError(f'no Vite config for {editor}')
        vite = vite_paths(cwd)
        env = {**os.environ, **target.get('env', {}),
               'B1_HOST_ROOT': str(cwd), 'B1_HOST_CONFIG': str(config),
               'B1_BUILD_ROOT': str(build_root), 'B1_VITE_MODULE': str(vite / 'dist/node/index.js'),
               'B1_HOST_ID': editor, 'B1_REPOS_ROOT': str(repos)}
        if editor == 'genoffice':
            env['GENOFFICE_REPO'] = str(repos / 'genoffice')
        if editor == 'apryse':
            env['APRYSE_API_KEY'] = key
        command = ['node', str(vite / 'bin/vite.js'), 'build', '--config', str(WRAPPER.resolve()), '--configLoader', 'native']
        proc = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=600)
        build_log = redact(proc.stdout + proc.stderr)
        if proc.returncode:
            raise RuntimeError(f'{editor} production build exited {proc.returncode}')
        dist = build_root / 'dist'
        if editor == 'docxodus':
            source = cwd / 'node_modules/docxodus/dist'
            shutil.copytree(source, dist / 'docxodus-dist', dirs_exist_ok=True)
            shutil.copytree(source, dist / 'wasm', dirs_exist_ok=True)
            if (source / 'wasm').is_dir():
                shutil.copytree(source / 'wasm', dist / 'wasm', dirs_exist_ok=True)
        if editor == 'genoffice':
            shutil.copyfile(cwd / 'desktop-stub.js', dist / 'desktop-stub.js')
        return {**metadata, 'host_build': 'production', 'outcome': 'ok', 'failure_reason': None,
                'tree_sha256': tree_hash(dist), 'build_directory': str(dist),
                'command': command, 'publishable': True, 'publication_block_reason': None}
    except Exception as exc:
        reason = redact(str(exc))
        # Accumulate before the single exclusive write, retaining timeout output.
        if isinstance(exc, subprocess.TimeoutExpired):
            for output in (exc.stdout, exc.stderr):
                if output:
                    build_log += redact(output.decode(errors='replace') if isinstance(output, bytes) else output)
        build_log += '\n' + reason + '\n'
        metadata.update(reason=reason, publication_block_reason='production build failed: ' + reason)
        raise HostBuildError(metadata) from exc
    finally:
        with log_path.open('x', encoding='utf-8') as log:
            log.write(build_log)


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
        repos = Path(target.get('repos_root') or (REPO / 'harness').resolve().parent / 'repos')
        root = repos / 'wordcraft/dist/web'
        meta = {**policy, 'tree_sha256': tree_hash(root),
                'host_tree_sha256': tree_hash(Path(target['cwd']).resolve())}
        if run is not None:
            run.hosts[editor] = meta
        target = {**target, 'env': {**target.get('env', {}), 'WC_DIST': str(root.resolve())}}
        return legacy_start(editor, target)
    if run is None:
        raise RuntimeError('production host requires a BrowserRun context')
    meta = run.hosts.get(editor, {})
    if not meta.get('build_directory'):
        try:
            meta = build_host(editor, target, run.out_root)
        except Exception as exc:
            run.hosts[editor] = exc.metadata if isinstance(exc, HostBuildError) else {
                'host_build': 'build_failed', 'outcome': 'failed', 'failure_reason': 'host_build',
                'publishable': False, 'publication_block_reason': f'production build failed: {exc}'}
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
    if fixture is not None:
        # Legacy-started node servers (wordcraft-host, officeopen) read
        # CORPUS_DOCX once at spawn; target['fixture'] only reaches StaticHost.
        target.setdefault('env', {})['CORPUS_DOCX'] = str(fixture)
    server = target.get('_static_server')
    if server is not None:
        server.fixture = fixture
