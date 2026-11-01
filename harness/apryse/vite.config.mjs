import { defineConfig } from 'vite';

// Serves the host page on 5210. /lib is WebViewer's own public/ folder
// (public/lib is a symlink into node_modules). The license key comes from the
// trial's .env: only variables prefixed APRYSE_ reach the page.
export default defineConfig({
  envDir: '../..',
  envPrefix: 'APRYSE_',
  // The hostile-package sandbox only lets a tool write inside its work
  // directory; it points the dependency cache there.
  cacheDir: process.env.APRYSE_VITE_CACHE || 'node_modules/.vite',
  // Cross-origin isolation lets WebViewer use WebAssembly threads, as Apryse's
  // deployment guide asks (docs.apryse.com/documentation/web/faq/wasm-threads).
  server: {
    port: 5210,
    strictPort: true,
    host: '127.0.0.1',
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },
});
