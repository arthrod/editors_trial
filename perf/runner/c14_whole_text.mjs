/**
 * C14's whole-document text for editors whose page shows only a window of it (#183).
 *
 * The probe's document text is what the page renders: Folio and SuperDoc mount
 * only the pages near the start of a long document, and WordCraft paints into
 * one canvas with no DOM text. C14's I01-I03 lines sit at the document's end,
 * so for these editors the check could never judge the editor. Here the text
 * is asked of the editor itself, after every timed step of the sample:
 *
 * - `superdoc_model`: SuperDoc's own document API (`activeEditor.doc.getText`),
 *   the same model the input gate reads.
 * - `folio_pm_model`: Folio's editing ProseMirror (`.paged-editor__hidden-pm`),
 *   which a click on a painted page mounts; its document node gives the text.
 *   Probed on prose-5kw: 40,694 characters, the same text WordCraft's copy
 *   gives, where the painted pages expose 9,305.
 * - `select_all_copy`: the editor's own select-all and copy, read back from the
 *   clipboard. A sentinel is written first, so a copy that never happened
 *   cannot pass for the document.
 *
 * Nothing here runs inside a timed interval: runScale calls it after the
 * witness has closed, and the result rides in the payload as `c14_text`.
 */

/** Editor id -> how its whole text is read. Editors not listed keep the page read. */
export const C14_WHOLE_TEXT_SOURCES = Object.freeze({
  folio: 'folio_pm_model',
  superdoc: 'superdoc_model',
  wordcraft: 'select_all_copy',
});

/** Where a select-all + copy editor takes keyboard focus, or a click mounts the model. */
export const C14_COPY_FOCUS = Object.freeze({
  folio: '.layout-page-content [data-block-id]',
  wordcraft: '#wordcraft_canvas',
});

/** Longest wait for Folio's editing ProseMirror to mount after the click. */
export const C14_MOUNT_WAIT_MS = 20_000;

/** Page context: Folio's document text from its editing ProseMirror. */
export const READ_FOLIO_PM_TEXT = () => {
  const pm = document.querySelector('.paged-editor__hidden-pm .ProseMirror');
  const node = pm && pm.pmViewDesc && pm.pmViewDesc.node;
  if (!node || typeof node.textBetween !== 'function') throw new Error('folio prosemirror model unavailable');
  return node.textBetween(0, node.content.size, '\n', '\n');
};

/** Characters of each end kept as evidence, as the probe keeps for its own read. */
export const C14_TEXT_EXCERPT_CHARS = 4000;

/** Longest wait for the clipboard to change after copy (a 250,000-word copy). */
export const C14_COPY_WAIT_MS = 120_000;

const SENTINEL = '__c14_clipboard_sentinel__';

/** Page context: SuperDoc's document text from its model. */
export const READ_SUPERDOC_MODEL_TEXT = async () => {
  const sd = globalThis.__SUPERDOC_E2E__;
  const editor = sd && sd.activeEditor;
  const doc = editor && editor.doc;
  if (doc && typeof doc.getText === 'function') return String(await doc.getText({}));
  const state = editor && editor.state;
  if (state && state.doc && typeof state.doc.textBetween === 'function') {
    return state.doc.textBetween(0, state.doc.content.size, '\n', '\n');
  }
  throw new Error('superdoc model unavailable');
};

async function clickFocus(page, editorId) {
  const selector = C14_COPY_FOCUS[editorId];
  if (!selector) return;
  const target = page.locator(selector).first();
  if ((await page.locator(selector).count()) === 0) throw new Error(`copy focus ${selector} not found`);
  await target.scrollIntoViewIfNeeded().catch(() => {});
  const box = await target.boundingBox();
  if (!box) throw new Error(`copy focus ${selector} has no box`);
  // A click inside the document area gives the editor keyboard focus.
  await page.mouse.click(box.x + box.width / 2, box.y + Math.min(box.height / 2, 200));
}

async function folioModel(page, editorId) {
  await clickFocus(page, editorId);
  await page.waitForSelector('.paged-editor__hidden-pm .ProseMirror', { state: 'attached', timeout: C14_MOUNT_WAIT_MS });
  return page.evaluate(READ_FOLIO_PM_TEXT);
}

export async function selectAllCopy(page, editorId, { waitMs }) {
  const origin = new URL(page.url()).origin;
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin });
  await page.evaluate((s) => navigator.clipboard.writeText(s), SENTINEL);
  await clickFocus(page, editorId);
  await page.keyboard.press('ControlOrMeta+A');
  await page.keyboard.press('ControlOrMeta+C');
  const deadline = Date.now() + waitMs;
  for (;;) {
    const text = await page.evaluate(() => navigator.clipboard.readText());
    if (text !== SENTINEL) return text;
    if (Date.now() > deadline) throw new Error(`clipboard unchanged ${waitMs} ms after copy`);
    await page.waitForTimeout(250);
  }
}

/**
 * The editor's whole document text, or null when the editor is not listed.
 * Never throws: a failed read is recorded as `error`, and C14's check then
 * falls back to the page read.
 */
export async function readC14WholeText(page, editorId, { waitMs = C14_COPY_WAIT_MS } = {}) {
  const source = C14_WHOLE_TEXT_SOURCES[editorId];
  if (!source) return null;
  const started = Date.now();
  try {
    let text;
    if (source === 'superdoc_model') text = await page.evaluate(READ_SUPERDOC_MODEL_TEXT);
    else if (source === 'folio_pm_model') text = await folioModel(page, editorId);
    else if (source === 'select_all_copy') text = await selectAllCopy(page, editorId, { waitMs });
    else throw new Error(`unknown C14 text source ${source}`);
    text = String(text ?? '');
    return {
      source,
      chars: text.length,
      head: text.slice(0, C14_TEXT_EXCERPT_CHARS),
      tail: text.slice(-C14_TEXT_EXCERPT_CHARS),
      read_ms: Date.now() - started,
      error: null,
    };
  } catch (error) {
    return {
      source, chars: null, head: null, tail: null, read_ms: Date.now() - started,
      error: String((error && error.message) || error).slice(0, 300),
    };
  }
}
