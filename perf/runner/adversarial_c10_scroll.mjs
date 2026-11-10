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
 *   1. it *finds the scroll container of the document*, piercing every
 *      **open** shadow root (a closed shadow root is not reachable from the
 *      page at all, and the refusal says so). The container is the scroller
 *      that **holds the document's text** — not the element with the largest
 *      scroll range, which is how a hidden probe box (docen's `aria-hidden`
 *      scroll proxy) or a small widget used to win. When the page carries no
 *      text at all (a canvas editor), the container is the scroller that
 *      covers the document's surface. A per-host override
 *      (`--container-selector`) is allowed and is recorded.
 *   2. it *scrolls* it and records the container's selector, the shadow host
 *      chain it lives under, the `scrollTop` before and after — a scroll that
 *      does not move `scrollTop` is not a scroll — and the **movement of the
 *      document's own content**, which is what proves the document moved and
 *      not merely that a frame changed.
 *   3. it *witnesses the frame* with B1c's shared module (`witness.mjs`): the
 *      first presented frame at or after the scroll whose pixels really
 *      changed **inside the container's own box** (the document region), in
 *      the page's own clock, with the run's clock check (the pixel anchor's
 *      evidence) carried in the record. The clock check of the run is handed
 *      to the witness, so the record carries the anchor's evidence and not a
 *      bare page offset.
 *   4. it refuses, with a reason, whenever there is no container, the
 *      container does not move, the document's content does not move, the
 *      skew is above the bound or no frame showed the change. `measured` is
 *      never a word the probe uses without a scroll it can point at.
 *
 * The output is one JSON object on stdout: the per-sample records (each with
 * its container, its `scrollTop` delta, the content movement and its witness
 * record) and the overall outcome. The Python side
 * (`adversarial_c10_scroll.py`) is the authority: it re-validates every
 * witness with B1c's reader (`perf/runner/witness.py`) before a sample may
 * become a measured number.
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
/** How far the probe scrolls, in CSS pixels: a scrollTop assignment, not a wheel. */
const scrollStep = Math.max(1, Number(opt['scroll-step'] || 600));
/** The witness window. The plan asks for at least 500 ms. */
const windowMs = Math.max(500, Number(opt['window-ms'] || 900));
/** The clock-skew bound; the sample is refused above it. */
const skewBoundMs = Number(opt['skew-bound-ms'] || DEFAULT_SKEW_BOUND_MS);
/**
 * The per-host override: the selector of the element that scrolls the
 * document on this host. It is honoured when it names a scrollable element
 * and it is recorded in the sample, so a measurement taken with an override
 * never looks like an automatic choice.
 */
