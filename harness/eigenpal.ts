// eigenpal/docx-editor round trip: docx bytes -> editor model -> docx bytes
// Uses the repo's own store lane (readOoxmlPackage / writeOoxmlPackage) and the
// editor-api server runtime (createServer -> save) - i.e. the editor's own code path.
//
// usage: bun run eigenpal.ts <in.docx> <out.docx> [mode]
//   mode = store  (default) canonical package round trip
//   mode = editor editor-api object-model round trip
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, '../repos/eigenpal-docx-editor');
const inPath = resolve(process.argv[2]);
const outPath = resolve(process.argv[3]);
const mode = process.argv[4] || 'store';

const bytes = new Uint8Array(readFileSync(inPath));

if (mode === 'editor') {
  // DOM-free byte runtime. DocxEditor.createServer is not the browser editor,
  // and index.ts does not export a bare createServer.
  const { DocxEditor } = await import(`${REPO}/packages/editor-api/src/index.ts`);
  const t0 = performance.now();
  const server = await DocxEditor.createServer(bytes);
  const t1 = performance.now();
  console.log(`PERF model_ready_ms=${(t1 - t0).toFixed(6)}`);
  const ts0 = performance.now();
  const out = await server.save();
  const ts1 = performance.now();
  console.log(`PERF save_ms=${(ts1 - ts0).toFixed(6)}`);
  writeFileSync(outPath, out);
  console.log(`[eigenpal:editor] wrote ${out.byteLength} bytes`);
} else {
  const { readOoxmlPackage, writeOoxmlPackage } = await import(
    `${REPO}/packages/core/src/store/index.ts`
  );
  const t0 = performance.now();
  const first = readOoxmlPackage(bytes);
  if (!first.ok) throw new Error(`open failed: ${first.reason}`);
  const t1 = performance.now();
  console.log(`PERF model_ready_ms=${(t1 - t0).toFixed(6)}`);
  const ts0 = performance.now();
  const out = writeOoxmlPackage(first.package);
  const ts1 = performance.now();
  console.log(`PERF save_ms=${(ts1 - ts0).toFixed(6)}`);
  writeFileSync(outPath, out);
  console.log(`[eigenpal:store] wrote ${out.byteLength} bytes`);
}
