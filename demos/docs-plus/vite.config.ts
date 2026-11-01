import { defineConfig, type Plugin } from 'vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
/** The demo app's own directory (its node_modules hold the single Tiptap copy). */
const appDir = here
/** The copied docs.plus checkout (commit a9b0c69). Read-only for the build. */
const repo = path.resolve(here, '..', 'src')
const hocuspocusSrc = path.join(repo, 'apps', 'hocuspocus.server', 'src')
const libDir = path.join(hocuspocusSrc, 'lib')

const extensionDist = (name: string) =>
  path.join(repo, 'extensions', name, 'dist', 'index.js')

/**
 * The docs.plus conversion domain is server code. Three of its leaf imports are
 * Node-only (pino, prom-client, node:crypto); they are replaced by browser
 * equivalents that keep the same call surface. Everything else — mammoth, the
 * Tiptap schemas, the linkedom-based HTML round trip, @turbodocx/html-to-docx —
 * is the product's own code, used unchanged.
 */
const serverLibShims: Record<string, string> = {
  logger: path.join(here, 'src', 'shims', 'server-logger.ts'),
  metrics: path.join(here, 'src', 'shims', 'server-metrics.ts'),
  mediaSession: path.join(here, 'src', 'shims', 'server-media-session.ts')
}

function serverLibShimPlugin(): Plugin {
  return {
    name: 'docsplus:server-lib-browser-shims',
    enforce: 'pre',
    resolveId(source, importer) {
      if (!importer || !source.startsWith('.')) return null
      const resolved = path.resolve(path.dirname(importer), source)
      if (path.dirname(resolved) !== libDir) return null
      return serverLibShims[path.basename(resolved)] ?? null
    }
  }
}

/**
 * One copy of Tiptap/ProseMirror for the whole bundle.
 *
 * The product's own extension bundles live in the checkout and import
 * `@tiptap/core` / `@tiptap/pm/*` from the checkout's node_modules. Two copies
 * of ProseMirror in one page break `instanceof DecorationSet`, which
 * prosemirror-view uses to merge plugin decorations — the editor would crash
 * on the first render. Everything therefore resolves to the demo app's copy.
 */
const singleInstancePackages = [
  /^@tiptap\//,
  /^prosemirror-/,
  /^@floating-ui\/dom$/,
  /^linkifyjs$/
]

function singleInstancePlugin(): Plugin {
  return {
    name: 'docsplus:single-prosemirror-instance',
    enforce: 'pre',
    resolveId(source, importer) {
      if (!singleInstancePackages.some((pattern) => pattern.test(source))) return null
      if (importer && importer.startsWith(appDir + path.sep)) return null
      return this.resolve(source, path.join(appDir, '__resolve__.js'), { skipSelf: true })
    }
  }
}

export default defineConfig({
  // Every asset URL stays relative, so dist/ works under any mount point.
  base: './',
  plugins: [serverLibShimPlugin(), singleInstancePlugin()],
  resolve: {
    alias: [
      // The docs.plus editor extensions, straight from the checkout's build output.
      // Their published stylesheets: the media loading shell is hidden by CSS once an image loads.
      {
        find: /^@docs\.plus\/(extension-[a-z-]+)\/styles\.css$/,
        replacement: path.join(repo, 'extensions', '$1', 'dist', 'styles.css')
      },
      { find: /^@docs\.plus\/extension-hyperlink$/, replacement: extensionDist('extension-hyperlink') },
      {
        find: /^@docs\.plus\/extension-hypermultimedia$/,
        replacement: extensionDist('extension-hypermultimedia')
      },
      { find: /^@docs\.plus\/extension-indent$/, replacement: extensionDist('extension-indent') },
      { find: /^@docs\.plus\/extension-inline-code$/, replacement: extensionDist('extension-inline-code') },
      { find: /^@docs\.plus\/extension-mermaid$/, replacement: extensionDist('extension-mermaid') },
      { find: /^@docs\.plus\/extension-placeholder$/, replacement: extensionDist('extension-placeholder') },
      // Browser platform shims (documented in REPORT.md).
      { find: /^mammoth$/, replacement: path.join(here, 'src', 'shims', 'mammoth.ts') },
      { find: /^linkedom$/, replacement: path.join(here, 'src', 'shims', 'linkedom.ts') },
      { find: /^node:zlib$/, replacement: path.join(here, 'src', 'shims', 'zlib.ts') },
      { find: /^pele\/lazy$/, replacement: path.join(here, 'src', 'shims', 'pele-lazy.ts') }
    ]
  },
  define: {
    // The server code reads process.env.NODE_ENV at module scope.
    'process.env.NODE_ENV': JSON.stringify('production')
  },
  build: {
    outDir: path.resolve(here, '..', 'dist'),
    emptyOutDir: true,
    target: 'es2022',
    sourcemap: false,
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 8192
  }
})
