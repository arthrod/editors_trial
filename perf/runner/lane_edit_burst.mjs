/**
 * Shared edit path for browser lanes outside the resources CPU sampler (#155.1).
 *
 * prepareEditSurface, caret placement, and verification reads stay outside any
 * measured timing window the lane owns.
 */
import {
  EDIT_SURFACES,
  prepareEditSurface,
  editSurface,
  placeCaret,
  verifyCaretAtParagraphStart,
  waitForTokenDelta,
  readModifiedFlag,
} from './edit_surface.mjs';
import {
  prepareResourceBurst,
  typeResourceBurst,
  verifyResourceBurst,
} from './resource_burst_edit.mjs';

export const LANE_LOAD_TIMEOUT_MS = 600_000;
export const LANE_POLL_BOUND_MS = 600_000;
/** Outside measured windows: poll until Enter+x is visible in the C12 census. */
export const LANE_EDIT_CONFIRM_MS = 10_000;

/**
 * Editors whose C12 has no paragraph geometry (r3lanes4 ruling 4): the host
 * paints whole pages (canvas pixels / a shadow model) and the only DOM box is
 * the page container, which is not a paragraph. A y-shift of the container can
 * never be attributed to one paragraph, so C12 is not_applicable for them —
 * never measured from a page box.
 */
export const C12_NO_PARAGRAPH_GEOMETRY = new Set(['canvas', 'docen']);

/**
 * The C12 anchor: the nearest block BELOW the caret on the same screen
 * (r3c12b ruling 3). Equal text is disambiguated by document-order
 * occurrence among blocks with that text, never by skipping to a farther block.
 *
 * Pure and self-contained (no module references): document_probe passes it
 * into the page as an argument to gatherReflowBefore.
 *
 * entries: [{ text, top }] with tops in CSS px; caret: { top, bottom } or
 * null; viewportHeight: window.innerHeight.
 */
export const PICK_ANCHOR_BELOW = (entries, caret, viewportHeight) => {
  if (!Array.isArray(entries) || entries.length < 2) {
    return { ok: false, reason: 'fewer than two document blocks; nothing below the insertion to move' };
  }
  if (!caret || !Number.isFinite(Number(caret.bottom))) {
    return {
      ok: false,
      reason: 'no caret box at the insertion; the paragraph below the caret cannot be identified',
      blocks: entries.length,
    };
  }
  if (!Number.isFinite(Number(viewportHeight)) || !(viewportHeight > 0)) {
    return {
      ok: false,
      reason: 'viewport height unavailable; a same-screen block below the caret cannot be identified',
      blocks: entries.length,
    };
  }
  let caretIndex = 0;
  if (caret && Number.isFinite(Number(caret.bottom))) {
    for (let idx = 0; idx < entries.length; idx++) {
      const top = Number(entries[idx].top);
      const bottom =
        Number.isFinite(Number(entries[idx].bottom)) && Number(entries[idx].bottom) > top
          ? Number(entries[idx].bottom)
          : top + 1;
      if (Number(caret.bottom) > top + 0.5 && Number(caret.top) < bottom - 0.5) {
        caretIndex = idx;
        break;
      }
    }
  }
  const anchorIndex = caretIndex + 1;
  if (anchorIndex >= entries.length) {
    return {
      ok: false,
      reason: 'no document block below the caret paragraph; a y-shift could not be attributed',
      blocks: entries.length,
    };
  }
  const anchor = entries[anchorIndex];
  const top = Number(anchor.top);
  if (!anchor.text || !Number.isFinite(top)) {
    return {
      ok: false,
      reason: 'anchor paragraph has no measurable box',
      blocks: entries.length,
    };
  }
  if (top >= Number(viewportHeight)) {
    return {
      ok: false,
      reason: 'anchor paragraph is off the viewport; a y-shift could not be attributed',
      blocks: entries.length,
    };
  }
  let occurrence = 0;
  for (let i = 0; i <= anchorIndex; i++) {
    if (entries[i].text === anchor.text) occurrence += 1;
  }
  return {
    ok: true,
    anchorText: anchor.text,
    anchorIndex,
    caretIndex,
    anchorOccurrence: occurrence,
    blockCount: entries.length,
    firstText: String(entries[0].text || '').slice(0, 40),
  };
};


/**
 * Page context: paragraph texts from the canvas/docen model APIs. Used only
 * as C12 evidence (the paragraphs that exist in the model while the DOM has
 * no paragraph boxes); never a measurement path (r3lanes4 ruling 4).
 */
