/**
 * Static @suite-phase tags in criteria_input.mjs must match RUN_CRITERIA_SUITE_PHASES.
 */
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';

const repo = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const moduleUrl = pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href;
const { RUN_CRITERIA_SUITE_PHASES } = await import(moduleUrl);

const src = fs.readFileSync(`${repo}/perf/runner/criteria_input.mjs`, 'utf8');
const tagged = [];
for (const line of src.split('\n')) {
  const match = line.match(/\/\/\s*@suite-phase\s+(\w+)/);
  if (match) tagged.push(match[1]);
}

const exported = [...RUN_CRITERIA_SUITE_PHASES];
const taggedSet = new Set(tagged);
const exportSet = new Set(exported);
const ok =
  tagged.length === exported.length &&
  tagged.every((p) => exportSet.has(p)) &&
  exported.every((p) => taggedSet.has(p));

const report = {
  ok,
  tagged,
  exported,
  missing_tags: exported.filter((p) => !taggedSet.has(p)),
  extra_tags: tagged.filter((p) => !exportSet.has(p)),
};
console.log(JSON.stringify(report));
process.exit(ok ? 0 : 1);
