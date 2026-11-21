// The pipeline react-docx documents for use below its viewer, with no browser
// (README, "Lower-level APIs"; "In Node ... the binary is read from
// node_modules on disk"):
//
//   const pkg = await parseDocx(arrayBuffer);
//   const model = buildDocModel(pkg);
//   const output = serializeDocx(model, pkg);
//
//   node headless.mjs <in.docx> <out.docx>
//
// This is NOT the trial's lane for react-docx; roundtrip.mjs is. It is kept
// because it is the evidence for why the lane needs a browser: on the trial's
// corpus the serialiser refuses ("Inline image paint cannot be preserved from
// source; a current full-viewport PNG is required before export"). The editor
// itself rasterises that picture on a canvas before it serialises
// (prepareImagePaintBoundsForExport in dist/index.js, called by getDocxBytes),
// and the package does not export that step.
// Exit code: 0 wrote the file, 1 the package refused.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { buildDocModel, parseDocx, serializeDocx } from '@extend-ai/react-docx';

const [input, output] = process.argv.slice(2);
if (!input || !output) {
  console.error('usage: node headless.mjs <in.docx> <out.docx>');
  process.exit(2);
}
const b = readFileSync(input);
try {
  const t0 = performance.now();
  const pkg = await parseDocx(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
  const model = await buildDocModel(pkg);
  console.log(`PERF model_ready_ms=${(performance.now() - t0).toFixed(6)}`);
  const ts = performance.now();
  const out = new Uint8Array(await serializeDocx(model, pkg));
  console.log(`PERF save_ms=${(performance.now() - ts).toFixed(6)}`);
  mkdirSync(dirname(resolve(output)), { recursive: true });
  writeFileSync(output, out);
  console.log(`react-docx headless: ${b.length} -> ${out.length} bytes`);
} catch (e) {
  console.log(`react-docx headless FAILED: ${e instanceof Error ? e.message : String(e)}`);
  process.exit(1);
}