export const LIST_MODEL_PARAGRAPHS = (model) => {
  if (model === 'docen') {
    const editor = window.__DOCEN__ && window.__DOCEN__.editor;
    if (!editor || !editor.state) return null;
    const out = [];
    editor.state.doc.descendants((node) => {
      if (node.isTextblock) {
        const text = String(node.textContent || '').trim();
        if (text) out.push(text);
      }
    });
    return out;
  }
  if (model === 'canvas_editor') {
    const inst = window.__CANVAS_EDITOR_INSTANCE__;
    const cmd = inst && inst.command;
    if (!cmd || typeof cmd.getValue !== 'function') return null;
    const out = [];
    const walk = (node) => {
      if (Array.isArray(node)) return node.forEach(walk);
      if (!node || typeof node !== 'object') return;
      if (typeof node.value === 'string') {
        const text = node.value.trim();
        if (text) out.push(text);
      }
      for (const key of ['valueList', 'trList', 'tdList']) {
        if (node[key]) walk(node[key]);
      }
    };
    const data = cmd.getValue().data;
    if (!data || typeof data !== 'object') return null;
    for (const zone of ['header', 'main', 'footer']) walk(data[zone]);
    return out;
  }
  return null;
};

/** Paint witness region for C12 reflow when it differs from the load surface. */
export function reflowWitnessSelector(editorId) {
  // Docxodus block-editor mode paints only inside #editorHost; the paginated
  // viewer chrome would otherwise pollute the shared documentRegion witness.
  if (editorId === 'docxodus') return '#editorHost';
  return '';
}

/** Block selector for C12 reflow after the shared adapter has entered edit mode. */
export function reflowBlockSelector(editorId, fallback) {
  if (!editorId || !EDIT_SURFACES[editorId]) return fallback;
  if (editorId === 'docxodus') return '#editorHost p';
  if (editorId === 'superdoc') return '#editor .superdoc-line';
  if (editorId === 'genoffice') return '.doc-page.ProseMirror:not(.mp-page) p';
  if (editorId === 'eigenpal') return '.docx-paragraph-fragment';
  if (editorId === 'folio') return '.layout-page-content [data-block-id]';
  if (editorId === 'plate') return '.doc-paragraph';
  const surface = editSurface(editorId);
  if (surface.kind === 'dom' && surface.block) return surface.block;
  return fallback;
}

/** Prose fixture headings at the start of body paragraphs (docx_workload). */
export const C12_PROSE_HEADING_LINE = (text) =>
  /^(Article \d+\.|Section \d+\.\d+\s)/.test(String(text || '').replace(/\s+/g, ' ').trim());

/** Document-order index of the first census block that is not a fixture heading. */
export function c12FirstBodyCaretIndex(entries) {
  const heading = (text) =>
    /^(Article \d+\.|Section \d+\.\d+\s)/.test(String(text || '').replace(/\s+/g, ' ').trim());
  if (!Array.isArray(entries) || !entries.length) {
    return { ok: false, reason: 'no blocks in census' };
  }
  for (let idx = 0; idx < entries.length; idx += 1) {
    const text = String(entries[idx].text || '');
    if (!heading(text)) {
      return { ok: true, caretIndex: idx, caretText: text };
    }
  }
  return { ok: false, reason: 'only heading blocks in census' };
}

