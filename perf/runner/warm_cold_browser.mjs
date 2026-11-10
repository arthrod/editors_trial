/**
 * Paired warm/cold browser probes for the perf harness.
 *
 * Usage (from repo root, with a dev server already listening):
 *   node perf/runner/warm_cold_browser.mjs \
 *     --driver playwright \
 *     --url http://127.0.0.1:5208/ \
 *     --corpus /abs/fixture.docx \
 *     --corpus-route /corpus.docx \
 *     --ready-selector ".status-ok" \
 *     --edit-selector "[data-slate-editor='true']" \
 *     --pairs 3
 *
 * Criteria mode (no warm/cold pairs, one page load, see criteria_input.mjs):
 *
 *   node perf/runner/warm_cold_browser.mjs \
 *     --driver playwright --editor plate --criteria C04,C07,C09,C08 \
 *     --url http://127.0.0.1:5208/ --corpus /abs/corpus.docx \
 *     --corpus-route /corpus.docx --ready-selector ".status-ok" \
 *     --edit-selector '[contenteditable="true"]'
 *
 * Optional: --frame-timeout, --quiescence-ms, --quiescence-timeout,
 * --bulk-chars. The payload goes to stdout.
 */
import fs from 'node:fs';
import { loadPlaywright, clockSkew, witnessFrame, stopRecorder } from './witness.mjs';

import {
  CRITERIA_SCHEMA,
  parseCriteriaList,
  runCriteriaSuite,
} from './criteria_input.mjs';


const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (!a.startsWith('--')) continue;
  const key = a.slice(2);
  const next = argv[i + 1];
  if (next === undefined || next.startsWith('--')) {
    opt[key] = true;
  } else {
    opt[key] = next;
    i++;
  }
}

const driver = opt.driver || 'playwright';
const url = opt.url;
const corpusFile = opt.corpus;
const corpusRoute = opt['corpus-route'] || '/corpus.docx';
const readySelector = opt['ready-selector'] || '.status-ok';
const readyText = opt['ready-text'] || '';
const readyJs = opt['ready-js'] || '';
const editSelector = opt['edit-selector'] || '[contenteditable="true"]';
const preEditClick = opt['pre-edit-click'] || '';
const skipEdit = opt['skip-edit'] === 'true' || opt['skip-edit'] === true;
const pairs = Math.max(1, Number(opt.pairs || 3));
const sampleRoute = opt['sample-route'] || corpusRoute;
const waitAfterReadyMs = Number(opt['wait-after-ready'] || 0);
const editorId = typeof opt.editor === 'string' ? opt.editor : null;
const frameTimeoutMs = Number(opt['frame-timeout'] || 2000);
const quiescenceMs = Number(opt['quiescence-ms'] || 500);
const quiescenceTimeoutMs = Number(opt['quiescence-timeout'] || 10_000);
const bulkChars = Number(opt['bulk-chars'] || 1500);
let criteriaList = [];
if (opt.criteria !== undefined) {
  try {
    criteriaList = parseCriteriaList(opt.criteria);
  } catch (err) {
    console.error(`warm_cold_browser: ${err.message}`);
    process.exit(2);
  }
  if (criteriaList.length === 0) {
    console.error('warm_cold_browser: --criteria named no criterion');
    process.exit(2);
  }
}

if (!url || !corpusFile) {
  console.error('warm_cold_browser: --url and --corpus are required');
  process.exit(2);
}

const corpusBytes = fs.readFileSync(corpusFile);

async function waitForReady(page, selector, timeoutMs = 120_000, t0 = Date.now()) {
  if (readyJs) {
    await page.waitForFunction(
      (expr) => {
        try {
          // eslint-disable-next-line no-eval
          return Boolean(eval(expr));
        } catch {
          return false;
        }
      },
      readyJs,
      { timeout: timeoutMs },
    );
  } else if (readyText) {
    await page.waitForFunction(
      ({ sel, text }) => {
        const el = document.querySelector(sel);
        return Boolean(el && el.textContent && el.textContent.includes(text));
      },
      { sel: selector, text: readyText },
      { timeout: timeoutMs },
    );
  } else {
    await page.waitForSelector(selector, { timeout: timeoutMs, state: 'visible' });
  }
  const first_usable_ms = Date.now() - t0;
  const settleStart = Date.now();
  if (waitAfterReadyMs > 0) {
    await page.waitForTimeout(waitAfterReadyMs);
  }
  const settle_ms = Date.now() - settleStart;
  const calibration = await page.context().newCDPSession(page);
  const clock_skew = await clockSkew(page, calibration);
  await stopRecorder(calibration);
  await calibration.detach();
  return { first_usable_ms, settle_ms, clock_skew };
}

