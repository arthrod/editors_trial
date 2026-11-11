import { normalizeDocumentText } from './document_text_normalize.mjs';

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

/**
 * When the document surface is canvas-only, DOM text is not an oracle. Prefer
 * the host model hook; otherwise mark the sample unverifiable.
 */
export function resolveDocumentText({ domText, canvasPresent }) {
  if (!canvasPresent) {
    return {
      text: domText,
      content_text_accessible: Boolean(domText),
      model_oracle: 'dom',
    };
  }
  const model = readPerfModelText();
  if (model.hook) {
    return {
      text: model.text,
      content_text_accessible: true,
      model_oracle: 'perf_model',
    };
  }
  return {
    text: domText,
    content_text_accessible: false,
    model_oracle: 'absent',
  };
}

export function openingContentVerdict({ expected, actual, canvasPresent, modelOracle }) {
  const normExpected = normalizeDocumentText(expected);
  const normActual = normalizeDocumentText(actual);
  if (!normExpected) {
    return { content_verified: false, surface_reason: null };
  }
  if (canvasPresent && modelOracle === 'absent') {
    return { content_verified: false, surface_reason: 'document_content_unverifiable' };
  }
  if (!normActual) {
    return {
      content_verified: false,
      surface_reason: modelOracle === 'perf_model' || !canvasPresent ? 'document_content_absent' : 'document_content_unverifiable',
    };
  }
  const content_verified = normActual.includes(normExpected);
  if (!content_verified) {
    return { content_verified: false, surface_reason: 'document_content_mismatch' };
  }
  return { content_verified: true, surface_reason: null };
}
