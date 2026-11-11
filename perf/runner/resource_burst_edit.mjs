/**
 * B8 resource lane edit burst.
 *
 * The resource lane measures keyboard input, not frame capture. Clock checks,
 * caret masks, screencasts, and pixel witnesses are deliberately absent: a
 * continuously encoding recorder would add renderer/GPU work to the measured
 * typing window, and pixels cannot prove that document text landed.
 */
import {
  BURST_VERIFY_MODEL,
  EDIT_SURFACES,
  insertedOnce,
  placeCaret,
  readBurstVerifyText,
  readModifiedFlag,
} from './edit_surface.mjs';

export const DEFAULT_PRE_TYPE_SETTLE_MS = 300;
export const DEFAULT_SETTLE_MS = 500;
export const DEFAULT_POLL_BOUND_MS = 2000;
export const DEFAULT_POLL_INTERVAL_MS = 50;

export function countToken(text, token) {
  const source = String(text || '');
  if (!token) return 0;
  let count = 0;
  let start = 0;
  while (true) {
    const at = source.indexOf(token, start);
    if (at < 0) return count;
    count += 1;
    start = at + token.length;
  }
}

const READ_DOM_TEXT = (selector) => {
  const el = document.querySelector(selector);
  if (!el) return '';
  const tag = String(el.tagName || '').toUpperCase();
  if ((tag === 'INPUT' || tag === 'TEXTAREA') && 'value' in el) return String(el.value || '');
  return String(el.innerText || el.textContent || '');
};

const READ_PERF_MODEL_TEXT = () => {
  const fn = window.__PERF_MODEL_TEXT__;
  if (typeof fn !== 'function') {
    return { text: '', hook: false, available: false, error: null };
  }
  try {
    return {
      text: String(fn() ?? ''),
      hook: true,
      available: true,
      error: null,
    };
  } catch (error) {
    return {
      text: '',
      hook: true,
      available: false,
      error: String(error && error.message ? error.message : error),
    };
  }
};

const READ_CANVAS_MODEL_TEXT = () => {
  const hook = window.__PERF_MODEL_TEXT__;
  if (typeof hook === 'function') {
    try {
      return {
        text: String(hook() ?? ''),
        hook: true,
        available: true,
        oracle: 'perf_model',
        error: null,
      };
    } catch (error) {
      return {
        text: '',
        hook: true,
        available: false,
        oracle: 'perf_model',
        error: String(error && error.message ? error.message : error),
      };
    }
  }

  const inst = window.__CANVAS_EDITOR_INSTANCE__;
  const cmd = inst && inst.command;
  if (!cmd || typeof cmd.getValue !== 'function') {
    return {
      text: '',
      hook: false,
      available: false,
      oracle: 'canvas_model',
      error: null,
    };
  }
  try {
    const out = [];
    const walk = (node) => {
      if (Array.isArray(node)) return node.forEach(walk);
      if (!node || typeof node !== 'object') return;
      if (typeof node.value === 'string') out.push(node.value);
      for (const key of ['valueList', 'trList', 'tdList']) {
        if (node[key]) walk(node[key]);
      }
    };
    const data = cmd.getValue().data;
    if (!data || typeof data !== 'object') {
      return {
        text: '',
        hook: false,
        available: true,
        oracle: 'canvas_model',
        error: null,
      };
    }
    for (const zone of ['header', 'main', 'footer']) walk(data[zone]);
    return {
      text: out.join('').replace(/\n/g, ' '),
      hook: false,
      available: true,
      oracle: 'canvas_model',
      error: null,
    };
  } catch (error) {
    return {
      text: '',
      hook: false,
      available: false,
      oracle: 'canvas_model',
      error: String(error && error.message ? error.message : error),
    };
  }
};