/** Refusal-only diagnostic for ruling 3 (a)–(e); paragraph lists truncated. */
export function C12_IDENTITY_REFUSAL_DIAGNOSTIC(snapshot, texts, norm, limit = 8, trunc = 80) {
  const n = (t) => norm(t);
  const clip = (list) => list.slice(0, limit).map((t) => String(t || '').slice(0, trunc));
  const base = {
    caretIndex: snapshot && Number.isFinite(Number(snapshot.caretIndex)) ? Number(snapshot.caretIndex) : null,
    anchorIndex: snapshot && Number.isFinite(Number(snapshot.anchorIndex)) ? Number(snapshot.anchorIndex) : null,
    before_blocks: clip(snapshot && Array.isArray(snapshot.blockTexts) ? snapshot.blockTexts : []),
    after_blocks: clip(texts.map(n)),
    failed: null,
  };
  if (!snapshot || !Array.isArray(snapshot.blockTexts)) {
    return { ...base, failed: 'a' };
  }
  const B = snapshot.blockTexts.map(n);
  const A = texts.map(n);
  const c = Number(snapshot.caretIndex);
  const i = Number(snapshot.anchorIndex);
  if (!Number.isFinite(c) || !Number.isFinite(i) || c < 0 || i < 0) {
    return { ...base, failed: 'a' };
  }
  const anchorText = n(snapshot.anchorText || B[i] || '');
  const beforeCount = B.filter((t) => t === anchorText).length;
  const afterCount = A.filter((t) => t === anchorText).length;
  if (afterCount !== beforeCount) {
    return { ...base, failed: 'b' };
  }
  const joinMid = (parts) => n(parts.filter((p) => n(p)).join(' '));
  const prefixEq = (a, b) => a.length === b.length && a.every((t, k) => t === b[k]);
  const candidates = [];
  for (let j = 0; j < A.length; j++) {
    const delta = j - i;
    if (delta !== 0 && delta !== 1) continue;
    if (!prefixEq(A.slice(0, c), B.slice(0, c))) continue;
    const change = joinMid(A.slice(c, j));
    const expected = n(`x${B[c]}`);
    if (change !== expected) continue;
    const K = Math.max(1, Math.min(5, A.length - j, B.length - i));
    if (!prefixEq(A.slice(j, j + K), B.slice(i, i + K))) continue;
    candidates.push(j);
  }
  if (candidates.length === 1) return base;
  if (!prefixEq(A.slice(0, c), B.slice(0, c))) {
    return { ...base, failed: 'c' };
  }
  const expectedCaret = n(`x${B[c]}`);
  if (n(A[c]) === n(B[c])) {
    return { ...base, failed: 'c' };
  }
  if (n(A[c]) !== expectedCaret) {
    return { ...base, failed: 'd' };
  }
  return { ...base, failed: 'e' };
}

/** Page context: click point at the start of the fixture's first body census block. */
export function c12BodyCaretClick({ editorId, docSel, excludeSel }) {
  const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const readBlock = (block) => {
    if (block && block.classList && block.classList.contains('superdoc-line')) {
      return norm(block.textContent);
    }
    return norm(block.innerText || block.textContent);
  };
  if (typeof c12BlockEntries !== 'function') return { ok: false, reason: 'census unavailable' };
  const entries = c12BlockEntries(String(editorId || ''), docSel, excludeSel || '', readBlock);
  const pick = c12FirstBodyCaretIndex(entries);
  if (!pick.ok || !entries[pick.caretIndex]) return { ok: false, reason: pick.reason || 'no body block' };
  const el = entries[pick.caretIndex].el;
  let click = null;
  try {
    const startMark = el.querySelector && el.querySelector('[data-start="0"]');
    const caretHost = startMark || el;
    caretHost.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    const rect = caretHost.getBoundingClientRect();
    if (rect && rect.height > 0) {
      click = {
        x: rect.left + 1,
        y: rect.top + rect.height / 2,
        line: String(pick.caretText || '').slice(0, 60),
      };
    }
    window.__c12ForcedCaretIndex = pick.caretIndex;
  } catch {
    return { ok: false, reason: 'could not resolve body block click point' };
  }
  if (!click) return { ok: false, reason: 'body block has no click box' };
  return {
    ok: true,
    caretIndex: pick.caretIndex,
    caretText: String(pick.caretText || '').slice(0, 80),
    click,
  };
}

/** Visible text of one reflow block; innerText matches what users see when runs split. */
export const C12_BLOCK_TEXT = (block, norm) => {
  if (block && block.classList && block.classList.contains('superdoc-line')) {
    return norm(block.textContent);
  }
  return norm(block.innerText || block.textContent);
};

