/**
 * Host config for the GenOffice rendering study.
 *
 * It serves the REAL docs renderer from the read-only repo
 * (repos/genoffice/apps/docs/src/renderer) on port 5201.  Two things differ
 * from the repo's own apps/docs/vite.renderer.config.ts:
 *
 *   1. `cacheDir` points outside the repo, so the dev server never writes
 *      anything under repos/.
 *   2. A plugin injects the browser-side `window.desktop` stand-in
 *      (desktop-stub.js).  In the shipped app that bridge comes from the
 *      Electron preload; the renderer is otherwise plain web code, so with the
 *      stand-in it boots and opens a document over HTTP unchanged.
 */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = process.env.GENOFFICE_REPO || '/Users/arthrod/temp/T/editors_trial/repos/genoffice'
const STUB = path.join(HERE, 'desktop-stub.js')

function desktopStub() {
  return {
    name: 'genoffice-desktop-stub',
    configureServer(server) {
      server.middlewares.use('/desktop-stub.js', (_req, res) => {
        res.setHeader('Content-Type', 'application/javascript; charset=utf-8')
        res.setHeader('Cache-Control', 'no-store')
        res.end(fs.readFileSync(STUB, 'utf8'))
      })
    },
    transformIndexHtml() {
      return [
        {
          tag: 'script',
          attrs: { src: '/desktop-stub.js' },
          injectTo: 'head-prepend',
        },
      ]
    },
  }
}

export default defineConfig({
  root: path.join(REPO, 'apps/docs/src/renderer'),
  cacheDir: path.join(HERE, '.vite-cache'),
  plugins: [desktopStub(), react()],
  server: {
    port: 5201,
    strictPort: true,
    fs: { allow: [REPO, HERE] },
  },
})
