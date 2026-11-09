/**
 * Document-structure probes for C11 (initial layout/pagination), C12
 * (incremental reflow), C14 (large-document scaling) and C15 (search/replace)
 * on published-package browser hosts.
 *
 * One invocation measures one sample against one already-running host. The
 * Python driver (perf/runner/benchmark_document.py) starts and stops each host
 * and decides how many samples a cell gets.
 *
 * Clocks, and what each one is allowed to claim:
 *   load    first-contentful-paint comes from `performance.getEntriesByType('paint')`
 *           (a browser paint entry). The first document block/page element is a
 *           DOM check sampled on the next animation frame; it is reported beside
 *           the paint entry, never substituted for it.
 *   reflow  the sample is input (Enter at the document start) to the first
 *           compositor frame captured by `Page.startScreencast` at or after the
 *           document anchor was observed to move down. A frame that arrives
 *           before the y-shift is not the sample.
 *   scale   the sample is navigation to the first compositor frame at or after
 *           the document became usable (element present, laid out, non-empty
 *           text). Screencast starts before navigation.
 *   find    the editor's own find widget is opened with its shortcut. Typing in
 *           it is the input; the editor's own match count is the acknowledgement.
 *           No widget means `not_applicable` with the reason, never a zero.
 *
 * Usage (from repo root, with a dev server already listening):
 *   node perf/runner/document_probe.mjs --mode load \
 *     --url http://127.0.0.1:5208/ --corpus /abs/fixture.docx \
 *     --corpus-route /corpus.docx --doc-selector ".doc-paragraph" \
 *     --page-model continuous_flow --ready-selector ".status-ok"
 */
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const here = path.dirname(new URL(import.meta.url).pathname);
const repoRoot = path.resolve(here, '../..');
const uiRoot = path.resolve(repoRoot, 'harness/ui');

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

const MODES = new Set(['load', 'reflow', 'scale', 'find']);
const mode = opt.mode;
if (!MODES.has(mode)) {
  console.error('document_probe: --mode must be one of load|reflow|scale|find');
  process.exit(2);
}
const url = opt.url;
const corpusFile = opt.corpus;
const corpusRoute = opt['corpus-route'] || '/corpus.docx';
const readySelector = opt['ready-selector'] || '';
const readyJs = opt['ready-js'] || '';
const waitAfterReadyMs = Number(opt['wait-after-ready'] || 0);
const docSelector = opt['doc-selector'] || '';
const pageSelector = opt['page-selector'] || '';
const pageModel = opt['page-model'] || (pageSelector ? 'page' : 'continuous_flow');
const editSelector = opt['edit-selector'] || docSelector;
const settleMs = Number(opt['settle-ms'] || 0);
const timeoutMs = Number(opt['timeout-ms'] || 120000);
const anchorIndex = Number(opt['anchor-index'] || 1);
const minTextChars = Number(opt['min-text-chars'] || 8);
const findInputSelector = opt['find-input-selector'] || '';
const findCountSelector = opt['find-count-selector'] || '';
const findMatchSelector = opt['find-match-selector'] || '';
const findQuery = opt['find-query'] || '';
const findExpected = opt['find-expected-matches'] ? Number(opt['find-expected-matches']) : null;
const findShortcuts = (opt['find-shortcuts'] || 'Control+f,Meta+f').split(',').map((s) => s.trim()).filter(Boolean);

if (!url || !corpusFile) {
  console.error('document_probe: --url and --corpus are required');
  process.exit(2);
}
if (!docSelector && mode !== 'find') {
  console.error('document_probe: --doc-selector is required for mode ' + mode);
  process.exit(2);
}

const corpusBytes = fs.readFileSync(corpusFile);

async function loadPlaywright() {
  const spec = path.join(uiRoot, 'node_modules/playwright/index.mjs');
  return import(pathToFileURL(spec).href);
}

async function routeCorpus(context) {
  await context.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname === corpusRoute) {
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

async function waitForReady(page) {
  const t0 = Date.now();
  const deadline = t0 + timeoutMs;
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
  } else if (readySelector) {
    await page.waitForSelector(readySelector, { timeout: timeoutMs, state: 'visible' });
  }
  if (waitAfterReadyMs > 0 && Date.now() < deadline) {
    await page.waitForTimeout(waitAfterReadyMs);
  }
  return Date.now() - t0;
}

/** Paint entries, read once after the page is usable. */
async function paintEntries(page) {
  return page.evaluate(() => performance.getEntriesByType('paint').map((e) => ({ name: e.name, start_ms: e.startTime })));
}

