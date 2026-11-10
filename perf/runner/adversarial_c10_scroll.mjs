/**
 * B5 — the C10 scroll probe (#106).
 *
 * The defect this probe fixes: the old one looked for an element with a
 * scroll range, and when it found none it *skipped the scroll*, timed two
 * `requestAnimationFrame` callbacks anyway and published the elapsed time as
 * `outcome: "measured"`. The published medians (apryse 14 ms, docxodus 16 ms,
 * docen 31 ms) were one frame of nothing at all. A shadow-DOM scroller was
 * never even looked for, because `document.querySelectorAll('*')` does not
 * pierce a shadow root.
 *
 * What this probe does instead:
 *
 *   1. it *finds* the scroll container, piercing every **open** shadow root
 *      (a closed shadow root is not reachable from the page at all, and the
 *      refusal says so);
 *   2. it *scrolls* it and records the container's selector, the shadow host
 *      chain it lives under, and the `scrollTop` before and after — a scroll
 *      that does not move `scrollTop` is not a scroll;
 *   3. it *witnesses the frame* with B1c's shared module (`witness.mjs`): the
 *      first presented frame at or after the scroll whose pixels really
 *      changed, converted into the page's own clock, with the clock-skew
 *      bound recorded and enforced;
 *   4. it refuses, with a reason, whenever there is no container, the
 *      container does not move, the skew is above the bound or no frame showed
 *      the change. `measured` is never a word the probe uses without a
 *      scroll it can point at.
 *
 * The output is one JSON object on stdout: the per-sample records (each with
 * its container, its `scrollTop` delta and its witness record) and the
 * overall outcome. The Python side (`adversarial_c10_scroll.py`) is the
 * authority: it re-validates every witness with B1c's reader
 * (`perf/runner/witness.py`) before a sample may become a measured number.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  DEFAULT_SKEW_BOUND_MS,
  clockSkew,
  getRecorder,
  loadPlaywright,
  witnessFrame,
} from './witness.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));

const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (!a.startsWith('--')) continue;
  const key = a.slice(2);
  const next = argv[i + 1];
  if (next === undefined || next.startsWith('--')) opt[key] = true;
  else {
    opt[key] = next;
    i++;
  }
}

const url = opt.url;
const corpusFile = opt.corpus;
const corpusRoute = opt['corpus-route'] || '/corpus.docx';
const sampleRoute = opt['sample-route'] || corpusRoute;
const readySelector = opt['ready-selector'] || '.status-ok';
const readyJs = opt['ready-js'] || '';
const readyText = opt['ready-text'] || '';
const pairs = Math.max(1, Number(opt.pairs || 3));
const waitAfterReadyMs = Number(opt['wait-after-ready'] || 0);
/** How far the probe scrolls, in CSS pixels. A wheel gesture, not a jump. */
const scrollStep = Math.max(1, Number(opt['scroll-step'] || 600));
/** The witness window. The plan asks for at least 500 ms. */
const windowMs = Math.max(500, Number(opt['window-ms'] || 900));
/** The clock-skew bound; the sample is refused above it. */
const skewBoundMs = Number(opt['skew-bound-ms'] || DEFAULT_SKEW_BOUND_MS);
const viewport = String(opt.viewport || '1280x900')
  .split('x')
  .map((value) => Number(value) || 1280);

const corpusBytes = fs.readFileSync(corpusFile);

/**
 * The page-side command. It is serialized into the browser as one function,
 * so every helper it uses lives inside it.
 *
 * Commands:
 *   `{op: 'discover'}`          → the scroll containers, the shadow roots that
 *                                  were searched and the elements that were
 *                                  inspected.
 *   `{op: 'reset', index}`      → put the container back at the top.
 *   `{op: 'scroll', index}`     → scroll the container down by `step` pixels
 *                                  and report the `scrollTop` delta.
 */
