// docen (@docen/docx) docx -> docx round trip.
//
// Uses the library's own public API, imported from SOURCE (no dist build):
//   packages/docx/src/converters/docx.ts:1337  parseDOCX(bytes)  -> Tiptap JSONContent
//   packages/docx/src/converters/docx.ts:1415  generateDOCX(json) -> uint8array
//
// parseDOCX delegates to @office-open/docx parseDocument; generateDOCX compiles
// the Tiptap JSON back to DocumentOptions and calls @office-open/docx
// generateDocument. No DOM required for the docx<->docx lane.
//
// usage: tsx harness/docen/roundtrip.mts <in.docx> <out.docx>
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, '../../repos/docen');
const inPath = resolve(process.argv[2]);
const outPath = resolve(process.argv[3]);

const { parseDOCX, generateDOCX } = await import(
  `${REPO}/packages/docx/src/converters/docx.ts`
);

const bytes = new Uint8Array(readFileSync(inPath));
const t0 = performance.now();
const json = await parseDOCX(bytes);
const t1 = performance.now();
console.log(`PERF model_ready_ms=${(t1 - t0).toFixed(6)}`);
const ts0 = performance.now();
const out = await generateDOCX(json, { packer: { type: 'uint8array' } });
const ts1 = performance.now();
console.log(`PERF save_ms=${(ts1 - ts0).toFixed(6)}`);
writeFileSync(outPath, out);
console.log(`[docen] wrote ${out.byteLength} bytes (nodes=${json.content?.length})`);
