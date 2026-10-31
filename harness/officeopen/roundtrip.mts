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
import { resolve } from 'node:path';

const REPO = '/Users/arthrod/temp/T/editors_trial/repos/office-open';
const inPath = resolve(process.argv[2]);
const outPath = resolve(process.argv[3]);

const { parseDocument, generateDocument } = await import(`${REPO}/packages/docx/src/index.ts`);

const bytes = new Uint8Array(readFileSync(inPath));
const parsed = await parseDocument(bytes);
const out = await generateDocument(parsed, { type: 'uint8array' });
writeFileSync(outPath, out);
console.log(`[officeopen] wrote ${out.byteLength} bytes (sections=${parsed.sections?.length})`);
