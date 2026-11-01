import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
  root: __dirname,
  build: { outDir: 'dist', emptyOutDir: true, chunkSizeWarningLimit: 20000 },
})
