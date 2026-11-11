/**
 * B5 — the C10 scroll probe (#106; the #134 fixes).
 *
 * The defect this probe fixes: the old one looked for an element with a
 * scroll range, and when it found none it *skipped the scroll*, timed two
 * `requestAnimationFrame` callbacks and published the elapsed time as
 * `outcome: "measured"`. The published medians (apryse 14 ms, docxodus 16 ms,
 * docen 31 ms) were one frame of nothing at all. A shadow-DOM scroller was
 * never even looked for, because `document.querySelectorAll('*')` does not
 * pierce a shadow root.
 *
 * What this probe does instead:
 *
 *   1. it *finds* the scroll container, piercing every **open** shadow root
 *      (a closed shadow root is not reachable from the page at all, and the
 *      refusal says so). The container is the scroller that holds the
 *      **document text** — not the scroller with the largest range. A
 *      scroller that holds the document's text (the deepest-text owner, not
 *      the innermost survivor). A textless page uses the scroller that
 *      covers at least half the viewport (`container_rule: surface`). An
 *      editor adapter may name one with `--container-selector`
 *      (`container_rule: adapter`). `--scroll-container` is the same flag.
 *   2. it *scrolls* it and records the container's selector, the shadow host
 *      chain it lives under, the `scrollTop` before and after and the
 *      **content probe**: the position of the scrolled content before and
 *      after, and the text visible at the top of the scroller before and
 *      after. A scroll that does not move `scrollTop`, or that does not move
 *      the content with it, is not a scroll.
 *   3. it *witnesses the frame* with B1c's shared module (`witness.mjs`):
 *      the first presented frame at or after the scroll whose pixels really
 *      changed **inside the scrolled container** (the document region), in
 *      the page's own clock, against the run's clock check (with its pixel
 *      anchor). Damage outside the document cannot pose as document paint.
 *   4. it refuses, with a reason, whenever there is no container, the
 *      container holds no document text, the container does not move, the
 *      content does not move, the skew is above the bound or no frame showed
 *      the change. `measured` is never a word the probe uses without a
 *      scroll it can point at.
 *
 * The output is one JSON object on stdout: the per-sample records (each with
 * its container, its `scrollTop` delta, its content probe and its witness
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
  clockSkewRefusalReason,
  getRecorder,
  loadPlaywright,
  witnessFrame,
} from './witness.mjs';
import { startChromeTrace, stopChromeTrace } from './chrome_trace.mjs';
import { loadTimeoutMs } from './load_timeout.mjs';

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
/** How far the probe scrolls, in CSS pixels: a scrollTop jump of one step. */
const scrollStep = Math.max(1, Number(opt['scroll-step'] || 600));
/** The witness window. The plan asks for at least 500 ms. */
const windowMs = Math.max(500, Number(opt['window-ms'] || 900));
/** The clock-skew bound; the sample is refused above it. */
const skewBoundMs = Number(opt['skew-bound-ms'] || DEFAULT_SKEW_BOUND_MS);
// Lax layer (owner 2026-11-11): ready/navigation waits are minutes, not 120 s.
const loadTimeout = loadTimeoutMs();
/** The operator's scroll container (`a >> b` walks into an open shadow root). */
const containerOverride =
  (typeof opt['container-selector'] === 'string' && opt['container-selector']) ||
  (typeof opt['scroll-container'] === 'string' && opt['scroll-container']) ||
  '';
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
 *                                  inspected and the container the probe chose.
 *   `{op: 'mask-caret'}`        → mask the caret inside every open shadow root
 *                                  (`addStyleTag` only reaches the light DOM).
 *   `{op: 'reset', index}`      → put the container back at the top.
 *   `{op: 'scroll', index}`     → scroll the container down by `step` pixels
 *                                  and report the `scrollTop` delta, the
 *                                  content probe and the scroll event.
 *   `{op: 'scroll-event'}`      → the scroll event the last scroll produced.
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

  const trimLen = (text) => (text || '').trim().length;

  /**
   * The text in an element's subtree, including that element's own shadow
   * root. `textContent` does not cross a shadow boundary, and a shadow root
   * is not a child node, so a host that is itself the scroller would
   * otherwise count as empty.
   *
   * Script and style source is not document text.
   */
  const fullText = (el) => {
    let total = 0;
    const skip = (node) => {
      if (!node || node.nodeType !== 1 || !node.tagName) return false;
      const tag = node.tagName.toLowerCase();
      return tag === 'script' || tag === 'style' || tag === 'noscript';
    };
    const walk = (node) => {
      if (!node || skip(node)) return;
      if (node.nodeType === 3) {
        total += trimLen(node.nodeValue);
        return;
      }
      if (node.nodeType === 1 && node.shadowRoot) walk(node.shadowRoot);
      const children = node.childNodes || [];
      for (let i = 0; i < children.length; i++) walk(children[i]);
    };
    walk(el);
    return total;
  };

  /** The children that scroll with this element, its own shadow root included. */
  const flowChildren = (root) => {
    if (!root) return [];
    if (root.shadowRoot && root.shadowRoot.children && root.shadowRoot.children.length) {
      return root.shadowRoot.children;
    }
    return root.children || [];
  };

  /** Is `inner` inside `outer`? The path crosses shadow hosts, so it does. */
  const nestedIn = (outer, inner) =>
    inner.path.length > outer.path.length && inner.path.startsWith(outer.path + ' > ');

  /** The visible box of a scroller, in CSS pixels. */
  const boxRect = (el, isViewport) => {
    if (isViewport) {
      return { x: 0, y: 0, width: window.innerWidth, height: window.innerHeight };
    }
    const r = el.getBoundingClientRect();
    return { x: r.left, y: r.top, width: r.width, height: r.height };
  };

  /**
   * The element whose position proves that the content moved.
   *
   * It must be an element *in the scrolled flow*: a fixed or sticky child
   * (a load veil, a floating toolbar) does not move when the scroller
   * scrolls, so it proves nothing. The tallest in-flow child is the
   * scrolled content.
   */
  const contentProbe = (root) => {
    if (!root) return null;
    const kids = flowChildren(root);
    let best = null;
    for (let i = 0; i < kids.length; i++) {
      const kid = kids[i];
      const tag = (kid.tagName || '').toLowerCase();
      if (tag === 'script' || tag === 'style' || tag === 'link') continue;
      const style = getComputedStyle(kid);
      if (style.position === 'fixed' || style.position === 'sticky') continue;
      const rect = kid.getBoundingClientRect();
      const text = trimLen(kid.textContent);
      if (!(rect.height > 0 || text)) continue;
      if (!best || rect.height > best.height) {
        best = { selector: shortSelector(kid), rect_top: rect.top, height: rect.height };
      }
    }
    return best;
  };

  /** The text visible at the top of the scroller: what the reader sees. */
  const visibleContent = (root, box) => {
    if (!root) return null;
    const kids = flowChildren(root);
    for (let i = 0; i < kids.length; i++) {
      const kid = kids[i];
      const tag = (kid.tagName || '').toLowerCase();
      if (tag === 'script' || tag === 'style' || tag === 'link') continue;
      const style = getComputedStyle(kid);
      if (style.position === 'fixed' || style.position === 'sticky') continue;
      const rect = kid.getBoundingClientRect();
      if (rect.height <= 0) continue;
      if (rect.bottom <= box.y || rect.top >= box.y + box.height) continue;
      const text = trimLen(kid.textContent);
      if (!text) continue;
      return { selector: shortSelector(kid), text: (kid.textContent || '').trim().slice(0, 120) };
    }
    return null;
  };

  const measure = (el, hostChain, isViewport) => {
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
      is_viewport: !!isViewport,
      opacity: style.opacity === '' ? 1 : Number(style.opacity),
      visibility: style.visibility || 'visible',
      display: style.display || 'block',
      aria_hidden: !!(el.getAttribute && el.getAttribute('aria-hidden') === 'true'),
      // The text is counted for the candidates only: counting it for every
      // element of the page would walk the whole document once per element.
      text_chars: 0,
      own_text_chars: 0,
      container_rule: null,
      region_rect: boxRect(el, isViewport),
    };
  };

  /** Why a scroller cannot show the document, or '' when it can. */
  const invisibleReason = (record) => {
    if (record.display === 'none') return 'display:none';
    if (record.visibility === 'hidden') return 'visibility:hidden';
    if (record.opacity !== null && record.opacity <= 0.01) return 'opacity:0';
    if (record.aria_hidden) return 'aria-hidden=true';
    const rect = record.region_rect || {};
    if (!(rect.width > 0) || !(rect.height > 0)) return 'no visible box';
    const vw = window.innerWidth || 0;
    const vh = window.innerHeight || 0;
    if (rect.x + rect.width <= 0 || rect.y + rect.height <= 0) return 'outside the viewport';
    if (rect.x >= vw || rect.y >= vh) return 'outside the viewport';
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
    const hidden = [];
    const shadowRoots = [];
    let inspected = 0;

    const visit = (root, hostChain) => {
      const found = root.querySelectorAll('*');
      for (const el of found) {
        inspected += 1;
        const record = measure(el, hostChain, false);
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
      const record = measure(scroller, [], true);
      record.is_viewport = true;
      if (record.scroll_range > 0) {
        records.push(record);
        elements.push(scroller);
        const at = hidden.findIndex((row) => row.path === record.path);
        if (at >= 0) hidden.splice(at, 1);
      }
    }

    // The text each candidate *scrolls itself*: its own text minus the text
    // of the scrollers nested inside it. A shell that contains the document
    // box holds the shell's text, not the document's.
    for (let at = 0; at < records.length; at++) {
      const record = records[at];
      record.text_chars = fullText(elements[at]);
    }
    for (const record of records) {
      let own = record.text_chars;
      for (const other of records) {
        if (other === record) continue;
        if (nestedIn(record, other)) own -= other.text_chars;
      }
      record.own_text_chars = Math.max(0, own);
    }

    const order = records
      .map((record, index) => ({ record, index }))
      .sort((a, b) => {
        const text = b.record.own_text_chars - a.record.own_text_chars;
        if (text !== 0) return text;
        const range = b.record.scroll_range - a.record.scroll_range;
        if (range !== 0) return range;
        return a.index - b.index;
      });
    // Deepest-text owner: each character belongs to the innermost scroller
    // that contains it (`own_text_chars`). The document's scroller is the
    // owner of that text, not the innermost scroller that happens to contain
    // some of it. A nested note loses to the scroller that holds the document.
    const pageText = fullText(document.body || document.documentElement);
    let owned = 0;
    for (const record of records) owned += record.own_text_chars;
    const outside = Math.max(0, pageText - owned);
    const viewportArea = Math.max(1, (window.innerWidth || 0) * (window.innerHeight || 0));
    const eligible = order.filter((entry) => !invisibleReason(entry.record));
    let chosen = null;
    let containerRule = null;
    let chosenReason = 'no scroller holds the document text';
    if (pageText > 0) {
      const holders = eligible.filter((entry) => entry.record.own_text_chars > 0);
      holders.sort((a, b) => {
        const text = b.record.own_text_chars - a.record.own_text_chars;
        if (text !== 0) return text;
        // Shallower wins a tie: the document, not the note nested inside it.
        const depth = (a.record.path || '').length - (b.record.path || '').length;
        if (depth !== 0) return depth;
        return a.index - b.index;
      });
      const best = holders[0];
      if (best && best.record.own_text_chars > outside) {
        chosen = best;
        containerRule = 'text';
        chosenReason =
          'the scroller that holds the document text (' +
          best.record.own_text_chars +
          ' characters; the deepest text owner)';
      } else if (holders.length) {
        chosenReason =
          'the document has no scroller: the document text is not inside a scroller (' +
          holders
            .map((entry) => entry.record.selector + ': ' + entry.record.own_text_chars + ' chars')
            .join(', ') +
          ')';
      }
    } else {
      const areaOf = (record) => {
        const rect = record.region_rect || {};
        return Math.max(0, Number(rect.width) || 0) * Math.max(0, Number(rect.height) || 0);
      };
      const covering = eligible.filter((entry) => areaOf(entry.record) / viewportArea >= 0.5);
      covering.sort((a, b) => {
        const area = areaOf(b.record) - areaOf(a.record);
        if (area !== 0) return area;
        return b.record.scroll_range - a.record.scroll_range;
      });
      if (covering.length) {
        chosen = covering[0];
        containerRule = 'surface';
        chosenReason =
          'the page carries no text; the container is the scroller that covers the document surface';
      } else {
        chosenReason =
          'the page carries no text and no scroll container covers at least half the viewport';
      }
    }
    if (chosen) chosen.record.container_rule = containerRule;
    return {
      records: order.map((entry) => entry.record),
      elements: order.map((entry) => elements[entry.index]),
      hidden: hidden.sort((a, b) => b.scroll_range - a.scroll_range),
      shadowRoots,
      inspected,
      chosen_index: chosen ? order.findIndex((entry) => entry.record === chosen.record) : -1,
      chosen_reason: chosenReason,
      container_rule: containerRule,
    };
  };

  /** The operator's container: `a >> b` walks into an open shadow root. */
  const resolveOverride = (selector) => {
    const parts = String(selector || '')
      .split('>>')
      .map((part) => part.trim())
      .filter(Boolean);
    if (!parts.length) return null;
    let node = document;
    for (const part of parts) {
      if (!node) return null;
      if (node === document) node = document.querySelector(part);
      else if (node.shadowRoot) node = node.shadowRoot.querySelector(part);
      else return null;
      if (!node) return null;
    }
    return node;
  };

  if (op === 'mask-caret') {
    // `addStyleTag` styles the light DOM only: a caret inside a shadow root
    // keeps blinking, and a blinking caret is a frame that changes for a
    // reason that has nothing to do with the scroll.
    const masked = [];
    const visit = (root) => {
      for (const el of root.querySelectorAll('*')) {
        if (!el.shadowRoot) continue;
        try {
          const style = document.createElement('style');
          style.textContent = '* { caret-color: transparent !important }';
          el.shadowRoot.appendChild(style);
          masked.push(cssPath(el));
        } catch (error) {
          /* a closed shadow root is not reachable from the page */
        }
        visit(el.shadowRoot);
      }
    };
    visit(document);
    return { masked_roots: masked, count: masked.length };
  }

  if (op === 'discover') {
    const found = scan();
    let chosen = -1;
    let reason = null;
    const override = resolveOverride(command && command.container);
    let rule = found.container_rule || null;
    if (override) {
      const at = found.elements.indexOf(override);
      if (at >= 0) {
        chosen = at;
        reason = 'the operator named the scroll container';
        rule = 'adapter';
        if (found.records[at]) found.records[at].container_rule = 'adapter';
      } else {
        reason = 'the operator named a scroll container that is not a scroller';
        rule = null;
      }
    } else if (command && command.container) {
      reason = 'container_selector_not_found';
      rule = null;
    } else {
      chosen = found.chosen_index;
      reason = found.chosen_reason;
    }
    return {
      candidates: found.records,
      hidden: found.hidden,
      shadow_roots: found.shadowRoots,
      elements_inspected: found.inspected,
      chosen_index: chosen,
      chosen_reason: reason,
      container_rule: rule,
    };
  }

  if (op === 'scroll-event') {
    return { scroll_event: window.__b5ScrollEvent || null };
  }

  const found = scan();
  const index = Number(command.index || 0);
  const el = found.elements[index];
  if (!el) {
    return { error: 'no scroll container at index ' + index };
  }
  const record = found.records[index];
  const range = Math.max(0, el.scrollHeight - el.clientHeight);
  const isViewport = !!(record && record.is_viewport);
  const box = boxRect(el, isViewport);
  const contentRoot = isViewport ? document.body || document.documentElement : el;

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
      region_rect: box,
    };
  }

  // The scroll event: the frame in which the scroll was applied. It is the
  // page's own statement that the content moved, at a known page time.
  window.__b5ScrollEvent = { page_ms: null, content_top: null };
  const onScroll = () => {
    const probe = contentProbe(contentRoot);
    window.__b5ScrollEvent = {
      page_ms: performance.now(),
      content_top: probe ? probe.rect_top : null,
    };
  };
  const eventTarget = isViewport ? document : el;
  eventTarget.addEventListener('scroll', onScroll, { once: true, passive: true });

  const visibleBefore = visibleContent(contentRoot, box);
  const probeBefore = contentProbe(contentRoot);
  const before = el.scrollTop;
  const at = performance.now();
  const target = Math.min(range, before + Math.max(1, Number(command.step || 600)));
  el.scrollTop = target;
  const after = el.scrollTop;
  const probeAfter = contentProbe(contentRoot);
  const visibleAfter = visibleContent(contentRoot, box);
  return {
    page_ms: at,
    scroll_top_before: before,
    scroll_top_after: after,
    scroll_top_delta: after - before,
    scroll_range: range,
    container: record || null,
    region_rect: box,
    content: {
      probe_selector: probeBefore ? probeBefore.selector : null,
      top_before: probeBefore ? probeBefore.rect_top : null,
      top_after: probeAfter ? probeAfter.rect_top : null,
      moved_px: probeBefore && probeAfter ? probeBefore.rect_top - probeAfter.rect_top : null,
      visible_selector_before: visibleBefore ? visibleBefore.selector : null,
      visible_selector_after: visibleAfter ? visibleAfter.selector : null,
      visible_text_before: visibleBefore ? visibleBefore.text : null,
      visible_text_after: visibleAfter ? visibleAfter.text : null,
    },
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
      { timeout: loadTimeout },
    );
  } else if (readyText) {
    await page.waitForFunction(
      ({ text }) => (document.body.innerText || '').includes(text),
      { text: readyText },
      { timeout: loadTimeout },
    );
  } else {
    await page.waitForSelector(readySelector, { timeout: loadTimeout, state: 'visible' });
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
  const hidden = discovery.hidden || [];
  const hiddenText = hidden.length
    ? '; ' + hidden.length + ' element(s) with a scroll range use overflow-y ' +
      hidden.map((row) => row.overflow_y).filter((value, at, all) => all.indexOf(value) === at).join('/')
    : '';
  const candidates = discovery.candidates || [];
  const withoutText = candidates.filter((row) => !(row.own_text_chars > 0));
  const textText = candidates.length
    ? withoutText.length === candidates.length
      ? '; ' + candidates.length + ' scroller(s) were found and none of them holds the document text (' +
        candidates.map((row) => row.selector + ': ' + row.own_text_chars + ' chars').join(', ') + ')'
      : ''
    : '; no element with overflow-y auto|scroll and a scroll range above 0 was found';
  const ruleText = discovery.chosen_reason ? '; ' + discovery.chosen_reason : '';
  return (
    'no scroll container: ' +
    (discovery.elements_inspected || 0) +
    ' element(s) inspected, ' +
    rootText +
    hiddenText +
    textText +
    ruleText
  );
}