function fcpFrom(paints) {
  const row = (paints || []).find((p) => p.name === 'first-contentful-paint');
  return row ? Number(row.start_ms) : null;
}

/** In-page DOM observation, installed before navigation. */
const INIT_SCRIPT = ({ docSel, pageSel, minTextChars }) => {
  const state = (window.__docProbeState = {
    firstElementAt: null,
    firstElementInfo: null,
    pageCountAtFirst: null,
    docTextAt: null,
    docTextCharsAt: null,
  });
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    if (!(r.width > 0 && r.height > 0)) return null;
    return { text: (el.textContent || '').trim().slice(0, 40), width: Math.round(r.width), height: Math.round(r.height) };
  };
  const docText = () =>
    Array.from(document.querySelectorAll(docSel))
      .map((el) => (el.textContent || '').trim())
      .filter(Boolean)
      .join(' ');
  const tick = () => {
    if (state.firstElementAt === null) {
      const target = pageSel ? document.querySelector(pageSel) : document.querySelector(docSel);
      const info = box(target);
      if (info) {
        state.firstElementAt = performance.now();
        state.firstElementInfo = info;
        state.pageCountAtFirst = pageSel ? document.querySelectorAll(pageSel).length : null;
      }
    }
    if (state.docTextAt === null) {
      const text = docText();
      if (text.length >= minTextChars) {
        state.docTextAt = performance.now();
        state.docTextCharsAt = text.length;
      }
    }
    const done = state.firstElementAt !== null && state.docTextAt !== null;
    if (!done && performance.now() < 120000) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
};

async function newPage(browser, { withScreencast = false } = {}) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await routeCorpus(context);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
  await page.addInitScript(INIT_SCRIPT, { docSel: docSelector, pageSel: pageSelector, minTextChars: minTextChars });
  let frames = null;
  let cdp = null;
  if (withScreencast) {
    cdp = await context.newCDPSession(page);
    frames = [];
    cdp.on('Page.screencastFrame', async (ev) => {
      frames.push(ev.metadata.timestamp * 1000);
      try {
        await cdp.send('Page.screencastFrameAck', { sessionId: ev.sessionId });
      } catch {
        /* ack races with stop; harmless */
      }
    });
    await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 40, everyNthFrame: 1, maxWidth: 1280, maxHeight: 900 });
  }
  return { context, page, frames, cdp, errors };
}

async function stopScreencast(ctx) {
  if (!ctx.cdp) return;
  try {
    await ctx.cdp.send('Page.stopScreencast');
  } catch {
    /* already stopped */
  }
}

async function launch() {
  const { chromium } = await loadPlaywright();
  return chromium.launch({ headless: true, args: ['--font-render-hinting=none', '--disable-lcd-text'] });
}

async function stateSnapshot(page) {
  return page.evaluate(
    ({ docSel, pageSel }) => {
      const s = window.__docProbeState || {};
      const pageEl = pageSel ? document.querySelector(pageSel) : null;
      const docText = Array.from(document.querySelectorAll(docSel))
        .map((el) => (el.textContent || '').trim())
        .filter(Boolean)
        .join(' ');
      return {
        first_element_ms: s.firstElementAt === null || s.firstElementAt === undefined ? null : s.firstElementAt,
        first_element_info: s.firstElementInfo || null,
        document_text_at_ms: s.docTextAt === null || s.docTextAt === undefined ? null : s.docTextAt,
        document_text_chars_at: s.docTextCharsAt === null || s.docTextCharsAt === undefined ? null : s.docTextCharsAt,
        page_count_at_first: s.pageCountAtFirst === null || s.pageCountAtFirst === undefined ? null : s.pageCountAtFirst,
        page_count: pageSel ? document.querySelectorAll(pageSel).length : null,
        page_text_chars: pageEl ? (pageEl.textContent || '').trim().length : null,
        document_text_chars: docText.length,
        document_text: docText.slice(0, 4000),
        time_origin_ms: performance.timeOrigin,
      };
    },
    { docSel: docSelector, pageSel: pageSelector },
  );
}