/** Paragraph-level painted blocks for C12: one census across before, after, identity and re-find. */
export function c12BlockEntries(editorId, docSel, excludeSel, readBlock) {
  const excluded = excludeSel ? Array.from(document.querySelectorAll(excludeSel)) : [];
  const skip = (el) => excluded.some((root) => root === el || root.contains(el));
  const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const read = (el) => norm(readBlock(el));
  const dropFixtureHeading = (text) =>
    /^(Article \d+\.|Section \d+\.\d+\s)/.test(norm(text)) ? null : { text: norm(text) };

  if (editorId === 'superdoc') {
    const lines = Array.from(document.querySelectorAll('#editor .superdoc-line')).filter((el) => !skip(el));
    const order = [];
    const groups = new Map();
    let orphanRun = null;
    let orphanTop = null;
    for (const line of lines) {
      const lineTop = line.getBoundingClientRect().top;
      let pid = line.getAttribute('data-paragraph-id');
      if (!pid) {
        const holder = line.closest('[data-paragraph-id]');
        pid = holder ? holder.getAttribute('data-paragraph-id') : '';
      }
      if (!pid) {
        if (orphanRun && orphanTop !== null && lineTop - orphanTop > 28) {
          orphanRun = null;
          orphanTop = null;
        }
        if (!orphanRun) orphanRun = `__linegroup__:${order.length}`;
        pid = orphanRun;
        orphanTop = lineTop;
      } else {
        orphanRun = null;
        orphanTop = null;
      }
      if (!groups.has(pid)) {
        groups.set(pid, []);
        order.push(pid);
      }
      groups.get(pid).push(line);
    }
    const out = [];
    for (const pid of order) {
      const grp = groups.get(pid);
      const text = norm(grp.map((el) => readBlock(el)).join(' '));
      if (!text) continue;
      const el = grp[0];
      const rect = el.getBoundingClientRect();
      const kept = dropFixtureHeading(text);
      if (!kept) continue;
      out.push({ el, text: kept.text, top: rect.top, bottom: rect.bottom });
    }
    out.sort((a, b) => a.top - b.top);
    return out;
  }

  let query = docSel;
  if (editorId === 'eigenpal') query = '.docx-paragraph-fragment';
  else if (editorId === 'genoffice') query = '.doc-page.ProseMirror:not(.mp-page) p';
  else if (editorId === 'docxodus') query = '#editorHost p';
  else if (editorId === 'folio') query = '.layout-page-content [data-block-id]';
  else if (editorId === 'plate') query = '.doc-paragraph';

  return Array.from(document.querySelectorAll(query))
    .filter((el) => !skip(el))
    .map((el) => {
      const text = read(el);
      if (!text) return null;
      const kept = dropFixtureHeading(text);
      if (!kept) return null;
      const rect = el.getBoundingClientRect();
      return { el, text: kept.text, top: rect.top, bottom: rect.bottom };
    })
    .filter(Boolean);
}

/** Resolve anchor paragraph index after Enter+x (r3c12d ruling 3). */
export function C12_RESOLVE_ANCHOR_INDEX(snapshot, texts, norm) {
  const n = (t) => norm(t);
  const joinMid = (parts) => n(parts.filter((p) => n(p)).join(' '));
  if (!snapshot || !Array.isArray(snapshot.blockTexts)) {
    return { ok: false, reason: 'anchor_identity_ambiguous' };
  }
  const B = snapshot.blockTexts.map(n);
  const A = texts.map(n);
  const c = Number(snapshot.caretIndex);
  const i = Number(snapshot.anchorIndex);
  const anchorText = n(snapshot.anchorText || B[i] || '');
  if (!Number.isFinite(c) || !Number.isFinite(i) || c < 0 || i < 0) {
    return { ok: false, reason: 'anchor_identity_ambiguous' };
  }
  const beforeCount = B.filter((t) => t === anchorText).length;
  const afterCount = A.filter((t) => t === anchorText).length;
  if (afterCount !== beforeCount) {
    return { ok: false, reason: 'anchor_identity_ambiguous' };
  }
  const prefixEq = (a, b) => a.length === b.length && a.every((t, k) => t === b[k]);
  const candidates = [];
  for (let j = 0; j < A.length; j++) {
    const delta = j - i;
    if (delta !== 0 && delta !== 1) continue;
    if (!prefixEq(A.slice(0, c), B.slice(0, c))) continue;
    const change = joinMid(A.slice(c, j));
    const expected = n(`x${B[c]}`);
    if (change !== expected) continue;
    const K = Math.max(1, Math.min(5, A.length - j, B.length - i));
    if (!prefixEq(A.slice(j, j + K), B.slice(i, i + K))) continue;
    candidates.push(j);
  }
  if (candidates.length !== 1) return { ok: false, reason: 'anchor_identity_ambiguous' };
  return { ok: true, anchorIndex: candidates[0] };
}

export function ANCHOR_REFIND_CONTEXT_OK(snapshot, blocks, readBlock) {
  const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  if (!snapshot || !Array.isArray(snapshot.blockTexts)) {
    return { ok: false, reason: 'anchor_identity_ambiguous' };
  }
  const texts = blocks.map((block) => norm(readBlock(block))).filter((text) => text);
  return C12_RESOLVE_ANCHOR_INDEX(snapshot, texts, norm);
}