async function armTrustedKeyCounter(page) {
  await page.evaluate(() => {
    window.__b8burst = { keys: 0 };
    const onKey = (event) => {
      // A key counts when an element holds focus: a key sent to the page body reached no editor.
      const onEditor = event.target && event.target !== document.body && event.target !== document.documentElement;
      if (event.isTrusted && event.key && event.key.length === 1 && onEditor) {
        window.__b8burst.keys += 1;
      }
    };
    window.__b8burst.stop = () => document.removeEventListener('keydown', onKey, true);
    document.addEventListener('keydown', onKey, true);
  });
}

async function trustedKeyCount(page) {
  return page.evaluate(() => {
    try {
      window.__b8burst?.stop?.();
    } catch {
      /* the page may already have navigated away */
    }
    return Number(window.__b8burst?.keys || 0);
  });
}

function burstParams(params = {}) {
  return {
    editorId: params.editorId || '',
    selector: params.selector || '',
    text: String(params.text || ''),
    repetitions: Math.max(0, Number(params.repetitions || 0)),
    witness: params.witness || { mode: 'dom_text' },
    preTypeSettleMs: Number.isFinite(Number(params.preTypeSettleMs))
      ? Math.max(0, Number(params.preTypeSettleMs))
      : DEFAULT_PRE_TYPE_SETTLE_MS,
    settleMs: Number.isFinite(Number(params.settleMs))
      ? Math.max(0, Number(params.settleMs))
      : DEFAULT_SETTLE_MS,
    pollBoundMs: Number.isFinite(Number(params.pollBoundMs))
      ? Math.max(0, Number(params.pollBoundMs))
      : DEFAULT_POLL_BOUND_MS,
    pollIntervalMs: Number.isFinite(Number(params.pollIntervalMs))
      ? Math.max(1, Number(params.pollIntervalMs))
      : DEFAULT_POLL_INTERVAL_MS,
  };
}

/**
 * Focus the editor and capture the pre-edit text outside the measured CPU
 * window. The fixed pre-type settle prevents the reproduced canvas race where
 * keystrokes sent immediately after focus are lost.
 */
export async function prepareResourceBurst(page, params = {}) {
  const opts = burstParams(params);
  if (EDIT_SURFACES[opts.editorId]) return prepareOnSurface(page, opts);
  if (opts.selector) {
    await page.locator(opts.selector).first().click({ timeout: 30000 });
  }
  if (opts.preTypeSettleMs > 0) {
    await page.waitForTimeout(opts.preTypeSettleMs);
  }

  let beforeText = '';
  let modelHook = false;
  let modelHookError = null;
  let modelAvailable = true;
  let oracleMode = opts.witness.mode;

  if (opts.witness.mode === 'canvas_model') {
    const snapshot = await page.evaluate(READ_CANVAS_MODEL_TEXT);
    beforeText = String(snapshot.text || '');
    modelHook = snapshot.hook === true;
    modelHookError = snapshot.error || null;
    modelAvailable = snapshot.available !== false;
    oracleMode = snapshot.oracle || 'canvas_model';
  } else if (opts.witness.mode === 'paint_ink') {
    const snapshot = await page.evaluate(READ_PERF_MODEL_TEXT);
    beforeText = String(snapshot.text || '');
    modelHook = snapshot.hook === true;
    modelHookError = snapshot.error || null;
    modelAvailable = snapshot.hook === true && snapshot.available !== false;
    oracleMode = snapshot.hook ? 'perf_model' : 'paint_ink';
  } else if (opts.selector) {
    beforeText = await page.evaluate(READ_DOM_TEXT, opts.selector);
  }

  await armTrustedKeyCounter(page);
  return {
    beforeText,
    modelAvailable,
    modelHook,
    modelHookError,
    oracleMode,
    preTypeSettleMs: opts.preTypeSettleMs,
    repetitions: opts.repetitions,
    text: opts.text,
    witnessMode: opts.witness.mode,
  };
}

const ORACLE_MODE = {
  dom: 'caret_block_text',
  model: 'caret_model_text',
  flag: 'editor_modified_flag',
  editor_model: 'editor_model_text',
};

/**
 * The editor's own edit surface (edit_surface.mjs): caret on a body text line
 * of the first screen, focus held by the editor, and the text of the block at
 * the caret as the pre-edit state. All of it is outside the measured window.
 */
