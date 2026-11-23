// E2 OpenDoc: the host page sets its three autocorrect preferences off and checks them.
// Runs harness/ui/opendoc/host.js against a stub page whose storage behaves as asked.
// Invoked from test_e2_opendoc_lists_off.py; prints JSON.
import fs from 'node:fs';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const HOST = fileURLToPath(new URL('../../harness/ui/opendoc/host.js', import.meta.url));
const src = fs.readFileSync(HOST, 'utf8');

function run(storage) {
  const classes = () => ({ contains: () => false });
  const root = { classList: classes() };
  const body = { classList: classes(), dataset: {} };
  const window = { localStorage: storage };
  const context = {
    window,
    document: { readyState: 'complete', documentElement: root, body, getElementById: () => null,
      querySelector: () => null, addEventListener: () => {} },
    MutationObserver: class { observe() {} disconnect() {} },
    requestAnimationFrame: (fn) => fn(),
    performance: { now: () => 1 },
  };
  vm.runInNewContext(src, context);
  const host = window.__host;
  return { error: host.error, ready: host.ready, autocorrect: host.autocorrect };
}

const memory = () => {
  const map = new Map();
  return { setItem: (k, v) => map.set(k, String(v)), getItem: (k) => (map.has(k) ? map.get(k) : null) };
};
// Storage that refuses its second write (a quota, a policy): the third is never made either.
const refusesSecond = () => {
  const map = new Map();
  let n = 0;
  return {
    setItem: (k, v) => { n += 1; if (n === 2) throw new Error('QuotaExceededError'); map.set(k, String(v)); },
    getItem: (k) => (map.has(k) ? map.get(k) : null),
  };
};
// Storage that accepts writes and keeps nothing.
const forgets = () => ({ setItem: () => {}, getItem: () => null });

process.stdout.write(JSON.stringify({
  works: run(memory()),
  refuses_second: run(refusesSecond()),
  forgets: run(forgets()),
}));
