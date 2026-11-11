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
export function gatherReflowBefore({ docSel, editorId, useModel, model }) {
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

  const pickAnchor = (texts) => {
    if (texts.length < 2) {
      return { ok: false, reason: 'fewer than two document blocks; nothing below the insertion to move' };
    }
    const counts = new Map();
    for (const text of texts) {
      counts.set(text, (counts.get(text) || 0) + 1);
    }
    let anchorText = null;
    let anchorIndex = -1;
    for (let i = texts.length - 1; i >= 1; i--) {
      const text = texts[i];
      if (text && counts.get(text) === 1) {
        anchorText = text;
        anchorIndex = i;
        break;
      }
    }
    if (!anchorText) {
      return {
        ok: false,
        reason: 'no block below the insertion point has unique non-empty text; a y-shift could not be attributed',
        blocks: texts.length,
      };
    }
    return { ok: true, anchorText, anchorIndex, blockCount: texts.length, firstText: texts[0].slice(0, 40) };
  };

  if (useModel) {
    const paragraphs = listModelParagraphs(model);
    if (!Array.isArray(paragraphs)) {
      return { ok: false, reason: 'fewer than two document blocks; nothing below the insertion to move' };
    }
    const picked = pickAnchor(paragraphs);
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

  const blocks = Array.from(document.querySelectorAll(docSel));
  const texts = blocks.map((block) => (block.textContent || '').trim()).filter(Boolean);
  const picked = pickAnchor(texts);
  if (!picked.ok) {
    return { ...picked, blocks: blocks.length };
  }
  window.__c12AnchorEl = blocks[picked.anchorIndex];
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
    first_block_top: blocks[0].getBoundingClientRect().top,
    first_block_text: picked.firstText,
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