/** Pick the anchor block at the resolved paragraph index after a DOM re-render. */
export function REFIND_ANCHOR(
  docSel,
  anchorText,
  anchorTop,
  norm,
  blockText,
  anchorOccurrence = null,
) {
  if (!anchorText || !docSel) return null;
  const editorId = typeof window !== 'undefined' ? window.__c12EditorId || '' : '';
  const excludeSel = typeof window !== 'undefined' ? window.__c12ExcludeSel || '' : '';
  const snapshot = typeof window !== 'undefined' ? window.__c12BeforeSnapshot : null;
  const readBlock =
    typeof blockText === 'function'
      ? blockText
      : (block, normalizer) => normalizer(block.innerText || block.textContent);
  const read = (block) => readBlock(block, norm);
  const entries = c12BlockEntries(editorId, docSel, excludeSel, read);
  if (!snapshot || !Array.isArray(snapshot.blockTexts)) {
    if (typeof window !== 'undefined') window.__c12AnchorRefusal = 'anchor_identity_ambiguous';
    return null;
  }
  const texts = entries.map((entry) => entry.text);
  const resolved = C12_RESOLVE_ANCHOR_INDEX(snapshot, texts, norm);
  if (!resolved.ok) {
    if (typeof window !== 'undefined') window.__c12AnchorRefusal = resolved.reason;
    return null;
  }
  const j = resolved.anchorIndex;
  const kept = typeof window !== 'undefined' ? window.__c12AnchorEl : null;
  if (kept && kept.isConnected && entries[j] && kept === entries[j].el) return kept;
  return entries[j] ? entries[j].el : null;
}

const toPageExport = (fn) => fn.toString().replace(/^export\s+/, '');

/** Page-evaluable source for ANCHOR_REFIND_CONTEXT_OK alone. */
export const ANCHOR_REFIND_CONTEXT_OK_PAGE_SRC = `${toPageExport(c12BlockEntries)};\n${toPageExport(C12_RESOLVE_ANCHOR_INDEX)};\n${toPageExport(ANCHOR_REFIND_CONTEXT_OK)}`;

/** Both helpers eval'd together in the page (REFIND_ANCHOR calls ANCHOR_REFIND_CONTEXT_OK). */
export const REFIND_ANCHOR_PAGE_SRC = `${ANCHOR_REFIND_CONTEXT_OK_PAGE_SRC};\n${toPageExport(REFIND_ANCHOR)}`;

export const C12_BLOCK_ENTRIES_PAGE_SRC = toPageExport(c12BlockEntries);

export const C12_BODY_CARET_PAGE_SRC = `${C12_BLOCK_ENTRIES_PAGE_SRC};\n${toPageExport(c12FirstBodyCaretIndex)};\n${toPageExport(c12BodyCaretClick)}`;

export const C12_IDENTITY_DIAGNOSTIC_PAGE_SRC = `${toPageExport(C12_IDENTITY_REFUSAL_DIAGNOSTIC)}`;

