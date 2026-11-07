// office-open (@office-open/docx) docx -> docx round trip.
//
// Uses the library's own public API, imported from SOURCE (no dist build):
//   packages/docx/src/parse.ts:501    parseDocument(data)      -> DocumentOptions
//   packages/docx/src/generate.ts:71  generateDocument(opts)   -> uint8array
//
// usage: tsx harness/officeopen/roundtrip.mts <in.docx> <out.docx>
//   (run from the office-open repo root so tsconfig paths + workspace
//    node_modules resolve; --tsconfig points at the repo tsconfig explicitly)
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, '../../repos/office-open');
const inPath = resolve(process.argv[2]);
const outPath = resolve(process.argv[3]);

const { parseDocument, generateDocument } = await import(`${REPO}/packages/docx/src/index.ts`);

const bytes = new Uint8Array(readFileSync(inPath));
const t0 = performance.now();
const parsed = await parseDocument(bytes);
const t1 = performance.now();
console.log(`PERF model_ready_ms=${(t1 - t0).toFixed(6)}`);
const ts0 = performance.now();
const out = await generateDocument(parsed, { type: 'uint8array' });
const ts1 = performance.now();
console.log(`PERF save_ms=${(ts1 - ts0).toFixed(6)}`);
writeFileSync(outPath, out);
console.log(`[officeopen] wrote ${out.byteLength} bytes (sections=${parsed.sections?.length})`);
