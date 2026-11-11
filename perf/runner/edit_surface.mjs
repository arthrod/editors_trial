/**
 * One edit adapter per editor, shared by every lane that edits (#155.1).
 *
 * A lane asks three things of an editor before it may count an edit:
 *   1. prepareEditSurface: put the host in the mode a user edits in.
 *   2. placeCaret: click a body text line on the first screen and wait until
 *      the editor has taken keyboard focus.
 *   3. readCaretScope: read the text around the caret, cheaply.
 *
 * The read is scoped to the block at the caret. Reading a whole 250k-word
 * document before and after a burst would bill that read to the editor.
 */

const HEADINGS_AND_BLOCKS =
  'p,h1,h2,h3,h4,h5,h6,li,td,th,[data-slate-node="element"],[data-paragraph-id],.superdoc-line';

/** kind: dom = text in the light DOM; model = text only in the editor's model; flag = the editor's own modified flag. */
export const EDIT_SURFACES = {
  plate: { kind: 'dom', root: '[contenteditable="true"]' },
  docxodus: {
    kind: 'dom',
    root: '#editorHost [contenteditable="true"]',
    // The host opens in its paginated viewer. Editing happens in the block editor.
    enter: { click: '#modeEditor', ready: 'window.__docxodus && window.__docxodus.editor === true' },
  },
  superdoc: {
    kind: 'dom',
    root: '#editor .superdoc-page',
    exclude: '.superdoc-page-header, .superdoc-page-footer',
    block: '.superdoc-line',
  },
  genoffice: { kind: 'dom', root: '.doc-page' },
  eigenpal: { kind: 'dom', root: '.docx-page-content [data-paragraph-id][data-start]' },
  folio: { kind: 'dom', root: '[data-page-number]' },
  canvas: { kind: 'model', model: 'canvas_editor' },
  docen: { kind: 'model', model: 'docen' },
  // No text is reachable: the app draws into one canvas and this pin has no API.
  // Its window title gains a bullet when the document is modified.
  wordcraft: { kind: 'flag', flag: 'wordcraft_title' },
};

export function editSurface(editorId) {
  return EDIT_SURFACES[editorId] || { kind: 'dom', root: null };
}

/** Page context. First body text line fully inside the viewport. */
export const FIND_TEXT_LINE = ({ root, exclude, minChars }) => {
  const roots = root ? Array.from(document.querySelectorAll(root)) : [];
  for (const el of roots) {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = String(node.nodeValue || '');
      if (text.trim().length < minChars) continue;
      const parent = node.parentElement;
      if (!parent || (exclude && parent.closest(exclude))) continue;
      // A page header or footer is not the body line every editor is aimed at.
      let margin = false;
      for (let up = parent; up && up !== el; up = up.parentElement) {
        const name = `${up.tagName} ${typeof up.className === 'string' ? up.className : ''}`;
        if (/\b(header|footer)\b|page-?(header|footer)/i.test(name)) margin = true;
      }
      if (margin) continue;
      const style = getComputedStyle(parent);
      if (style.visibility === 'hidden' || style.display === 'none') continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      const rect = range.getClientRects()[0];
      if (!rect || rect.width < 20 || rect.height < 4) continue;
      if (rect.top < 0 || rect.bottom > innerHeight || rect.left < 0 || rect.right > innerWidth) continue;
      return {
        // The start of the line: the same character in every editor, whatever its font.
        x: rect.left + 1,
        y: rect.top + rect.height / 2,
        line: text.trim().slice(0, 60),
      };
    }
  }
  return null;
};

/** Page context. Text of the block under a point; null when nothing is there. */
export const READ_BLOCK_AT_POINT = ({ x, y, block }) => {
  const hit = document.elementFromPoint(x, y);
  if (!hit) return null;
  const scope = hit.closest(block) || hit;
  return String(scope.textContent || '');
};

/** Page context. Text of the paragraph at the caret, from the editor's model. */
export const READ_MODEL_AT_CARET = (model) => {
  if (model === 'docen') {
    const editor = window.__DOCEN__ && window.__DOCEN__.editor;
    if (!editor || !editor.state) return null;
    const from = editor.state.selection && editor.state.selection.$from;
    return from ? String(from.parent.textContent || '') : null;
  }
  if (model === 'canvas_editor') {
    const inst = window.__CANVAS_EDITOR_INSTANCE__;
    const cmd = inst && inst.command;
    if (!cmd || typeof cmd.getRangeParagraph !== 'function') return null;
    const paragraph = cmd.getRangeParagraph();
    if (!Array.isArray(paragraph)) return null;
    return paragraph.map((el) => (el && typeof el.value === 'string' ? el.value : '')).join('');
  }
  return null;
};