async function prepareOnSurface(page, opts) {
  const surface = EDIT_SURFACES[opts.editorId];
  const modelBurst = BURST_VERIFY_MODEL.has(opts.editorId);
  const prepared = {
    surface: surface.kind,
    editorId: opts.editorId,
    oracleMode: modelBurst ? ORACLE_MODE.editor_model : ORACLE_MODE[surface.kind],
    witnessMode: opts.witness.mode,
    preTypeSettleMs: opts.preTypeSettleMs,
    repetitions: opts.repetitions,
    text: opts.text,
    point: null,
    line: null,
    focused: false,
    placeError: null,
    beforeText: null,
    beforeFlag: null,
  };
  try {
    const placed = await placeCaret(page, opts.editorId, opts.selector);
    prepared.point = placed.point ? { x: placed.point.x, y: placed.point.y } : null;
    prepared.line = placed.point ? placed.point.line : null;
    prepared.focused = placed.focused;
  } catch (error) {
    prepared.placeError = String(error && error.message ? error.message : error).slice(0, 200);
    return prepared;
  }
  if (opts.preTypeSettleMs > 0) await page.waitForTimeout(opts.preTypeSettleMs);
  if (surface.kind === 'flag') {
    prepared.beforeFlag = await readModifiedFlag(page, opts.editorId);
  } else {
    prepared.beforeText = await readBurstVerifyText(page, opts.editorId, prepared.point);
  }
  await armTrustedKeyCounter(page);
  return prepared;
}

async function verifyOnSurface(page, opts, prepared) {
  const keys = prepared.placeError ? 0 : await trustedKeyCount(page);
  const minKeys = opts.text.length * opts.repetitions;
  const started = Date.now();
  const deadline = started + opts.pollBoundMs;
  let status = 'edit_not_applied';
  let reason = null;
  let delta = null;
  let afterText = null;
  let afterFlag = null;
  let attempts = 0;

  if (prepared.placeError) {
    reason = prepared.placeError;
  } else if (prepared.surface === 'flag') {
    if (!prepared.beforeFlag) {
      status = 'edit_unverified';
      reason = 'modified_flag_unreadable';
    } else if (prepared.beforeFlag.modified) {
      status = 'edit_unverified';
      reason = 'modified_before_edit';
    } else {
      while (true) {
        attempts += 1;
        afterFlag = await readModifiedFlag(page, prepared.editorId);
        if (afterFlag && afterFlag.modified) {
          status = 'verified';
          break;
        }
        if (Date.now() >= deadline) {
          reason = 'poll_timeout';
          break;
        }
        await page.waitForTimeout(opts.pollIntervalMs);
      }
    }
  } else if (prepared.beforeText == null) {
    status = 'edit_unverified';
    reason = 'caret_scope_unreadable';
  } else {
    const base = countToken(prepared.beforeText, opts.text);
    while (true) {
      attempts += 1;
      afterText = await readBurstVerifyText(page, prepared.editorId, prepared.point);
      delta = countToken(afterText, opts.text) - base;
      if (delta === opts.repetitions) {
        // The same block must hold the burst as one insertion; a block that
        // was replaced under the caret is not this edit.
        if (insertedOnce(prepared.beforeText, afterText, opts.text.repeat(opts.repetitions))) {
          status = 'verified';
        } else {
          reason = 'not_one_insertion';
        }
        break;
      }
      if (Date.now() >= deadline) {
        reason = 'poll_timeout';
        break;
      }
      await page.waitForTimeout(opts.pollIntervalMs);
    }
  }
  if (status === 'verified' && keys < minKeys) {
    status = 'edit_not_applied';
    reason = 'trusted_keys_below_min';
  }
  if (!opts.text || opts.repetitions <= 0) {
    status = 'edit_not_applied';
    reason = reason || 'empty_edit_burst';
  }
  const clip = (value) => (value == null ? null : String(value).slice(0, 160));
  const oracle = {
    mode: prepared.oracleMode,
    witness_mode: prepared.oracleMode,
    status,
    reason,
    model_hook: prepared.surface === 'model' || BURST_VERIFY_MODEL.has(prepared.editorId),
    model_hook_error: null,
    trusted_keys: keys,
    min_trusted_keys: minKeys,
    expected_text_delta: prepared.surface === 'flag' ? null : opts.repetitions,
    text_delta: delta,
    poll_attempts: attempts,
    poll_bound_ms: opts.pollBoundMs,
    poll_interval_ms: opts.pollIntervalMs,
    poll_elapsed_ms: Date.now() - started,
    caret_line: prepared.line,
    editor_focused: prepared.focused,
    scope_before: clip(prepared.surface === 'flag' ? prepared.beforeFlag && prepared.beforeFlag.evidence : prepared.beforeText),
    scope_after: clip(prepared.surface === 'flag' ? afterFlag && afterFlag.evidence : afterText),
  };
  const result = {
    applied: status === 'verified',
    kind: 'keyboard.type',
    text: opts.text,
    repetitions: opts.repetitions,
    witness: prepared.oracleMode,
    oracle,
  };
  if (prepared.surface !== 'flag') {
    result.beforeText = String(prepared.beforeText ?? '');
    result.editorText = String(afterText ?? '');
  }
  return result;
}