/** Page context. C12 block census after the caret is placed (light-DOM blocks). */
export function gatherReflowBefore({ editorId, docSel, pickBelowSrc, excludeSel, entriesSrc }) {
  // The shared picker (PICK_ANCHOR_BELOW) travels as source: page.evaluate
  // arguments must be serializable values.
  let pickBelow = null;
  if (typeof pickBelowSrc === 'string' && pickBelowSrc) {
    try {
      // eslint-disable-next-line no-eval
      pickBelow = eval(pickBelowSrc);
    } catch {
      pickBelow = null;
    }
  }
  // The caret box of the placed caret, read before any Enter: the anchor is
  // the block below THIS box on the same screen (r3lanes4 ruling 3).
  const caretBox = () => {
    try {
      const sel = typeof document.getSelection === 'function' ? document.getSelection() : null;
      if (!sel || sel.rangeCount === 0) return null;
      const range = sel.getRangeAt(0).cloneRange();
      let rect = range.getBoundingClientRect();
      if ((!rect || !rect.height) && typeof range.getClientRects === 'function') {
        const rects = range.getClientRects();
        if (rects.length) rect = rects[0];
      }
      if (!rect || !Number.isFinite(rect.top) || !Number.isFinite(rect.bottom)) return null;
      return { top: rect.top, bottom: rect.bottom };
    } catch {
      return null;
    }
  };

  const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const readBlock = (block) => {
    if (block && block.classList && block.classList.contains('superdoc-line')) {
      return norm(block.textContent);
    }
    return norm(block.innerText || block.textContent);
  };
  let collect = null;
  if (typeof entriesSrc === 'string' && entriesSrc) {
    try {
      // eslint-disable-next-line no-eval
      collect = (0, eval)(`(function(){ ${entriesSrc}; return c12BlockEntries; })()`);
    } catch {
      collect = null;
    }
  }
  const eid = String(editorId || '');
  const entries =
    typeof collect === 'function'
      ? collect(eid, docSel, excludeSel || '', readBlock)
      : [];
  window.__c12EditorId = eid;
  window.__c12ExcludeSel = excludeSel || '';
  let caret = caretBox();
  const forcedCaret = Number(window.__c12ForcedCaretIndex);
  let picked = null;
  if (Number.isFinite(forcedCaret) && forcedCaret >= 0 && forcedCaret < entries.length) {
    const caretEntry = entries[forcedCaret];
    const anchorIndex = forcedCaret + 1;
    if (anchorIndex >= entries.length) {
      return {
        ok: false,
        reason: 'no document block below the caret paragraph; a y-shift could not be attributed',
        blocks: entries.length,
      };
    }
    const anchor = entries[anchorIndex];
    const top = Number(anchor.top);
    if (!anchor.text || !Number.isFinite(top)) {
      return { ok: false, reason: 'anchor paragraph has no measurable box', blocks: entries.length };
    }
    if (top >= Number(window.innerHeight)) {
      return {
        ok: false,
        reason: 'anchor paragraph is off the viewport; a y-shift could not be attributed',
        blocks: entries.length,
      };
    }
    let occurrence = 0;
    for (let i = 0; i <= anchorIndex; i += 1) {
      if (entries[i].text === anchor.text) occurrence += 1;
    }
    const cr = caretEntry.el.getBoundingClientRect();
    caret = { top: cr.top, bottom: cr.bottom || cr.top + 1 };
    picked = {
      ok: true,
      anchorText: anchor.text,
      anchorIndex,
      caretIndex: forcedCaret,
      anchorOccurrence: occurrence,
      blockCount: entries.length,
      firstText: String(entries[0].text || '').slice(0, 40),
    };
  } else {
    // Some hosts keep the selection in an off-DOM textbox; Home then reports
    // (0,0). After restoreReflowCaret, treat the caret as inside the first
    // visible reflow block so the anchor is the next block down, not the one
    // being split by Enter at the document start.
    if ((!caret || caret.bottom <= caret.top + 1) && entries.length) {
      const r = entries[0].el.getBoundingClientRect();
      if (r.height > 0) caret = { top: r.top, bottom: r.top + Math.min(1, r.height) };
    }
    // The anchor is the nearest block below the caret on the same screen.
    picked =
      typeof pickBelow === 'function'
        ? pickBelow(entries, caret, window.innerHeight)
        : { ok: false, reason: 'anchor picker unavailable; a y-shift could not be attributed' };
  }
  if (!picked.ok) {
    return { ...picked, blocks: entries.length, caret_top: caret ? caret.top : null };
  }
  window.__c12AnchorEl = entries[picked.anchorIndex].el;
  window.__c12AnchorTop = window.__c12AnchorEl.getBoundingClientRect().top;
  window.__c12AnchorText = picked.anchorText;
  window.__c12AnchorOccurrence = picked.anchorOccurrence;
  window.__c12DocSel = docSel;
  window.__c12ModelReflow = false;
  const blockTexts = entries.map((entry) => entry.text);
  const anchorTextCount = blockTexts.filter((text) => text === picked.anchorText).length;
  const prefixTexts = blockTexts.slice(0, picked.anchorIndex);
  window.__c12BeforeSnapshot = {
    prefixTexts,
    anchorText: picked.anchorText,
    anchorTextCount,
    anchorOccurrence: picked.anchorOccurrence,
    anchorIndex: picked.anchorIndex,
    caretIndex: picked.caretIndex,
    blockTexts,
  };
  const caretParagraph = entries[picked.caretIndex] ? String(entries[picked.caretIndex].text || '') : '';
  return {
    ok: true,
    blocks: picked.blockCount,
    anchor_index: picked.anchorIndex,
    anchor_text: picked.anchorText,
    anchor_occurrence: picked.anchorOccurrence,
    anchor_text_count: anchorTextCount,
    prefix_texts: prefixTexts,
    anchor_top: window.__c12AnchorTop,
    first_block_top: entries[0].el.getBoundingClientRect().top,
    first_block_text: picked.firstText,
    caret_index: picked.caretIndex,
    caret_paragraph_text: caretParagraph,
    caret_top: caret ? caret.top : null,
  };
}