async function oneSample(context, page) {
  const cdp = await context.newCDPSession(page);
  const recorder = getRecorder(cdp, { manageScreencast: true });

  const skew = await clockSkew(page, cdp, { boundMs: skewBoundMs, recorder });
  if (!skew.acceptable) {
    return {
      outcome: 'failed',
      reason: clockSkewRefusalReason(skew),
      clock_skew: skew,
      witness: null,
      container: null,
      scroll_top_before: null,
      scroll_top_after: null,
      scroll_top_delta: null,
      scroll_frame_ms: null,
    };
  }

  // The caret mask must reach inside the shadow roots: `addStyleTag` only
  // styles the light DOM, and a blinking caret is damage that has nothing to
  // do with the scroll.
  const caretMask = await page.evaluate(pageScrollCommand, { op: 'mask-caret' });

  const discovery = await page.evaluate(pageScrollCommand, {
    op: 'discover',
    container: containerOverride,
  });
  if (!discovery.candidates || !discovery.candidates.length || discovery.chosen_index < 0) {
    const reason = containerOverride
      ? 'no scroll container: the operator named ' + containerOverride + ' and ' +
        (discovery.chosen_reason || 'it is not a scroller') +
        '; ' + noContainerReason(discovery)
      : noContainerReason(discovery);
    return {
      outcome: 'not_applicable',
      reason,
      clock_skew: skew,
      caret_mask_in_shadow_roots: caretMask,
      witness: null,
      container: null,
      scroll_top_before: null,
      scroll_top_after: null,
      scroll_top_delta: null,
      scroll_frame_ms: null,
      search: discovery,
    };
  }

  const chosen = discovery.candidates[discovery.chosen_index];

  // Put the container at the top before the baseline is taken, so the frame
  // the witness compares against is the one the scroll starts from.
  await page.evaluate(pageScrollCommand, { op: 'reset', index: discovery.chosen_index });

  let scroll = null;
  const arm = async () => {
    scroll = await page.evaluate(pageScrollCommand, {
      op: 'scroll',
      index: discovery.chosen_index,
      step: scrollStep,
    });
    return { after_page_ms: scroll.page_ms };
  };

  const witness = await witnessFrame(page, cdp, {
    arm,
    recorder,
    // The run's clock check, with its pixel anchor: a bare page offset is
    // not a check (#130).
    clockCheck: skew,
    windowMs,
    // The document region: the scrolled container. Damage outside the
    // document cannot pose as the document's paint (#130).
    region: { rect: chosen.region_rect },
  });

  const scrollEvent = await page.evaluate(pageScrollCommand, { op: 'scroll-event' });
  const container = scroll && scroll.container ? scroll.container : null;
  if (container) {
    container.container_rule = discovery.container_rule || container.container_rule || null;
  }
  const delta = scroll ? scroll.scroll_top_delta : null;
  const content = (scroll && scroll.content) || null;
  if (!scroll || scroll.error) {
    return {
      outcome: 'failed',
      reason: 'the scroll could not be applied: ' + ((scroll && scroll.error) || 'no container'),
      clock_skew: skew,
      caret_mask_in_shadow_roots: caretMask,
      witness,
      container,
      content,
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
      caret_mask_in_shadow_roots: caretMask,
      witness,
      container,
      content,
      scroll_top_before: scroll.scroll_top_before,
      scroll_top_after: scroll.scroll_top_after,
      scroll_top_delta: delta,
      scroll_frame_ms: null,
      search: discovery,
    };
  }
  if (!(content && content.moved_px > 0)) {
    return {
      outcome: 'failed',
      reason:
        'the scroll did not move the content: the content of the scroller stayed at ' +
        (content && content.top_after) + ' (the scrollTop moved by ' + delta + ' px)',
      clock_skew: skew,
      caret_mask_in_shadow_roots: caretMask,
      witness,
      container,
      content,
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
      caret_mask_in_shadow_roots: caretMask,
      witness,
      container,
      content,
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
    caret_mask_in_shadow_roots: caretMask,
    witness,
    container,
    content,
    scroll_event: scrollEvent && scrollEvent.scroll_event ? scrollEvent.scroll_event : null,
    scroll_top_before: scroll.scroll_top_before,
    scroll_top_after: scroll.scroll_top_after,
    scroll_top_delta: delta,
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
      const trace = await startChromeTrace(browser, page, 'C10');
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: loadTimeout });
      await waitForReady(page);
      const sample = await oneSample(context, page);
      samples.push({ sample_index: i, ...sample });
      await stopChromeTrace(browser, trace);
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
  load_timeout_ms: loadTimeout,
  witness_window_ms: windowMs,
  skew_bound_ms: skewBoundMs,
  scroll_container_override: containerOverride || null,
};
process.stdout.write(JSON.stringify(payload));
