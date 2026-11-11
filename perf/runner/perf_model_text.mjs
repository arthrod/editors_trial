import { normalizeDocumentText } from './document_text_normalize.mjs';

/** Fixture model length may differ by this fraction of the joined corpus text. */
export const MODEL_LENGTH_TOLERANCE = 0.02;

/** Coarse band for complex fixtures whose w:t baseline is editor-dependent. */
export const MODEL_COARSE_MIN_RATIO = 0.5;
export const MODEL_COARSE_MAX_RATIO = 1.5;

const flatText = (value) => value.replace(/[\s\p{White_Space}]+/gu, '');

/** Plain text from `window.__PERF_MODEL_TEXT__` when the host provides it. */
export function readPerfModelText() {
  const fn = typeof window !== 'undefined' ? window.__PERF_MODEL_TEXT__ : null;
  if (typeof fn !== 'function') {
    return { text: '', hook: false };
  }
  try {
    return { text: String(fn() ?? ''), hook: true };
  } catch (error) {
    return { text: '', hook: true, error: String(error && error.message ? error.message : error) };
  }
}

export function domTextFromSelector(selector) {
  const pick = (el) => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
  if (!selector) return pick(document.body || document.documentElement);
  const el = document.querySelector(selector);
  return el ? pick(el) : '';
}

/**
 * Canvas hosts with a text layer (Apryse) keep DOM/shadow text. The model hook is
 * used only when the surface is canvas-only (no disclosed DOM text) and the hook exists.
 */
export function resolveDocumentText({ domText, canvasPresent, hookPresent = false }) {
  const trimmedDom = (domText || '').trim();
  if (!canvasPresent) {
    return {
      text: domText,
      content_text_accessible: Boolean(trimmedDom),
      model_oracle: 'dom',
    };
  }
  if (hookPresent && !trimmedDom) {
    const model = readPerfModelText();
    return {
      text: model.text,
      content_text_accessible: Boolean((model.text || '').trim()),
      model_oracle: 'perf_model',
    };
  }
  if (trimmedDom) {
    return {
      text: domText,
      content_text_accessible: true,
      model_oracle: 'dom',
    };
  }
  return {
    text: domText,
    content_text_accessible: false,
    model_oracle: 'absent',
  };
}

function closingAtEnd(normText, normClosing) {
  if (!normClosing) return true;
  const text = flatText(normText);
  const closing = flatText(normClosing);
  if (!closing) return true;
  return text.endsWith(closing);
}

function lengthBandOk(modelChars, fixtureChars, lengthCheckMode) {
  if (!fixtureChars || fixtureChars <= 0 || lengthCheckMode === 'not_applicable') return true;
  if (lengthCheckMode === 'coarse') {
    const ratio = modelChars / fixtureChars;
    return ratio >= MODEL_COARSE_MIN_RATIO && ratio <= MODEL_COARSE_MAX_RATIO;
  }
  if (lengthCheckMode === 'opening_only') return true;
  return Math.abs(modelChars - fixtureChars) / fixtureChars <= MODEL_LENGTH_TOLERANCE;
}

/**
 * Whole-document gate for perf_model: opening and closing sentinels plus length band.
 * Runs on the full model string in the page; the runner receives integers and flags only.
 */
export function evaluatePerfModelDocument({
  text,
  expectedOpening,
  expectedClosing,
  fixtureChars,
  lengthCheckMode = null,
}) {
  const mode = lengthCheckMode || (fixtureChars > 0 ? 'applied' : 'not_applicable');
  const normText = normalizeDocumentText(text);
  const normOpening = normalizeDocumentText(expectedOpening);
  const normClosing = normalizeDocumentText(expectedClosing);
  const modelChars = text.length;
  const openingPresent = normOpening ? normText.includes(normOpening) : true;
  const closingPresent = closingAtEnd(normText, normClosing);
  const lengthOk = lengthBandOk(modelChars, fixtureChars, mode);
  const ok = Boolean(normText) && openingPresent && closingPresent && lengthOk;
  let surface_reason = null;
  if (!ok) {
    if (!normText) surface_reason = 'document_content_absent';
    else surface_reason = 'document_content_mismatch';
  }
  return {
    ok,
    openingPresent,
    closingPresent,
    lengthOk,
    model_chars: modelChars,
    surface_reason,
    length_check_mode: mode,
  };
}

const OPENING_ONLY_REASON =
  'editor DOM holds only the visible pages; closing witness and length band are not enforced';

/**
 * DOM document gate. Virtualized hosts (`whole: false`) verify opening text only.
 */
