// SuperDoc headless round trip via the published @superdoc/sdk.
// This is the editor's OWN documented headless lane (examples/sdk-batch/batch.ts in
// the repo does exactly this):
//   new SuperDocClient() -> client.open({doc}) -> doc.save({out, force:true}) -> doc.close()
//
// The SDK is ESM ("type": "module"). It is installed in the superdoc repo's pnpm store.
import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const SDK =
  '/Users/arthrod/temp/T/editors_trial/repos/superdoc/node_modules/.pnpm/' +
  '@superdoc+sdk@2.25.0-next.14/node_modules/@superdoc/sdk/dist/index.js';

const inPath = resolve(process.argv[2]);
const outPath = resolve(process.argv[3]);

const { SuperDocClient } = await import(SDK);

const client = new SuperDocClient();
const doc = await client.open({ doc: inPath });
await doc.save({ out: outPath, force: true });
await doc.close();

console.log(`[superdoc] wrote ${outPath}`);

// The SDK keeps its native host alive, so the process would otherwise hang
// after the round trip is done and stall the batch runner.
process.exit(0);
