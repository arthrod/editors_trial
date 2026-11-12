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
  READ_CLICK_HIT,
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
  const clipText = (t) => String(t || '').slice(0, trunc);
  const Braw = snapshot && Array.isArray(snapshot.blockTexts) ? snapshot.blockTexts : [];
  const Araw = Array.isArray(texts) ? texts : [];
  const c = Number(snapshot && snapshot.caretIndex);
  const i = Number(snapshot && snapshot.anchorIndex);
  const indexed = Number.isFinite(c) && Number.isFinite(i) && c >= 0 && i >= 0;
  // caret-3 .. anchor+5, inclusive. A prefix of `limit` hides a pair past
  // that prefix (the complex-corpus pair is at 9/10; limit 8 is page chrome).
  // Missing indexes keep the old prefix.
  const windowOf = (list) => {
    const normalized = list.map(n);
    if (!indexed) return { from: 0, texts: normalized.slice(0, limit).map(clipText) };
    const from = Math.max(0, Math.min(c, i) - 3);
    const to = Math.min(normalized.length, Math.max(c, i) + 5 + 1);
    return { from, texts: normalized.slice(from, to).map(clipText) };
  };
  const beforeWin = windowOf(Braw);
  const afterWin = windowOf(Araw);
  const B = Braw.map(n);
  const A = Araw.map(n);
  const anchorText = n((snapshot && snapshot.anchorText) || (indexed ? B[i] : '') || '');
  const indexesOf = (list) => {
    const found = [];
    if (!anchorText) return found;
    for (let k = 0; k < list.length; k += 1) if (list[k] === anchorText) found.push(k);
    return found;
  };
  const base = {
    caretIndex: indexed ? c : null,
    anchorIndex: indexed ? i : null,
    window_from: beforeWin.from,
    before_blocks: beforeWin.texts,
    after_blocks: afterWin.texts,
    anchor_indexes_before: indexesOf(B),
    anchor_indexes_after: indexesOf(A),
    failed: null,
  };
  if (!snapshot || !Array.isArray(snapshot.blockTexts)) {
    return { ...base, failed: 'a' };
  }
  if (!indexed) {
    return { ...base, failed: 'a' };
  }
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

/**
 * First census entry equal to the fixture caret string, then the first entry
 * after it equal to the fixture anchor string. A miss is a refusal: the next
 * block below a heading or a header is not a substitute.
 */