export function evaluateDomDocument({
  text,
  expectedOpening,
  expectedClosing,
  fixtureChars,
  lengthCheckMode = null,
  whole = true,
}) {
  if (!whole) {
    const normText = normalizeDocumentText(text);
    const normOpening = normalizeDocumentText(expectedOpening);
    const openingPresent = normOpening ? normText.includes(normOpening) : true;
    const ok = Boolean(normText) && openingPresent;
    return {
      ok,
      openingPresent,
      closingPresent: null,
      lengthOk: null,
      model_chars: text.length,
      surface_reason: ok ? null : (!normText ? 'document_content_absent' : 'document_content_mismatch'),
      content_check: 'opening_only',
      content_check_reason: OPENING_ONLY_REASON,
      length_check_mode: 'opening_only',
    };
  }
  const mode = lengthCheckMode || (fixtureChars > 0 ? 'applied' : 'not_applicable');
  const check = evaluatePerfModelDocument({
    text,
    expectedOpening,
    expectedClosing,
    fixtureChars,
    lengthCheckMode: mode,
  });
  return {
    ...check,
    content_check: 'full',
    content_check_reason: null,
    length_check_mode: mode,
  };
}

export function openingContentVerdict({
  expected,
  actual,
  modelOracle,
  modelDocumentCheck,
  domDocumentCheck,
  editorError = null,
}) {
  const normExpected = normalizeDocumentText(expected);
  if (!normExpected) {
    return { content_verified: false, surface_reason: null, editor_error: editorError || null };
  }
  if (editorError) {
    return {
      content_verified: false,
      surface_reason: 'document_content_unverifiable',
      editor_error: String(editorError),
    };
  }
  if (modelOracle === 'perf_model') {
    if (modelDocumentCheck?.ok) {
      return { content_verified: true, surface_reason: null, editor_error: null };
    }
    return {
      content_verified: false,
      surface_reason: modelDocumentCheck?.surface_reason || 'document_content_mismatch',
      editor_error: null,
    };
  }
  if (modelOracle === 'absent') {
    return { content_verified: false, surface_reason: 'document_content_unverifiable', editor_error: null };
  }
  if (modelOracle === 'dom') {
    if (domDocumentCheck) {
      if (domDocumentCheck.ok) {
        return { content_verified: true, surface_reason: null, editor_error: null };
      }
      return {
        content_verified: false,
        surface_reason: domDocumentCheck.surface_reason || 'document_content_mismatch',
        editor_error: null,
      };
    }
    const normActual = normalizeDocumentText(actual);
    if (!normActual) {
      return { content_verified: false, surface_reason: 'document_content_absent', editor_error: null };
    }
    const content_verified = flatText(normActual).includes(flatText(normExpected));
    if (!content_verified) {
      return { content_verified: false, surface_reason: 'document_content_mismatch', editor_error: null };
    }
    return { content_verified: true, surface_reason: null, editor_error: null };
  }
  const normActual = normalizeDocumentText(actual);
  if (!normActual) {
    return { content_verified: false, surface_reason: 'document_content_absent', editor_error: null };
  }
  const content_verified = flatText(normActual).includes(flatText(normExpected));
  if (!content_verified) {
    return { content_verified: false, surface_reason: 'document_content_mismatch', editor_error: null };
  }
  return { content_verified: true, surface_reason: null, editor_error: null };
}

/**
 * Resolve disclosure fields for a document read plus corpus flags.
 * Shared by warm_cold_browser.mjs and document_probe.mjs.
 */
export function documentContentGateMeta({
  documentRead,
  whole,
  expectedOpening,
  expectedClosing,
  fixtureChars,
  lengthCheckMode,
}) {
  const mode =
    lengthCheckMode
    || (documentRead.oracle === 'dom' && whole === false ? 'opening_only' : null)
    || (fixtureChars > 0 ? 'applied' : 'not_applicable');
  let modelDocumentCheck = null;
  let domDocumentCheck = null;
  let content_check = null;
  let content_check_reason = null;
  if (documentRead.oracle === 'perf_model') {
    modelDocumentCheck = evaluatePerfModelDocument({
      text: documentRead.text,
      expectedOpening,
      expectedClosing,
      fixtureChars,
      lengthCheckMode: mode,
    });
  } else if (documentRead.oracle === 'dom') {
    domDocumentCheck = evaluateDomDocument({
      text: documentRead.text,
      expectedOpening,
      expectedClosing,
      fixtureChars,
      lengthCheckMode: mode,
      whole: whole !== false,
    });
    content_check = domDocumentCheck.content_check;
    content_check_reason = domDocumentCheck.content_check_reason;
  }
  const verdict = openingContentVerdict({
    expected: expectedOpening,
    actual: documentRead.text,
    modelOracle: documentRead.oracle,
    modelDocumentCheck,
    domDocumentCheck,
    editorError: documentRead.error,
  });
  let length_check = 'not_applicable';
  if (documentRead.oracle === 'dom' && domDocumentCheck?.content_check === 'opening_only') {
    length_check = 'opening_only';
  } else if (mode === 'coarse' && fixtureChars > 0) {
    length_check = 'coarse';
  } else if (mode === 'applied' && fixtureChars > 0) {
    length_check = 'applied';
  }
  const length_enforced = length_check === 'applied' || length_check === 'coarse';
  return {
    verdict,
    modelDocumentCheck,
    domDocumentCheck,
    content_check,
    content_check_reason,
    length_check,
    length_enforced,
  };
}