function pageScrollCommand(command) {
  const op = (command && command.op) || 'discover';

  const cssPath = (el) => {
    const parts = [];
    let node = el;
    let guard = 0;
    while (node && node.nodeType === 1 && guard++ < 12) {
      let part = node.tagName ? node.tagName.toLowerCase() : '?';
      if (node.id) {
        part += '#' + node.id;
      } else if (typeof node.className === 'string' && node.className.trim()) {
        part += '.' + node.className.trim().split(/\s+/).slice(0, 2).join('.');
      }
      parts.unshift(part);
      if (node.parentElement) {
        node = node.parentElement;
        continue;
      }
      const root = node.getRootNode ? node.getRootNode() : null;
      node = root && root.host ? root.host : null;
    }
    return parts.join(' > ');
  };

  const shortSelector = (el) => {
    if (el.id) return '#' + el.id;
    const full = cssPath(el);
    return full.split(' > ').pop() || full;
  };

  const measure = (el, hostChain) => {
    const style = getComputedStyle(el);
    const overflowY = style.overflowY || 'visible';
    return {
      selector: shortSelector(el),
      path: cssPath(el),
      tag: el.tagName.toLowerCase(),
      id: el.id || null,
      overflow_y: overflowY,
      scroll_height: el.scrollHeight,
      client_height: el.clientHeight,
      scroll_range: el.scrollHeight - el.clientHeight,
      in_shadow_root: hostChain.length > 0,
      shadow_hosts: hostChain.slice(),
      is_viewport: false,
    };
  };

  /**
   * Walk the document and every open shadow root under it. A closed shadow
   * root is not reachable from the page: `element.shadowRoot` is null for it,
   * so it is invisible here too — the refusal says so.
   */
  const scan = () => {
    const records = [];
    const elements = [];
    const hidden = [];
    const shadowRoots = [];
    let inspected = 0;

    const visit = (root, hostChain) => {
      const found = root.querySelectorAll('*');
      for (const el of found) {
        inspected += 1;
        const record = measure(el, hostChain);
        if (record.scroll_range > 0) {
          if (/^(auto|scroll|overlay)$/.test(record.overflow_y)) {
            records.push(record);
            elements.push(el);
          } else {
            hidden.push(record);
          }
        }
        if (el.shadowRoot) {
          const hostPath = cssPath(el);
          shadowRoots.push(hostPath);
          visit(el.shadowRoot, hostChain.concat([hostPath]));
        }
      }
    };
    visit(document, []);

    // The viewport scrolls whatever its computed overflow says, so the
    // document scroller is a candidate in its own right.
    const scroller = document.scrollingElement || document.documentElement;
    if (scroller) {
      const record = measure(scroller, []);
      record.is_viewport = true;
      if (record.scroll_range > 0) {
        records.push(record);
        elements.push(scroller);
        const at = hidden.findIndex((row) => row.path === record.path);
        if (at >= 0) hidden.splice(at, 1);
      }
    }

    const order = records
      .map((record, index) => ({ record, index }))
      .sort((a, b) => b.record.scroll_range - a.record.scroll_range);
    return {
      records: order.map((entry) => entry.record),
      elements: order.map((entry) => elements[entry.index]),
      hidden: hidden.sort((a, b) => b.scroll_range - a.scroll_range),
      shadowRoots,
      inspected,
    };
  };

  if (op === 'discover') {
    const found = scan();
    return {
      candidates: found.records,
      hidden: found.hidden,
      shadow_roots: found.shadowRoots,
      elements_inspected: found.inspected,
    };
  }

  const found = scan();
  const index = Number(command.index || 0);
  const el = found.elements[index];
  if (!el) {
    return { error: 'no scroll container at index ' + index };
  }
  const record = found.records[index];
  const range = Math.max(0, el.scrollHeight - el.clientHeight);

  if (op === 'reset') {
    const before = el.scrollTop;
    el.scrollTop = 0;
    return {
      page_ms: performance.now(),
      scroll_top_before: before,
      scroll_top_after: el.scrollTop,
      scroll_top_delta: el.scrollTop - before,
      scroll_range: range,
      container: record || null,
    };
  }

  const before = el.scrollTop;
  const at = performance.now();
  const target = Math.min(range, before + Math.max(1, Number(command.step || 600)));
  el.scrollTop = target;
  const after = el.scrollTop;
  return {
    page_ms: at,
    scroll_top_before: before,
    scroll_top_after: after,
    scroll_top_delta: after - before,
    scroll_range: range,
    container: record || null,
  };
}

