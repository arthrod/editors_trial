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
      reason: 'no caret box at the insertion; the block below the caret cannot be identified',
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
  let anchor = null;
  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];
    const top = Number(entry.top);
    if (!entry.text || !Number.isFinite(top)) continue;
    // Blocks flush under the caret (top ~= caret.bottom) still carry the shift.
    if (top < Number(caret.bottom) - 0.5) continue;
    if (top >= Number(viewportHeight)) continue;
    if (!anchor || top < anchor.top) anchor = { ...entry, index: i, top };
  }
  if (!anchor) {
    return {
      ok: false,
      reason: 'no document block below the caret in the viewport; a y-shift could not be attributed',
      blocks: entries.length,
    };
  }
  let occurrence = 0;
  for (let i = 0; i <= anchor.index; i++) {
    if (entries[i].text === anchor.text) occurrence += 1;
  }
  return {
    ok: true,
    anchorText: anchor.text,
    anchorIndex: anchor.index,
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
  if (editorId === 'docxodus') return '#editorHost';
  return '';
}

/** Block selector for C12 reflow after the shared adapter has entered edit mode. */
export function reflowBlockSelector(editorId, fallback) {
  if (!editorId || !EDIT_SURFACES[editorId]) return fallback;
  if (editorId === 'docxodus') return '#editorHost p, #editorHost [data-anchor]';
  if (editorId === 'superdoc') return '#editor .superdoc-line';
  if (editorId === 'genoffice') return '.doc-page p';
  if (editorId === 'eigenpal') return '[data-paragraph-id]';
  if (editorId === 'folio') return '.layout-page-content [data-block-id]';
  if (editorId === 'plate') return '.doc-paragraph';
  const surface = editSurface(editorId);
  if (surface.kind === 'dom' && surface.block) return surface.block;
  return fallback;
}

/** Visible text of one reflow block; innerText matches what users see when runs split. */
export const C12_BLOCK_TEXT = (block, norm) => norm(block.innerText || block.textContent);

/**
 * Occurrence re-find is allowed only when the equal-text block count is unchanged
 * and the prefix before the anchor still matches (one Enter insertion permitted).
 */
export function ANCHOR_REFIND_CONTEXT_OK(snapshot, blocks, readBlock) {
  const caretBlockTextMatches = (beforeText, afterText) => {
    if (beforeText === afterText) return true;
    // The reflow probe types one ascii key after Enter at the caret block.
    if (afterText === `x${beforeText}`) return true;
    return false;
  };
  if (!snapshot || !snapshot.anchorText) return { ok: true };
  const anchorText = snapshot.anchorText;
  const texts = blocks.map((block) => readBlock(block)).filter((text) => text);
  const beforeCount = Number(snapshot.anchorTextCount);
  if (!Number.isFinite(beforeCount)) return { ok: true };
  const afterCount = texts.filter((text) => text === anchorText).length;
  if (afterCount !== beforeCount) {
    return { ok: false, reason: 'anchor_identity_ambiguous' };
  }
  if (beforeCount === 1) {
    return { ok: true };
  }
  const wantOccurrence = Number(snapshot.anchorOccurrence);
  if (!Number.isFinite(wantOccurrence) || wantOccurrence < 1) return { ok: true };
  let seen = 0;
  let afterAnchorIndex = -1;
  for (let i = 0; i < texts.length; i++) {
    if (texts[i] !== anchorText) continue;
    seen += 1;
    if (seen === wantOccurrence) {
      afterAnchorIndex = i;
      break;
    }
  }
  if (afterAnchorIndex < 0) return { ok: false, reason: 'anchor_identity_ambiguous' };
  const beforePrefix = Array.isArray(snapshot.prefixTexts) ? snapshot.prefixTexts : [];
  const afterPrefix = texts.slice(0, afterAnchorIndex);
  if (afterPrefix.length === beforePrefix.length) {
    if (beforePrefix.length && !caretBlockTextMatches(beforePrefix[0], afterPrefix[0])) {
      return { ok: false, reason: 'anchor_identity_ambiguous' };
    }
    if (afterPrefix.slice(1).join('\u0000') !== beforePrefix.slice(1).join('\u0000')) {
      return { ok: false, reason: 'anchor_identity_ambiguous' };
    }
    return { ok: true };
  }
  if (afterPrefix.length === beforePrefix.length + 1) {
    if (beforePrefix.length === 0) return { ok: false, reason: 'anchor_identity_ambiguous' };
    if (!caretBlockTextMatches(beforePrefix[0], afterPrefix[0])) {
      return { ok: false, reason: 'anchor_identity_ambiguous' };
    }
    if (afterPrefix.slice(2).join('\u0000') !== beforePrefix.slice(1).join('\u0000')) {
      return { ok: false, reason: 'anchor_identity_ambiguous' };
    }
    return { ok: true };
  }
  return { ok: false, reason: 'anchor_identity_ambiguous' };
}

