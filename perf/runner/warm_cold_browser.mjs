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
import {
  loadPlaywright,
  clockSkew,
  witnessFrame,
  stopRecorder,
  captureBaseline,
  decodePng,
  diffRatio,
  DEFAULT_CHANNEL_TOLERANCE,
  DEFAULT_MIN_PIXELS,
} from './witness.mjs';

function convertFrameToPageMs(frame, clock) {
  const kind = clock.timestamp_kind || 'epoch_seconds';
  if (kind === 'epoch_seconds') {
    if (typeof frame.ts !== 'number') return null;
    return frame.ts * 1000 - clock.time_origin_ms;
  }
  if (kind === 'monotonic_seconds') {
    const value = typeof frame.mono === 'number' ? frame.mono : frame.ts;
    if (typeof value !== 'number' || typeof clock.monotonic_origin_ms !== 'number') return null;
    return value * 1000 - clock.monotonic_origin_ms;
  }
  return null;
}

function clipRectToDocument(rect, doc) {
  const x = Math.max(rect.x, doc.x);
  const y = Math.max(rect.y, doc.y);
  const right = Math.min(rect.x + rect.width, doc.x + doc.width);
  const bottom = Math.min(rect.y + rect.height, doc.y + doc.height);
  if (right <= x || bottom <= y) return null;
  return { x, y, width: right - x, height: bottom - y };
}

function rectDamageVsBaseline(baselinePixels, framePixels, rects, dpr, doc, tolerance) {
  return rects.map(rect => {
    const clipped = clipRectToDocument(rect, doc);
    if (!clipped) return { rect, changed_pixels: 0 };
    const region = {
      x: clipped.x * dpr,
      y: clipped.y * dpr,
      width: clipped.width * dpr,
      height: clipped.height * dpr,
    };
    const diff = diffRatio(baselinePixels, framePixels, { channelTolerance: tolerance, region });
    return { rect, changed_pixels: diff.comparable ? diff.changed : 0 };
  });
}

import { settleFrames } from './b2_settle.mjs';
import { createRegionClassifier } from './b2_pixels.mjs';

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
const quiescenceMs = opt['quiescence-ms'] !== undefined ? Number(opt['quiescence-ms']) : 300;
const settleMaxWaitMs = opt['settle-max-wait-ms'] !== undefined ? Number(opt['settle-max-wait-ms']) : 3000;
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
  try {
    return await measureEdit(page, selector, cdp);
  } catch (error) {
    return { mechanism: 'cdp_screencast_changed_frame', outcome: 'failed',
      edit_ms: null, paint_ms: null, failure_reason: 'input_probe_error: ' + String(error.message || error) };
  } finally {
    await page.evaluate(() => {
      clearInterval(window.__b2?.pulseTimer);
      window.__b2?.pulse?.remove();
      window.__b2?.observer?.disconnect();
      window.__b2?.mutationObserver?.disconnect();
      if (window.__b2?.onKey) window.removeEventListener('keydown', window.__b2.onKey, true);
    }).catch(() => {}); // A navigation may already have destroyed the context.
    await stopRecorder(cdp);
  }
}

