/**
 * r3c07b reviewer plants on fake hosts, end to end: a real Chromium page, a
 * real CDP screencast witness, and the production C07 measurement. Each plant
 * keeps repainting inside the click box — a blinking caret already in the
 * box, a hover highlight, a toolbar repaint, scroll jitter, and a canvas
 * blink — so the box is never quiet and C07 must refuse every point. The
 * quiet control measures.
 */
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import * as ci from '../runner/criteria_input.mjs';
import { getRecorder, witnessFrame } from '../runner/witness.mjs';

const require = createRequire(fileURLToPath(new URL('../../harness/ui/package.json', import.meta.url)));
const { chromium } = require('playwright');

let failed = 0;
let checks = 0;
function assert(cond, msg) {
  checks += 1;
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failed += 1;
  }
}

const WORDCRAFT_NOTE =
  "caret position not readable; sample is the first paint in a box proven quiet before an untouched editor's first click";

const FIXTURES = fileURLToPath(new URL('./fixtures/click_hosts/', import.meta.url));
const server = createServer(async (req, res) => {
  const name = req.url.split('?')[0].replace(/^\//, '') || 'plant.html';
  try {
    const body = await readFile(FIXTURES + name);
    res.writeHead(200, { 'content-type': 'text/html' });
    res.end(body);
  } catch {
    res.writeHead(404);
    res.end('not found');
  }
});
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;

// Same shape as the production tap: serializable inputs plus the element
// refs (`targets`) DOCUMENT_UNTOUCHED reads page-side.
const INSTALL_TAP = () => {
  window.__perfCriteria = { inputs: [], targets: [], timeOrigin: performance.timeOrigin, target: null };
  const tap = window.__perfCriteria;
  const push = (kind, extra, el) => {
    if (tap.targets.length < 2000) tap.targets.push({ kind, el: el || null });
    if (tap.inputs.length < 200) {
      tap.inputs.push(Object.assign({ kind, t: performance.now() }, extra || {}));
    }
    return tap.inputs[tap.inputs.length - 1];
  };
  const opts = { capture: true, passive: true };
  document.addEventListener(
    'pointerdown',
    (event) => {
      tap.target = event.target;
      push('pointerdown', { x: event.clientX, y: event.clientY }, event.target);
    },
    opts,
  );
  document.addEventListener('keydown', (event) => push('keydown', { key: event.key }, event.target), opts);
  document.addEventListener('paste', (event) => push('paste', null, event.target), opts);
  document.addEventListener('beforeinput', (event) => push('beforeinput', { inputType: event.inputType }, event.target), opts);
};

const browser = await chromium.launch({ headless: true });

/**
 * Resolve the click points exactly the way the suite does: the ONE routine —
 * clip probe, ink scan before the timed window, distinct painted lines.
 * Falls back to line-box geometry only if the pipeline cannot run.
 */
async function resolvePoints(page, context, fallback) {
  const resolved = await ci.resolveInkClickPoints(page, context).catch(() => null);
  if (resolved && !resolved.error && (resolved.points || []).length >= 2) {
    return resolved.points;
  }
  return page.evaluate(fallback);
}

async function measureHost(path, { selector, surface, context, fallbackPoints }) {
  const browserContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await browserContext.newPage();
  const cdp = await browserContext.newCDPSession(page);
  const recorder = getRecorder(cdp, { manageScreencast: true });
  await page.goto(`${base}/${path}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector(selector, { timeout: 15000 });
  await page.waitForTimeout(500);
  await page.evaluate(INSTALL_TAP);

  const points = await resolvePoints(page, context, fallbackPoints);

  const witness = {
    frameIntervalMs: 16.667,
    paintAfter: (inputMs, callOptions = {}) =>
      witnessFrame(page, cdp, {
        recorder,
        settleMs: 40,
        caretMask: callOptions.caretMask === true,
        region: callOptions.region,
        arm: callOptions.arm,
        windowMs: 15000,
        quietMs: callOptions.quietMs,
        quietBudgetMs: callOptions.quietBudgetMs,
      }),
  };
  const meta = {
    editable: { selector, is_content_editable: surface ? false : true, input_reachable: true },
    points,
    surface: surface || { kind: 'dom' },
  };
  const reloadPage = async () => {
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector(selector, { timeout: 15000 });
    await page.waitForTimeout(500);
    await page.evaluate(INSTALL_TAP);
    return true;
  };
  const entry = await ci.measureClicks(page, meta, {
    frameTimeoutMs: 15000,
    expectedBodyText: null,
    quietMs: 1000,
    quietBudgetMs: 4500,
    reloadPage,
    witness,
  });
  const clicks = await page
    .evaluate(() => (window.__perfCriteria ? window.__perfCriteria.inputs.filter((i) => i.kind === 'pointerdown').length : -1))
    .catch(() => -1);
  await browserContext.close();
  return { entry, points, tapPointerdowns: clicks };
}

// Fallback point geometry if the shared pipeline is unavailable (RED stage).
const DOM_FALLBACK = () =>
  [...document.querySelectorAll('#doc p')].slice(0, 3).map((p, i) => {
    const r = p.getBoundingClientRect();
    const d = document.querySelector('#doc').getBoundingClientRect();
    return {
      point: ['first_text_line', 'page_centre', 'last_text_line'][i],
      x: d.left + 120,
      y: (r.top + r.bottom) / 2,
      line: { top: r.top, bottom: r.bottom },
      hit_inside_editable: true,
    };
  });
const CANVAS_FALLBACK = () => {
  const r = document.querySelector('canvas').getBoundingClientRect();
  return [0, 2, 4].map((line, i) => ({
    point: ['first_text_line', 'page_centre', 'last_text_line'][i],
    x: r.left + 200,
    y: r.top + 30 + line * 36 + 13,
    line: { top: r.top + 30 + line * 36, bottom: r.top + 30 + line * 36 + 26 },
    hit_inside_editable: true,
  }));
};

const domSpec = {
  selector: '#doc',
  surface: null,
  context: { kind: 'dom', selector: '#doc' },
  fallbackPoints: DOM_FALLBACK,
};
const canvasSpec = {
  selector: 'canvas',
  surface: { kind: 'flag', pageRoot: 'canvas', selector: 'canvas' },
  context: { kind: 'surface', spec: { kind: 'flag', pageRoot: 'canvas', selector: 'canvas' } },
  fallbackPoints: CANVAS_FALLBACK,
};

for (const plant of ['quiet', 'blink', 'hover', 'toolbar', 'scroll']) {
  const { entry, points, tapPointerdowns } = await measureHost(`plant.html?plant=${plant}`, domSpec);
  console.log(`DOM plant=${plant}: outcome=${entry.outcome} reason=${entry.failure_reason} samples=${entry.samples_ms.length} points=${points.length}`);
  if (plant === 'quiet') {
    assert(entry.outcome === 'measured', `quiet DOM host measures (got ${entry.outcome}: ${entry.failure_reason})`);
    assert(entry.samples_ms.length >= 2, 'at least two distinct lines paint');
    const sampled = entry.observations.filter((o) => o.sample_ms !== undefined);
    assert(
      sampled.every((o) => o.quiet_window && o.quiet_window.proven === true && o.quiet_window.observed_ms >= 1000),
      'every DOM sample carries a proven >=1000 ms quiet window',
    );
    assert(
      sampled.every((o) => o.caret_on_clicked_line === true),
      'the DOM caret lands on each clicked line',
    );
  } else {
    assert(entry.outcome === 'failed', `DOM plant ${plant} refuses (got ${entry.outcome})`);
    assert(
      String(entry.failure_reason || '').includes('quiet'),
      `DOM plant ${plant} names the quiet box (got ${entry.failure_reason})`,
    );
    assert(
      !entry.observations.some((o) => o.sample_ms !== undefined),
      `DOM plant ${plant} keeps no painted sample`,
    );
  }
}

for (const plant of ['quiet', 'blink']) {
  const { entry } = await measureHost(`canvas_plant.html?plant=${plant}`, canvasSpec);
  console.log(`canvas plant=${plant}: outcome=${entry.outcome} reason=${entry.failure_reason} samples=${entry.samples_ms.length}`);
  if (plant === 'quiet') {
    assert(entry.outcome === 'measured', `quiet canvas host measures (got ${entry.outcome}: ${entry.failure_reason})`);
    const sampled = entry.observations.filter((o) => o.sample_ms !== undefined);
    assert(
      sampled.every((o) => o.caret_note === WORDCRAFT_NOTE && o.caret_evidence === 'unreadable'),
      'the unreadable-caret surface records the note verbatim on every sample',
    );
  } else {
    assert(entry.outcome === 'failed', `canvas blink plant refuses (got ${entry.outcome})`);
    assert(
      !entry.observations.some((o) => o.sample_ms !== undefined),
      'the canvas blink keeps no painted sample',
    );
  }
}

await browser.close();
server.close();
if (failed) process.exit(1);
console.log(`b4_c07_quiet_hosts: ${checks} checks ok`);
