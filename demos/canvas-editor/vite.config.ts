import { defineConfig } from 'vite'
import { fileURLToPath } from 'node:url'

const canvasRoot = fileURLToPath(new URL('./src', import.meta.url))
const editorEntry = fileURLToPath(
  new URL('./src/src/editor/index.ts', import.meta.url)
)
const pluginEntry = fileURLToPath(
  new URL('./plugin/packages/docx/src/docx/index.ts', import.meta.url)
)

export default defineConfig({
  base: './',
  publicDir: 'public',
  resolve: {
    alias: [
      {
        find: /^@hufe921\/canvas-editor-plugin-docx$/,
        replacement: pluginEntry
      },
      {
        find: /^@hufe921\/canvas-editor$/,
        replacement: editorEntry
      },
      {
        find: /^@\//,
        replacement: canvasRoot + '/src/'
      }
    ]
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    cssCodeSplit: true,
    chunkSizeWarningLimit: 8000,
    assetsInlineLimit: 4096
  }
})
