// E2 C15: the find probe's page side (perf/runner/find_probe.mjs) on a fake find bar.
// Invoked from test_e2_find_probe.py; prints JSON. FIND_PROBE_MODULE overrides the
// module (the test's red run points it at the probe as it was before the fix).
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';

const repo = fileURLToPath(new URL('../..', import.meta.url)).replace(/\/$/, '');
const require = createRequire(`${repo}/harness/ui/package.json`);
const { chromium } = require('playwright');
const modulePath = process.env.FIND_PROBE_MODULE || `${repo}/perf/runner/find_probe.mjs`;
const { INSTALL_FIND_PROBE } = await import(pathToFileURL(modulePath).href);

// OnlyOffice's shape: the first input starts one interval; each tick searches
// what the input holds and writes its count.
const INTERVAL_PAGE = (counts) => `<!doctype html><body>
<input id="q"><span id="count"></span>
<script>
  const counts = ${JSON.stringify(counts)};
  let started = false;
  document.getElementById('q').addEventListener('input', () => {
    if (started) return;
    started = true;
    setInterval(() => {
      const v = document.getElementById('q').value;
      if (counts[v] !== undefined) document.getElementById('count').textContent = counts[v] + ' results';
    }, 20);
  });
</script></body>`;

// BetterOffice's shape: each input's timer runs the search, and the count
// renders in a later task (renderMs after the timer).
const LATE_PAGE = (counts, renderMs) => `<!doctype html><body>
<input id="q"><span id="count"></span>
<script>
  const counts = ${JSON.stringify(counts)};
  document.getElementById('q').addEventListener('input', () => {
    setTimeout(() => {
      const v = document.getElementById('q').value;
      const n = counts[v];
      // The render, in a later task (not scheduled from an input).
      setTimeout(() => { document.getElementById('count').textContent = n + ' results'; }, ${renderMs});
    }, 0);
  });
</script></body>`;

async function run(browser, html, args, steps) {
  const page = await browser.newPage();
  await page.setContent(html);
  await page.locator('#q').click();
  await page.evaluate(INSTALL_FIND_PROBE, {
    countSel: '#count', matchSel: null, inputSel: '#q', ...args,
  });
  for (const [key, waitMs] of steps) {
    await page.keyboard.type(key, { delay: 0 });
    await page.waitForTimeout(waitMs);
  }
  const out = await page.evaluate(() => {
    const p = window.__findProbe;
    const row = { complete: p.complete_at !== null, accepted: p.accepted_text, ambiguous: p.ambiguous_reply === true };
    if (p.stop) p.stop();
    return row;
  });
  await page.close();
  return out;
}

const browser = await chromium.launch({ headless: true });
try {
  const out = {
    // Prefix ticks show 3 then 2; the full query's tick shows 3 again.
    interval_back_to_a_prefix_count: await run(browser, INTERVAL_PAGE({ a: 3, ab: 2, abc: 3 }),
      { expected: 3, query: 'abc', intervalReplies: true, lateReply: false },
      [['a', 120], ['b', 120], ['c', 200]]),
    // Two timers run before the first render commits: "a" renders 3 (the expected count).
    late_overlap: await run(browser, LATE_PAGE({ a: 3, ab: 3 }, 80),
      { expected: 3, query: 'ab', intervalReplies: false, lateReply: true },
      [['a', 0], ['b', 300]]),
    // The same page, keystrokes far apart: each reply commits before the next timer.
    late_apart: await run(browser, LATE_PAGE({ a: 2, ab: 3 }, 30),
      { expected: 3, query: 'ab', intervalReplies: false, lateReply: true },
      [['a', 200], ['b', 300]]),
  };
  process.stdout.write(JSON.stringify(out));
} finally {
  await browser.close();
}
