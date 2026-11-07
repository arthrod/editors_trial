/**
 * Docxodus WASM boundary probe (C24). No synthetic RNG loops.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '../..');

const opt = {};
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

const wasmPath =
  opt.wasm ||
  path.join(
    repo,
    'harness/ui/docxodus/node_modules/docxodus/dist/wasm/_framework/dotnet.native.wasm',
  );

if (!fs.existsSync(wasmPath)) {
  console.error(JSON.stringify({ error: 'missing wasm', wasmPath }));
  process.exit(2);
}

const bytes = fs.readFileSync(wasmPath);
const samples = {};

const t0 = performance.now();
const mod = await WebAssembly.compile(bytes);
const instance = await WebAssembly.instantiate(mod, {});
samples.compile_and_instantiate = [performance.now() - t0];

const exports = instance.exports || {};
const emptyKey = Object.keys(exports).find((k) => typeof exports[k] === 'function');
if (emptyKey) {
  const t1 = performance.now();
  exports[emptyKey]();
  samples.empty_call = [performance.now() - t1];
}

const mem = instance.exports.memory;
if (mem && typeof mem.grow === 'function') {
  const t2 = performance.now();
  mem.grow(1);
  samples.memory_grow = [performance.now() - t2];
}

const probe = {
  wasm_artifact: wasmPath,
  samples_ms: samples,
  operations: Object.keys(samples),
};

process.stdout.write(JSON.stringify(probe));