async function performEdit(page, selector, cdp) {
  // Focus/actionability and witness calibration are preconditioning, outside
  // the event-to-frame interval. No typing delay is introduced.
  if (preEditClick) await page.click(preEditClick, { timeout: 30_000 });
  await page.locator(selector).first().click({ timeout: 30_000 });
  const skew = await clockSkew(page, cdp);
  const mechanism = 'cdp_screencast_changed_frame';
  if (!skew.acceptable) return {
    mechanism, clock_skew: skew, outcome: 'failed', edit_ms: null,
    failure_reason: skew.skew_ms === null ? 'clock_skew_unavailable' : 'clock_skew_above_bound',
  };
  await page.evaluate(() => {
    window.__b2 = { event: null, entries: [], supported: PerformanceObserver.supportedEntryTypes.includes('event') };
    window.addEventListener('keydown', function onKey(e) {
      if (e.key !== 'x') return;
      window.__b2.event = { startTime: e.timeStamp, trusted: e.isTrusted };
      window.removeEventListener('keydown', onKey, true);
    }, true);
    if (window.__b2.supported) {
      window.__b2.observer = new PerformanceObserver(list => {
        window.__b2.entries.push(...list.getEntries().map(e => ({
          name:e.name, startTime:e.startTime, duration:e.duration, interactionId:e.interactionId
        })));
        window.__b2.notify?.();
      });
      window.__b2.observer.observe({type:'event', durationThreshold:16});
    }
  });
  const frame = await witnessFrame(page, cdp, {
    windowMs: Math.max(500, frameTimeoutMs), clockSkewMs: skew.skew_ms,
    arm: async () => {
      await cdp.send('Input.dispatchKeyEvent', {type:'keyDown', key:'x', code:'KeyX', text:'x', windowsVirtualKeyCode:88});
      await cdp.send('Input.dispatchKeyEvent', {type:'keyUp', key:'x', code:'KeyX', windowsVirtualKeyCode:88});
      const event = await page.evaluate(() => window.__b2.event);
      if (!event?.trusted) throw new Error('trusted keydown not observed');
      return event.startTime;
    },
  });
  // An observer delivery deadline is not a latency: durations come only
  // from matching Event Timing entries, and absence is explicitly censored.
  const timing = await page.evaluate(async () => {
    const state = window.__b2;
    const matching = () => state.entries.filter(e => e.name === 'keydown' && Math.abs(e.startTime-state.event.startTime)<0.1);
    if (state.supported && !matching().length) await new Promise(resolve => {
      const timer = setTimeout(resolve, 500);
      state.notify = () => { if (matching().length) { clearTimeout(timer); resolve(); } };
    });
    state.observer?.disconnect();
    return { event: state.event, entries: matching(), supported:state.supported,
      outcome: !state.supported ? 'unsupported' : matching().length ? 'observed' : 'censored_below_16_ms',
      duration_threshold_ms:16, duration_step_ms:8 };
  });
  const duration = frame.frame_page_ms === null ? null : frame.frame_page_ms - timing.event.startTime;
  const ok = frame.outcome === 'witnessed' && frame.clock_skew_acceptable && duration >= 0;
  return { mechanism, clock_skew:skew, witness:frame, event_timing:timing,
    outcome: ok ? 'measured' : 'failed',
    failure_reason: ok ? null : !frame.clock_skew_acceptable ? 'clock_skew_above_bound' : 'no_frame',
    edit_ms:ok ? duration : null, paint_ms:ok ? duration : null };
}

async function routeCorpus(context, routePath, bytes) {
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname === routePath || u.pathname === sampleRoute) {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: bytes,
      });
      return;
    }
    await route.continue();
  });
}