export async function runLaneEditBurst(page, cdp, { editorId, selector, text, repetitions, pollBoundMs }) {
  const poll = pollBoundMs ?? LANE_POLL_BOUND_MS;
  await prepareEditSurface(page, editorId, { timeoutMs: poll });
  const params = {
    editorId,
    selector,
    text,
    repetitions,
    pollBoundMs: poll,
    pollIntervalMs: 50,
    preTypeSettleMs: 100,
  };
  const prepared = await prepareResourceBurst(page, params);
  if (prepared.placeError) {
    return {
      applied: false,
      edit_effective: false,
      edit_error: prepared.placeError,
      oracle: { status: 'edit_not_applied', reason: prepared.placeError },
      prepared,
    };
  }
  await typeResourceBurst(page, params);
  const verified = await verifyResourceBurst(page, cdp, params, prepared);
  return {
    ...verified,
    edit_effective: verified.applied === true,
    edit_error: verified.oracle && verified.oracle.reason ? verified.oracle.reason : null,
    prepared,
  };
}

/** Place the caret at the start of the first body block in the shared C12 census. */
export async function placeC12BodyCaret(page, editorId, reflowSel, excludeSel) {
  const pick = await page.evaluate(
    ({ editorId, docSel, excludeSel, bundleSrc }) => {
      let resolveClick = null;
      try {
        // eslint-disable-next-line no-eval
        resolveClick = (0, eval)(`(function(){ ${bundleSrc}; return c12BodyCaretClick; })()`);
      } catch {
        resolveClick = null;
      }
      if (typeof resolveClick !== 'function') return { ok: false, reason: 'body caret bundle failed' };
      return resolveClick({ editorId, docSel, excludeSel });
    },
    {
      editorId: editorId || '',
      docSel: reflowSel,
      excludeSel: excludeSel || '',
      bundleSrc: C12_BODY_CARET_PAGE_SRC,
    },
  );
  if (!pick || pick.ok !== true || !pick.click) return pick;
  const blockSelector = String(reflowSel || '').split(',')[0].trim() || null;
  const surface = editSurface(editorId);
  if (surface.hidden) {
    await page.mouse.click(pick.click.x, pick.click.y);
    await page.waitForTimeout(150);
  }
  let placed = null;
  try {
    placed = await placeCaret(page, editorId, reflowSel, {
      clickPoint: pick.click,
      atBlockStart: true,
      blockSelector,
      focusTimeoutMs: 5000,
    });
  } catch (error) {
    return {
      ok: false,
      reason: String(error && error.message ? error.message : error).slice(0, 200),
    };
  }
  const verified = await verifyCaretAtParagraphStart(page, editorId, {
    blockSelector,
    clickPoint: pick.click,
    expectedParagraphText: pick.caretText,
  });
  if (!verified.ok) {
    return {
      ok: false,
      reason: verified.reason || 'caret_not_at_paragraph_start',
      caretIndex: pick.caretIndex,
      caretText: pick.caretText,
      caret_verify: verified,
      point: placed.point,
      focused: placed.focused,
    };
  }
  await page.waitForTimeout(80);
  return {
    ok: true,
    caretIndex: pick.caretIndex,
    caretText: pick.caretText,
    click: pick.click,
    point: placed.point,
    focused: placed.focused,
    caret_verify: verified,
  };
}

/** Poll the C12 census until the caret paragraph changes (outside the measured window). */
export async function waitForC12CaretEdit(
  page,
  editorId,
  reflowSel,
  excludeSel,
  snapshot,
  { timeoutMs = LANE_EDIT_CONFIRM_MS, pollMs = 50 } = {},
) {
  const c = snapshot && Number.isFinite(Number(snapshot.caretIndex)) ? Number(snapshot.caretIndex) : -1;
  const beforeText =
    snapshot && Array.isArray(snapshot.blockTexts) && c >= 0
      ? String(snapshot.blockTexts[c] || '')
      : '';
  const deadline = Date.now() + timeoutMs;
  let lastTexts = null;
  while (Date.now() < deadline) {
    const sampled = await page.evaluate(
      ({ editorId, docSel, excludeSel, bundleSrc, blockTextSrc }) => {
        const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
        let readBlock = (block) => norm(block.innerText || block.textContent);
        try {
          // eslint-disable-next-line no-eval
          const fn = eval(blockTextSrc);
          if (typeof fn === 'function') readBlock = (block) => fn(block, norm);
        } catch {
          /* keep default */
        }
        let collect = null;
        try {
          // eslint-disable-next-line no-eval
          collect = (0, eval)(`(function(){ ${bundleSrc}; return c12BlockEntries; })()`);
        } catch {
          collect = null;
        }
        if (typeof collect !== 'function') return { ok: false, reason: 'census unavailable' };
        const entries = collect(String(editorId || ''), docSel, excludeSel || '', readBlock);
        return { ok: true, texts: entries.map((entry) => entry.text) };
      },
      {
        editorId: editorId || '',
        docSel: reflowSel,
        excludeSel: excludeSel || '',
        bundleSrc: C12_BLOCK_ENTRIES_PAGE_SRC,
        blockTextSrc: `${C12_BLOCK_TEXT}`,
      },
    );
    if (sampled && sampled.ok && Array.isArray(sampled.texts)) {
      lastTexts = sampled.texts;
      const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
      const afterText = c >= 0 && c < sampled.texts.length ? norm(sampled.texts[c]) : '';
      const expected = norm(`x${beforeText}`);
      if (afterText === expected) {
        return { ok: true, texts: sampled.texts };
      }
    }
    await page.waitForTimeout(pollMs);
  }
  return { ok: false, reason: 'edit_not_observed', texts: lastTexts, caretIndex: c, beforeText };
}

