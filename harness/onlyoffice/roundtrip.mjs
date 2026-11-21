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
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync, existsSync, rmSync } from 'node:fs';
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
// The files run are the pinned ones, checked here too: fetch.mjs may have run long ago.
for (const f of pin.files) {
  if (existsSync(join(DIR, f)) && createHash('sha256').update(readFileSync(join(DIR, f))).digest('hex') !== pin.sha256[f]) {
    console.error(`${f} in ${DIR} is not the pinned x2t ${pin.tag}: run "node fetch.mjs"`);
    process.exit(2);
  }
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
// A lane with no output says what happened (build/no_output.py): a converter that
// did not return is not an editor that refused. The record sits where the output
// would have been, and is removed when an output is written.
const record = join(dirname(resolve(output)), 'no_output.json');
// Output is flushed before the process ends: on a pipe, process.exit can cut the last lines.
const end = (code) => worker.terminate().finally(() => process.stdout.write('', () => process.exit(code)));
const fail = (message, outcome = 'error') => {
  mkdirSync(dirname(record), { recursive: true });
  // An output left by an earlier run is not this run's result.
  rmSync(output, { force: true });
  writeFileSync(record, `${JSON.stringify({
    outcome, step, limit_s: limit, message, tool: `x2t ${pin.tag}`, input: bytesIn.length,
  }, null, 1)}\n`);
  console.log(`[onlyoffice] FAILED: ${message}`);
  end(1);
};
const watchdog = setTimeout(
  () => fail(`x2t did not return from "${step}" within ${limit} s; its call into WebAssembly was still running and the harness stopped it`, 'did-not-return'),
  limit * 1000,
);
worker.on('error', (e) => fail(`x2t threw: ${e.message}`));
worker.on('message', (msg) => {
  if (msg.type === 'ready') console.log(`PERF host_start_ms=${(performance.now() - t0).toFixed(6)}`);
  else if (msg.type === 'step') step = msg.step;
  else if (msg.type === 'imported') {
    // For this lane "model ready" is x2t's docx -> binary conversion: the binary is the editor's
    // model on disk, and no editor loads it here (see "What it is not" above).
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
    rmSync(record, { force: true });
    const same = Buffer.compare(Buffer.from(bytesIn), out) === 0;
    console.log(`[onlyoffice] bin -> docx: main1 returned ${msg.rc}; ${bytesIn.length} -> ${out.length} bytes${same ? '  IDENTICAL TO INPUT (pass-through)' : ''}`);
    end(0);
  }
});