async function runPlaywrightPair() {
  const { chromium } = await loadPlaywright();
  const launchT0 = Date.now();
  const browser = await chromium.launch({
    headless: true,
    args: ['--font-render-hinting=none', '--disable-lcd-text'],
  });
  const browserLaunchMs = Date.now() - launchT0;

  const coldContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await routeCorpus(coldContext, corpusRoute, corpusBytes);
  const coldPage = await coldContext.newPage();
  const cdp = await coldContext.newCDPSession(coldPage);

  const navT0 = Date.now();
  await coldPage.goto(url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  const documentNavigationMs = Date.now() - navT0;

  const coldReady = await waitForReady(coldPage, readySelector, 120_000, navT0);
  const modelReadyMs = coldReady.first_usable_ms;
  let coldEdit = { edit_ms: null, paint_ms: null };
  let warmEdit = { edit_ms: null, paint_ms: null };
  const warmBurst = [];
  const coldBurst = [];
  if (!skipEdit) {
    coldEdit = await performEdit(coldPage, editSelector, cdp);
    for (let i = 0; i < 3; i++) {
      coldBurst.push(await performEdit(coldPage, editSelector, cdp));
    }
  }

  const reloadT0 = Date.now();
  await coldPage.reload({ waitUntil: 'domcontentloaded', timeout: 120_000 });
  await stopRecorder(cdp);
  const warmReady = await waitForReady(coldPage, readySelector, 120_000, reloadT0);
  const documentReloadSameContextMs = warmReady.first_usable_ms;

  if (!skipEdit) {
    warmEdit = await performEdit(coldPage, editSelector, cdp);
    for (let i = 0; i < 3; i++) {
      warmBurst.push(await performEdit(coldPage, editSelector, cdp));
    }
  }

  await stopRecorder(cdp);
  await coldContext.close();
  await browser.close();

  return {
    browser_launch_only_ms: browserLaunchMs,
    document_navigation_only_ms: documentNavigationMs,
    model_ready_browser_ms: modelReadyMs,
    document_reload_same_context_ms: documentReloadSameContextMs,
    cold: {
      ...coldReady, ...coldEdit, burst: coldBurst,
      first_usable_ms: modelReadyMs,
      model_ready_browser_ms: modelReadyMs,
      single_edit_ms: coldEdit.edit_ms,
      presented_frame_ms: coldEdit.paint_ms,
      sustained_typing_median_ms:
        coldBurst.every(e => e.edit_ms !== null) && coldBurst.length ? coldBurst.map(e => e.edit_ms).sort((a,b) => a-b)[1] : null,
    },
    warm: {
      ...warmReady, ...warmEdit, burst: warmBurst,
      single_edit_ms: warmEdit.edit_ms,
      presented_frame_ms: warmEdit.paint_ms,
      sustained_typing_median_ms: warmBurst.every(e => e.edit_ms !== null) && warmBurst.length ? warmBurst.map(e => e.edit_ms).sort((a,b) => a-b)[1] : null,
    },
  };
}

/**
 * One page load, the requested criteria, no navigation in between.
 *
 * The page is the non-warm arm: it is the first navigation of a fresh browser
 * context, so C04 records `process_cold_fs_warm`. C07/C08/C09 run after the
 * load, the ready signal and the C04 quiescence window, which is the declared
 * preconditioning for `warm_steady` in their trial hints.
 */
async function runCriteriaSession() {
  if (driver !== 'playwright') {
    const entries = {};
    for (const id of criteriaList) {
      entries[id] = {
        criterion_id: id,
        outcome: 'unsupported',
        samples_ms: [],
        failure_reason: `criteria probe requires the playwright driver (got ${driver}): no CDP screencast frame witness`,
        assertion: { name: null, passed: false, scope: null, checks: {}, failures: ['driver'] },
        observations: [],
        notes: [],
      };
    }
    return {
      probe: 'criteria_input',
      schema: CRITERIA_SCHEMA,
      driver,
      editor_id: editorId,
      url,
      corpus_route: corpusRoute,
      criteria_requested: criteriaList.slice(),
      criteria: entries,
      paint_witness: {
        mechanism: null,
        frames_seen: 0,
        timeout_ms: frameTimeoutMs,
        message: 'driver is not playwright',
      },
    };
  }

  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--font-render-hinting=none', '--disable-lcd-text'],
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await routeCorpus(context, corpusRoute, corpusBytes);
  let clipboardPermission = null;
  try {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'], {
      origin: new URL(url).origin,
    });
    clipboardPermission = 'clipboard-read,clipboard-write';
  } catch (err) {
    clipboardPermission = `unavailable: ${String(err && err.message ? err.message : err)}`;
  }
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  const ready = await waitForReady(page, readySelector);
  const payload = await runCriteriaSuite({
    page,
    cdp,
    editSelector,
    criteria: criteriaList,
    frameTimeoutMs,
    quiescenceMs,
    quiescenceTimeoutMs,
    bulkChars,
  });
  await context.close();
  await browser.close();

  payload.editor_id = editorId;
  payload.url = url;
  payload.corpus_route = corpusRoute;
  payload.ready = {
    selector: readySelector,
    ready_ms: ready.first_usable_ms,
    first_usable_ms: ready.first_usable_ms,
    settle_ms: ready.settle_ms,
    clock_skew: ready.clock_skew,
    ready_page_ms: payload.ready.ready_page_ms,
    note: payload.ready.note,
  };
  payload.clipboard_permission = clipboardPermission;
  return payload;
}

async function coldOnlyFreshContext() {
  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  await routeCorpus(context, corpusRoute, corpusBytes);
  const page = await context.newPage();
  const t0 = Date.now();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  const ready = await waitForReady(page, readySelector, 120_000, t0);
  await browser.close();
  return ready;
}

const collected = [];
if (criteriaList.length > 0) {
  const payload = await runCriteriaSession();
  process.stdout.write(JSON.stringify(payload));
  process.exit(0);
}
for (let i = 0; i < pairs; i++) {
  if (driver === 'puppeteer') {
    throw new Error('puppeteer input timing unsupported: requires shared CDP frame witness');
  } else {
    collected.push(await runPlaywrightPair());
  }
}

let freshContextMedians = [];
if (opt['fresh-context-probe'] !== 'false') {
  const freshSamples = [];
  for (let i = 0; i < Math.min(pairs, 3); i++) {
    freshSamples.push(await coldOnlyFreshContext());
  }
  freshContextMedians = freshSamples;
}

const result = {
  driver,
  url,
  corpus_route: corpusRoute,
  ready_selector: readySelector,
  edit_selector: editSelector,
  server_cold_pair: collected[0] || null,
  pairs: collected.map((pair, index) => ({...pair, server_cold: index === 0})),
  fresh_context_load_ms: freshContextMedians,
};

process.stdout.write(JSON.stringify(result));
