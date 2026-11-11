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

async function measureHost(path, { selector, surface, context, fallbackPoints, preClickInside = false, noReload = false }) {
  const browserContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await browserContext.newPage();
  const cdp = await browserContext.newCDPSession(page);
  const recorder = getRecorder(cdp, { manageScreencast: true });
  await page.goto(`${base}/${path}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector(selector, { timeout: 15000 });
  await page.waitForTimeout(500);
  await page.evaluate(INSTALL_TAP);

  const points = await resolvePoints(page, context, fallbackPoints);

  if (preClickInside) {
    // Harness input before the measured click: this is the only touched
    // state left under the r3c07c ruling.
    const box = await page.evaluate(
      (sel) => {
        const el = document.querySelector(sel);
        const r = el && el.getBoundingClientRect();
        return r ? { x: r.left + r.width / 2, y: r.top + r.height / 2 } : null;
      },
      selector,
    );
    if (box) await page.mouse.click(box.x, box.y);
    await page.waitForTimeout(120);
  }

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
  const reloadPage = noReload
    ? null
    : async () => {
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

// r3c07c: a host that focuses itself on load with ZERO harness input is the
// editor's own load behaviour — it measures and the samples are flagged.
{
  const { entry } = await measureHost('selffocus.html', domSpec);
  console.log(`selffocus host: outcome=${entry.outcome} reason=${entry.failure_reason} samples=${entry.samples_ms.length}`);
  assert(
    entry.outcome === 'measured',
    `a self-focusing host measures (got ${entry.outcome}: ${entry.failure_reason})`,
  );
  const sampled = entry.observations.filter((o) => o.sample_ms !== undefined);
  assert(
    sampled.length >= 2 && sampled.every((o) => o.editor_self_focused_on_load === true),
    'every self-focused sample carries the flag',
  );
  assert(
    sampled.every(
      (o) =>
        o.fresh_state &&
        o.fresh_state.untouched &&
        o.fresh_state.untouched.anchor_inside === true &&
        (o.fresh_state.untouched.events || []).length === 0,
    ),
    'the planted selection is recorded with empty recorded inputs',
  );
}

// r3c07c: harness input inside the editable before the click is the only
// touched state left — every point refuses by name.
{
  const { entry } = await measureHost('plant.html?plant=quiet', { ...domSpec, preClickInside: true, noReload: true });
  console.log(`clicked-before host: outcome=${entry.outcome} reason=${entry.failure_reason} samples=${entry.samples_ms.length}`);
  assert(entry.outcome === 'failed', `a harness-clicked host refuses (got ${entry.outcome})`);
  assert(
    String(entry.failure_reason || '').includes('untouched'),
    `the touched state is named (got ${entry.failure_reason})`,
  );
  assert(
    entry.observations.length > 0 && entry.observations.every((o) => String(o.failure || '').includes('untouched')),
    'every point after harness input refuses as touched',
  );
  assert(
    !entry.observations.some((o) => o.editor_self_focused_on_load === true),
    'no point may claim self-focus once harness input exists',
  );
}

// r3c07c: a fragment-selector editable (eigenpal: one caret root per
// paragraph) counts a selection inside ANY fragment, not only the first.
{
  const browserContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await browserContext.newPage();
  await page.goto(`${base}/fragments.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector('.docx-page-content [data-paragraph-id][data-start]', { timeout: 15000 });
  const lastFrag = await page.evaluate(() => {
    const els = Array.from(document.querySelectorAll('.docx-page-content [data-paragraph-id][data-start]'));
    const last = els[els.length - 1];
    const r = last.getBoundingClientRect();
    return { x: r.left + r.width - 4, y: r.top + r.height / 2 };
  });
  await page.mouse.click(lastFrag.x, lastFrag.y);
  await page.waitForTimeout(150);
  const state = await page.evaluate(
    ci.READ_EDITABLE_STATE,
    '.docx-page-content [data-paragraph-id][data-start]',
  );
  console.log(`fragment host: anchor_inside=${state.anchor_inside} caret=${JSON.stringify(state.caret)}`);
  assert(
    state.anchor_inside === true,
    'a caret in a later paragraph-fragment is inside the editable (eigenpal read)',
  );
  await browserContext.close();
}

// r3c07c: a pointerdown on a .docx-line's trailing gap — inside the fragment
// root but outside every run — is inside the editable. Eigenpal maps it to
// the line-end caret; refusing it as outside misread the hit.
{
  const browserContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await browserContext.newPage();
  await page.goto(`${base}/fragments.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector('.docx-page-content [data-paragraph-id][data-start]', { timeout: 15000 });
  await page.evaluate(INSTALL_TAP);
  const gap = await page.evaluate(() => {
    const line = document.querySelector('.docx-paragraph-fragment[data-paragraph-id="p3"] .docx-line');
    const run = line && line.querySelector('.layout-run');
    const lr = line.getBoundingClientRect();
    const rr = run.getBoundingClientRect();
    return { x: (rr.right + lr.right) / 2, y: lr.top + lr.height / 2 };
  });
  const hit = await page.evaluate(({ x, y }) => {
    const t = document.elementFromPoint(x, y);
    return t ? { tag: t.tagName, cls: String(t.className || '').slice(0, 40) } : null;
  }, gap);
  assert(hit && hit.cls.includes('docx-line'), `the gap click lands on .docx-line (got ${JSON.stringify(hit)})`);
  await page.mouse.click(gap.x, gap.y);
  await page.waitForTimeout(150);
  const target = await ci.pointerTargetInside(page, '.docx-page-content [data-paragraph-id][data-start]');
  console.log(`fragment gap click: target=${JSON.stringify(target)}`);
  assert(target && target.inside === true, 'a .docx-line hit inside the fragment root is inside the editable');
  const state = await page.evaluate(
    ci.READ_EDITABLE_STATE,
    '.docx-page-content [data-paragraph-id][data-start]',
  );
  assert(
    state.anchor_inside === true,
    'the gap click still places a caret inside the editable',
  );
  await browserContext.close();
}

// r3c07c: the witness document region for a multi-piece editable is the
// union of every match, never the first fragment's box alone.
{
  const browserContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await browserContext.newPage();
  await page.goto(`${base}/fragments.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector('.docx-page-content [data-paragraph-id][data-start]', { timeout: 15000 });
  const union = await page.evaluate(
    ci.UNION_MATCHED_RECTS,
    '.docx-page-content [data-paragraph-id][data-start]',
  );
  const first = await page.evaluate(() => {
    const el = document.querySelector('.docx-page-content [data-paragraph-id][data-start]');
    const r = el.getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height };
  });
  const all = await page.evaluate(() => {
    const els = Array.from(document.querySelectorAll('.docx-page-content [data-paragraph-id][data-start]'));
    const last = els[els.length - 1].getBoundingClientRect();
    return { bottom: last.bottom };
  });
  console.log(`fragment union: ${JSON.stringify(union)} first=${JSON.stringify(first)}`);
  assert(union && Number.isFinite(union.width), 'the union region resolves');
  assert(
    union.height > first.h * 3 && union.y <= first.y && union.y + union.height >= all.bottom,
    'the union region covers every fragment, not only the first',
  );
  await browserContext.close();
}

await browser.close();
server.close();
if (failed) process.exit(1);
console.log(`b4_c07_quiet_hosts: ${checks} checks ok`);
