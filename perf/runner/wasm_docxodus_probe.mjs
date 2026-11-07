/**
 * Docxodus C24 WASM boundary probe — product initialize() and bridge calls, not RNG.
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '../..');

const opt = { iterations: 3 };
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (!a.startsWith('--')) continue;
  const key = a.slice(2);
  const next = process.argv[i + 1];
  if (next && !next.startsWith('--')) {
    opt[key] = next;
    i++;
  } else opt[key] = true;
}

const wasmRel =
  'harness/ui/docxodus/node_modules/docxodus/dist/wasm/_framework/dotnet.native.wasm';
const wasmPath = opt.wasm ? path.resolve(opt.wasm) : path.join(repo, wasmRel);
const wasmBaseDir = path.dirname(path.dirname(wasmPath));

function wasmMeta() {
  if (!fs.existsSync(wasmPath)) {
    return { error: 'missing wasm', wasmPath };
  }
  const bytes = fs.readFileSync(wasmPath);
  return {
    wasm_artifact: wasmPath,
    wasm_byte_size: bytes.length,
    wasm_sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
    wasm_base: wasmBaseDir,
    engine: 'node',
  };
}

const mode = opt.mode || 'warm';

if (mode === 'cold_init') {
  const meta = wasmMeta();
  if (meta.error) {
    console.error(JSON.stringify(meta));
    process.exit(2);
  }
  const coreUrl = pathToFileURL(
    path.join(repo, 'harness/ui/docxodus/node_modules/docxodus/dist/core.js'),
  ).href;
  const { initialize } = await import(coreUrl);
  const baseUrl = pathToFileURL(meta.wasm_base.endsWith('/') ? meta.wasm_base : `${meta.wasm_base}/`)
    .href;
  const t0 = performance.now();
  try {
    await initialize(baseUrl);
  } catch (err) {
    console.error(JSON.stringify({ error: String(err), ...meta }));
    process.exit(1);
  }
  const ms = performance.now() - t0;
  process.stdout.write(
    JSON.stringify({
      ...meta,
      operation: 'compile_and_instantiate',
      samples_ms: [ms],
    }),
  );
  process.exit(0);
}

const meta = wasmMeta();
if (meta.error) {
  console.error(JSON.stringify(meta));
  process.exit(2);
}

const n = Math.max(3, parseInt(String(opt.iterations), 10) || 3);
const coreUrl = pathToFileURL(
  path.join(repo, 'harness/ui/docxodus/node_modules/docxodus/dist/core.js'),
).href;
const { initialize, getVersion, getWasmExports } = await import(coreUrl);
const baseUrl = pathToFileURL(meta.wasm_base.endsWith('/') ? meta.wasm_base : `${meta.wasm_base}/`).href;
await initialize(baseUrl);
const exports = getWasmExports();
const samples = {};

samples.empty_call = [];
for (let i = 0; i < n; i++) {
  const t0 = performance.now();
  getVersion();
  samples.empty_call.push(performance.now() - t0);
}

const tiny = new Uint8Array([0x50, 0x4b, 0x05, 0x06]);
samples.typed_array_transfer = [];
for (let i = 0; i < n; i++) {
  const t0 = performance.now();
  exports.DocumentConverter.GetVersion();
  const slice = tiny.slice(0);
  slice.byteLength;
  samples.typed_array_transfer.push(performance.now() - t0);
}

samples.string_conversion = [];
const probeStr = 'docxodus-c24-utf8-probe-αβ';
for (let i = 0; i < n; i++) {
  const t0 = performance.now();
  const encoded = new TextEncoder().encode(probeStr);
  new TextDecoder().decode(encoded);
  JSON.stringify(getVersion());
  samples.string_conversion.push(performance.now() - t0);
}

samples.scalar_call = [];
for (let i = 0; i < n; i++) {
  const t0 = performance.now();
  const parsed = JSON.parse(exports.DocumentConverter.GetVersion());
  const nFields = Object.keys(parsed).length;
  if (!Number.isFinite(nFields)) throw new Error('scalar_call: bad field count');
  samples.scalar_call.push(performance.now() - t0);
}

samples.batched_call = [];
for (let i = 0; i < n; i++) {
  const t0 = performance.now();
  for (let j = 0; j < 100; j++) {
    getVersion();
  }
  samples.batched_call.push(performance.now() - t0);
}

samples.memory_grow = [];
const wasmMem = globalThis.WebAssembly?.Memory;
if (wasmMem) {
  for (let i = 0; i < n; i++) {
    const t0 = performance.now();
    const mem = new wasmMem({ initial: 1 });
    mem.grow(1);
    samples.memory_grow.push(performance.now() - t0);
  }
}

process.stdout.write(
  JSON.stringify({
    ...meta,
    samples_ms: samples,
    operations: Object.keys(samples),
  }),
);
