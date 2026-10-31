// eigenpal/docx-editor round trip: docx bytes -> editor model -> docx bytes
// Uses the repo's own store lane (readOoxmlPackage / writeOoxmlPackage) and the
// editor-api server runtime (createServer -> save) - i.e. the editor's own code path.
//
// usage: bun run eigenpal.ts <in.docx> <out.docx> [mode]
//   mode = store  (default) canonical package round trip
//   mode = editor editor-api object-model round trip
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const REPO = '/Users/arthrod/temp/T/editors_trial/repos/eigenpal-docx-editor';
const inPath = resolve(process.argv[2]);
const outPath = resolve(process.argv[3]);
const mode = process.argv[4] || 'store';

const bytes = new Uint8Array(readFileSync(inPath));

if (mode === 'editor') {
  const { createServer } = await import(`${REPO}/packages/editor-api/src/index.ts`);
  const server = await createServer(bytes);
  const out = await server.save();
  writeFileSync(outPath, out);
  console.log(`[eigenpal:editor] wrote ${out.byteLength} bytes`);
} else {
  const { readOoxmlPackage, writeOoxmlPackage } = await import(
    `${REPO}/packages/core/src/store/index.ts`
  );
  const first = readOoxmlPackage(bytes);
  if (!first.ok) throw new Error(`open failed: ${first.reason}`);
  const out = writeOoxmlPackage(first.package);
  writeFileSync(outPath, out);
  console.log(`[eigenpal:store] wrote ${out.byteLength} bytes`);
}
