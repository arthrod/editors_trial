// OnlyOffice (CryptPad build) round trip with no browser and no document
// server: docx -> x2t -> the editor's own binary (Editor.bin, "DOCY") -> x2t
// -> docx.
//
//   node fetch.mjs                       once: the pinned release archive
//   node roundtrip.mjs <in.docx> <out.docx>
//
// What this lane is. OnlyOffice never reads a .docx in its editor: x2t, its
// converter, turns the .docx into the editor's binary on open and turns the
// editor's binary back into a .docx on save. CryptPad compiles x2t to
// WebAssembly (cryptpad/onlyoffice-x2t-wasm) so both conversions run without a
// server. This lane runs those two conversions back to back, with x2t's own
// output as the input of the second, and nothing of ours in between.
//
// What it is not: the editor (sdkjs, cryptpad/onlyoffice-editor) is not in the
// loop, so the binary is not loaded into the editor's model and written out of
// it again (asc_nativeGetFile). That needs a browser.
//
// A conversion that does not return is stopped after X2T_TIMEOUT_S seconds
// (default 120) and reported as a failure of that step.
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Worker } from 'node:worker_threads';

const HERE = dirname(fileURLToPath(import.meta.url));
const DIR = join(HERE, 'vendor', 'x2t');
const pin = JSON.parse(readFileSync(join(HERE, 'pin.json'), 'utf8')).x2t;

const [input, output] = process.argv.slice(2);
if (!input || !output) {
  console.error('usage: node roundtrip.mjs <in.docx> <out.docx>');
  process.exit(2);
}
if (!existsSync(join(DIR, 'x2t.wasm'))) {
  console.error(`x2t is not unpacked in ${DIR}: run "node fetch.mjs" first`);
  process.exit(2);
}
const limit = Number(process.env.X2T_TIMEOUT_S || 120);
const bytesIn = new Uint8Array(readFileSync(input));
console.log(`[onlyoffice] x2t ${pin.tag} (${pin.repository})`);

const t0 = performance.now();
const worker = new Worker(join(HERE, 'x2t-worker.cjs'), { workerData: { dir: DIR, input: bytesIn }, stdout: false, stderr: false });
let step = 'starting x2t';
const fail = (message) => {
  console.log(`[onlyoffice] FAILED: ${message}`);
  worker.terminate().finally(() => process.exit(1));
};
const watchdog = setTimeout(
  () => fail(`x2t did not return from "${step}" within ${limit} s; its call into WebAssembly was still running and the harness stopped it`),
  limit * 1000,
);
worker.on('error', (e) => fail(`x2t threw: ${e.message}`));
worker.on('message', (msg) => {
  if (msg.type === 'ready') console.log(`PERF host_start_ms=${(performance.now() - t0).toFixed(6)}`);
  else if (msg.type === 'step') step = msg.step;
  else if (msg.type === 'imported') {
    console.log(`PERF model_ready_ms=${msg.ms.toFixed(6)}`);
    console.log(`[onlyoffice] docx -> bin: ${msg.binBytes} bytes, main1 returned ${msg.rc}, media ${JSON.stringify(msg.media)}`);
  } else if (msg.type === 'error') {
    clearTimeout(watchdog);
    fail(msg.message);
  } else if (msg.type === 'done') {
    clearTimeout(watchdog);
    console.log(`PERF save_ms=${msg.ms.toFixed(6)}`);
    const out = Buffer.from(msg.bytes);
    mkdirSync(dirname(resolve(output)), { recursive: true });
    writeFileSync(output, out);
    const same = Buffer.compare(Buffer.from(bytesIn), out) === 0;
    console.log(`[onlyoffice] bin -> docx: main1 returned ${msg.rc}; ${bytesIn.length} -> ${out.length} bytes${same ? '  IDENTICAL TO INPUT (pass-through)' : ''}`);
    worker.terminate().finally(() => process.exit(0));
  }
});
