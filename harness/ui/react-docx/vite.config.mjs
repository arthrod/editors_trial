import { defineConfig } from 'vite';

// Serves the host page on 5211. The package's README asks for this exclusion in
// Vite development, so that Vite resolves the import worker and the WebAssembly
// parser next to the package's own files.
export default defineConfig({
  optimizeDeps: { exclude: ['@extend-ai/react-docx/vanilla'] },
  server: { port: 5211, strictPort: true, host: '127.0.0.1' },
});
