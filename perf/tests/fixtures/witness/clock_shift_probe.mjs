// B1c fix (#130 defect 1) — the permanent fault-injection clock probe.
//
// It is the reviewer's probe (/tmp/rev-b1c/probe.mjs, review finding 1) made
// permanent: a CDP forwarding wrapper that changes ONLY each screencast
// event's `metadata.timestamp` by a stated offset, leaving every pixel and
// every page-clock reading untouched, and then runs `clockSkew()` under
// shifts 0, +1000 and -1000 ms. The clock gate must accept the untouched
// clock (shift 0) and refuse both injected conversion errors, with a reason.
//
// Usage: node clock_shift_probe.mjs <path-to-witness.mjs>
// Prints one JSON record per line: {"case": "shift", "shift": <ms>, ...record}

import { pathToFileURL } from 'node:url';

const target = process.argv[2];
if (!target) {
  process.stderr.write('usage: node clock_shift_probe.mjs <path-to-witness.mjs>\n');
  process.exit(2);
}

const witness = await import(pathToFileURL(target).href);
const { chromium } = await witness.loadPlaywright();
const browser = await chromium.launch({ headless: true });
let failed = 0;
try {
  for (const shift of [0, 1000, -1000]) {
    const page = await browser.newPage();
    await page.setContent('<body><main>Unchanged document</main></body>');
    const real = await page.context().newCDPSession(page);
    // Forward every call untouched, but shift each screencast frame's
    // metadata.timestamp on the way through. This is exactly the fault the
    // gate must catch: a wrong screencast->page-time conversion.
    const cdp = {
      send: (...args) => real.send(...args),
      on: (name, fn) =>
        real.on(name, (event) =>
          fn({
            ...event,
            metadata: {
              ...event.metadata,
              timestamp: event.metadata.timestamp + shift / 1000,
            },
          }),
        ),
      off: (name, fn) => real.off(name, fn),
    };
    try {
      const record = await witness.clockSkew(page, cdp);
      console.log(JSON.stringify({ case: 'shift', shift, ...record }));
    } catch (error) {
      failed += 1;
      console.log(
        JSON.stringify({
          case: 'shift',
          shift,
          error: String(error).slice(0, 300),
        }),
      );
    }
    await page.close();
  }
} finally {
  await browser.close();
}
process.exitCode = failed ? 1 : 0;
