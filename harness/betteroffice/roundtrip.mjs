// BetterOffice DOCX round trip through the published @betteroffice/docx, with
// no browser: docx bytes -> its Rust/WebAssembly engines -> docx bytes.
//
//   node roundtrip.mjs <in.docx> <out.docx> [mode]
//     mode = model  (default) the package's documented parse-and-save:
//                     parseDocx(bytes) -> repackDocxWithWarnings(document)
//                   (README, "Usage": "Parse a DOCX and save it while
//                   preserving untouched package parts")
//     mode = editor the editing session its React editor saves from:
//                     createYrsSession() -> session.seedFromDocx(bytes)
//                     -> saveYrsDocx(session)
//                   (@betteroffice/docx/yrs; @betteroffice/docx-react's
//                   DocxEditor ref.save() goes through the same session)
//
// The package loads its own .wasm assets from dist/generated/ ("no manual
// initialization is required"). It is pinned exactly in package.json, so the
// measured version is in this repository. Nothing is edited between the two
// calls. The driver reports whether the bytes out equal the bytes in, so a
// pass-through cannot hide.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const [input, output, mode = 'model'] = process.argv.slice(2);
if (!input || !output || !['model', 'editor'].includes(mode)) {
  console.error('usage: node roundtrip.mjs <in.docx> <out.docx> [model|editor]');
  process.exit(2);
}
const bytes = new Uint8Array(readFileSync(input));
let out;

if (mode === 'editor') {
  const { createYrsSession, saveYrsDocx } = await import('@betteroffice/docx/yrs');
  const t0 = performance.now();
  const session = await createYrsSession();
  session.seedFromDocx(bytes);
  console.log(`PERF model_ready_ms=${(performance.now() - t0).toFixed(6)}`);
  try {
    const ts = performance.now();
    const saved = await saveYrsDocx(session);
    console.log(`PERF save_ms=${(performance.now() - ts).toFixed(6)}`);
    out = saved.bytes;
    console.log(`[betteroffice] editor session: ${saved.paragraphs.length} anchored paragraph(s), conflicts ${JSON.stringify(saved.conflicts ?? [])}`);
  } finally {
    session.destroy();
  }
} else {
  const { VERSION, parseDocx, repackDocxWithWarnings } = await import('@betteroffice/docx');
  console.log(`[betteroffice] @betteroffice/docx ${VERSION}`);
  const t0 = performance.now();
  const document = await parseDocx(bytes);
  console.log(`PERF model_ready_ms=${(performance.now() - t0).toFixed(6)}`);
  const ts = performance.now();
  const saved = await repackDocxWithWarnings(document);
  console.log(`PERF save_ms=${(performance.now() - ts).toFixed(6)}`);
  out = new Uint8Array(saved.buffer);
  console.log(`[betteroffice] save warnings: ${JSON.stringify(saved.warnings)}`);
}

mkdirSync(dirname(resolve(output)), { recursive: true });
writeFileSync(output, out);
const same = Buffer.compare(Buffer.from(bytes), Buffer.from(out)) === 0;
console.log(`[betteroffice] ${mode}: ${bytes.length} -> ${out.length} bytes${same ? '  IDENTICAL TO INPUT (pass-through)' : ''}`);
// The engines keep handles open; the round trip is done.
process.exit(0);