async function waitForReady(page) {
  if (readyJs) {
    await page.waitForFunction(
      (expr) => {
        try {
          return Boolean(eval(expr)); // eslint-disable-line no-eval
        } catch {
          return false;
        }
      },
      readyJs,
      { timeout: 120_000 },
    );
  } else if (readyText) {
    await page.waitForFunction(
      ({ text }) => (document.body.innerText || '').includes(text),
      { text: readyText },
      { timeout: 120_000 },
    );
  } else {
    await page.waitForSelector(readySelector, { timeout: 120_000, state: 'visible' });
  }
  if (waitAfterReadyMs > 0) await page.waitForTimeout(waitAfterReadyMs);
}

/**
 * The reason a sample has no container. It names the shadow roots that were
 * searched, so a shadow-DOM host can never be mistaken for a host without a
 * scroller.
 */
function noContainerReason(discovery) {
  const roots = discovery.shadow_roots || [];
  const rootText = roots.length
    ? 'open shadow roots searched: ' + roots.join(', ')
    : 'no open shadow root in the page (a closed shadow root is not reachable from the page)';
  const hidden = discovery.hidden || [];
  const hiddenText = hidden.length
    ? '; ' + hidden.length + ' element(s) with a scroll range use overflow-y ' +
      hidden.map((row) => row.overflow_y).filter((value, at, all) => all.indexOf(value) === at).join('/')
    : '';
  return (
    'no scroll container: ' +
    (discovery.elements_inspected || 0) +
    ' element(s) inspected, ' +
    rootText +
    hiddenText +
    '; no element with overflow-y auto|scroll and a scroll range above 0 was found'
  );
}

