// stella/folio round trip: docx bytes -> model -> docx bytes
// Mirrors the repo's own corpus invariant (scripts/lib/corpus-invariants/save-idempotence.ts):
//   parseDocx(buffer, { preloadFonts: false }) -> repackDocx(document)
//
// usage: bun run folio.ts <in.docx> <out.docx> [mode]
//   mode = model  (default) parse -> repack
//   mode = editor full editor model round trip (parseDocx -> toProseDoc -> fromProseDoc -> repack)
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const REPO = '/Users/arthrod/temp/T/editors_trial/repos/folio';
const inPath = resolve(process.argv[2]);
const outPath = resolve(process.argv[3]);
const mode = process.argv[4] || 'model';

const buffer = readFileSync(inPath);
const ab = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);

const { parseDocx } = await import(`${REPO}/packages/core/src/docx/parser.ts`);
const { repackDocx } = await import(`${REPO}/packages/core/src/docx/rezip.ts`);

if (mode === 'editor') {
  const { toProseDoc, fromProseDoc } = await import(`${REPO}/packages/core/src/prose/index.ts`);
  const doc = await parseDocx(ab, { preloadFonts: false });
  const prose = toProseDoc(doc);
  const back = fromProseDoc(prose);
  const out = await repackDocx(back, { updateModifiedDate: false });
  writeFileSync(outPath, Buffer.from(out));
  console.log(`[folio:editor] wrote ${out.byteLength} bytes`);
} else {
  const doc = await parseDocx(ab, { preloadFonts: false });
  const out = await repackDocx(doc, { updateModifiedDate: false });
  writeFileSync(outPath, Buffer.from(out));
  console.log(`[folio:model] wrote ${out.byteLength} bytes`);
}