async function runLoad(browser) {
  const ctx = await newPage(browser);
  try {
    const navT0 = Date.now();
    await ctx.page.goto(url, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    const navigationMs = Date.now() - navT0;
    const readyMs = await waitForReady(ctx.page);
    if (settleMs > 0) await ctx.page.waitForTimeout(settleMs);
    const paints = await paintEntries(ctx.page);
    const snap = await stateSnapshot(ctx.page);
    const fcp = fcpFrom(paints);
    return {
      mode: 'load',
      driver: 'playwright',
      url,
      navigation_ms: navigationMs,
      ready_ms: readyMs,
      paints,
      fcp_ms: fcp,
      first_element_ms: snap.first_element_ms,
      first_element_info: snap.first_element_info,
      first_element_selector: pageSelector || docSelector,
      document_text_at_ms: snap.document_text_at_ms,
      first_element_delta_from_fcp_ms:
        fcp !== null && snap.first_element_ms !== null ? snap.first_element_ms - fcp : null,
      document_text_ms_delta_from_fcp_ms:
        fcp !== null && snap.document_text_at_ms !== null ? snap.document_text_at_ms - fcp : null,
      page_model: pageModel,
      page_count: snap.page_count,
      page_count_at_first: snap.page_count_at_first,
      document_text_chars: snap.document_text_chars,
      document_text: snap.document_text,
      page_errors: ctx.errors,
    };
  } finally {
    await ctx.context.close();
  }
}

async function runScale(browser) {
  const ctx = await newPage(browser, { withScreencast: true });
  try {
    const navT0 = Date.now();
    await ctx.page.goto(url, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    const navigationMs = Date.now() - navT0;
    const readyMs = await waitForReady(ctx.page);
    if (settleMs > 0) await ctx.page.waitForTimeout(settleMs);
    const snap = await stateSnapshot(ctx.page);
    const paints = await paintEntries(ctx.page);
    await ctx.page.waitForTimeout(120);
    await stopScreencast(ctx);
    const usableMs = snap.document_text_at_ms;
    const usableEpoch = usableMs === null ? null : snap.time_origin_ms + usableMs;
    const frames = (ctx.frames || []).slice().sort((a, b) => a - b);
    const after = usableEpoch === null ? [] : frames.filter((ts) => ts >= usableEpoch);
    const presented = after.length ? after[0] - snap.time_origin_ms : null;
    return {
      mode: 'scale',
      driver: 'playwright',
      url,
      navigation_ms: navigationMs,
      ready_ms: readyMs,
      paints,
      fcp_ms: fcpFrom(paints),
      usable_ms: usableMs,
      usable_source: 'document_text_laid_out',
      first_element_ms: snap.first_element_ms,
      page_model: pageModel,
      page_count: snap.page_count,
      document_text_chars: snap.document_text_chars,
      document_text: snap.document_text,
      presented_frame_ms: presented,
      frames_total: frames.length,
      frames_after_usable: after.length,
      frame_source: 'cdp_screencast',
      page_errors: ctx.errors,
    };
  } finally {
    await stopScreencast(ctx);
    await ctx.context.close();
  }
}

async function runReflow(browser) {
  const ctx = await newPage(browser, { withScreencast: true });
  try {
    const navT0 = Date.now();
    await ctx.page.goto(url, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    const navigationMs = Date.now() - navT0;
    const readyMs = await waitForReady(ctx.page);
    if (settleMs > 0) await ctx.page.waitForTimeout(settleMs);

    const before = await ctx.page.evaluate(
      ({ docSel }) => {
        const blocks = Array.from(document.querySelectorAll(docSel));
        if (blocks.length < 2) {
          return { ok: false, reason: 'fewer than two document blocks; nothing below the insertion to move' };
        }
        const counts = new Map();
        for (const block of blocks) {
          const text = (block.textContent || '').trim();
          if (!text) continue;
          counts.set(text, (counts.get(text) || 0) + 1);
        }
        // The anchor is a block with unique text below the insertion point. Index
        // identity is not usable: inserting at the top renumbers every block and
        // makes an unchanged index look like an unchanged position.
        let anchor = null;
        for (let i = blocks.length - 1; i >= 1; i--) {
          const text = (blocks[i].textContent || '').trim();
          if (text && counts.get(text) === 1) {
            anchor = { el: blocks[i], index: i, text };
            break;
          }
        }
        if (!anchor) {
          return {
            ok: false,
            reason: 'no block below the insertion point has unique non-empty text; a y-shift could not be attributed',
            blocks: blocks.length,
          };
        }
        window.__c12AnchorEl = anchor.el;
        window.__c12AnchorTop = anchor.el.getBoundingClientRect().top;
        return {
          ok: true,
          blocks: blocks.length,
          anchor_index: anchor.index,
          anchor_text: anchor.text,
          anchor_top: window.__c12AnchorTop,
          first_block_top: blocks[0].getBoundingClientRect().top,
          first_block_text: (blocks[0].textContent || '').trim().slice(0, 40),
        };
      },
      { docSel: docSelector },
    );
    if (!before.ok) {
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        error: before.reason,
      };
    }

    const box = await ctx.page.locator(editSelector).first().boundingBox();
    if (!box) {
      return {
        mode: 'reflow',
        driver: 'playwright',
        url,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
        error: 'edit target has no box',
      };
    }
    await ctx.page.mouse.click(box.x + 3, box.y + Math.min(8, Math.max(2, box.height / 2)));
    await ctx.page.waitForTimeout(150);
    await ctx.page.keyboard.press('Control+Home');
    await ctx.page.waitForTimeout(150);
    await ctx.page.keyboard.press('Home');
    await ctx.page.waitForTimeout(100);

    const inputEpoch = Date.now();
    await ctx.page.keyboard.press('Enter');
    await ctx.page.keyboard.type('x', { delay: 0 });

    const shift = await ctx.page.evaluate(
      async ({ docSel, anchorText, beforeTop, timeoutMs }) => {
        const started = Date.now();
        const locate = () => {
          const kept = window.__c12AnchorEl;
          if (kept && kept.isConnected) {
            const text = (kept.textContent || '').trim();
            if (text === anchorText) return { el: kept, by: 'element' };
          }
          const match = Array.from(document.querySelectorAll(docSel)).find(
            (block) => (block.textContent || '').trim() === anchorText,
          );
          return match ? { el: match, by: 'text' } : null;
        };
        while (Date.now() - started < timeoutMs) {
          const hit = locate();
          if (hit) {
            const top = hit.el.getBoundingClientRect().top;
            if (top > beforeTop + 0.5) {
              return {
                moved: true,
                observed_epoch_ms: Date.now(),
                block_count: document.querySelectorAll(docSel).length,
                anchor_top_after: top,
                matched_by: hit.by,
              };
            }
          }
          await new Promise((r) => requestAnimationFrame(r));
        }
        const hit = locate();
        return {
          moved: false,
          observed_epoch_ms: null,
          block_count: document.querySelectorAll(docSel).length,
          anchor_top_after: hit ? hit.el.getBoundingClientRect().top : null,
          matched_by: hit ? hit.by : null,
        };
      },
      { docSel: docSelector, anchorText: before.anchor_text, beforeTop: before.anchor_top, timeoutMs: 3000 },
    );

    await ctx.page.waitForTimeout(120);
    await stopScreencast(ctx);
    const frames = (ctx.frames || []).slice().sort((a, b) => a - b);
    const firstAfterInput = frames.find((ts) => ts >= inputEpoch);
    const afterObserved = shift.moved ? frames.filter((ts) => ts >= shift.observed_epoch_ms) : [];
    const presented = afterObserved.length ? afterObserved[0] : null;

    return {
      mode: 'reflow',
      driver: 'playwright',
      url,
      navigation_ms: navigationMs,
      ready_ms: readyMs,
      before,
      anchor_index: before.anchor_index,
      anchor_text: before.anchor_text,
      shift_px: shift.moved ? shift.anchor_top_after - before.anchor_top : null,
      moved: shift.moved,
      matched_by: shift.matched_by,
      block_count_before: before.blocks,
      block_count_after: shift.block_count,
      insertion_created_block: shift.block_count > before.blocks,
      anchor_top_after: shift.anchor_top_after,
      input_wall_ms: inputEpoch,
      shift_observed_wall_ms: shift.observed_epoch_ms,
      first_frame_after_input_ms: firstAfterInput ? firstAfterInput - inputEpoch : null,
      presented_frame_ms: presented ? presented - inputEpoch : null,
      frames_total: frames.length,
      frames_after_shift_observed: afterObserved.length,
      frame_source: 'cdp_screencast',
      page_errors: ctx.errors,
    };
  } finally {
    await stopScreencast(ctx);
    await ctx.context.close();
  }
}

async function findWidget(page) {
  for (const shortcut of findShortcuts) {
    await page.keyboard.press(shortcut);
    try {
      await page.waitForSelector(findInputSelector, { state: 'visible', timeout: 1500 });
      return { opened: true, shortcut };
    } catch {
      /* try the next binding */
    }
  }
  return { opened: false, shortcut: null };
}

async function runFind(browser) {
  const ctx = await newPage(browser);
  try {
    const navT0 = Date.now();
    await ctx.page.goto(url, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    const navigationMs = Date.now() - navT0;
    const readyMs = await waitForReady(ctx.page);
    if (settleMs > 0) await ctx.page.waitForTimeout(settleMs);
    if (!findInputSelector || !findQuery) {
      return {
        mode: 'find',
        status: 'not_applicable',
        reason: 'probe has no find-input-selector/find-query for this host',
        navigation_ms: navigationMs,
        ready_ms: readyMs,
      };
    }
    const opened = await findWidget(ctx.page);
    if (!opened.opened) {
      return {
        mode: 'find',
        status: 'not_applicable',
        reason:
          'no find widget appears after ' +
          findShortcuts.join('/') +
          ' (selector ' +
          findInputSelector +
          ' not visible)',
        shortcuts_tried: findShortcuts,
        navigation_ms: navigationMs,
        ready_ms: readyMs,
      };
    }
    await ctx.page.locator(findInputSelector).first().click({ timeout: 5000 });
    await ctx.page.evaluate(
      ({ countSel, matchSel, expected }) => {
        const probe = (window.__findProbe = { first_at: null, complete_at: null, last: '', expected: expected });
        const read = () => {
          const el = countSel ? document.querySelector(countSel) : null;
          const text = el ? (el.textContent || '').trim() : '';
          const matches = matchSel ? document.querySelectorAll(matchSel).length : null;
          return { text, matches };
        };
        const total = (text, matches) => {
          if (typeof matches === 'number') return matches;
          const numbers = (text.match(/\d+/g) || []).map(Number);
          return numbers.length ? Math.max.apply(null, numbers) : null;
        };
        const check = () => {
          const now = read();
          const changed = now.text !== probe.last;
          probe.last = now.text;
          if (changed && probe.first_at === null && now.text) probe.first_at = performance.now();
          const count = total(now.text, now.matches);
          const done =
            probe.expected === null ? Boolean(now.text) && !changed : count !== null && count === probe.expected;
          if (done && probe.complete_at === null) probe.complete_at = performance.now();
        };
        probe.check = check;
        const obs = new MutationObserver(check);
        obs.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true });
        probe.stop = () => obs.disconnect();
        check();
      },
      { countSel: findCountSelector, matchSel: findMatchSelector, expected: findExpected },
    );
    const inputEpoch = Date.now();
    await ctx.page.keyboard.type(findQuery, { delay: 0 });
    await ctx.page.waitForTimeout(2000);
    const observed = await ctx.page.evaluate(() => {
      const probe = window.__findProbe || {};
      const origin = performance.timeOrigin;
      const toEpoch = (v) => (v === null || v === undefined ? null : origin + v);
      const out = {
        first_match_ms: probe.first_at === null || probe.first_at === undefined ? null : probe.first_at,
        search_complete_ms: probe.complete_at === null || probe.complete_at === undefined ? null : probe.complete_at,
        last_count_text: probe.last || '',
        first_match_epoch_ms: toEpoch(probe.first_at),
        search_complete_epoch_ms: toEpoch(probe.complete_at),
      };
      if (probe.stop) probe.stop();
      return out;
    });
    return {
      mode: 'find',
      status: 'measured',
      shortcut: opened.shortcut,
      navigation_ms: navigationMs,
      ready_ms: readyMs,
      query: findQuery,
      expected_matches: findExpected,
      first_match_ms: observed.first_match_epoch_ms === null ? null : observed.first_match_epoch_ms - inputEpoch,
      search_complete_ms:
        observed.search_complete_epoch_ms === null ? null : observed.search_complete_epoch_ms - inputEpoch,
      observed_count_text: observed.last_count_text,
      input_wall_ms: inputEpoch,
      page_errors: ctx.errors,
    };
  } finally {
    await ctx.context.close();
  }
}

const browser = await launch();
try {
  let result;
  if (mode === 'load') result = await runLoad(browser);
  else if (mode === 'scale') result = await runScale(browser);
  else if (mode === 'reflow') result = await runReflow(browser);
  else result = await runFind(browser);
  process.stdout.write(JSON.stringify(result));
} catch (error) {
  process.stdout.write(JSON.stringify({ mode, status: 'probe_error', reason: String(error && error.message ? error.message : error).slice(0, 500) }));
  process.exitCode = 1;
} finally {
  await browser.close();
}