async function oneSample(context, page) {
  const cdp = await context.newCDPSession(page);
  const recorder = getRecorder(cdp, { manageScreencast: true });

  const skew = await clockSkew(page, cdp, { boundMs: skewBoundMs, recorder });
  if (!skew.acceptable) {
    const why =
      skew.skew_ms === null || skew.skew_ms === undefined
        ? 'the screencast timestamp kind is ' + skew.timestamp_kind +
          ', so a frame cannot be placed in the page clock'
        : 'the clock skew ' + skew.skew_ms + ' ms is above the bound of ' + skew.bound_ms + ' ms';
    return {
      outcome: 'failed',
      reason: 'clock_skew_above_bound: ' + why,
      clock_skew: skew,
      witness: null,
      container: null,
      scroll_top_before: null,
      scroll_top_after: null,
      scroll_top_delta: null,
      scroll_frame_ms: null,
    };
  }

  const discovery = await page.evaluate(pageScrollCommand, { op: 'discover' });
  if (!discovery.candidates || !discovery.candidates.length) {
    return {
      outcome: 'not_applicable',
      reason: noContainerReason(discovery),
      clock_skew: skew,
      witness: null,
      container: null,
      scroll_top_before: null,
      scroll_top_after: null,
      scroll_top_delta: null,
      scroll_frame_ms: null,
      search: discovery,
    };
  }

  // Put the container at the top before the baseline is taken, so the frame
  // the witness compares against is the one the scroll starts from.
  await page.evaluate(pageScrollCommand, { op: 'reset', index: 0 });

  let scroll = null;
  const arm = async () => {
    scroll = await page.evaluate(pageScrollCommand, {
      op: 'scroll',
      index: 0,
      step: scrollStep,
    });
    return { after_page_ms: scroll.page_ms };
  };

  const witness = await witnessFrame(page, cdp, {
    arm,
    recorder,
    clockSkewMs: skew.skew_ms,
    windowMs,
  });

  const container = scroll && scroll.container ? scroll.container : null;
  const delta = scroll ? scroll.scroll_top_delta : null;
  if (!scroll || scroll.error) {
    return {
      outcome: 'failed',
      reason: 'the scroll could not be applied: ' + ((scroll && scroll.error) || 'no container'),
      clock_skew: skew,
      witness,
      container,
      scroll_top_before: null,
      scroll_top_after: null,
      scroll_top_delta: null,
      scroll_frame_ms: null,
      search: discovery,
    };
  }
  if (!(delta > 0)) {
    return {
      outcome: 'failed',
      reason:
        'the scroll did not move: scrollTop stayed at ' + scroll.scroll_top_after +
        ' (range ' + scroll.scroll_range + ' px)',
      clock_skew: skew,
      witness,
      container,
      scroll_top_before: scroll.scroll_top_before,
      scroll_top_after: scroll.scroll_top_after,
      scroll_top_delta: delta,
      scroll_frame_ms: null,
      search: discovery,
    };
  }
  if (witness.outcome !== 'witnessed' || typeof witness.frame_page_ms !== 'number') {
    return {
      outcome: 'failed',
      reason:
        'no_frame: the witness saw no frame that showed the scroll (frames after the ' +
        'scroll: ' + witness.frames_after + ', biggest pixel difference: ' +
        witness.max_diff_ratio + ')',
      clock_skew: skew,
      witness,
      container,
      scroll_top_before: scroll.scroll_top_before,
      scroll_top_after: scroll.scroll_top_after,
      scroll_top_delta: delta,
      scroll_frame_ms: null,
      search: discovery,
    };
  }

  return {
    outcome: 'measured',
    reason: null,
    clock_skew: skew,
    witness,
    container,
    scroll_top_before: scroll.scroll_top_before,
    scroll_top_after: scroll.scroll_top_after,
    scroll_top_delta: delta,
    scroll_frame_ms: witness.frame_page_ms - scroll.page_ms,
    search: discovery,
  };
}

async function routeCorpus(context) {
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname === corpusRoute || u.pathname === sampleRoute) {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: corpusBytes,
      });
      return;
    }
    await route.continue();
  });
}

const { chromium } = await loadPlaywright();
const samples = [];
try {
  for (let i = 0; i < pairs; i++) {
    const browser = await chromium.launch({ headless: true });
    try {
      const context = await browser.newContext({
        viewport: { width: viewport[0], height: viewport[1] },
      });
      await routeCorpus(context);
      const page = await context.newPage();
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
      await waitForReady(page);
      const sample = await oneSample(context, page);
      samples.push({ sample_index: i, ...sample });
      await context.close().catch(() => {});
    } finally {
      await browser.close().catch(() => {});
    }
  }
} catch (error) {
  process.stdout.write(
    JSON.stringify({
      status: 'error',
      outcome: 'failed',
      reason: 'the probe failed: ' + (error && error.message ? error.message : String(error)),
      samples,
    }) + '\n',
  );
  process.exit(1);
}

const measured = samples.filter((sample) => sample.outcome === 'measured');
const refused = samples.filter((sample) => sample.outcome !== 'measured');
const payload = {
  status: 'ok',
  outcome: measured.length ? 'measured' : refused.length ? refused[0].outcome : 'failed',
  reason: measured.length ? null : refused.length ? refused[0].reason : 'the probe produced no sample',
  samples,
  scroll_step_px: scrollStep,
  witness_window_ms: windowMs,
  skew_bound_ms: skewBoundMs,
};
process.stdout.write(JSON.stringify(payload));