const containerOverride =
  typeof opt['container-selector'] === 'string' ? opt['container-selector'] : '';
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
 *                                  were searched, the elements that were
 *                                  inspected and the ones that were rejected
 *                                  (with the reason).
 *   `{op: 'mask-caret'}`        → the caret mask inside every open shadow root
 *                                  (a document stylesheet does not reach into
 *                                  a shadow tree).
 *   `{op: 'reset'}`             → put the container back at the top.
 *   `{op: 'scroll'}`            → scroll the container down by `step` pixels
 *                                  and report the `scrollTop` delta and the
 *                                  movement of the document's content.
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

  /** The text an element carries directly (not its descendants'). */
  const ownTextLength = (el) => {
    let total = 0;
    for (const node of el.childNodes) {
      if (node.nodeType === 3) total += (node.nodeValue || '').trim().length;
    }
    return total;
  };

  /**
   * The text of a subtree, shadow roots included: a container that holds a
   * shadow-DOM document holds its text too.
   */
  const subtreeTextLength = (el, guard = 0) => {
    if (guard > 12) return 0;
    let total = ownTextLength(el);
    for (const child of el.children) {
      total += subtreeTextLength(child, guard + 1);
    }
    if (el.shadowRoot) {
      for (const child of el.shadowRoot.children) {
        total += subtreeTextLength(child, guard + 1);
      }
    }
    return total;
  };

  const measure = (el, hostChain, depth) => {
    const style = getComputedStyle(el);
    const overflowY = style.overflowY || 'visible';
    const rect = el.getBoundingClientRect();
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
      depth,
      is_viewport: false,
      opacity: style.opacity === '' ? 1 : Number(style.opacity),
      visibility: style.visibility || 'visible',
      display: style.display || 'block',
      aria_hidden: el.getAttribute ? el.getAttribute('aria-hidden') === 'true' : false,
      client_width: el.clientWidth,
      rect_css_px: {
        x: rect.left,
        y: rect.top,
        width: rect.width,
        height: rect.height,
      },
    };
  };

  /** Why an element cannot be the document's scroller (or '' when it can). */
  const invisibleReason = (record) => {
    if (record.display === 'none') return 'display:none';
    if (record.visibility === 'hidden') return 'visibility:hidden';
    if (record.opacity !== null && record.opacity <= 0.01) return 'opacity:0';
    if (record.aria_hidden) return 'aria-hidden=true';
    if (!(record.client_width > 0) || !(record.client_height > 0)) return 'no visible box';
    const rect = record.rect_css_px;
    if (rect.x + rect.width <= 0 || rect.y + rect.height <= 0) return 'outside the viewport';
    return '';
  };

  /**
   * Walk the document and every open shadow root under it. A closed shadow
   * root is not reachable from the page: `element.shadowRoot` is null for it,
   * so it is invisible here too — the refusal says so.
   */
  const scan = () => {
    const records = [];
    const elements = [];
    const rejected = [];
    const shadowRoots = [];
    let inspected = 0;
    let documentText = 0;

    const visit = (root, hostChain, depth) => {
      const found = root.querySelectorAll('*');
      for (const el of found) {
        inspected += 1;
        documentText += ownTextLength(el);
        const record = measure(el, hostChain, depth);
        if (record.scroll_range > 0) {
          if (/^(auto|scroll|overlay)$/.test(record.overflow_y)) {
            records.push(record);
            elements.push(el);
          } else {
            rejected.push({
              ...record,
              rejected_because: `overflow-y is ${record.overflow_y}: the element does not scroll`,
            });
          }
        }
        if (el.shadowRoot) {
          const hostPath = cssPath(el);
          shadowRoots.push(hostPath);
          visit(el.shadowRoot, hostChain.concat([hostPath]), depth + 1);
        }
      }
    };
    visit(document, [], 1);

    // The viewport scrolls whatever its computed overflow says, so the
    // document scroller is a candidate in its own right.
    const scroller = document.scrollingElement || document.documentElement;
    if (scroller) {
      const record = measure(scroller, [], 1);
      record.is_viewport = true;
      if (record.scroll_range > 0) {
        records.push(record);
        elements.push(scroller);
      }
    }

    return {
      records,
      elements,
      rejected,
      shadowRoots,
      inspected,
      documentText,
    };
  };

  /**
   * The container of the document: the scroller that holds the document's
   * text. The largest scroll range wins nothing here — that is how a hidden
   * probe box or a small widget used to be measured as the document.
   */
  const choose = (scanResult, overrideSelector) => {
    const candidates = scanResult.records;
    const notes = [];
    let chosen = null;

    if (overrideSelector) {
      const index = candidates.findIndex((record) => record.selector === overrideSelector);
      if (index >= 0) {
        chosen = { index, record: candidates[index], how: 'override' };
        notes.push(`the container was taken from the per-host override ${overrideSelector}`);
      } else {
        notes.push(
          `the per-host override ${overrideSelector} names no scroll container here; the automatic choice is used`,
        );
      }
    }

    if (!chosen) {
      // The viewport area, measured in the page (this function is serialized
      // into the browser, so it may not close over the Node side).
      const viewportArea = Math.max(1, (window.innerWidth || 0) * (window.innerHeight || 0));
      const scored = candidates.map((record, index) => {
        const invisible = invisibleReason(record);
        const text = scanResult.documentText > 0 ? subtreeTextLength(scanResult.elements[index]) : 0;
        const share = scanResult.documentText > 0 ? text / scanResult.documentText : 0;
        const area = Math.max(1, record.client_width * record.client_height);
        return { index, record, invisible, text, share, areaShare: area / viewportArea };
      });
      const usable = scored.filter((row) => !row.invisible);
      if (scanResult.documentText > 0) {
        const withText = usable.filter((row) => row.text > 0);
        if (!withText.length) {
          notes.push(
            `no scroll container holds the document's text (${scanResult.documentText} characters in the page)`,
          );
        } else {
          withText.sort((a, b) => {
            if (b.share !== a.share) return b.share - a.share;
            if (b.record.depth !== a.record.depth) return b.record.depth - a.record.depth;
            if (b.record.scroll_range !== a.record.scroll_range)
              return b.record.scroll_range - a.record.scroll_range;
            return a.index - b.index;
          });
          chosen = { index: withText[0].index, record: withText[0].record, how: 'document_text' };
          notes.push(
            `the container is the scroller that holds the document's text (${withText[0].text} of ${scanResult.documentText} characters)`,
          );
        }
      } else {
        const covering = usable.filter((row) => row.areaShare >= 0.5);
        if (!covering.length) {
          notes.push(
            "the page carries no text and no scroll container covers the document's surface",
          );
        } else {
          covering.sort((a, b) => {
            if (b.areaShare !== a.areaShare) return b.areaShare - a.areaShare;
            if (b.record.scroll_range !== a.record.scroll_range)
              return b.record.scroll_range - a.record.scroll_range;
            return a.index - b.index;
          });
          chosen = { index: covering[0].index, record: covering[0].record, how: 'document_surface' };
          notes.push(
            "the page carries no text; the container is the scroller that covers the document's surface",
          );
        }
      }
      for (const row of scored) {
        if (row.invisible) {
          scanResult.rejected.push({
            ...row.record,
            rejected_because: `${row.invisible}: the element cannot show the document`,
          });
        } else if (scanResult.documentText > 0 && row.text <= 0) {
          scanResult.rejected.push({
            ...row.record,
            rejected_because: `the element does not hold the document's text (0 of ${scanResult.documentText} characters)`,
          });
        }
      }
    }

    return { chosen, notes };
  };

  /**
   * The element that shows the document's content inside the container: the
   * first element that carries text, else the container's first child, else
   * the container. Its box moves when the document scrolls — that is the
   * evidence that the *document* scrolled and not merely that a frame
   * changed.
   */
  const contentProbe = (el, isViewport) => {
    const findText = (node, guard) => {
      if (guard > 12) return null;
      for (const child of node.children) {
        if (ownTextLength(child) > 0) return child;
        const deeper = findText(child, guard + 1);
        if (deeper) return deeper;
      }
      return null;
    };
    let target = null;
    if (isViewport) {
      // The scrolling element's own content: its first child that is not
      // head-ish. The head does not move when the page scrolls.
      for (const child of el.children) {
        const tag = (child.tagName || '').toLowerCase();
        if (
          tag === 'head' ||
          tag === 'script' ||
          tag === 'style' ||
          tag === 'link' ||
          tag === 'meta' ||
          tag === 'title'
        ) {
          continue;
        }
        target = child;
        break;
      }
      if (!target) target = el;
    } else {
      target = findText(el, 0);
      if (!target) target = el.firstElementChild || null;
      if (!target) target = el;
    }
    const rect = target.getBoundingClientRect();
    return {
      target_selector: shortSelector(target),
      target_path: cssPath(target),
      top: rect.top,
      left: rect.left,
      height: rect.height,
    };
  };

  if (op === 'mask-caret') {
    // `page.addStyleTag` (the witness's own caret mask) reaches the document
    // only: a stylesheet of the document does not match the elements inside a
    // shadow tree, so a caret blinking in a shadow root would still change
    // the pixels the witness compares.
    const css = '* { caret-color: transparent !important }';
    let masked = 0;
    const visit = (root) => {
      for (const el of root.querySelectorAll('*')) {
        if (!el.shadowRoot) continue;
        try {
          const style = document.createElement('style');
          style.textContent = css;
          el.shadowRoot.appendChild(style);
          masked += 1;
        } catch (error) {
          /* a closed root is not reachable from the page */
        }
        visit(el.shadowRoot);
      }
    };
    visit(document);
    return { caret_mask_shadow_roots: masked };
  }

  const found = scan();

  if (op === 'discover') {
    const { chosen, notes } = choose(found, (command && command.container_selector) || '');
    return {
      candidates: found.records.map((record, index) => ({
        ...record,
        selected: Boolean(chosen && chosen.index === index),
        text_share:
          found.documentText > 0
            ? subtreeTextLength(found.elements[index]) / found.documentText
            : null,
      })),
      rejected: found.rejected,
      shadow_roots: found.shadowRoots,
      elements_inspected: found.inspected,
      document_text_length: found.documentText,
      selection: chosen
        ? {
            index: chosen.index,
            selector: chosen.record.selector,
            how: chosen.how,
            notes,
          }
        : { index: null, selector: null, how: null, notes },
    };
  }

  const { chosen, notes } = choose(found, (command && command.container_selector) || '');
  if (!chosen) {
    return { error: 'no scroll container holds the document', notes, search: null };
  }
  const index = chosen.index;
  const el = found.elements[index];
  const record = found.records[index];
  const range = Math.max(0, el.scrollHeight - el.clientHeight);

  if (op === 'reset') {
    const before = el.scrollTop;
    el.scrollTop = 0;
    const content = contentProbe(el, record.is_viewport);
    return {
      page_ms: performance.now(),
      scroll_top_before: before,
      scroll_top_after: el.scrollTop,
      scroll_top_delta: el.scrollTop - before,
      scroll_range: range,
      container: record || null,
      container_how: chosen.how,
      content_top: content.top,
      content: content,
    };
  }

  const before = el.scrollTop;
  const at = performance.now();
  const target = Math.min(range, before + Math.max(1, Number(command.step || 600)));
  el.scrollTop = target;
  const after = el.scrollTop;
  const content = contentProbe(el, record.is_viewport);
  return {
    page_ms: at,
    scroll_top_before: before,
    scroll_top_after: after,
    scroll_top_delta: after - before,
    scroll_range: range,
    container: record || null,
    container_how: chosen.how,
    content_top: content.top,
    content: content,
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
    : 'no open shadow root in the page (a closed shadow root, if the page has one, is not reachable from the page)';
  const rejected = discovery.rejected || [];
  const hidden = rejected.filter((row) =>
    /opacity|visibility|aria-hidden|outside|no visible box/.test(row.rejected_because || ''),
  );
  const hiddenText = hidden.length
    ? '; ' + hidden.length + ' element(s) with a scroll range are not visible (' +
      hidden
        .slice(0, 4)
        .map((row) => row.selector + ': ' + row.rejected_because)
        .join('; ') +
      ')'
    : '';
  const scrollers = rejected.filter((row) => !hidden.includes(row));
  const scrollerText = scrollers.length
    ? '; rejected scrollers: ' +
      scrollers
        .slice(0, 4)
        .map((row) => row.selector + ' (' + row.rejected_because + ')')
        .join('; ')
    : '';
  const notes = (discovery.selection && discovery.selection.notes) || [];
  const noteText = notes.length ? '; ' + notes.join('; ') : '';
  return (
    'no scroll container: ' +
    (discovery.elements_inspected || 0) +
    ' element(s) inspected, ' +
    rootText +
    hiddenText +
    scrollerText +
    noteText +
    "; no element with overflow-y auto|scroll, a scroll range above 0 and the document's text was found"
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
      content_moved_px: null,
      scroll_frame_ms: null,
    };
  }

  // The caret mask of the document does not reach into a shadow tree.
  const masked = await page.evaluate(pageScrollCommand, { op: 'mask-caret' });

  const discovery = await page.evaluate(pageScrollCommand, {
    op: 'discover',
    container_selector: containerOverride,
  });
  const selection = discovery.selection || {};
  if (!selection.selector) {
    return {
      outcome: 'not_applicable',
      reason: noContainerReason(discovery),
      clock_skew: skew,
      caret_mask_shadow_roots: masked.caret_mask_shadow_roots,
      witness: null,
      container: null,
      scroll_top_before: null,
      scroll_top_after: null,
      scroll_top_delta: null,
      content_moved_px: null,
      scroll_frame_ms: null,
      search: discovery,
    };
  }

  // Put the container at the top before the baseline is taken, so the frame
  // the witness compares against is the one the scroll starts from.
  const reset = await page.evaluate(pageScrollCommand, {
    op: 'reset',
    container_selector: containerOverride,
  });
  if (reset.error) {
    return {
      outcome: 'failed',
      reason: 'the scroll container could not be prepared: ' + reset.error,
      clock_skew: skew,
      caret_mask_shadow_roots: masked.caret_mask_shadow_roots,
      witness: null,
      container: null,
      scroll_top_before: null,
      scroll_top_after: null,
      scroll_top_delta: null,
      content_moved_px: null,
      scroll_frame_ms: null,
      search: discovery,
    };
  }

  let scroll = null;
  const arm = async () => {
    scroll = await page.evaluate(pageScrollCommand, {
      op: 'scroll',
      container_selector: containerOverride,
      step: scrollStep,
    });
    return { after_page_ms: scroll.page_ms };
  };

  // The document region is the container's own box: a change outside it is
  // shell damage, not the document's paint (#130).
  const region =
    reset.container && reset.container.rect_css_px ? { rect: reset.container.rect_css_px } : null;

  const witness = await witnessFrame(page, cdp, {
    arm,
    recorder,
    clockCheck: skew,
    region,
    windowMs,
  });

  const container = scroll && scroll.container ? scroll.container : null;
  const delta = scroll ? scroll.scroll_top_delta : null;
  const contentBefore = reset.content_top;
  const contentAfter = scroll ? scroll.content_top : null;
  const contentMoved =
    typeof contentBefore === 'number' && typeof contentAfter === 'number'
      ? contentBefore - contentAfter
      : null;
  if (!scroll || scroll.error) {
    return {
      outcome: 'failed',
      reason: 'the scroll could not be applied: ' + ((scroll && scroll.error) || 'no container'),
      clock_skew: skew,
      caret_mask_shadow_roots: masked.caret_mask_shadow_roots,
      witness,
      container,
      scroll_top_before: null,
      scroll_top_after: null,
      scroll_top_delta: null,
      content_moved_px: contentMoved,
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
      caret_mask_shadow_roots: masked.caret_mask_shadow_roots,
      witness,
      container,
      scroll_top_before: scroll.scroll_top_before,
      scroll_top_after: scroll.scroll_top_after,
      scroll_top_delta: delta,
      content_moved_px: contentMoved,
      scroll_frame_ms: null,
      search: discovery,
    };
  }
  if (!(contentMoved > 0)) {
    return {
      outcome: 'failed',
      reason:
        'the document did not scroll: the content of the container did not move (before ' +
        contentBefore +
        ', after ' +
        contentAfter +
        ')',
      clock_skew: skew,
      caret_mask_shadow_roots: masked.caret_mask_shadow_roots,
      witness,
      container,
      scroll_top_before: scroll.scroll_top_before,
      scroll_top_after: scroll.scroll_top_after,
      scroll_top_delta: delta,
      content_moved_px: contentMoved,
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
      caret_mask_shadow_roots: masked.caret_mask_shadow_roots,
      witness,
      container,
      scroll_top_before: scroll.scroll_top_before,
      scroll_top_after: scroll.scroll_top_after,
      scroll_top_delta: delta,
      content_moved_px: contentMoved,
      scroll_frame_ms: null,
      search: discovery,
    };
  }

  return {
    outcome: 'measured',
    reason: null,
    clock_skew: skew,
    caret_mask_shadow_roots: masked.caret_mask_shadow_roots,
    witness,
    container,
    container_how: scroll.container_how,
    scroll_top_before: scroll.scroll_top_before,
    scroll_top_after: scroll.scroll_top_after,
    scroll_top_delta: delta,
    content_top_before: contentBefore,
    content_top_after: contentAfter,
    content_moved_px: contentMoved,
    content: scroll.content,
    scroll_frame_ms: Math.round((witness.frame_page_ms - scroll.page_ms) * 1000) / 1000,
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
  container_override: containerOverride || null,
};
process.stdout.write(JSON.stringify(payload));
