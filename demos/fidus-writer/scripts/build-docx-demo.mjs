#!/usr/bin/env node
// Build demo/docx as a standalone static page (the benchmarks.law live demo), the way
// scripts/deploy-pages.sh builds the other demos: esbuild bundle, local CSS, no CDN.
// usage: node scripts/build-docx-demo.mjs <out-dir> <document.docx>
import {build} from "esbuild"
import {copyFileSync, cpSync, mkdirSync, rmSync} from "node:fs"
import {join, resolve} from "node:path"

const ROOT = resolve(import.meta.dirname, "..")
const [out, docx] = process.argv.slice(2).map(p => resolve(p))
if (!out || !docx) throw new Error("usage: build-docx-demo.mjs <out-dir> <document.docx>")

rmSync(out, {recursive: true, force: true})
mkdirSync(out, {recursive: true})
mkdirSync(join(out, "css"), {recursive: true})

await build({
    entryPoints: [join(ROOT, "demo/docx/index.ts")],
    bundle: true,
    format: "esm",
    splitting: true,
    outdir: out,  // next to index.html: citeproc-plus fetches its .gz styles relative to the page
    minify: true,
    target: ["es2020"],
    external: ["node:*"],  // citeproc-plus imports these only when it runs under Node
    loader: {".gz": "file", ".woff": "file", ".woff2": "file", ".ttf": "file", ".svg": "file", ".png": "file"},
    logLevel: "warning"
})

copyFileSync(join(ROOT, "demo/docx/index.html"), join(out, "index.html"))
copyFileSync(join(ROOT, "demo/docx/docx.css"), join(out, "docx.css"))
cpSync(join(ROOT, "css"), join(out, "css/document"), {recursive: true})
copyFileSync(docx, join(out, "document.docx"))
console.log(`built ${out}`)