async function measureEdit(page, selector, cdp) {
  // Focus/actionability and witness calibration are preconditioning, outside
  // the event-to-frame interval. No typing delay is introduced.
  if (preEditClick) await page.click(preEditClick, { timeout: 30_000 });
  await page.locator(selector).first().click({ timeout: 30_000 });
  const skew = await clockSkew(page, cdp);
  const mechanism = 'cdp_screencast_changed_frame';
  if (!skew.acceptable) return {
    mechanism, clock_skew: skew, outcome: 'failed', edit_ms: null,
    failure_reason: skew.reason || 'clock_check_not_acceptable',
  };
  await page.evaluate(selector => {
    const documentElement = document.querySelector(selector);
    const count = () => (documentElement.textContent.match(/x/g) || []).length;
    const before = count();
    window.__b2 = { event: null, entries: [], supported: PerformanceObserver.supportedEntryTypes.includes('event') };
    const state = window.__b2;
    // Arm only after dispatching the key: never alter the pre-key baseline
    // or delay dispatch. Dense delivery must also witness short delayed
    // reveals before witnessFrame returns.
    state.startPulse = () => {
      const box = documentElement.getBoundingClientRect();
      const corner = [[innerWidth-4,innerHeight-4],[0,innerHeight-4],[innerWidth-4,0],[0,0]]
        .find(([x,y]) => x+3<=box.left || x>=box.right || y+3<=box.top || y>=box.bottom);
      if (corner) {
        const pulse = document.createElement('div');
        pulse.style.cssText = `position:fixed;left:${corner[0]}px;top:${corner[1]}px;width:3px;height:3px;pointer-events:none;z-index:2147483647`;
        document.body.appendChild(pulse);
        let phase = false;
        state.pulse = pulse;
        const tick = () => {phase=!phase;pulse.style.background=phase?'#00f':'#0f0';};
        tick();
        state.pulseTimer = setInterval(tick,16);
      }
    };
    const intersect = (a, b) => {
      const x = Math.max(a.x, b.x), y = Math.max(a.y, b.y);
      const right = Math.min(a.x + a.width, b.x + b.width);
      const bottom = Math.min(a.y + a.height, b.y + b.height);
      return right > x && bottom > y ? {x, y, width: right-x, height: bottom-y} : null;
    };
    const textNodes = root => {
      if (root.nodeType === Node.TEXT_NODE) return [root];
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      return nodes;
    };
    const priorText = new WeakMap(textNodes(documentElement).map(n => [n, n.data]));
    state.edit_confirmation = {confirmed: false, before_count: before, expected: 'x', mutations: []};
    const visibleRects = (node, start, end) => {
      const parent = node.parentElement;
      if (!parent || !documentElement.contains(node) ||
          !parent.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) return [];
      let clip = intersect(documentElement.getBoundingClientRect(),
        {x: 0, y: 0, width: innerWidth, height: innerHeight});
      for (let el = parent; el && clip; el = el.parentElement) {
        const css = getComputedStyle(el);
        // Complex clipping/masks cannot be proven from bounding rectangles.
        if (css.display === 'none' || css.visibility !== 'visible' || Number(css.opacity) === 0 ||
            css.clipPath !== 'none' || css.clip !== 'auto' || css.maskImage !== 'none') return [];
        const box = el.getBoundingClientRect();
        const overflowX = ['hidden', 'clip', 'scroll', 'auto'].includes(css.overflowX);
        const overflowY = ['hidden', 'clip', 'scroll', 'auto'].includes(css.overflowY);
        if (overflowX || overflowY) clip = intersect(clip, {
          x: overflowX ? box.x + el.clientLeft : clip.x,
          y: overflowY ? box.y + el.clientTop : clip.y,
          width: overflowX ? el.clientWidth : clip.width,
          height: overflowY ? el.clientHeight : clip.height,
        });
      }
      if (!clip) return [];
      const range = document.createRange();
      range.setStart(node, start); range.setEnd(node, end);
      return [...range.getClientRects()].map(r => intersect(r, clip)).filter(Boolean);
    };
    state.insertions = [];
    state.confirmInsertion = insertion => {
      const current = insertion.ranges.flatMap(([start, end]) =>
        insertion.node.data.slice(start, end) === 'x'
          ? visibleRects(insertion.node, start, end) : []);
      // A later reveal/move cannot validate an earlier snapshot, nor can a
      // node hidden or detached since mutation delivery remain confirmed.
      return JSON.stringify(current) === JSON.stringify(insertion.proof.visible_rects) ? current : [];
    };
    state.mutationObserver = new MutationObserver(records => {
      if (!state.event?.trusted) return;
      const nodes = new Set(records.flatMap(record => record.type === 'characterData'
        ? [record.target] : [...record.addedNodes].flatMap(textNodes)));
      for (const node of nodes) {
        const old = priorText.get(node) || '', text = node.data;
        priorText.set(node, text);
        if ((text.match(/x/g) || []).length <= (old.match(/x/g) || []).length) continue;
        let start = 0, end = text.length, oldEnd = old.length;
        while (start < old.length && start < text.length && old[start] === text[start]) start++;
        while (oldEnd > start && end > start && old[oldEnd-1] === text[end-1]) { oldEnd--; end--; }
        const rects = [], ranges = [];
        for (let i = start; i < end; i++) {
          if (text[i] === 'x') {
            ranges.push([i, i+1]);
            rects.push(...visibleRects(node, i, i+1));
          }
        }
        const proof = {mutation_page_ms: performance.now(), visible_rects: rects};
        state.edit_confirmation.mutations.push(proof);
        state.insertions.push({node, ranges, proof});
      }
    });
    state.mutationObserver.observe(documentElement, {subtree: true, childList: true, characterData: true});
    state.onKey = function onKey(e) {
      if (e.key !== 'x') return;
      window.__b2.event = { startTime: e.timeStamp, trusted: e.isTrusted };
      window.removeEventListener('keydown', onKey, true);
    };
    window.addEventListener('keydown', state.onKey, true);
    if (window.__b2.supported) {
      window.__b2.observer = new PerformanceObserver(list => {
        window.__b2.entries.push(...list.getEntries().map(e => ({
          name:e.name, startTime:e.startTime, duration:e.duration, interactionId:e.interactionId
        })));
        window.__b2.notify?.();
      });
      window.__b2.observer.observe({type:'event', durationThreshold:16});
    }
  }, selector);
  const baseline = await captureBaseline(page, cdp);
  const frame = await witnessFrame(page, cdp, {
    baseline: baseline.frame,
    windowMs: Math.max(500, frameTimeoutMs), clockCheck: skew, region: {selector},
    arm: async () => {
      await cdp.send('Input.dispatchKeyEvent', {type:'keyDown', key:'x', code:'KeyX', text:'x', windowsVirtualKeyCode:88});
      await cdp.send('Input.dispatchKeyEvent', {type:'keyUp', key:'x', code:'KeyX', windowsVirtualKeyCode:88});
      const event = await page.evaluate(() => {
        window.__b2.startPulse();
        const state=window.__b2;
        return {...state.event, unconfirmable:state.insertions.length>0 &&
          state.insertions.every(insertion=>insertion.proof.visible_rects.length===0)};
      });
      if (!event?.trusted) throw new Error('trusted keydown not observed');
      // Acquire the bounded witness sequence before B1's synchronous PNG
      // reader runs. Otherwise that reader can starve acknowledgements while
      // a delayed glyph is still pending. The timestamp window remains W.
      // Empty insertion proofs cannot later pass confirmInsertion's fixed
      // geometry check, so there is no settlement window to establish.
      if (!event.unconfirmable) await page.waitForTimeout(settleMaxWaitMs);
      await page.evaluate(() => clearInterval(window.__b2?.pulseTimer));
      return event.startTime;
    },
  });
  // Check the document before waiting for Event Timing delivery. A later edit
  // cannot retroactively turn an earlier caret frame into the edit's paint.
  const confirmation = await page.evaluate(({selector, frameTime}) => {
    const state = window.__b2;
    const proof = state.edit_confirmation;
    const after = (document.querySelector(selector).textContent.match(/x/g) || []).length;
    const eligible = state.insertions.filter(m => frameTime !== null && m.proof.mutation_page_ms <= frameTime + 2);
    return {...proof, after_count: after, confirmed: false,
      visible_rects: eligible.flatMap(state.confirmInsertion), changed_pixels: 0};
  }, {selector, frameTime: frame.frame_page_ms});
  let confirmationFramePageMs = frame.frame_page_ms;
  confirmation.settled_channel_tolerance = DEFAULT_CHANNEL_TOLERANCE;
  confirmation.settled_quiescence_ms = quiescenceMs;
  confirmation.settle_max_wait_ms = settleMaxWaitMs;
  confirmation.frame_collection = 'before_document_witness_decode';
  let settleFailure = null;
  if (baseline.frame && confirmation.visible_rects.length && frame.document_region?.device_pixel_ratio > 0) {
    const event = await page.evaluate(() => window.__b2?.event);
    const recorder = baseline.recorder;
    const beforePixels = decodePng(Buffer.from(baseline.frame.data, 'base64'));
    const region = frame.document_region;
    const doc = region.rect_css_px;
    const dpr = region.device_pixel_ratio;
    const clock = {
      time_origin_ms: frame.time_origin_ms,
      timestamp_kind: frame.timestamp_kind,
      monotonic_origin_ms: skew.monotonic_origin_ms,
    };
    const markerMs = typeof event?.startTime === 'number' ? event.startTime : frame.after_page_ms;
    if (clock.timestamp_kind === 'monotonic_seconds' && typeof clock.monotonic_origin_ms !== 'number') {
      settleFailure = 'monotonic_origin_missing';
    } else if (typeof markerMs === 'number') {
      const recorded = [];
      let decision;
      const classifier = createRegionClassifier({baseline:baseline.frame.data,
        rects:confirmation.visible_rects,dpr,doc,tolerance:DEFAULT_CHANNEL_TOLERANCE});
      try {
        // Classification runs off-thread; CDP remains free to acknowledge
        // every frame while the recorded snapshot is processed.
        // W has elapsed in arm(). Snapshot all evidence, sort by timestamp,
        // and classify through the decision time, including late delivery.
        const snapshot=[...recorder.frames].sort((a,b)=>
          convertFrameToPageMs(a,clock)-convertFrameToPageMs(b,clock));
        for (const candidate of snapshot) {
          if (candidate.ack !== 'acked' || !candidate.data) continue;
          const pageMs = convertFrameToPageMs(candidate,clock);
          if (pageMs === null || pageMs < markerMs || pageMs > markerMs + settleMaxWaitMs) continue;
          const classification = await classifier.classify(candidate.data);
          recorded.push({frame:candidate,pageMs,...classification});
          decision = settleFrames(recorded, {quietMs:quiescenceMs,maxWaitMs:settleMaxWaitMs,
            markerMs,minPixels:Math.ceil(DEFAULT_MIN_PIXELS*dpr*dpr),tolerance:DEFAULT_CHANNEL_TOLERANCE,
            frameIntervalMs:skew.frame_interval_ms});
          // All snapshot frames at or before this decision are now classified.
          // Include equal timestamps too, before accepting the prefix.
          const next=snapshot[snapshot.indexOf(candidate)+1];
          if (!decision.failure_reason && (!next || convertFrameToPageMs(next,clock)>pageMs)) break;
        }
        decision = settleFrames(recorded, {quietMs:quiescenceMs,maxWaitMs:settleMaxWaitMs,
          markerMs,minPixels:Math.ceil(DEFAULT_MIN_PIXELS*dpr*dpr),tolerance:DEFAULT_CHANNEL_TOLERANCE,
          frameIntervalMs:skew.frame_interval_ms});
      } finally {await classifier.close();}
      confirmation.frame_diagnostic = recorded.map(({frame,pageMs,ink_pixels,regions}) =>
        ({seq:frame.seq,page_ms:pageMs,delay_ms:pageMs-markerMs,ink_pixels,regions}));
      confirmation.settle_decision = decision;
      settleFailure = decision.failure_reason || null;
      if (!settleFailure) {
        const chosen = recorded[decision.reference_index];
        const reference = {...chosen,page_ms:chosen.pageMs};
        const first = recorded[decision.match_index];
        const match = {...first,page_ms:first.pageMs};
        if (match) {
          const matchPixels = decodePng(Buffer.from(match.frame.data, 'base64'));
          confirmation.rect_damage = rectDamageVsBaseline(
            beforePixels, matchPixels, confirmation.visible_rects, dpr, doc, DEFAULT_CHANNEL_TOLERANCE,
          );
          confirmation.changed_pixels = confirmation.rect_damage.reduce((sum, row) => sum + row.changed_pixels, 0);
          confirmation.baseline_seq = baseline.frame.seq;
          confirmation.settled_seq = reference.frame.seq;
          confirmation.witness_seq = match.frame.seq;
          confirmation.witness_page_ms = match.page_ms;
          confirmation.settled_page_ms = reference.page_ms;
          confirmation.settle_reference_seq = reference.frame.seq;
          confirmationFramePageMs = match.page_ms;
          confirmation.confirmed = (
            confirmation.after_count > confirmation.before_count
            && confirmation.changed_pixels >= DEFAULT_MIN_PIXELS
          );
        } else if (!settleFailure) {
          settleFailure = 'settle_not_reached';
        }
      }
    }
  }
  confirmation.settle_failure = settleFailure;
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
  const duration = confirmationFramePageMs === null || !timing.event
    ? null
    : confirmationFramePageMs - timing.event.startTime;
  const ok = frame.outcome === 'witnessed' && frame.document_scoped && frame.clock_skew_acceptable && confirmation.confirmed && duration !== null && duration >= 0;
  return { mechanism, clock_skew:skew, witness:frame, event_timing:timing, edit_confirmation:confirmation,
    timestamp_note: 'Uncorrected frame-to-page conversion; page_offset_ms is not a conversion correction. See clock_skew conversion bounds.',
    outcome: ok ? 'measured' : 'failed',
    failure_reason: ok ? null : ((settleFailure === 'witness_sparse' || settleFailure === 'monotonic_origin_missing' ? settleFailure : null) || (!confirmation.confirmed && confirmation.changed_pixels < DEFAULT_MIN_PIXELS
      ? 'expected_edit_not_confirmed'
      : settleFailure || (!frame.clock_skew_acceptable ? 'clock_check_not_acceptable' : !frame.document_scoped ? 'not_document_scoped' : frame.outcome !== 'witnessed' ? 'no_frame' : !confirmation.confirmed ? 'expected_edit_not_confirmed' : 'negative_input_latency'))),
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

  await stopRecorder(cdp);
  const reloadT0 = Date.now();
  await coldPage.reload({ waitUntil: 'domcontentloaded', timeout: 120_000 });
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
    note: [payload.ready.note, 'ready_ms and first_usable_ms in criteria mode measure domcontentloaded to ready; pair and fresh modes include navigation.'].filter(Boolean).join(' '),
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
