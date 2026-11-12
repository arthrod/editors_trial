import { documentContentGateMeta } from './perf_model_text.mjs';

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
    usable: '!!(window.__docxodus && window.__docxodus.rendered)',
  },
  superdoc: {
    kind: 'dom',
    root: '#editor .superdoc-line, #editor .superdoc__document, #editor .superdoc-page',
    exclude: '.superdoc-page-header, .superdoc-page-footer',
    block: '.superdoc-line',
    // v2 paints the document into a worker-driven DOM behind a hidden
    // textarea; nothing on the page is contenteditable, so usability is the
    // mounted stage, not a contenteditable probe.
    usable: '!!document.querySelector("#editor [role=\'textbox\']")',
  },
  genoffice: { kind: 'dom', root: '.doc-page' },
  eigenpal: { kind: 'dom', root: '.docx-page-content [data-paragraph-id][data-start]' },
  folio: {
    kind: 'dom',
    root: '.layout-page-content [data-block-id], [data-page-number]',
    block: '[data-block-id]',
    // The painted [data-page-number] pages are a virtualized window, not the
    // document. Text and selection live in an offscreen ProseMirror that a
    // click on a painted page mounts; read it, never the mounted DOM sum.
    hidden: '.paged-editor__hidden-pm .ProseMirror',
  },
  canvas: {
    kind: 'model',
    model: 'canvas_editor',
    // One painted page per canvas element; the first one is the C07 surface.
    pageRoot: '#editor .ce-page-container > canvas, #editor canvas',
    inputHost: '#editor',
  },
  docen: {
    kind: 'model',
    model: 'docen',
    // <docen-document> paints pages and the input bridge inside a shadow root.
    shadow: 'docen-document',
    pageRoot: '.canvas-pages > div',
  },
  // No text is reachable: the app draws into one canvas and this pin has no API.
  // Its window title gains a bullet when the document is modified.
  wordcraft: { kind: 'flag', flag: 'wordcraft_title', pageRoot: '#wordcraft_canvas' },
};

export function editSurface(editorId) {
  return EDIT_SURFACES[editorId] || { kind: 'dom', root: null };
}

/**
 * One whole-document text source per editor.
 *
 * These roots are deliberately separate from the caret roots above. A caret
 * root may be one paragraph (Eigenpal), one page (Folio), or a hidden editing
 * surface (Docxodus); the content gate must ask the editor what document it
 * says it has, not inspect the first edit fragment.
 */
export const DOCUMENT_TEXT_SURFACES = {
  // Prose body is in one contenteditable; the DOM holds the whole document.
  plate: { kind: 'dom', root: '[contenteditable="true"]', whole: true },
  // Paginated viewer: only mounted pages carry text at load time.
  docxodus: { kind: 'dom', root: '#pages', whole: false },
  // v2: one clean copy on .superdoc-page innerText (lines may not expose text nodes to the walker).
  superdoc: { kind: 'dom', root: '#editor .superdoc-page', whole: false, domText: 'innerText' },
  genoffice: { kind: 'dom', root: '.doc-page.ProseMirror:not(.mp-page)', whole: false },
  eigenpal: { kind: 'model', model: 'eigenpal' },
  folio: { kind: 'dom', root: '[data-page-number]', whole: false },
  canvas: { kind: 'model', model: 'canvas_editor' },
  docen: { kind: 'model', model: 'docen' },
  // WordCraft exposes no document text at this pin, only its modified flag.
  wordcraft: { kind: 'unavailable' },
};

export function hasDocumentTextSurface(editorId) {
  return Object.prototype.hasOwnProperty.call(DOCUMENT_TEXT_SURFACES, editorId);
}

export function documentTextSurface(editorId) {
  return DOCUMENT_TEXT_SURFACES[editorId] || { kind: 'dom', root: null };
}

/**
 * Page context. Read the editor's whole document, not a caret-scoped block.
 *
 * The result is deliberately bounded by the caller: this function returns the
 * full text so the content gate can compare its opening, closing witness and
 * (for model hosts) total length, while persisted evidence keeps only an
 * excerpt.
 */
