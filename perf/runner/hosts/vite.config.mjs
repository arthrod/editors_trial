// Load configs in memory: never write bundled configs into protected hosts.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

export default async function wrapper(environment) {
  const { loadConfigFromFile } = await import(pathToFileURL(process.env.B1_VITE_MODULE).href);
  const host = process.env.B1_HOST_ROOT;
  const output = process.env.B1_BUILD_ROOT;
  const repos = process.env.B1_REPOS_ROOT;
  const id = process.env.B1_HOST_ID;
  // Eigenpal's config relies on the __dirname supplied by Vite's bundler.
  // Supply its config directory while loading in memory, avoiding .vite-temp
  // writes in the checkout. Its imported config helpers use import.meta.url.
  const previousDirname = Object.getOwnPropertyDescriptor(globalThis, '__dirname');
  let loaded;
  try {
    if (id === 'eigenpal') globalThis.__dirname = path.dirname(process.env.B1_HOST_CONFIG);
    loaded = await loadConfigFromFile(environment, process.env.B1_HOST_CONFIG, host, undefined, undefined, 'runner');
  } finally {
    if (id === 'eigenpal') {
      if (previousDirname) Object.defineProperty(globalThis, '__dirname', previousDirname);
      else delete globalThis.__dirname;
    }
  }
  if (!loaded) throw new Error('Host config did not load');
  const config = loaded.config;
  let root = id === 'genoffice' && config.root ? path.resolve(host, config.root) : host;
  const build = { ...config.build, outDir: path.join(output, 'dist'), emptyOutDir: true };
  const resolve = { ...config.resolve };
  const plugins = [...(config.plugins || [])];
  if (id === 'plate') {
    // Keep the host's exact-match regexes and subpath mappings, relocate sources.
    resolve.alias = config.resolve.alias.map(alias => {
      const marker = '/repos/plate/';
      const offset = alias.replacement.indexOf(marker);
      return offset < 0 ? alias : { ...alias,
        replacement: path.join(repos, 'plate', alias.replacement.slice(offset + marker.length)) };
    });
  }
  if (id === 'docxodus') {
    // This module fetches import.meta.url and verifies its admitted bytes.
    // Bundling it changes both the URL and the bytes, invalidating attestation.
    plugins.unshift({ name: 'b1-docxodus-materializer', enforce: 'pre', resolveId(source) {
      if (source === 'docxodus/export-browser') {
        return { id: '/docxodus-dist/export-browser.bundle.js', external: true };
      }
    } });
  }
  if (id === 'genoffice' && !fs.existsSync(path.join(root, 'index.html'))) {
    const renderer = root;
    root = path.join(output, 'entry');
    fs.mkdirSync(root, { recursive: true });
    fs.writeFileSync(path.join(root, 'index.html'),
      '<!doctype html><html><head><meta charset="utf-8"></head><body><div id="root"></div><script type="module" src="/__b1_renderer_main__"></script></body></html>');
    plugins.push({ name: 'b1-renderer-entry', resolveId(source) {
      if (source === '/__b1_renderer_main__') return path.join(renderer, 'main.tsx');
    } });
  }
  if (id === 'apryse') {
    build.rollupOptions = { ...build.rollupOptions, input: path.join(root, 'perf.html') };
  }
  // Never load a host/workspace .env. Apryse gets its key only from process env.
  return { ...config, root, resolve, plugins, envDir: output,
    cacheDir: path.join(output, 'cache'), build };
}