export function c12LocateFixtureParagraphs(entries, caretText, anchorText, norm) {
  const collapse = typeof norm === 'function'
    ? norm
    : (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const normalize = (value) => {
    const collapsed = collapse(value);
    const text = String(collapsed == null ? '' : collapsed);
    return typeof text.normalize === 'function' ? text.normalize('NFC') : text;
  };
  const refuse = () => {
    const list = Array.isArray(entries) ? entries : [];
    const limit = Math.min(60, list.length);
    const parts = [];
    for (let i = 0; i < limit; i += 1) {
      parts.push(normalize(list[i] && list[i].text).slice(0, 80));
    }
    return {
      ok: false,
      reason: `fixture_paragraph_not_in_census: n=${list.length} | ${parts.join(' | ')}`,
    };
  };
  const wantCaret = normalize(caretText);
  const wantAnchor = normalize(anchorText);
  if (!Array.isArray(entries) || !wantCaret || !wantAnchor) return refuse();
  let caretIndex = -1;
  for (let i = 0; i < entries.length; i += 1) {
    if (normalize(entries[i] && entries[i].text) === wantCaret) {
      caretIndex = i;
      break;
    }
  }
  if (caretIndex < 0) return refuse();
  let anchorIndex = -1;
  for (let i = caretIndex + 1; i < entries.length; i += 1) {
    if (normalize(entries[i] && entries[i].text) === wantAnchor) {
      anchorIndex = i;
      break;
    }
  }
  if (anchorIndex < 0) return refuse();
  return { ok: true, caretIndex, anchorIndex };
}

/** Page context: click point at the start of the fixture's first body census block. */
export function c12BodyCaretClick({ editorId, docSel, excludeSel, caretText, anchorText }) {
  const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const readBlock = (block) => {
    if (block && block.classList && block.classList.contains('superdoc-line')) {
      return norm(block.textContent);
    }
    return norm(block.innerText || block.textContent);
  };
  if (typeof c12BlockEntries !== 'function') return { ok: false, reason: 'census unavailable' };
  const entries = c12BlockEntries(String(editorId || ''), docSel, excludeSel || '', readBlock);
  const fixtureCaret = String(caretText || '');
  const fixtureAnchor = String(anchorText || '');
  const useFixture = Boolean(fixtureCaret && fixtureAnchor);
  let pick;
  if (useFixture) {
    if (typeof c12LocateFixtureParagraphs !== 'function') {
      return { ok: false, reason: 'fixture_paragraph_not_in_census' };
    }
    const located = c12LocateFixtureParagraphs(entries, fixtureCaret, fixtureAnchor, norm);
    if (!located.ok || !entries[located.caretIndex]) {
      return { ok: false, reason: located.reason || 'fixture_paragraph_not_in_census' };
    }
    pick = {
      ok: true,
      caretIndex: located.caretIndex,
      anchorIndex: located.anchorIndex,
      caretText: String(entries[located.caretIndex].text || ''),
    };
  } else {
    pick = c12FirstBodyCaretIndex(entries);
    if (!pick.ok || !entries[pick.caretIndex]) return { ok: false, reason: pick.reason || 'no body block' };
  }
  const el = entries[pick.caretIndex].el;
  let click = null;
  try {
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }
    // The block box's corner can belong to the next paragraph. The first
    // glyph's own line box is this paragraph's text.
    const firstGlyphRect = (host) => {
      if (
        !host ||
        typeof document.createRange !== 'function' ||
        typeof document.createTreeWalker !== 'function' ||
        typeof NodeFilter === 'undefined'
      ) {
        return null;
      }
      let walker;
      try {
        walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
      } catch {
        return null;
      }
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const text = String(node.nodeValue || '');
        const start = text.search(/\S/);
        if (start < 0) continue;
        try {
          const range = document.createRange();
          range.setStart(node, start);
          range.setEnd(node, Math.min(text.length, start + 1));
          const rects = typeof range.getClientRects === 'function' ? range.getClientRects() : null;
          const glyph = rects && rects.length ? rects[0] : null;
          if (glyph && glyph.width > 0 && glyph.height > 0) return glyph;
        } catch {
          /* the next text node */
        }
      }
      return null;
    };
    const glyph = firstGlyphRect(el);
    let rect = null;
    let box = 'block';
    if (glyph) {
      rect = glyph;
      box = 'glyph';
    } else if (el && typeof el.getBoundingClientRect === 'function') {
      rect = el.getBoundingClientRect();
    }
    if (rect && rect.height > 0) {
      click = {
        x: rect.left + 1,
        y: rect.top + rect.height / 2,
        line: String(pick.caretText || '').slice(0, 60),
        box,
      };
    }
    window.__c12ForcedCaretIndex = pick.caretIndex;
    if (useFixture) {
      window.__c12ForcedAnchorIndex = pick.anchorIndex;
      window.__c12FixtureCaretText = fixtureCaret;
      window.__c12FixtureAnchorText = fixtureAnchor;
    }
  } catch {
    return { ok: false, reason: 'could not resolve body block click point' };
  }
  if (!click) return { ok: false, reason: 'body block has no click box' };
  return {
    ok: true,
    caretIndex: pick.caretIndex,
    anchorIndex: pick.anchorIndex,
    caretText: String(pick.caretText || '').slice(0, 80),
    anchorText: String((entries[pick.anchorIndex] && entries[pick.anchorIndex].text) || '').slice(0, 80),
    click,
  };
}