/** Keyboard input only. No model reads or key counting happen in this phase. */
export async function typeResourceBurst(page, params = {}) {
  const opts = burstParams(params);
  const start = performance.now();
  for (let i = 0; i < opts.repetitions; i++) {
    await page.keyboard.type(opts.text, { delay: 0 });
  }
  const end = performance.now();
  return {
    typed_chars: opts.text.length * opts.repetitions,
    typing_duration_ms: end - start,
    start_page_ms: start,
    end_page_ms: end,
  };
}

async function pollModelText(page, reader, prepared, opts) {
  const started = Date.now();
  const deadline = started + opts.pollBoundMs;
  let attempts = 0;
  let snapshot = null;
  let delta = null;

  while (true) {
    attempts += 1;
    snapshot = await reader(page);
    if (snapshot.error) {
      return {
        status: 'edit_unverified',
        reason: 'model_hook_error',
        mode: snapshot.oracle || prepared.oracleMode,
        modelHook: snapshot.hook === true,
        modelHookError: snapshot.error,
        textDelta: null,
        attempts,
        elapsedMs: Date.now() - started,
        snapshot,
      };
    }
    if (snapshot.available === false) {
      const reason = prepared.witnessMode === 'paint_ink'
        ? 'model_hook_unavailable'
        : 'model_unavailable';
      return {
        status: 'edit_unverified',
        reason,
        mode: snapshot.oracle || prepared.oracleMode,
        modelHook: snapshot.hook === true,
        modelHookError: null,
        textDelta: null,
        attempts,
        elapsedMs: Date.now() - started,
        snapshot,
      };
    }

    delta = countToken(snapshot.text, opts.text) - countToken(prepared.beforeText, opts.text);
    if (delta === opts.repetitions) {
      return {
        status: 'verified',
        reason: null,
        mode: snapshot.oracle || prepared.oracleMode,
        modelHook: snapshot.hook === true,
        modelHookError: null,
        textDelta: delta,
        attempts,
        elapsedMs: Date.now() - started,
        snapshot,
      };
    }
    if (Date.now() >= deadline) {
      return {
        status: 'edit_not_applied',
        reason: 'poll_timeout',
        mode: snapshot.oracle || prepared.oracleMode,
        modelHook: snapshot.hook === true,
        modelHookError: null,
        textDelta: delta,
        attempts,
        elapsedMs: Date.now() - started,
        snapshot,
      };
    }
    const remaining = deadline - Date.now();
    await page.waitForTimeout(Math.min(opts.pollIntervalMs, Math.max(1, remaining)));
  }
}

