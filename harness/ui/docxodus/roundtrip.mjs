/**
 * Docxodus round trip: load the corpus into Docxodus's own package reader
 * and write it back out, with no edits.
 *
 * This is the product's own code path — `docxodus/core` is the published
 * WebAssembly build of the .NET OOXML engine, and `DocxSession.save()`
 * re-serialises the package through the OpenXML SDK. Nothing in `repos/` is
 * touched and no transformation is applied here.
 *
 * usage: node roundtrip.mjs <input.docx> <output.docx>
 */
import fs from 'node:fs';
import { initialize, openDocxSession } from 'docxodus/core';

const [, , inPath, outPath] = process.argv;
if (!inPath || !outPath) {
  console.error('usage: node roundtrip.mjs <input.docx> <output.docx>');
  process.exit(2);
}

const bytes = new Uint8Array(fs.readFileSync(inPath));
await initialize();

const t0 = performance.now();
const session = openDocxSession(bytes);
const t1 = performance.now();
console.log(`PERF model_ready_ms=${(t1 - t0).toFixed(6)}`);
let saved;
try {
  saved = session.save();
} finally {
  session.close();
}

fs.mkdirSync(outPath.replace(/\/[^/]+$/, ''), { recursive: true });
fs.writeFileSync(outPath, saved);
console.log('docxodus round trip: %d -> %d bytes', bytes.length, saved.length);