/** Page context. True once the editor, not the page body, holds keyboard focus. */
export const EDITOR_HAS_FOCUS = () => {
  let active = document.activeElement;
  while (active && active.shadowRoot && active.shadowRoot.activeElement) {
    active = active.shadowRoot.activeElement;
  }
  return Boolean(active && active !== document.body && active !== document.documentElement);
};

/** Page context. The editor's own statement that the document is modified. */
export const READ_MODIFIED_FLAG = (flag) => {
  if (flag === 'wordcraft_title') {
    const host = window.__WORDCRAFT_HOST__;
    const titles = host && Array.isArray(host.titles) ? host.titles : [];
    if (!titles.length) return null;
    const title = String(titles[titles.length - 1].title || '');
    return { evidence: title, modified: title.includes('\u2022') };
  }
  return null;
};

export async function readModifiedFlag(page, editorId) {
  const surface = editSurface(editorId);
  if (surface.kind !== 'flag') return null;
  return page.evaluate(READ_MODIFIED_FLAG, surface.flag);
}

export async function prepareEditSurface(page, editorId, { timeoutMs = 600000 } = {}) {
  const surface = editSurface(editorId);
  const enter = surface.enter;
  if (enter) {
    await page.locator(enter.click).first().click({ timeout: 30000 });
    await page.waitForFunction(
      (expr) => {
        try {
          return Boolean(eval(expr));
        } catch {
          return false;
        }
      },
      enter.ready,
      { timeout: timeoutMs },
    );
  }
  // A host can say "ready" before a long document has a painted line
  // (SuperDoc at 250k words). Editing starts when there is text to click.
  let textLine = null;
  if (surface.kind === 'dom' && surface.root) {
    const request = { root: surface.root, exclude: surface.exclude || null, minChars: 12 };
    try {
      await page.waitForFunction(FIND_TEXT_LINE, request, { timeout: timeoutMs, polling: 100 });
      textLine = true;
    } catch {
      textLine = false;
    }
  }
  return { entered: Boolean(enter), text_line: textLine };
}

/**
 * Click where a user would start typing and wait for focus.
 * Returns the click point, or throws 'edit_surface_no_text_line'.
 */
export async function placeCaret(page, editorId, selector, { focusTimeoutMs = 5000 } = {}) {
  const surface = editSurface(editorId);
  let point = null;
  if (surface.kind === 'dom') {
    point = await page.evaluate(FIND_TEXT_LINE, {
      root: surface.root || selector,
      exclude: surface.exclude || null,
      minChars: 12,
    });
    if (!point) throw new Error('edit_surface_no_text_line');
    await page.mouse.click(point.x, point.y);
  } else {
    await page.locator(selector).first().click({ timeout: 30000 });
  }
  let focused = true;
  try {
    await page.waitForFunction(EDITOR_HAS_FOCUS, null, { timeout: focusTimeoutMs });
  } catch {
    focused = false;
  }
  // Two frames: an editor that focuses its input in a task after the click
  // (canvas-editor) loses keys typed in the same task.
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(null)))),
  );
  return { point, focused };
}

export async function readCaretScope(page, editorId, point) {
  const surface = editSurface(editorId);
  if (surface.kind === 'model') return page.evaluate(READ_MODEL_AT_CARET, surface.model);
  if (surface.kind === 'dom' && point) {
    return page.evaluate(READ_BLOCK_AT_POINT, {
      x: point.x,
      y: point.y,
      block: surface.block || HEADINGS_AND_BLOCKS,
    });
  }
  return null;
}

/**
 * True when `after` is `before` with `inserted` put in at one place and
 * nothing else changed. A line that wraps may lose its tail to the next line.
 */
export function insertedOnce(before, after, inserted) {
  const a = String(before || '');
  const b = String(after || '');
  if (!inserted) return false;
  let at = b.indexOf(inserted);
  while (at >= 0) {
    const tailBefore = a.slice(at);
    const tailAfter = b.slice(at + inserted.length);
    // A wrapped line keeps most of its old text; an emptied block is another block.
    const wrapped = tailBefore.startsWith(tailAfter) && tailAfter.length * 2 >= tailBefore.length;
    if (b.slice(0, at) === a.slice(0, at) && (wrapped || tailAfter.startsWith(tailBefore))) {
      return true;
    }
    at = b.indexOf(inserted, at + 1);
  }
  return false;
}

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

/**
 * Poll the caret scope until it gained exactly `expected` tokens.
 * An editor that paints a burst a few frames late (Folio) is not a failed edit.
 */
export async function waitForTokenDelta(page, editorId, point, { token, before, expected, timeoutMs = 10000, pollMs = 50 }) {
  const base = countToken(before, token);
  const deadline = Date.now() + timeoutMs;
  let text = before;
  let delta = 0;
  while (true) {
    text = await readCaretScope(page, editorId, point);
    delta = countToken(text, token) - base;
    if (delta === expected || Date.now() >= deadline) break;
    await page.waitForTimeout(pollMs);
  }
  return { text, delta, applied: delta === expected };
}