export const READ_EDITOR_DOCUMENT_TEXT = ({ kind, root, model, deep = false, domText = null }) => {
  const result = (text, oracle, source, error = null) => ({
    text: String(text || ''),
    chars: String(text || '').length,
    oracle,
    source,
    error: error ? String(error) : null,
  });

  if (kind === 'unavailable') {
    return result('', 'absent', model || 'unavailable');
  }

  if (kind === 'model' && model === 'eigenpal') {
    const hook = window.__DOCX_EDITOR_E2E__;
    const editor = hook && typeof hook.getEditor === 'function' ? hook.getEditor() : null;
    const session = editor && editor.surface && editor.surface.session;
    if (!session || typeof session.bodyText !== 'function') {
      return result('', 'absent', 'eigenpal_model', 'eigenpal model unavailable');
    }
    try {
      return result(session.bodyText(), 'perf_model', 'eigenpal_model');
    } catch (error) {
      return result('', 'absent', 'eigenpal_model', error && error.message ? error.message : error);
    }
  }

  if (kind === 'model' && model === 'docen') {
    const editor = window.__DOCEN__ && window.__DOCEN__.editor;
    const doc = editor && editor.state && editor.state.doc;
    if (!doc) return result('', 'absent', 'docen_model', 'docen model unavailable');
    try {
      const text = typeof doc.textBetween === 'function'
        ? doc.textBetween(0, doc.content.size, ' ')
        : String(doc.textContent || '');
      return result(text, 'perf_model', 'docen_model');
    } catch (error) {
      return result('', 'absent', 'docen_model', error && error.message ? error.message : error);
    }
  }

  if (kind === 'model' && model === 'canvas_editor') {
    try {
      const command = window.__CANVAS_EDITOR_INSTANCE__ && window.__CANVAS_EDITOR_INSTANCE__.command;
      if (command && typeof command.getText === 'function') {
        const value = command.getText();
        const text = [value.header, value.main, value.footer]
          .filter((part) => part && String(part).trim())
          .join('\n');
        return result(text, 'perf_model', 'canvas_model');
      }
      const hook = window.__PERF_MODEL_TEXT__;
      if (typeof hook === 'function') {
        return result(String(hook() ?? ''), 'perf_model', 'canvas_model');
      }
      return result('', 'absent', 'canvas_model', 'canvas model unavailable');
    } catch (error) {
      return result('', 'absent', 'canvas_model', error && error.message ? error.message : error);
    }
  }

  const elementHidden = (el) => {
    if (!el) return true;
    if (el.nodeType !== undefined && el.nodeType !== 1) return true;
    if (el.getAttribute && el.getAttribute('aria-hidden') === 'true') return true;
    if (typeof getComputedStyle !== 'function') return false;
    const style = getComputedStyle(el);
    return style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse';
  };
  const visibleTextFromRoot = (rootEl) => {
    if (elementHidden(rootEl)) return '';
    const childNodes = rootEl.childNodes || [];
    if (!childNodes || childNodes.length === 0) {
      return String(rootEl.textContent || '');
    }
    const parts = [];
    const walk = (node, hidden) => {
      if (node.nodeType === 1) {
        if (hidden || elementHidden(node)) return;
        for (const child of node.childNodes) walk(child, false);
        return;
      }
      if (node.nodeType === 3 && !hidden) {
        const chunk = String(node.nodeValue || '');
        if (chunk.trim()) parts.push(chunk);
      }
    };
    walk(rootEl, false);
    return parts.join('');
  };
  const queryDeep = (selector) => {
    const found = [];
    const visit = (root) => {
      for (const element of root.querySelectorAll(selector)) found.push(element);
      for (const element of root.querySelectorAll('*')) {
        if (element.shadowRoot) visit(element.shadowRoot);
      }
    };
    visit(document);
    return found;
  };
  const roots = root
    ? Array.from(deep ? queryDeep(root) : document.querySelectorAll(root))
    : [];
  const pickDom = (element) => {
    if (domText === 'innerText') {
      return String(element.innerText ?? element.textContent ?? '');
    }
    return visibleTextFromRoot(element);
  };
  const text = roots
    .map((element) => pickDom(element))
    .filter((part) => part.length > 0)
    .join('\n');
  return result(text, 'dom', 'dom');
};

export async function readEditorDocumentText(page, editorId, { root = null } = {}) {
  const surface = documentTextSurface(editorId);
  const request = hasDocumentTextSurface(editorId)
    ? surface
    : { kind: 'dom', root, deep: true };
  return page.evaluate(
    READ_EDITOR_DOCUMENT_TEXT,
    { ...request, domText: surface.domText || null },
  );
}

