import { defineConfig } from 'vite';

export default defineConfig({
  optimizeDeps: {
    exclude: ['@superdoc/docx-engine'],
  },
  server: {
    host: '127.0.0.1',
    port: 5199,
    strictPort: true,
  },
});