/** Read and verify the document/model text after the measured CPU endpoint. */
export async function verifyResourceBurst(page, cdp, params = {}, prepared = {}) {
  void cdp;
  const opts = burstParams(params);
  if (prepared && prepared.surface) return verifyOnSurface(page, opts, prepared);
  const state = {
    beforeText: String(prepared.beforeText || ''),
    modelAvailable: prepared.modelAvailable !== false,
    modelHook: prepared.modelHook === true,
    modelHookError: prepared.modelHookError || null,
    oracleMode: prepared.oracleMode || opts.witness.mode,
    repetitions: opts.repetitions,
    text: opts.text,
    witnessMode: prepared.witnessMode || opts.witness.mode,
  };
  const keys = await trustedKeyCount(page);
  const minKeys = opts.text.length * opts.repetitions;

  let status;
  let reason = null;
  let mode = state.oracleMode;
  let modelHook = state.modelHook;
  let modelHookError = state.modelHookError;
  let delta = null;
  let afterText = '';
  let pollAttempts = 0;
  let pollElapsedMs = null;

  if (opts.witness.mode === 'canvas_model') {
    const polled = await pollModelText(page, (target) => target.evaluate(READ_CANVAS_MODEL_TEXT), state, opts);
    status = polled.status;
    reason = polled.reason;
    mode = polled.mode;
    modelHook = polled.modelHook;
    modelHookError = polled.modelHookError;
    delta = polled.textDelta;
    pollAttempts = polled.attempts;
    pollElapsedMs = polled.elapsedMs;
    afterText = String(polled.snapshot?.text || '');
  } else if (opts.witness.mode === 'paint_ink') {
    const polled = await pollModelText(page, (target) => target.evaluate(READ_PERF_MODEL_TEXT), state, opts);
    status = polled.status;
    reason = polled.reason;
    mode = polled.mode;
    modelHook = polled.modelHook;
    modelHookError = polled.modelHookError;
    delta = polled.textDelta;
    pollAttempts = polled.attempts;
    pollElapsedMs = polled.elapsedMs;
    afterText = String(polled.snapshot?.text || '');
  } else {
    if (opts.selector) afterText = await page.evaluate(READ_DOM_TEXT, opts.selector);
    delta = countToken(afterText, opts.text) - countToken(state.beforeText, opts.text);
    if (delta === opts.repetitions) {
      status = 'verified';
      mode = 'dom_text';
    } else {
      status = 'edit_not_applied';
      reason = 'text_delta_mismatch';
      mode = 'dom_text';
    }
  }

  if (status === 'verified' && keys < minKeys) {
    status = 'edit_not_applied';
    reason = 'trusted_keys_below_min';
  }
  if (!opts.text || opts.repetitions <= 0) {
    status = 'edit_not_applied';
    reason = reason || 'empty_edit_burst';
  }

  const oracle = {
    mode,
    witness_mode: state.witnessMode,
    status,
    reason,
    model_hook: modelHook,
    model_hook_error: modelHookError,
    trusted_keys: keys,
    min_trusted_keys: minKeys,
    expected_text_delta: opts.repetitions,
    text_delta: delta,
    poll_attempts: pollAttempts,
    poll_bound_ms: opts.witness.mode === 'dom_text' ? null : opts.pollBoundMs,
    poll_interval_ms: opts.witness.mode === 'dom_text' ? null : opts.pollIntervalMs,
    poll_elapsed_ms: pollElapsedMs,
  };
  return {
    applied: status === 'verified',
    beforeText: state.beforeText,
    editorText: afterText,
    kind: 'keyboard.type',
    text: opts.text,
    repetitions: opts.repetitions,
    witness: state.witnessMode,
    oracle,
  };
}

/**
 * Compatibility wrapper. The production resource lane calls the three phases
 * separately so Python can own the CPU boundaries; this wrapper delegates to
 * the same implementations for existing bridge callers.
 */
export async function applyResourceBurst(page, cdp, params = {}) {
  const opts = burstParams(params);
  const prepared = await prepareResourceBurst(page, opts);
  await typeResourceBurst(page, opts);
  if (opts.settleMs > 0) await page.waitForTimeout(opts.settleMs);
  return verifyResourceBurst(page, cdp, opts, prepared);
}
