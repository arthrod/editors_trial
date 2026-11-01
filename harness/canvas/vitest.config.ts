import { defineConfig } from 'vitest/config'
import { fileURLToPath } from 'node:url'

const CANVAS = '/Users/arthrod/temp/T/editors_trial/repos/canvas-editor'
const PLUGIN =
  '/Users/arthrod/temp/T/editors_trial/repos/canvas-editor-plugin/packages/docx'

export default defineConfig({
  // Vite's dependency cache can move. The config bundle cannot: Vite writes
  // that next to the nearest node_modules, and the seatbelt allows that one
  // directory. The bomb runner sets VITEST_CACHE_DIR inside the work dir.
  ...(process.env.VITEST_CACHE_DIR
    ? { cacheDir: process.env.VITEST_CACHE_DIR }
    : {}),
  resolve: {
    alias: [
      // most specific first (the plugin must win over the core package name)
      {
        find: '@hufe921/canvas-editor-plugin-docx',
        replacement: PLUGIN + '/src/docx/index.ts'
      },
      {
        find: '@hufe921/canvas-editor',
        replacement: CANVAS + '/src/editor/index.ts'
      },
      { find: /^@\//, replacement: CANVAS + '/src/' },
      // the harness has no node_modules of its own: point the bare specifiers
      // the setup file needs at the canvas-editor checkout's node_modules
      {
        find: 'vitest-canvas-mock',
        replacement: CANVAS + '/node_modules/vitest-canvas-mock/dist/index.js'
      },
      {
        find: 'vitest/config',
        replacement: CANVAS + '/node_modules/vitest/dist/config.js'
      }
    ]
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: [fileURLToPath(new URL('./setup.ts', import.meta.url))],
    include: ['**/*.test.ts'],
    css: false,
    pool: 'threads',
    testTimeout: 180000,
    hookTimeout: 180000
  }
})
