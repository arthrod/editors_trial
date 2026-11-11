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

/** Editors whose C12 blocks are read from the editor model, not light-DOM text nodes. */
export const REFLOW_MODEL_EDITORS = new Set(['canvas', 'docen']);

/**
 * The C12 anchor: the nearest unique block BELOW the caret that is on the
 * same screen as the caret (r3lanes4 ruling 3). The last unique block of the
 * document could sit on a later page that never moves when the insertion
 * reflows the first screen, so it can never carry the measured shift.
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
  const counts = new Map();
  for (const entry of entries) counts.set(entry.text, (counts.get(entry.text) || 0) + 1);
  let anchor = null;
  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];
    const top = Number(entry.top);
    if (!entry.text || counts.get(entry.text) !== 1) continue;
    if (!Number.isFinite(top)) continue;
    if (top <= Number(caret.bottom)) continue;
    if (top >= Number(viewportHeight)) continue;
    if (!anchor || top < anchor.top) anchor = { ...entry, index: i, top };
  }
  if (!anchor) {
    return {
      ok: false,
      reason: 'no unique document block below the caret in the viewport; a y-shift could not be attributed',
      blocks: entries.length,
    };
  }
  return {
    ok: true,
    anchorText: anchor.text,
    anchorIndex: anchor.index,
    blockCount: entries.length,
    firstText: String(entries[0].text || '').slice(0, 40),
  };
};


/** Block selector for C12 reflow after the shared adapter has entered edit mode. */
export function reflowBlockSelector(editorId, fallback) {
  if (!editorId || !EDIT_SURFACES[editorId]) return fallback;
  if (editorId === 'docxodus') return '#editorHost p, #editorHost [data-anchor]';
  if (editorId === 'superdoc') return '.superdoc-line';
  if (editorId === 'genoffice') return '.doc-page p';
  if (editorId === 'eigenpal') return '[data-paragraph-id]';
  if (editorId === 'folio') return '.layout-page-content [data-block-id]';
  if (editorId === 'plate') return '.doc-paragraph';
  const surface = editSurface(editorId);
  if (surface.kind === 'dom' && surface.block) return surface.block;
  return fallback;
}

/** Page context: paragraph texts from the model APIs canvas/docen use elsewhere. */
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

/** Page context: y-shift proxy for canvas/docen when paragraphs live only in the model. */
export const REFLOW_Y_PROXY = (editorId) => {
  if (editorId === 'canvas') {
    return document.querySelector('#editor .ce-page-container');
  }
  if (editorId === 'docen') {
    const host = document.querySelector('docen-document');
    const root = host && host.shadowRoot;
    return (root && root.querySelector('.canvas-pages > div')) || null;
  }
  return null;
};

/** Page context. C12 block census after edit-surface prep (dom or model paragraphs). */
export function gatherReflowBefore({ docSel, editorId, useModel, model, pickBelowSrc }) {
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
  const listModelParagraphs = (kind) => {
    if (kind === 'docen') {
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
    if (kind === 'canvas_editor') {
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
  const yProxy = (key) => {
    if (key === 'canvas') return document.querySelector('#editor .ce-page-container');
    if (key === 'docen') {
      const host = document.querySelector('docen-document');
      const root = host && host.shadowRoot;
      return (root && root.querySelector('.canvas-pages > div')) || null;
    }
    return null;
  };

  const pickAnchor = (entries) => {
    if (entries.length < 2) {
      return { ok: false, reason: 'fewer than two document blocks; nothing below the insertion to move' };
    }
    const counts = new Map();
    for (const entry of entries) {
      counts.set(entry.text, (counts.get(entry.text) || 0) + 1);
    }
    let anchor = null;
    for (let i = entries.length - 1; i >= 1; i--) {
      const entry = entries[i];
      if (entry.text && counts.get(entry.text) === 1) {
        anchor = { ...entry, index: i };
        break;
      }
    }
    if (!anchor) {
      return {
        ok: false,
        reason: 'no block below the insertion point has unique non-empty text; a y-shift could not be attributed',
        blocks: entries.length,
      };
    }
    return {
      ok: true,
      anchorText: anchor.text,
      anchorIndex: anchor.index,
      anchorEl: anchor.el || null,
      blockCount: entries.length,
      firstText: entries[0].text.slice(0, 40),
    };
  };

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

  if (useModel) {
    const paragraphs = listModelParagraphs(model);
    if (!Array.isArray(paragraphs)) {
      return { ok: false, reason: 'fewer than two document blocks; nothing below the insertion to move' };
    }
    const picked = pickAnchor(paragraphs.map((text) => ({ text })));
    if (!picked.ok) return picked;
    const proxy = yProxy(editorId);
    if (!proxy) {
      return { ok: false, reason: 'edit target has no box' };
    }
    window.__c12AnchorEl = proxy;
    window.__c12AnchorTop = proxy.getBoundingClientRect().top;
    window.__c12AnchorText = picked.anchorText;
    window.__c12DocSel = docSel;
    window.__c12ModelReflow = true;
    return {
      ok: true,
      blocks: picked.blockCount,
      anchor_index: picked.anchorIndex,
      anchor_text: picked.anchorText,
      anchor_top: window.__c12AnchorTop,
      first_block_top: window.__c12AnchorTop,
      first_block_text: picked.firstText,
      model_oracle: model,
    };
  }

  const entries = Array.from(document.querySelectorAll(docSel))
    .map((block) => ({
      el: block,
      text: (block.textContent || '').trim(),
      top: block.getBoundingClientRect().top,
    }))
    .filter((entry) => entry.text);
  const caret = caretBox();
  // The anchor is the nearest unique block below the caret on the same
  // screen, never the last unique block of the document (r3lanes4 ruling 3).
  const picked = typeof pickBelow === 'function'
    ? pickBelow(entries, caret, window.innerHeight)
    : { ok: false, reason: 'anchor picker unavailable; a y-shift could not be attributed' };  if (!picked.ok) {
    return { ...picked, blocks: entries.length, caret_top: caret ? caret.top : null };
  }
  window.__c12AnchorEl = entries[picked.anchorIndex].el;
  window.__c12AnchorTop = window.__c12AnchorEl.getBoundingClientRect().top;
  window.__c12AnchorText = picked.anchorText;
  window.__c12DocSel = docSel;
  window.__c12ModelReflow = false;
  return {
    ok: true,
    blocks: picked.blockCount,
    anchor_index: picked.anchorIndex,
    anchor_text: picked.anchorText,
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