/** One SuperDoc paragraph: lines that share a paragraph id, or orphan lines within 28px. */
export function superdocParagraphGroups(lines, rect) {
  const order = [];
  const groups = new Map();
  let orphanRun = null;
  let orphanTop = null;
  for (const line of lines) {
    const lineTop = rect(line).top;
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
  return order.map((pid) => groups.get(pid));
}

/** Joined painted text of one SuperDoc paragraph. Census and identity re-read both use this. */
export function joinSuperdocLines(lines, norm) {
  const normalize = typeof norm === 'function'
    ? norm
    : (value) => String(value || '').replace(/\s+/g, ' ').trim();
  return normalize((lines || []).map((el) => (el && el.textContent) || '').join(' '));
}

/** Paragraph text of one SuperDoc line, from the same groups the census builds. */
export function c12SuperdocParagraphText(line, norm) {
  const normalize = typeof norm === 'function'
    ? norm
    : (value) => String(value || '').replace(/\s+/g, ' ').trim();
  if (!line) return normalize('');
  const root = typeof document !== 'undefined' ? document : globalThis.document;
  if (!root || typeof root.querySelectorAll !== 'function') return normalize(line.textContent);
  let lines = Array.from(root.querySelectorAll('#editor .superdoc-line'));
  const excludeSel = typeof window !== 'undefined' ? String(window.__c12ExcludeSel || '') : '';
  if (excludeSel) {
    const excluded = Array.from(root.querySelectorAll(excludeSel));
    lines = lines.filter((el) => !excluded.some((node) => node === el || (node.contains && node.contains(el))));
  }
  const groups = superdocParagraphGroups(lines, (el) => el.getBoundingClientRect());
  const group = groups.find((grp) => grp.indexOf(line) !== -1);
  return joinSuperdocLines(group && group.length ? group : [line], normalize);
}

/** Visible text of one reflow block. A SuperDoc line answers as its whole paragraph. */
export const C12_BLOCK_TEXT = (block, norm) => {
  if (block && block.classList && block.classList.contains('superdoc-line')) {
    return c12SuperdocParagraphText(block, norm);
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
  // Every probe-driven layout read is counted: a poll inside the C12 window
  // forces layout, and the sample must report that work, never hide it. Each
  // read is timestamped so the report can bound it to the measured window.
  const rect = (el) => {
    const t0 = performance.now();
    const box = el.getBoundingClientRect();
    const log = globalThis.__c12ProbeReadLog;
    // The frame recorder closes the log when it has the moved frame. A later
    // census is the after-path; it must not be counted as a read inside the
    // window, and it must not add one rect per block to that count.
    if (Array.isArray(log) && globalThis.__c12ProbeReadLogClosed !== true) {
      log.push({ t: t0, ms: performance.now() - t0 });
    }
    return box;
  };

  if (editorId === 'superdoc') {
    // One pass over the lines. Do not call c12SuperdocParagraphText per line:
    // that re-queries and would join the paragraph once per line.
    const lines = Array.from(document.querySelectorAll('#editor .superdoc-line')).filter((el) => !skip(el));
    const groups = superdocParagraphGroups(lines, rect);
    const out = [];
    for (const grp of groups) {
      const text = joinSuperdocLines(grp, norm);
      if (!text) continue;
      const el = grp[0];
      const box = rect(el);
      const kept = dropFixtureHeading(text);
      if (!kept) continue;
      out.push({ el, text: kept.text, top: box.top, bottom: box.bottom });
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
      const box = rect(el);
      return { el, text: kept.text, top: box.top, bottom: box.bottom };
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

/**
 * The anchor block whose text is the fixture anchor string, in census order.
 * No getBoundingClientRect: the caller reads the matched block only. SuperDoc
 * lines that share a paragraph id are one paragraph; a line with no id is its
 * own paragraph, because grouping orphan lines needs their rects.
 */
export function c12AnchorElementByText(editorId, docSel, excludeSel, anchorText, occurrence) {
  const normalize = (value) => {
    const collapsed = String(value || '').replace(/\s+/g, ' ').trim();
    return typeof collapsed.normalize === 'function' ? collapsed.normalize('NFC') : collapsed;
  };
  const want = normalize(anchorText);
  if (!want || !docSel) return null;
  const root = typeof document !== 'undefined' ? document : globalThis.document;
  if (!root || typeof root.querySelectorAll !== 'function') return null;
  const excluded = excludeSel ? Array.from(root.querySelectorAll(excludeSel)) : [];
  const skip = (el) => excluded.some((node) => node === el || (node.contains && node.contains(el)));
  const nodes = Array.from(root.querySelectorAll(docSel)).filter((el) => el && !skip(el));
  const matches = [];
  if (String(editorId || '') === 'superdoc') {
    const groups = new Map();
    const order = [];
    for (const line of nodes) {
      let pid = '';
      if (typeof line.getAttribute === 'function') pid = line.getAttribute('data-paragraph-id') || '';
      if (!pid && typeof line.closest === 'function') {
        const holder = line.closest('[data-paragraph-id]');
        if (holder && typeof holder.getAttribute === 'function') pid = holder.getAttribute('data-paragraph-id') || '';
      }
      if (!pid) {
        const solo = `__line__:${order.length}`;
        groups.set(solo, [line]);
        order.push(solo);
        continue;
      }
      if (!groups.has(pid)) {
        groups.set(pid, []);
        order.push(pid);
      }
      groups.get(pid).push(line);
    }
    for (const key of order) {
      const grp = groups.get(key);
      const text = normalize(grp.map((el) => (el && el.textContent) || '').join(' '));
      if (text === want) matches.push(grp[0]);
    }
  } else {
    for (const el of nodes) {
      if (normalize(el.textContent == null ? '' : el.textContent) === want) matches.push(el);
    }
  }
  const occ = Number(occurrence);
  if (!Number.isFinite(occ) || occ < 1) return matches.length === 1 ? matches[0] : null;
  return matches[occ - 1] || null;
}

/** Bring the caret paragraph into view. Same call for every editor. */
export function c12ScrollCaretIntoView(editorId, docSel, excludeSel, caretText, occurrence) {
  const spec = { block: 'center', inline: 'nearest', behavior: 'instant' };
  const el = c12AnchorElementByText(editorId, docSel, excludeSel, caretText, occurrence);
  if (!el || typeof el.getBoundingClientRect !== 'function') {
    return { ok: false, ...spec, reason: 'caret paragraph is not in the census' };
  }
  const topBefore = el.getBoundingClientRect().top;
  if (typeof el.scrollIntoView === 'function') el.scrollIntoView(spec);
  const topAfter = el.getBoundingClientRect().top;
  return {
    ok: true,
    block: spec.block,
    inline: spec.inline,
    behavior: spec.behavior,
    top_before: topBefore,
    top_after: topAfter,
  };
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
  const found = entries[j] ? entries[j].el : null;
  if (!found) {
    if (typeof window !== 'undefined') window.__c12AnchorRefusal = 'anchor_identity_ambiguous';
    return null;
  }
  // A miss on an earlier frame (the recorder refinds before the caret "x"
  // exists) must not outlive a later resolution of this same anchor.
  if (typeof window !== 'undefined') window.__c12AnchorRefusal = null;
  const kept = typeof window !== 'undefined' ? window.__c12AnchorEl : null;
  if (kept && kept.isConnected && kept === found) return kept;
  return found;
}

/**
 * The recorded frame and the confirmed census node are the same paragraph.
 * Same node, a wrapper or child with the same text, or a disconnected
 * replacement that still carries the same block id. A second live node is
 * not accepted. No per-editor branch. No layout read.
 */
export function c12SameAnchorElement(recorded, confirmed) {
  if (!recorded || !confirmed) return false;
  if (recorded === confirmed) return true;
  const normalize = (value) => {
    const collapsed = String(value || '').replace(/\s+/g, ' ').trim();
    return typeof collapsed.normalize === 'function' ? collapsed.normalize('NFC') : collapsed;
  };
  const textOf = (el) => {
    const raw = el.innerText != null && String(el.innerText) !== '' ? el.innerText : el.textContent;
    return normalize(raw);
  };
  const textA = textOf(recorded);
  const textB = textOf(confirmed);
  if (!textA || textA !== textB) return false;
  if (typeof recorded.contains === 'function' && recorded.contains(confirmed)) return true;
  if (typeof confirmed.contains === 'function' && confirmed.contains(recorded)) return true;
  if (recorded.isConnected !== false || confirmed.isConnected !== true) return false;
  const attr = (el, name) => {
    if (typeof el.getAttribute === 'function') {
      const value = el.getAttribute(name);
      return value == null ? '' : String(value);
    }
    const attrs = el.attributes;
    if (!attrs || typeof attrs.length !== 'number') return '';
    for (const item of Array.from(attrs)) {
      if (item && item.name === name) return item.value == null ? '' : String(item.value);
    }
    return '';
  };
  const names = ['data-block-id', 'data-para-id', 'data-paragraph-id', 'data-source-node-id'];
  let saw = false;
  for (const name of names) {
    const left = attr(recorded, name);
    const right = attr(confirmed, name);
    if (!left && !right) continue;
    if (left !== right) return false;
    saw = true;
  }
  return saw;
}

/**
 * Both elements of a failed frame tie. The refusal has to say which nodes
 * differed: tag, data-* attributes, normalized text prefix, rect top, and
 * whether the node is still connected. Same comparison for every editor.
 */
export function c12FrameTieDiagnostic(recorded, confirmed) {
  const normalize = (value) => {
    const collapsed = String(value || '').replace(/\s+/g, ' ').trim();
    return typeof collapsed.normalize === 'function' ? collapsed.normalize('NFC') : collapsed;
  };
  const describe = (el) => {
    if (!el) return null;
    const data = {};
    const attrs = el.attributes;
    if (attrs && typeof attrs.length === 'number') {
      for (const attr of Array.from(attrs)) {
        const name = attr && attr.name;
        if (typeof name === 'string' && name.indexOf('data-') === 0) {
          data[name] = attr.value == null ? '' : String(attr.value);
        }
      }
    }
    const raw = el.innerText != null && String(el.innerText) !== '' ? el.innerText : el.textContent;
    let top = null;
    if (typeof el.getBoundingClientRect === 'function') {
      const box = el.getBoundingClientRect();
      if (box && typeof box.top === 'number') top = box.top;
    }
    return {
      tag: el.tagName || null,
      data,
      text_prefix: normalize(raw).slice(0, 80),
      top,
      isConnected: el.isConnected === true,
    };
  };
  let relation = 'distinct';
  if (recorded && confirmed && recorded === confirmed) relation = 'same';
  else if (
    recorded &&
    confirmed &&
    typeof recorded.contains === 'function' &&
    recorded.contains(confirmed)
  ) {
    relation = 'recorded_contains_confirmed';
  } else if (
    recorded &&
    confirmed &&
    typeof confirmed.contains === 'function' &&
    confirmed.contains(recorded)
  ) {
    relation = 'confirmed_contains_recorded';
  }
  return { recorded: describe(recorded), confirmed: describe(confirmed), relation };
}

/**
 * Where the caret really is, before Enter. The selection's anchor node mapped
 * onto the census already in hand, plus the offset inside that block. A node
 * that is not in the census is described. No layout read.
 */
export function c12CaretSelection(entries) {
  const list = Array.isArray(entries) ? entries : [];
  const root = typeof document !== 'undefined' ? document : globalThis.document;
  const fromWindow = typeof window !== 'undefined' && typeof window.getSelection === 'function'
    ? window.getSelection()
    : null;
  const sel = root && typeof root.getSelection === 'function' ? root.getSelection() : fromWindow;
  const none = { block_index: null, offset: null, text_prefix: null, anchor: null };
  if (!sel || !sel.rangeCount || !sel.anchorNode) return none;
  const anchorNode = sel.anchorNode;
  const anchorOffset = Number.isFinite(Number(sel.anchorOffset)) ? Number(sel.anchorOffset) : 0;
  let blockIndex = null;
  let block = null;
  let node = anchorNode;
  const seen = new Set();
  while (node && !seen.has(node)) {
    seen.add(node);
    for (let i = 0; i < list.length; i += 1) {
      if (list[i] && list[i].el === node) {
        blockIndex = i;
        block = node;
        node = null;
        break;
      }
    }
    if (node) node = node.parentNode || null;
  }
  const norm = (value) => {
    const collapsed = String(value || '').replace(/\s+/g, ' ').trim();
    return typeof collapsed.normalize === 'function' ? collapsed.normalize('NFC') : collapsed;
  };
  let offset = null;
  if (block && typeof sel.getRangeAt === 'function') {
    try {
      const pre = sel.getRangeAt(0).cloneRange();
      pre.selectNodeContents(block);
      pre.setEnd(anchorNode, anchorOffset);
      offset = norm(pre.toString()).length;
    } catch {
      offset = null;
    }
  }
  if (blockIndex != null) {
    return {
      block_index: blockIndex,
      offset,
      text_prefix: norm(list[blockIndex].text).slice(0, 80),
      anchor: null,
    };
  }
  const el = anchorNode.nodeType === 3 ? anchorNode.parentNode : anchorNode;
  const data = {};
  if (el && el.attributes && typeof el.attributes.length === 'number') {
    for (const attr of Array.from(el.attributes)) {
      const name = attr && attr.name;
      if (typeof name === 'string' && name.indexOf('data-') === 0) {
        data[name] = attr.value == null ? '' : String(attr.value);
      }
    }
  }
  const raw = el
    ? (el.innerText != null && String(el.innerText) !== '' ? el.innerText : el.textContent)
    : '';
  return {
    block_index: null,
    offset,
    text_prefix: null,
    anchor: el ? { tag: el.tagName || null, data, text_prefix: norm(raw).slice(0, 80) } : null,
  };
}

/**
 * The identity window with the empty paragraphs the census drops. A row the
 * census keeps carries its census index. An empty row carries null. Headings
 * still drop. No layout read. SuperDoc lines that share a paragraph id are
 * one paragraph; grouping them does not read rects.
 */
export function c12EmptyInclusiveWindow(editorId, docSel, excludeSel, snapshot) {
  const norm = (value) => {
    const collapsed = String(value || '').replace(/\s+/g, ' ').trim();
    return typeof collapsed.normalize === 'function' ? collapsed.normalize('NFC') : collapsed;
  };
  const heading = (text) => /^(Article \d+\.|Section \d+\.\d+\s)/.test(norm(text));
  const root = typeof document !== 'undefined' ? document : globalThis.document;
  const blank = { from: 0, to: 0, rows: [] };
  if (!root || typeof root.querySelectorAll !== 'function') return blank;
  const excluded = excludeSel ? Array.from(root.querySelectorAll(excludeSel)) : [];
  const skip = (el) => excluded.some((node) => node === el || (node.contains && node.contains(el)));
  const eid = String(editorId || '');
  let query = docSel;
  if (eid === 'eigenpal') query = '.docx-paragraph-fragment';
  else if (eid === 'genoffice') query = '.doc-page.ProseMirror:not(.mp-page) p';
  else if (eid === 'docxodus') query = '#editorHost p';
  else if (eid === 'folio') query = '.layout-page-content [data-block-id]';
  else if (eid === 'plate') query = '.doc-paragraph';
  else if (eid === 'superdoc') query = '#editor .superdoc-line';
  const nodes = Array.from(root.querySelectorAll(query || '')).filter((el) => el && !skip(el));
  const textOf = (el) => {
    const raw = el && el.innerText != null && String(el.innerText) !== '' ? el.innerText : el && el.textContent;
    return norm(raw);
  };
  let blocks = nodes.map((el) => ({ text: textOf(el) }));
  if (eid === 'superdoc') {
    const groups = [];
    const byId = new Map();
    for (const line of nodes) {
      let pid = '';
      if (typeof line.getAttribute === 'function') pid = line.getAttribute('data-paragraph-id') || '';
      if (!pid && typeof line.closest === 'function') {
        const holder = line.closest('[data-paragraph-id]');
        if (holder && typeof holder.getAttribute === 'function') {
          pid = holder.getAttribute('data-paragraph-id') || '';
        }
      }
      if (!pid) {
        groups.push([line]);
        continue;
      }
      if (!byId.has(pid)) {
        const grp = [line];
        byId.set(pid, grp);
        groups.push(grp);
      } else byId.get(pid).push(line);
    }
    blocks = groups.map((grp) => ({
      text: norm(grp.map((el) => (el && el.textContent) || '').join(' ')),
    }));
  }
  const annotated = [];
  let census = 0;
  for (const block of blocks) {
    if (heading(block.text)) continue;
    if (!block.text) {
      annotated.push({ text_prefix: '', empty: true, census_index: null });
      continue;
    }
    annotated.push({ text_prefix: block.text.slice(0, 80), empty: false, census_index: census });
    census += 1;
  }
  const c = Number(snapshot && snapshot.caretIndex);
  const i = Number(snapshot && snapshot.anchorIndex);
  const indexed = Number.isFinite(c) && Number.isFinite(i) && c >= 0 && i >= 0;
  const from = indexed ? Math.max(0, Math.min(c, i) - 3) : 0;
  const to = indexed ? Math.max(c, i) + 6 : annotated.length;
  const rows = [];
  let started = false;
  for (const row of annotated) {
    if (row.census_index != null && row.census_index >= to) break;
    if (!started) {
      if (row.census_index != null && row.census_index >= from) started = true;
      else continue;
    }
    rows.push(row);
  }
  return { from, to, rows };
}

const toPageExport = (fn) => fn.toString().replace(/^export\s+/, '');

// The helpers have to travel inside each eval. An indirect eval of the entries
// IIFE cannot see module bindings, and the block-text arrow closes over the
// helpers only when they are declared in the same eval.
const SUPERDOC_TEXT_HELPERS_PAGE_SRC = `${toPageExport(superdocParagraphGroups)};\n${toPageExport(joinSuperdocLines)};\n${toPageExport(c12SuperdocParagraphText)}`;

/** Eval returns the arrow. The helpers stay in its closure. */
export const C12_BLOCK_TEXT_PAGE_SRC = `${SUPERDOC_TEXT_HELPERS_PAGE_SRC};\n${C12_BLOCK_TEXT}`;

export const C12_BLOCK_ENTRIES_PAGE_SRC = `${toPageExport(superdocParagraphGroups)};\n${toPageExport(joinSuperdocLines)};\n${toPageExport(c12BlockEntries)}`;

export const C12_LOCATE_PAGE_SRC = toPageExport(c12LocateFixtureParagraphs);

/** Page-evaluable source for ANCHOR_REFIND_CONTEXT_OK alone. */
export const ANCHOR_REFIND_CONTEXT_OK_PAGE_SRC = `${C12_BLOCK_ENTRIES_PAGE_SRC};\n${toPageExport(C12_RESOLVE_ANCHOR_INDEX)};\n${toPageExport(ANCHOR_REFIND_CONTEXT_OK)}`;

/** Both helpers eval'd together in the page (REFIND_ANCHOR calls ANCHOR_REFIND_CONTEXT_OK). */
export const REFIND_ANCHOR_PAGE_SRC = `${ANCHOR_REFIND_CONTEXT_OK_PAGE_SRC};\n${toPageExport(REFIND_ANCHOR)}`;

/** Text match only. The frame recorder must not eval the census with this. */
export const C12_ANCHOR_BY_TEXT_PAGE_SRC = toPageExport(c12AnchorElementByText);

/** Element facts for a failed frame tie, plus the same-block comparison. No census. */
export const C12_FRAME_TIE_PAGE_SRC = `${toPageExport(c12SameAnchorElement)};\n${toPageExport(c12FrameTieDiagnostic)}`;

/** The scroll call eval'd with the text finder it uses. */
export const C12_SCROLL_CARET_PAGE_SRC = `${C12_ANCHOR_BY_TEXT_PAGE_SRC};\n${toPageExport(c12ScrollCaretIntoView)}`;

export const C12_BODY_CARET_PAGE_SRC = `${C12_BLOCK_ENTRIES_PAGE_SRC};\n${C12_LOCATE_PAGE_SRC};\n${toPageExport(c12FirstBodyCaretIndex)};\n${toPageExport(c12BodyCaretClick)}`;

export const C12_IDENTITY_DIAGNOSTIC_PAGE_SRC = `${toPageExport(C12_IDENTITY_REFUSAL_DIAGNOSTIC)};\n${toPageExport(c12EmptyInclusiveWindow)}`;

export const C12_CARET_SELECTION_PAGE_SRC = toPageExport(c12CaretSelection);

/** Page context. C12 block census after the caret is placed (light-DOM blocks). */
export function gatherReflowBefore({
  editorId,
  docSel,
  pickBelowSrc,
  excludeSel,
  entriesSrc,
  locateSrc,
  caretText,
  anchorText,
  selectionSrc,
}) {
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
  const argCaret = String(caretText || '');
  const argAnchor = String(anchorText || '');
  const rememberedCaret = String(window.__c12FixtureCaretText || '');
  const rememberedAnchor = String(window.__c12FixtureAnchorText || '');
  const fixtureCaret = argCaret && argAnchor ? argCaret : rememberedCaret;
  const fixtureAnchor = argCaret && argAnchor ? argAnchor : rememberedAnchor;
  if (fixtureCaret && fixtureAnchor) {
    window.__c12FixtureCaretText = fixtureCaret;
    window.__c12FixtureAnchorText = fixtureAnchor;
  }
  let picked = null;
  if (fixtureCaret && fixtureAnchor) {
    // Re-find by the fixture strings. forcedCaret+1 is the next census row,
    // which is a header or a page number on some editors.
    let locate = null;
    if (typeof locateSrc === 'string' && locateSrc) {
      try {
        // eslint-disable-next-line no-eval
        locate = (0, eval)(`(function(){ ${locateSrc}; return c12LocateFixtureParagraphs; })()`);
      } catch {
        locate = null;
      }
    }
    if (typeof locate !== 'function') {
      return { ok: false, reason: 'fixture_paragraph_not_in_census', blocks: entries.length };
    }
    const located = locate(entries, fixtureCaret, fixtureAnchor, norm);
    if (!located || located.ok !== true) {
      return {
        ok: false,
        reason: (located && located.reason) || 'fixture_paragraph_not_in_census',
        blocks: entries.length,
      };
    }
    const caretIndex = located.caretIndex;
    const anchorIndex = located.anchorIndex;
    const caretEntry = entries[caretIndex];
    const anchor = entries[anchorIndex];
    if (!caretEntry || !anchor) {
      return { ok: false, reason: 'fixture_paragraph_not_in_census', blocks: entries.length };
    }
    const top = Number(anchor.top);
    if (!anchor.text || !Number.isFinite(top)) {
      return { ok: false, reason: 'anchor paragraph has no measurable box', blocks: entries.length };
    }
    if (top >= Number(window.innerHeight)) {
      return {
        ok: false,
        reason: 'anchor paragraph is off the viewport; a y-shift could not be attributed',
        blocks: entries.length,
        caretIndex,
        anchorIndex,
        caretText: String(caretEntry.text || '').slice(0, 80),
        anchorText: String(anchor.text || '').slice(0, 80),
        anchorTop: top,
        viewportHeight: Number(window.innerHeight),
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
      caretIndex,
      anchorOccurrence: occurrence,
      blockCount: entries.length,
      firstText: String(entries[0].text || '').slice(0, 40),
    };
  } else if (Number.isFinite(forcedCaret) && forcedCaret >= 0 && forcedCaret < entries.length) {
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
        caretIndex: forcedCaret,
        anchorIndex,
        caretText: String(caretEntry.text || '').slice(0, 80),
        anchorText: String(anchor.text || '').slice(0, 80),
        anchorTop: top,
        viewportHeight: Number(window.innerHeight),
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
  let caretSelection = null;
  if (typeof selectionSrc === 'string' && selectionSrc) {
    try {
      // eslint-disable-next-line no-eval
      const readSelection = (0, eval)(`(function(){ ${selectionSrc}; return c12CaretSelection; })()`);
      if (typeof readSelection === 'function') caretSelection = readSelection(entries);
    } catch {
      caretSelection = null;
    }
  }
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
    caret_selection: caretSelection,
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

/** Place the caret at the start of the fixture caret paragraph, or the first body block. */
export async function placeC12BodyCaret(page, editorId, reflowSel, excludeSel, fixture = {}) {
  const caretText = fixture && typeof fixture.caretText === 'string' ? fixture.caretText : '';
  const anchorText = fixture && typeof fixture.anchorText === 'string' ? fixture.anchorText : '';
  const pick = await page.evaluate(
    ({ editorId, docSel, excludeSel, bundleSrc, caretText, anchorText }) => {
      let resolveClick = null;
      try {
        // eslint-disable-next-line no-eval
        resolveClick = (0, eval)(`(function(){ ${bundleSrc}; return c12BodyCaretClick; })()`);
      } catch {
        resolveClick = null;
      }
      if (typeof resolveClick !== 'function') return { ok: false, reason: 'body caret bundle failed' };
      return resolveClick({ editorId, docSel, excludeSel, caretText, anchorText });
    },
    {
      editorId: editorId || '',
      docSel: reflowSel,
      excludeSel: excludeSel || '',
      bundleSrc: C12_BODY_CARET_PAGE_SRC,
      caretText,
      anchorText,
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
      click: pick.click,
    };
  }
  let clickHit = null;
  if (placed && placed.point && Number.isFinite(placed.point.x) && Number.isFinite(placed.point.y)) {
    try {
      clickHit = await page.evaluate(READ_CLICK_HIT, { x: placed.point.x, y: placed.point.y });
    } catch {
      clickHit = null;
    }
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
      anchorIndex: pick.anchorIndex,
      caretText: pick.caretText,
      anchorText: pick.anchorText,
      caret_verify: verified,
      point: placed.point,
      click: pick.click,
      click_hit: clickHit,
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
    click_hit: clickHit,
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
        blockTextSrc: C12_BLOCK_TEXT_PAGE_SRC,
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
  { settleMs = 100, editorId = '', excludeSel = '', caretText = '', anchorText = '' } = {},
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
  const bodyCaret = await placeC12BodyCaret(page, editorId, reflowSel, excludeSel, { caretText, anchorText });
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
