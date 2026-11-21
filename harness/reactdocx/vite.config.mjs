import { defineConfig } from 'vite';

// Serves the host page on 5231.
export default defineConfig({
  // The hostile-package sandbox only lets a tool write inside its work
  // directory; it points the dependency cache there.
  cacheDir: process.env.REACTDOCX_VITE_CACHE || 'node_modules/.vite',
  // The package's README: "In Vite development, exclude the vanilla entry from
  // dependency optimization so Vite can resolve the import worker asset."
  optimizeDeps: { exclude: ['@extend-ai/react-docx/vanilla', '@extend-ai/react-docx'] },
  server: { port: 5231, strictPort: true, host: '127.0.0.1' },
});