/** After Control+Home/Home, some hosts leave a zero-height selection (off-DOM). */
export async function ensureReflowCaret(
  page,
  reflowSel,
  { settleMs = 100, editorId = '', excludeSel = '' } = {},
) {
  const primary = String(reflowSel || '').split(',')[0].trim();
  const need = await page.evaluate((sel) => {
    const pick = typeof document.getSelection === 'function' ? document.getSelection() : null;
    if (!pick || pick.rangeCount === 0) return true;
    const rect = pick.getRangeAt(0).getBoundingClientRect();
    const badRect = !(rect.height > 0.5 && rect.bottom > rect.top);
    if (!sel) return badRect;
    let node = pick.anchorNode;
    let el = node && node.nodeType === 3 ? node.parentElement : node;
    const inReflow = () => {
      for (; el; el = el.parentElement) {
        try {
          if (el.matches && el.matches(sel)) return true;
        } catch {
          return false;
        }
      }
      return false;
    };
    return badRect || !inReflow();
  }, primary);
  if (!need) return { restored: false };
  const bodyCaret = await placeC12BodyCaret(page, editorId, reflowSel, excludeSel);
  if (bodyCaret && bodyCaret.ok) {
    if (settleMs > 0) await page.waitForTimeout(settleMs);
    return { restored: true, ...bodyCaret };
  }
  if (!primary) return { restored: false, reason: bodyCaret?.reason || 'no reflow selector' };
  const box = await page.locator(primary).first().boundingBox();
  if (!box) return { restored: false, reason: 'no caret box' };
  await page.mouse.click(box.x + 3, box.y + Math.min(8, Math.max(2, box.height / 2)));
  await page.keyboard.press('Home');
  if (settleMs > 0) await page.waitForTimeout(settleMs);
  return { restored: true };
}

/** Caret and pre-edit read only; used when the lane measures its own keystroke window. */
export async function prepareLaneCaret(page, editorId, selector, { timeoutMs = LANE_LOAD_TIMEOUT_MS } = {}) {
  await prepareEditSurface(page, editorId, { timeoutMs });
  return prepareResourceBurst(page, {
    editorId,
    selector,
    text: 'x',
    repetitions: 0,
    preTypeSettleMs: 100,
    pollBoundMs: timeoutMs,
  });
}

/** Post-keystroke confirmation through the shared adapter (outside measured intervals). */
export async function confirmLaneEdit(
  page,
  editorId,
  point,
  { token = 'x', before, beforeFlag, expected = 1, timeoutMs = LANE_POLL_BOUND_MS } = {},
) {
  const surface = editSurface(editorId);
  if (surface.kind === 'flag') {
    if (beforeFlag && beforeFlag.modified) {
      return { confirmed: false, reason: 'modified_before_edit', adapter: 'flag', before_count: 1, after_count: 1 };
    }
    const after = await readModifiedFlag(page, editorId);
    const modified = Boolean(after && after.modified);
    return {
      confirmed: modified,
      adapter: 'flag',
      before_count: 0,
      after_count: modified ? 1 : 0,
    };
  }
  const waited = await waitForTokenDelta(page, editorId, point, {
    token,
    before: before || '',
    expected,
    timeoutMs,
    pollMs: 50,
  });
  return {
    confirmed: waited.applied,
    adapter: surface.kind,
    before_count: 0,
    after_count: waited.applied ? expected : 0,
    text_delta: waited.delta,
    reason: waited.applied ? null : 'caret_scope_token_mismatch',
  };
}
