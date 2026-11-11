import { normalizeDocumentText } from './document_text_normalize.mjs';

/** Fixture model length may differ by this fraction of the joined corpus text. */
export const MODEL_LENGTH_TOLERANCE = 0.02;

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

/**
 * Whole-document gate for perf_model: opening and closing sentinels plus length band.
 * Runs on the full model string in the page; the runner receives integers and flags only.
 */
export function evaluatePerfModelDocument({ text, expectedOpening, expectedClosing, fixtureChars }) {
  const normText = normalizeDocumentText(text);
  const normOpening = normalizeDocumentText(expectedOpening);
  const normClosing = normalizeDocumentText(expectedClosing);
  const modelChars = text.length;
  const openingPresent = normOpening ? normText.includes(normOpening) : true;
  const closingPresent = normClosing ? normText.includes(normClosing) : true;
  const lengthOk =
    fixtureChars > 0
      ? Math.abs(modelChars - fixtureChars) / fixtureChars <= MODEL_LENGTH_TOLERANCE
      : true;
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
  };
}

export function openingContentVerdict({ expected, actual, modelOracle, modelDocumentCheck, editorError = null }) {
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
  const normActual = normalizeDocumentText(actual);
  if (!normActual) {
    return { content_verified: false, surface_reason: 'document_content_absent', editor_error: null };
  }
  // Paragraph separators and a space before punctuation are not a different
  // document (owner decision: tolerant text comparison).
  const flat = (value) => value.replace(/[\s\p{White_Space}]+/gu, '');
  const content_verified = flat(normActual).includes(flat(normExpected));
  if (!content_verified) {
    return { content_verified: false, surface_reason: 'document_content_mismatch', editor_error: null };
  }
  return { content_verified: true, surface_reason: null, editor_error: null };
}
