// SuperDoc headless round trip via the published @superdoc/sdk.
// This is the editor's OWN documented headless lane (examples/sdk-batch/batch.ts in
// the repo does exactly this):
//   new SuperDocClient() -> client.open({doc}) -> doc.save({out, force:true}) -> doc.close()
//
// The SDK is ESM ("type": "module"). It is pinned exactly in harness/superdoc-sdk/package.json
// (build/update_editors.sh moves the pin), so the measured version is in this repository.
import { writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SDK = join(HERE, 'superdoc-sdk/node_modules/@superdoc/sdk/dist/index.js');

const inPath = resolve(process.argv[2]);
const outPath = resolve(process.argv[3]);

const { SuperDocClient } = await import(SDK);

const client = new SuperDocClient();
const t0 = performance.now();
const doc = await client.open({ doc: inPath });
const t1 = performance.now();
console.log(`PERF model_ready_ms=${(t1 - t0).toFixed(6)}`);
const ts0 = performance.now();
await doc.save({ out: outPath, force: true });
const ts1 = performance.now();
console.log(`PERF save_ms=${(ts1 - ts0).toFixed(6)}`);
await doc.close();

console.log(`[superdoc] wrote ${outPath}`);

// The SDK keeps its native host alive, so the process would otherwise hang
// after the round trip is done and stall the batch runner.
process.exit(0);
