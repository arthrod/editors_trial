import { copyFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, type Plugin } from "vite";

const demoDir = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(demoDir, "../src");
const docx = path.join(repo, "packages/docx/src");
const core = path.join(repo, "packages/core/src");
const xml = path.join(repo, "packages/xml/src");
const dist = path.resolve(demoDir, "../dist");
const zlibShim = path.resolve(demoDir, "shims/node-zlib.ts");

function alias(find: RegExp, replacement: string) {
  return { find, replacement };
}

function demoAssets(): Plugin {
  return {
    name: "office-open-demo-assets",
    resolveId(id) {
      if (id === "node:zlib" || id === "zlib") return zlibShim;
    },
    generateBundle(_options, bundle) {
      const limit = 25 * 1024 * 1024;
      for (const [file, item] of Object.entries(bundle)) {
        const size = item.type === "chunk" ? Buffer.byteLength(item.code) : item.source.length;
        if (size > limit) {
          this.error(`${file} is ${size} bytes, over the 25 MiB limit`);
        }
      }
    },
    closeBundle() {
      copyFileSync("/tmp/demos/office-open.docx", path.join(dist, "document.docx"));
      copyFileSync(path.join(repo, "LICENSE"), path.join(dist, "LICENSE"));
      writeFileSync(
        path.join(dist, "SOURCE.txt"),
        [
          "office-open live demo for benchmarks.law",
          "Repository: https://github.com/DemoMacro/office-open",
          "Commit: 567addf",
          "License: MIT (see LICENSE)",
          "Demo host page and build configuration: https://github.com/arthrod/editors_trial/tree/main/demos/office-open",
          "",
        ].join("\n"),
      );
    },
  };
}

export default defineConfig({
  base: "./",
  plugins: [demoAssets()],
  build: {
    outDir: dist,
    emptyOutDir: true,
    minify: "esbuild",
    sourcemap: false,
    cssCodeSplit: false,
    modulePreload: false,
    target: "es2022",
    chunkSizeWarningLimit: 10000,
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
      },
    },
  },
  esbuild: {
    legalComments: "none",
  },
  resolve: {
    alias: [
      alias(/^node:zlib$/, zlibShim),
      alias(/^@office-open\/docx$/, path.join(docx, "index.ts")),
      alias(/^@office-open\/xml$/, path.join(xml, "index.ts")),
      alias(/^@office-open\/core$/, path.join(core, "index.ts")),
      alias(/^@office-open\/core\/(.+)$/, `${core}/$1/index.ts`),
      alias(/^@parts\/(.+)$/, `${docx}/parts/$1`),
      alias(/^@shared\/(.+)$/, `${docx}/shared/$1`),
      alias(/^@util\/(.+)$/, `${docx}/util/$1`),
      alias(/^@export\/(.+)$/, `${docx}/export/$1`),
    ],
  },
});