/** Pick the anchor block among equal-text matches after a DOM re-render. */
export function REFIND_ANCHOR(
  docSel,
  anchorText,
  anchorTop,
  norm,
  blockText,
  anchorOccurrence = null,
) {
  if (!anchorText || !docSel) return null;
  const blocks = Array.from(document.querySelectorAll(docSel));
  const readBlock =
    typeof blockText === 'function'
      ? blockText
      : (block, normalizer) => normalizer(block.innerText || block.textContent);
  const read = (block) => readBlock(block, norm);
  const snapshot = typeof window !== 'undefined' ? window.__c12BeforeSnapshot : null;
  const useOccurrence = Number.isFinite(Number(anchorOccurrence)) && Number(anchorOccurrence) >= 1;
  if (useOccurrence && snapshot) {
    const check = ANCHOR_REFIND_CONTEXT_OK(snapshot, blocks, read);
    if (!check.ok) {
      if (typeof window !== 'undefined') window.__c12AnchorRefusal = check.reason;
      return null;
    }
  }
  if (useOccurrence) {
    let seen = 0;
    for (const block of blocks) {
      if (read(block) !== anchorText) continue;
      seen += 1;
      if (seen === Number(anchorOccurrence)) return block;
    }
    return null;
  }
  const matches = blocks.filter((block) => blockText(block, norm) === anchorText);
  if (matches.length === 1) return matches[0];
  if (matches.length > 1 && Number.isFinite(Number(anchorTop))) {
    let best = null;
    let bestDist = Infinity;
    for (const block of matches) {
      const top = block.getBoundingClientRect().top;
      const dist = Math.abs(top - Number(anchorTop));
      if (dist < bestDist) {
        bestDist = dist;
        best = block;
      }
    }
    return best;
  }
  return null;
}

const toPageExport = (fn) => fn.toString().replace(/^export\s+/, '');

/** Page-evaluable source for ANCHOR_REFIND_CONTEXT_OK alone. */
export const ANCHOR_REFIND_CONTEXT_OK_PAGE_SRC = toPageExport(ANCHOR_REFIND_CONTEXT_OK);

/** Both helpers eval'd together in the page (REFIND_ANCHOR calls ANCHOR_REFIND_CONTEXT_OK). */
export const REFIND_ANCHOR_PAGE_SRC = `${ANCHOR_REFIND_CONTEXT_OK_PAGE_SRC};\n${toPageExport(REFIND_ANCHOR)}`;

/** Page context. C12 block census after the caret is placed (light-DOM blocks). */
export function gatherReflowBefore({ docSel, pickBelowSrc, excludeSel }) {
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
  const readBlock = (block) => norm(block.innerText || block.textContent);
  const excluded = excludeSel ? Array.from(document.querySelectorAll(excludeSel)) : [];
  const entries = Array.from(document.querySelectorAll(docSel))
    .filter((block) => !excluded.some((root) => root === block || root.contains(block)))
    .map((block) => ({
      el: block,
      text: readBlock(block),
      top: block.getBoundingClientRect().top,
    }))
    .filter((entry) => entry.text);
  let caret = caretBox();
  // Some hosts keep the selection in an off-DOM textbox; Home then reports
  // (0,0). After restoreReflowCaret, treat the caret as inside the first
  // visible reflow block so the anchor is the next block down, not the one
  // being split by Enter at the document start.
  if ((!caret || caret.bottom <= caret.top + 1) && entries.length) {
    const r = entries[0].el.getBoundingClientRect();
    if (r.height > 0) caret = { top: r.top, bottom: r.top + Math.min(1, r.height) };
  }
  // The anchor is the nearest block below the caret on the same screen.
  const picked = typeof pickBelow === 'function'
    ? pickBelow(entries, caret, window.innerHeight)
    : { ok: false, reason: 'anchor picker unavailable; a y-shift could not be attributed' };  if (!picked.ok) {
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
  };
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

/** After Control+Home/Home, some hosts leave a zero-height selection (off-DOM). */
export async function ensureReflowCaret(page, reflowSel, { settleMs = 100 } = {}) {
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
  if (!primary) return { restored: false, reason: 'no reflow selector' };
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