/** Whole-document read plus opening/closing/length gate for one editor. */
export async function readAndGateDocumentText(
  page,
  editorId,
  {
    expectedOpening = '',
    expectedClosing = '',
    fixtureChars = 0,
    lengthCheckMode = null,
    root = null,
    expectedBody = null,
  } = {},
) {
  const surface = documentTextSurface(editorId);
  const read = await readEditorDocumentText(page, editorId, { root });
  const whole = surface.whole !== false;
  const gate = documentContentGateMeta({
    documentRead: read,
    whole,
    expectedOpening,
    expectedClosing,
    fixtureChars,
    lengthCheckMode,
    fixtureBody: expectedBody,
  });
  return { ...read, ...gate, whole };
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

/** Page context. What a caret click hit, and the selection after it. Bounded. */
export const READ_CLICK_HIT = ({ x, y }) => {
  const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim().slice(0, 80);
  const describe = (el) => {
    if (!el || !el.tagName) return null;
    const data = {};
    const attrs = el.attributes ? Array.from(el.attributes) : [];
    for (const attr of attrs) {
      const name = attr && attr.name;
      if (typeof name === 'string' && name.indexOf('data-') === 0) {
        data[name] = String(attr.value || '').slice(0, 80);
      }
    }
    return {
      tag: el.tagName,
      id: el.id || '',
      className: typeof el.className === 'string' ? el.className.slice(0, 120) : '',
      text_prefix: norm(el.innerText || el.textContent),
      data,
    };
  };
  const hit = typeof document.elementFromPoint === 'function' ? document.elementFromPoint(x, y) : null;
  const sel = typeof document.getSelection === 'function' ? document.getSelection() : null;
  let selection = null;
  if (sel && sel.rangeCount) {
    const node = sel.anchorNode;
    const el = node && node.nodeType === 3 ? node.parentElement : node;
    selection = {
      collapsed: sel.isCollapsed === true,
      anchor_offset: Number.isFinite(Number(sel.anchorOffset)) ? Number(sel.anchorOffset) : null,
      anchor: describe(el),
    };
  }
  let active = document.activeElement;
  while (active && active.shadowRoot && active.shadowRoot.activeElement) {
    active = active.shadowRoot.activeElement;
  }
  return { x, y, hit: describe(hit), selection, active: describe(active) };
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

/** The JS expression a load observer evaluates to stamp "first usable". */
export function usableExpression(editorId, selector) {
  const surface = editSurface(editorId);
  const sel = JSON.stringify(selector || surface.root || '');
  if (surface.kind === 'model') {
    if (surface.model === 'docen') {
      return '!!(window.__DOCEN__ && window.__DOCEN__.editor && window.__DOCEN__.editor.state)';
    }
    return '!!(window.__CANVAS_EDITOR_INSTANCE__ && window.__CANVAS_EDITOR_INSTANCE__.command'
      + ' && typeof window.__CANVAS_EDITOR_INSTANCE__.command.getValue === "function")';
  }
  if (surface.kind === 'flag') {
    return '!!(window.__WORDCRAFT_HOST__ && Array.isArray(window.__WORDCRAFT_HOST__.titles)'
      + ' && window.__WORDCRAFT_HOST__.titles.length > 0)';
  }
  if (surface.usable) return surface.usable;
  return `(() => { const el = document.querySelector(${sel});`
    + ' return !!(el && el.isContentEditable && el.getBoundingClientRect().height > 0); })()';
}

/**
 * The whole document's text from the editor's model — the correctness read
 * for surfaces whose DOM cannot carry text (canvas, docen). Paragraphs keep
 * their own lines so a marker-only paragraph stays visible to the compare.
 * For docen the paragraph separator must be explicit: textBetween's default
 * flattens blocks onto one line, hiding marker-only paragraphs.
 */
export const READ_MODEL_DOCUMENT_TEXT = (model) => {
  if (model === 'docen') {
    const editor = window.__DOCEN__ && window.__DOCEN__.editor;
    if (!editor || !editor.state || !editor.state.doc) return null;
    const doc = editor.state.doc;
    // Absorbed evidence is positional: the line index of every empty list
    // item inside the returned text. Only an item AT a missing marker-only
    // paragraph's index can answer for it — never a count elsewhere.
    const absorbed = [];
    doc.descendants((node, pos) => {
      const name = String((node.type && node.type.name) || '');
      if (!/item|list/i.test(name)) return true;
      const empty = node.textContent === '';
      const lineIndex = doc.textBetween(0, pos, '\n').split('\n').length - 1;
      let marker = null;
      const attrs = node.attrs || {};
      if (attrs.listMarker) marker = String(attrs.listMarker).trim();
      else if (attrs['data-list-marker']) marker = String(attrs['data-list-marker']).trim();
      absorbed.push({index: lineIndex, marker: marker || null, empty});
      return true;
    });
    return { text: String(doc.textBetween(0, doc.content.size, '\n')), absorbed_items: absorbed };
  }
  if (model === 'canvas_editor') {
    const inst = window.__CANVAS_EDITOR_INSTANCE__;
    const cmd = inst && inst.command;
    if (!cmd || typeof cmd.getText !== 'function') return null;
    const parts = cmd.getText() || {};
    const text = ['header', 'main', 'footer']
      .map((zone) => String(parts[zone] || ''))
      .filter(Boolean)
      .join('\n');
    return { text, absorbed_items: [] };
  }
  return null;
};

/**
 * DOM surface text plus every list item the editor exposes in the tree.
 * Each absorbed entry is ``{index, marker, empty}`` at that item's line in
 * ``text``. `editable` reports whether the read surface can take typed input.
 */
export const READ_DOM_TEXT_WITH_MARKERS = (selector) => {
  const els = Array.from(document.querySelectorAll(selector));
  if (!els.length) return { text: '', absorbed_markers: [], editable: false };
  // innerText inserts margin blanks between blocks that no child's own
  // innerText contains. Sibling line sums land early; match each block's
  // own lines forward instead. NBSP is a space (painted list labels).
  const itemSel = 'li,[role=listitem],[data-list-marker],[data-marker],.doc-li,.superdoc-list-marker,.superdoc-web-flow-list-marker,.track-list-marker-dec';
  const blockTag = /^(P|DIV|LI|H[1-6]|UL|OL|BLOCKQUOTE|SECTION|ARTICLE|TR|TD|TH)$/;
  const norm = (value) => String(value ?? '').replace(/\u00a0/g, ' ');
  const asLines = (value) => {
    const text = norm(value);
    return text === '' ? [''] : text.split('\n');
  };
  const labelOf = (node) => {
    // Folio stores the Word lvlText template (%1.) on data-list-marker for
    // every format. The format class is the marker class. A decimal template
    // stays the template so it still normalises to decimal, not alpha.
    let marker = null;
    if (node.hasAttribute && node.hasAttribute('data-list-marker')) {
      marker = String(node.getAttribute('data-list-marker') || '').trim() || null;
    } else if (node.hasAttribute && node.hasAttribute('data-marker')) {
      marker = String(node.getAttribute('data-marker') || '').trim() || null;
    } else {
      const painted = String(node.className || '');
      if (/superdoc-list-marker|track-list-marker-dec/.test(painted)) {
        marker = norm(node.textContent).trim() || null;
      }
    }
    if (marker && marker.indexOf('%') !== -1) {
      const cls = String(node.className || '');
      const punct = marker.indexOf(')') !== -1 ? ')' : '.';
      if (/docx-list-lower-alpha/.test(cls)) return 'a' + punct;
      if (/docx-list-upper-alpha/.test(cls)) return 'A' + punct;
      if (/docx-list-lower-roman/.test(cls)) return 'i' + punct;
      if (/docx-list-upper-roman/.test(cls)) return 'I' + punct;
    }
    return marker;
  };
  const listMarker = (block) => {
    const nodes = [];
    if (block.matches && block.matches(itemSel)) nodes.push(block);
    for (const node of block.querySelectorAll(itemSel)) nodes.push(node);
    if (!nodes.length) return null;
    let marker = null;
    for (const node of nodes) {
      marker = labelOf(node);
      if (marker) break;
    }
    return { marker };
  };
  const blankLines = (lines) => lines.every((line) => line.trim() === '');
  const sameLines = (lines, at, own) => {
    if (at < 0 || at + own.length > lines.length) return false;
    for (let k = 0; k < own.length; k += 1) {
      if (lines[at + k] !== own[k]) return false;
    }
    return true;
  };
  // Non-empty blocks anchor on their own text. Empty blocks take a slot in
  // the gap after that anchor so a margin blank is not the list line.
  const placeBlocks = (lines, blocks) => {
    const own = blocks.map((block) => asLines(block.innerText));
    const isBlank = own.map(blankLines);
    const indexes = blocks.map(() => -1);
    let cursor = 0;
    const anchors = [];
    for (let i = 0; i < blocks.length; i += 1) {
      if (isBlank[i]) continue;
      let found = -1;
      for (let p = cursor; p + own[i].length <= lines.length; p += 1) {
        if (sameLines(lines, p, own[i])) {
          found = p;
          break;
        }
      }
      if (found < 0) continue;
      indexes[i] = found;
      anchors.push(i);
      cursor = found + own[i].length;
    }
    const bounds = [-1, ...anchors, blocks.length];
    for (let g = 0; g < bounds.length - 1; g += 1) {
      const left = bounds[g];
      const right = bounds[g + 1];
      const empties = [];
      for (let i = left + 1; i < right; i += 1) if (isBlank[i]) empties.push(i);
      if (!empties.length) continue;
      const lineFrom = left < 0 ? 0 : indexes[left] + own[left].length;
      const lineTo = right >= blocks.length ? lines.length : indexes[right];
      if (lineFrom < 0 || lineTo < lineFrom) continue;
      const owned = empties.reduce((sum, i) => sum + own[i].length, 0);
      const extras = lineTo - lineFrom - owned;
      if (extras < 0) continue;
      let lead = left >= 0 && extras >= 1 ? 1 : 0;
      let afterPool = extras - lead;
      let pos = lineFrom + lead;
      for (const i of empties) {
        indexes[i] = pos;
        pos += own[i].length;
        if (afterPool > 0) {
          pos += 1;
          afterPool -= 1;
        }
      }
    }
    return indexes;
  };
  const absorbed = [];
  let base = 0;
  for (const el of els) {
    const elLines = asLines(el.innerText);
    const kids = Array.from(el.children).filter((kid) => blockTag.test(kid.tagName));
    const blocks = kids.length ? kids : [el];
    const indexes = placeBlocks(elLines, blocks);
    blocks.forEach((block, i) => {
      const info = listMarker(block);
      if (!info || indexes[i] < 0) return;
      const text = norm(block.innerText).trim();
      const marker = info.marker;
      let body = text;
      if (marker && text.startsWith(marker)) body = text.slice(marker.length).trim();
      else if (marker && text.startsWith(marker.replace(/^%/, ''))) {
        body = text.slice(marker.replace(/^%/, '').length).trim();
      }
      absorbed.push({ index: base + indexes[i], marker, empty: !body });
    });
    base += elLines.length;
  }
  const text = els.map((el) => String(el.innerText ?? el.textContent ?? '')).join('\n');
  const editable = els.some(
    (el) => el.isContentEditable
      || el.querySelectorAll('[contenteditable="true"], [contenteditable=""]').length > 0);
  return { text, absorbed_markers: absorbed, editable };
};

export async function armTrustedKeyCounter(page) {
  await page.evaluate(() => {
    window.__b9trusted = { keys: 0, pending: Object.create(null) };
    // Two trusted channels carry a typed character: keydown when the layout
    // maps it (the § produces none), insertText in every case. Dedup so a
    // mapped char counts once: its insertText consumes the pending keydown.
    const onKeydown = (event) => {
      if (event.isTrusted && event.key && event.key.length === 1) {
        window.__b9trusted.keys += 1;
        window.__b9trusted.pending[event.key] = (window.__b9trusted.pending[event.key] || 0) + 1;
      }
    };
    const onInput = (event) => {
      if (!(event.isTrusted && event.inputType === 'insertText')) return;
      for (const ch of event.data || '') {
        const pending = window.__b9trusted.pending[ch] || 0;
        if (pending > 0) window.__b9trusted.pending[ch] = pending - 1;
        else window.__b9trusted.keys += 1;
      }
    };
    window.__b9trusted.stop = () => {
      document.removeEventListener('keydown', onKeydown, true);
      document.removeEventListener('beforeinput', onInput, true);
    };
    document.addEventListener('keydown', onKeydown, true);
    document.addEventListener('beforeinput', onInput, true);
  });
}

export async function trustedKeyCount(page) {
  return page.evaluate(() => {
    try {
      window.__b9trusted?.stop?.();
    } catch {
      /* the page may already have navigated away */
    }
    return Number(window.__b9trusted?.keys || 0);
  });
}

/**
 * Page context. SuperDoc typing correctness is the model, not painted lines.
 * getText glues paragraphs; newline-joined blocks.list text is the document.
 * A flat mismatch returns null — the session refuses rather than publish.
 */
export const READ_SUPERDOC_TYPING_TEXT = async () => {
  try {
    const sd = globalThis.__SUPERDOC_E2E__;
    const doc = sd && sd.activeEditor && sd.activeEditor.doc;
    if (!doc || typeof doc.getText !== 'function' || !doc.blocks || typeof doc.blocks.list !== 'function') {
      return null;
    }
    const flat = (value) => String(value).replace(/\n/g, '');
    const blocks = [];
    let offset = 0;
    let total = null;
    while (total === null || blocks.length < total) {
      const page = await doc.blocks.list({ includeText: true, offset, limit: 200 });
      if (!page || typeof page.total !== 'number' || !Array.isArray(page.blocks)) return null;
      total = page.total;
      if (!page.blocks.length) {
        if (blocks.length >= total) break;
        return null;
      }
      blocks.push(...page.blocks);
      offset += page.blocks.length;
      if (blocks.length > total) return null;
    }
    if (blocks.length !== total) return null;
    const texts = blocks.map((block) => (block && block.text != null ? String(block.text) : ''));
    const text = texts.join('\n');
    const got = await doc.getText({});
    if (typeof got !== 'string' || flat(text) !== flat(got)) return null;
    const absorbed_items = [];
    blocks.forEach((block, i) => {
      if (!block) return;
      const numbering = block.numbering || null;
      const isList = block.nodeType === 'listItem' || block.paragraphNumbering || numbering;
      if (!isList) return;
      const marker = numbering && numbering.marker ? String(numbering.marker).trim() || null : null;
      const body = texts[i];
      const empty = block.isEmpty === true || !String(body).trim();
      let index = 0;
      for (let k = 0; k < i; k += 1) {
        index += texts[k] === '' ? 1 : texts[k].split('\n').length;
      }
      absorbed_items.push({ index, marker, empty });
    });
    return { text, absorbed_items };
  } catch {
    return null;
  }
};

export async function prepareEditSurface(page, editorId, { timeoutMs = 600000, textLineTimeoutMs = null } = {}) {
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
  // A zero-text document never gains a text line: a 0 timeout skips the wait.
  let textLine = null;
  if (surface.kind === 'dom' && surface.root && textLineTimeoutMs !== 0) {
    const request = { root: surface.root, exclude: surface.exclude || null, minChars: 12 };
    try {
      await page.waitForFunction(FIND_TEXT_LINE, request, {
        timeout: textLineTimeoutMs === null ? timeoutMs : textLineTimeoutMs, polling: 100,
      });
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
 * `emptyDocument`: the document has no text line to find (the typing lane
 * loads a zero-text document) — click the declared surface itself.
 */
/** Page context. Collapse the selection at offset 0 of the block under a click point. */
export const COLLAPSE_CARET_AT_CLICK_BLOCK = ({ x, y, blockSelector, editorId }) => {
  const hit = document.elementFromPoint(x, y);
  if (!hit) return { ok: false, reason: 'no hit target' };
  const block = blockSelector ? hit.closest(blockSelector) : hit;
  if (!block) return { ok: false, reason: 'no block' };
  const startMark = block.querySelector && block.querySelector('[data-start="0"]');
  const caretHost = startMark || block;
  try {
    const range = document.createRange();
    const target =
      caretHost.firstChild && caretHost.firstChild.nodeType === 3 ? caretHost.firstChild : caretHost;
    range.setStart(target, 0);
    range.collapse(true);
    const sel = document.getSelection();
    if (sel) {
      sel.removeAllRanges();
      sel.addRange(range);
    }
    if (editorId === 'folio') {
      const pm = document.querySelector('.paged-editor__hidden-pm .ProseMirror');
      if (pm && typeof pm.focus === 'function') pm.focus();
    }
    return { ok: true };
  } catch (error) {
    return { ok: false, reason: String(error && error.message ? error.message : error) };
  }
};

export async function placeCaret(
  page,
  editorId,
  selector,
  {
    focusTimeoutMs = 5000,
    emptyDocument = false,
    clickPoint = null,
    atBlockStart = false,
    blockSelector = null,
  } = {},
) {
  const surface = editSurface(editorId);
  let point = null;
  if (clickPoint && Number.isFinite(clickPoint.x) && Number.isFinite(clickPoint.y)) {
    point = {
      x: clickPoint.x,
      y: clickPoint.y,
      line: clickPoint.line ? String(clickPoint.line) : null,
    };
    await page.mouse.click(point.x, point.y);
    if (atBlockStart) {
      const primary =
        blockSelector || String(surface.block || '').trim() || String(selector || '').split(',')[0].trim();
      const readHere = () =>
        page.evaluate(READ_CARET_BLOCK_OFFSET, {
          editorId: editorId || '',
          blockSelector: primary || null,
        });
      const collapseHere = () =>
        page.evaluate(COLLAPSE_CARET_AT_CLICK_BLOCK, {
          x: point.x,
          y: point.y,
          blockSelector: primary || null,
          editorId: editorId || '',
        });
      // Some editors commit the click on a later turn. Home and the block
      // collapse must run on the paragraph the click selected.
      const clickedText = await page.evaluate(
        ({ x, y, blockSelector: sel }) => {
          const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
          const hit = document.elementFromPoint(x, y);
          const block = sel && hit && typeof hit.closest === 'function' ? hit.closest(sel) : hit;
          return block ? norm(block.innerText || block.textContent) : '';
        },
        { x: point.x, y: point.y, blockSelector: primary || null },
      );
      const sameText = (left, right) =>
        Boolean(left && right && (left === right || left.startsWith(right) || right.startsWith(left)));
      const landDeadline = Date.now() + 1000;
      while (Date.now() < landDeadline) {
        const landed = await readHere();
        const landedText = landed && typeof landed.paragraphText === 'string' ? landed.paragraphText : '';
        if (sameText(clickedText, landedText)) break;
        await page.waitForTimeout(16);
      }
      await collapseHere();
      const before = await readHere();
      // One Home for every editor. It is the line-start key only when the
      // caret stays in the paragraph the click already occupied.
      await page.keyboard.press('Home');
      const after = await readHere();
      const textOf = (row) => (row && typeof row.paragraphText === 'string' ? row.paragraphText : '');
      const beforeText = textOf(before);
      const afterText = textOf(after);
      const sameParagraph = Boolean(
        beforeText &&
          afterText &&
          (beforeText === afterText || beforeText.startsWith(afterText) || afterText.startsWith(beforeText)),
      );
      if (beforeText && afterText && !sameParagraph) {
        await page.mouse.click(point.x, point.y);
        await collapseHere();
      }
    }
  } else if (surface.kind === 'dom' && !emptyDocument) {
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
  const frames = editorId === 'canvas' ? 3 : 2;
  await page.evaluate(
    (count) => new Promise((resolve) => {
      let left = count;
      const tick = () => {
        left -= 1;
        if (left <= 0) resolve(null);
        else requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }),
    frames,
  );
  const input_editable = await page.evaluate(() => {
    const el = document.activeElement;
    if (!el || el === document.body || el === document.documentElement) return false;
    if (el.isContentEditable) return true;
    if (el.matches('textarea, input')) return !el.readOnly && !el.disabled;
    return false;
  });
  return { point, focused, input_editable };
}

/** Page context. SuperDoc caret paragraph from the editor model, not painted lines. */
export const READ_SUPERDOC_CARET_MODEL = () => {
  const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  try {
    const sd = globalThis.__SUPERDOC_E2E__;
    const handle = sd && sd.ui && sd.ui.selection;
    if (!handle || typeof handle.getSnapshot !== 'function') {
      return { offset: null, paragraphText: null, focused: false, source: 'superdoc_model' };
    }
    const snap = handle.getSnapshot();
    const target = snap && snap.selectionTarget;
    const start = target && target.start;
    const end = target && target.end;
    const offset = start && Number.isFinite(start.offset) ? start.offset : null;
  const expanded =
    start &&
    end &&
    (start.blockId !== end.blockId || start.offset !== end.offset || start.edge !== end.edge);
  if (expanded && typeof handle.apply === 'function') {
    try {
      handle.apply({ kind: 'selection', start, end: start, story: target.story });
    } catch {
      /* best effort */
    }
  }
    let paragraphText = null;
    if (typeof snap.quotedText === 'string' && snap.quotedText.trim()) {
      paragraphText = norm(snap.quotedText);
    }
    if (!paragraphText && start && typeof start.blockId === 'string') {
      const esc = start.blockId.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
      const line =
        document.querySelector(`[data-source-node-id="${esc}"]`) ||
        document.querySelector(`[blockId="${esc}"]`);
      if (line) paragraphText = norm(line.textContent);
    }
    let focused = false;
    let active = document.activeElement;
    while (active && active.shadowRoot && active.shadowRoot.activeElement) {
      active = active.shadowRoot.activeElement;
    }
    focused = Boolean(active && active !== document.body && active !== document.documentElement);
    return { offset, paragraphText, focused, source: 'superdoc_model', blockId: start && start.blockId };
  } catch {
    return { offset: null, paragraphText: null, focused: false, source: 'superdoc_model' };
  }
};

/** Page context. Collapse the Folio hidden ProseMirror caret at a paragraph's start. */
export const PLACE_FOLIO_PARAGRAPH_START = ({ expectedText }) => {
  const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const want = norm(expectedText);
  if (!want) return { ok: false, reason: 'no_expected_paragraph' };
  const pm = document.querySelector('.paged-editor__hidden-pm .ProseMirror');
  if (!pm) return { ok: false, reason: 'hidden_pm_missing' };
  if (typeof pm.focus === 'function') pm.focus();
  let target = null;
  for (const block of pm.querySelectorAll('[data-block-id], p, h1, h2, h3, h4, h5, h6, li')) {
    const text = norm(block.innerText || block.textContent);
    if (text !== want) continue;
    target = block;
    break;
  }
  if (!target) return { ok: false, reason: 'paragraph_not_found' };
  try {
    const range = document.createRange();
    const node = target.firstChild && target.firstChild.nodeType === 3 ? target.firstChild : target;
    range.setStart(node, 0);
    range.collapse(true);
    const sel = document.getSelection();
    if (sel) {
      sel.removeAllRanges();
      sel.addRange(range);
    }
    return { ok: true };
  } catch (error) {
    return { ok: false, reason: String(error && error.message ? error.message : error).slice(0, 200) };
  }
};

/** Page context. Place the SuperDoc model caret at paragraph start via the public selection handle. */
export const PLACE_SUPERDOC_PARAGRAPH_START = ({ expectedText }) => {
  const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const want = norm(expectedText);
  if (!want) return { ok: false, reason: 'no_expected_paragraph' };
  try {
    const sd = globalThis.__SUPERDOC_E2E__;
    const handle = sd && sd.ui && sd.ui.selection;
    if (!handle || typeof handle.apply !== 'function' || typeof handle.getSnapshot !== 'function') {
      return { ok: false, reason: 'superdoc_selection_unavailable' };
    }
    const snap = handle.getSnapshot();
    const story = snap && snap.selectionTarget && snap.selectionTarget.story;
    const lines = Array.from(document.querySelectorAll('#editor .superdoc-line'));
    let blockId = null;
    for (const line of lines) {
      const text = norm(line.textContent);
      if (text !== want) continue;
      blockId =
        line.getAttribute('data-source-node-id') ||
        line.getAttribute('blockId') ||
        line.getAttribute('data-block-id');
      if (blockId) break;
    }
    if (!blockId) return { ok: false, reason: 'paragraph_block_unresolved' };
    handle.apply({
      kind: 'selection',
      start: { blockId, offset: 0, edge: 'start' },
      end: { blockId, offset: 0, edge: 'start' },
      story,
    });
    return { ok: true, blockId };
  } catch (error) {
    return { ok: false, reason: String(error && error.message ? error.message : error).slice(0, 200) };
  }
};

/** Page context. Offset of the caret from the start of its text block (0 = block start). */
export const READ_CARET_BLOCK_OFFSET = ({ editorId, blockSelector }) => {
  const norm = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  let active = document.activeElement;
  while (active && active.shadowRoot && active.shadowRoot.activeElement) {
    active = active.shadowRoot.activeElement;
  }
  const focused = Boolean(active && active !== document.body && active !== document.documentElement);
  if (editorId === 'superdoc') {
    try {
      const sd = globalThis.__SUPERDOC_E2E__;
      const handle = sd && sd.ui && sd.ui.selection;
      if (!handle || typeof handle.getSnapshot !== 'function') {
        return { offset: null, paragraphText: null, focused, source: 'superdoc_model' };
      }
      const snap = handle.getSnapshot();
      const target = snap && snap.selectionTarget;
      const start = target && target.start;
      const end = target && target.end;
      const offset = start && Number.isFinite(start.offset) ? start.offset : null;
      const expanded =
        start &&
        end &&
        (start.blockId !== end.blockId || start.offset !== end.offset || start.edge !== end.edge);
      if (expanded && typeof handle.apply === 'function') {
        try {
          handle.apply({ kind: 'selection', start, end: start, story: target.story });
        } catch {
          /* best effort */
        }
      }
      let paragraphText = null;
      if (typeof snap.quotedText === 'string' && snap.quotedText.trim()) {
        paragraphText = norm(snap.quotedText);
      }
      if (!paragraphText && start && typeof start.blockId === 'string') {
        const esc = start.blockId.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
        const node =
          document.querySelector(`[data-source-node-id="${esc}"]`) ||
          document.querySelector(`[blockId="${esc}"]`);
        // The fragment's own text glues wrapped lines together. The census
        // paragraph is the same line groups as superdocParagraphGroups,
        // joined with a space. A shared 80-character prefix is not that text.
        const seed =
          node && node.classList && node.classList.contains('superdoc-line')
            ? node
            : node && typeof node.querySelector === 'function'
              ? node.querySelector('.superdoc-line')
              : node && typeof node.closest === 'function'
                ? node.closest('.superdoc-line')
                : null;
        if (seed && typeof document.querySelectorAll === 'function') {
          const excludeSel = '.superdoc-page-header, .superdoc-page-footer';
          const excluded = Array.from(document.querySelectorAll(excludeSel));
          const skip = (el) =>
            excluded.some((root) => root === el || (root.contains && root.contains(el)));
          const lines = Array.from(document.querySelectorAll('#editor .superdoc-line')).filter(
            (el) => el && !skip(el),
          );
          const order = [];
          const groups = new Map();
          let orphanRun = null;
          let orphanTop = null;
          for (const line of lines) {
            const lineTop = line.getBoundingClientRect().top;
            let pid = line.getAttribute('data-paragraph-id');
            if (!pid && typeof line.closest === 'function') {
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
          const group = order.map((pid) => groups.get(pid)).find((grp) => grp.indexOf(seed) !== -1);
          const joined = (group && group.length ? group : [seed])
            .map((el) => (el && el.textContent) || '')
            .join(' ');
          paragraphText = norm(joined);
        } else if (node) {
          paragraphText = norm(node.textContent);
        }
      }
      return { offset, paragraphText, focused, source: 'superdoc_model', blockId: start && start.blockId };
    } catch {
      return { offset: null, paragraphText: null, focused, source: 'superdoc_model' };
    }
  }
  if (editorId === 'folio') {
    const pm = document.querySelector('.paged-editor__hidden-pm .ProseMirror');
    const sel = typeof document.getSelection === 'function' ? document.getSelection() : null;
    if (!pm || !sel || sel.rangeCount === 0) {
      return { offset: null, paragraphText: null, focused, source: 'hidden_pm' };
    }
    const range = sel.getRangeAt(0);
    const startEl =
      range.startContainer && range.startContainer.nodeType === 3
        ? range.startContainer.parentNode
        : range.startContainer;
    const block =
      startEl && typeof startEl.closest === 'function'
        ? startEl.closest('p,li,h1,h2,h3,h4,h5,h6,td,th,[data-block-id]')
        : null;
    if (!block || !pm.contains(block)) {
      return { offset: null, paragraphText: null, focused, source: 'hidden_pm' };
    }
    try {
      const pre = range.cloneRange();
      pre.selectNodeContents(block);
      pre.setEnd(range.startContainer, range.startOffset);
      return {
        offset: norm(pre.toString()).length,
        paragraphText: norm(block.innerText || block.textContent),
        focused,
        source: 'hidden_pm',
      };
    } catch {
      return { offset: null, paragraphText: null, focused, source: 'hidden_pm' };
    }
  }
  const sel = typeof document.getSelection === 'function' ? document.getSelection() : null;
  if (!sel || sel.rangeCount === 0) {
    return { offset: null, focused, source: 'dom' };
  }
  const range = sel.getRangeAt(0);
  const startEl =
    range.startContainer && range.startContainer.nodeType === 3
      ? range.startContainer.parentNode
      : range.startContainer;
  const blockSel =
    blockSelector ||
    (editorId === 'plate'
      ? '.doc-paragraph'
      : editorId === 'eigenpal'
        ? '[data-paragraph-id]'
        : editorId === 'folio'
          ? '[data-block-id]'
          : 'p,h1,h2,h3,h4,h5,h6,li,td,th,[data-slate-node="element"],[data-paragraph-id],.superdoc-line');
  const block =
    startEl && typeof startEl.closest === 'function' ? startEl.closest(blockSel) : null;
  if (!block) {
    return { offset: null, focused, source: 'dom' };
  }
  try {
    const pre = range.cloneRange();
    pre.selectNodeContents(block);
    pre.setEnd(range.startContainer, range.startOffset);
    const paragraphText = norm(block.innerText || block.textContent);
    return { offset: norm(pre.toString()).length, paragraphText, focused, source: 'dom' };
  } catch {
    return { offset: null, focused, source: 'dom' };
  }
};

export async function verifyCaretAtParagraphStart(
  page,
  editorId,
  { blockSelector = null, clickPoint = null, expectedParagraphText = null } = {},
) {
  const primary = blockSelector || String(EDIT_SURFACES[editorId]?.block || '').trim() || null;
  const normExpected = expectedParagraphText ? String(expectedParagraphText).replace(/\s+/g, ' ').trim() : null;
  const readOffset = async () =>
    page.evaluate(READ_CARET_BLOCK_OFFSET, {
      editorId: editorId || '',
      blockSelector: primary,
    });
  let read = await readOffset();
  const paragraphMismatch = () =>
    normExpected &&
    read &&
    typeof read.paragraphText === 'string' &&
    read.paragraphText &&
    read.paragraphText !== normExpected;
  const needsPlacement = () =>
    read.offset !== 0 ||
    paragraphMismatch() ||
    (editorId === 'folio' && read.offset === null && clickPoint && Number.isFinite(clickPoint.x));
  if (needsPlacement() && editorId === 'superdoc' && normExpected) {
    await page.evaluate(PLACE_SUPERDOC_PARAGRAPH_START, { expectedText: normExpected });
    await page.waitForTimeout(80);
    read = await readOffset();
  } else if (needsPlacement() && editorId === 'folio' && normExpected) {
    await page.evaluate(PLACE_FOLIO_PARAGRAPH_START, { expectedText: normExpected });
    await page.waitForTimeout(80);
    read = await readOffset();
  } else if (needsPlacement() && clickPoint && Number.isFinite(clickPoint.x)) {
    await page.evaluate(COLLAPSE_CARET_AT_CLICK_BLOCK, {
      x: clickPoint.x,
      y: clickPoint.y,
      blockSelector: primary || null,
      editorId: editorId || '',
    });
    read = await readOffset();
  }
  if (editorId === 'folio') {
    await page.evaluate(() => {
      const pm = document.querySelector('.paged-editor__hidden-pm .ProseMirror');
      if (pm && typeof pm.focus === 'function') pm.focus();
    });
    try {
      await page.waitForFunction(
        () => {
          const pm = document.querySelector('.paged-editor__hidden-pm .ProseMirror');
          const sel = typeof document.getSelection === 'function' ? document.getSelection() : null;
          return Boolean(
            pm &&
              sel &&
              sel.rangeCount > 0 &&
              sel.getRangeAt(0).startContainer &&
              pm.contains(sel.getRangeAt(0).startContainer),
          );
        },
        null,
        { timeout: 5000, polling: 50 },
      );
    } catch {
      /* bounded */
    }
    read = await readOffset();
  }
  if (!read.focused) {
    return { ok: false, reason: 'caret_not_at_paragraph_start', detail: 'editor_not_focused', ...read };
  }
  if (read.offset !== 0) {
    return { ok: false, reason: 'caret_not_at_paragraph_start', detail: 'nonzero_offset', ...read };
  }
  if (paragraphMismatch()) {
    return {
      ok: false,
      reason: 'caret_not_at_paragraph_start',
      detail: 'paragraph_text_mismatch',
      expected: normExpected,
      ...read,
    };
  }
  return { ok: true, ...read };
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

/** Editors whose burst oracle must read the model, not painted DOM at the caret. */
export const BURST_VERIFY_MODEL = new Set(['superdoc', 'eigenpal']);

/** Page context. SuperDoc model text for burst verification (painted lines lag). */
export const READ_SUPERDOC_BURST_TEXT = async () => {
  try {
    const sd = globalThis.__SUPERDOC_E2E__;
    const doc = sd && sd.activeEditor && sd.activeEditor.doc;
    if (!doc || typeof doc.getText !== 'function') return null;
    const value = await doc.getText({});
    return typeof value === 'string' ? value : null;
  } catch {
    return null;
  }
};

/** Page context. Eigenpal session body for burst verification (virtualized paint jumps). */
export const READ_EIGENPAL_BURST_TEXT = () => {
  const hook = globalThis.__DOCX_EDITOR_E2E__;
  const editor = hook && typeof hook.getEditor === 'function' ? hook.getEditor() : null;
  const session = editor && editor.surface && editor.surface.session;
  if (!session || typeof session.bodyText !== 'function') return null;
  try {
    return session.bodyText();
  } catch {
    return null;
  }
};

/**
 * Text for keyboard-burst verification: model hosts whose painted DOM lies
 * about whether keystrokes landed, everyone else stays caret-scoped.
 */
export async function readBurstVerifyText(page, editorId, point) {
  if (editorId === 'superdoc') {
    return page.evaluate(READ_SUPERDOC_BURST_TEXT);
  }
  if (editorId === 'eigenpal') {
    return page.evaluate(READ_EIGENPAL_BURST_TEXT);
  }
  return readCaretScope(page, editorId, point);
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
    text = await readBurstVerifyText(page, editorId, point);
    delta = countToken(text, token) - base;
    if (delta === expected || Date.now() >= deadline) break;
    await page.waitForTimeout(pollMs);
  }
  return { text, delta, applied: delta === expected };
}
