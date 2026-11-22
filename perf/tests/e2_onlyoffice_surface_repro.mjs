// OnlyOffice's model readers in edit_surface.mjs read the host page's window.__host
// (test_e2_onlyoffice_surface.py). Fake page globals; no browser.
import { EDIT_SURFACES, DOCUMENT_TEXT_SURFACES, READ_EDITOR_DOCUMENT_TEXT, READ_MODEL_AT_CARET, READ_MODEL_DOCUMENT_TEXT } from '../runner/edit_surface.mjs';
const host = { text: () => 'Article 1\n\u{2000B} body', caretParagraphText: () => '\u{2000B} body' };
const parent = { __host: host };
// In the editor's frame: no __host of its own, the host page is the parent.
globalThis.window = { parent };
globalThis.document = { querySelector: () => null };
const out = {};
out.frame_text = READ_EDITOR_DOCUMENT_TEXT({ kind: 'model', model: 'onlyoffice' });
out.frame_caret = READ_MODEL_AT_CARET('onlyoffice');
out.frame_model = READ_MODEL_DOCUMENT_TEXT('onlyoffice');
// In the host page itself.
globalThis.window = { __host: host };
globalThis.window.parent = globalThis.window;
out.page_text = READ_EDITOR_DOCUMENT_TEXT({ kind: 'model', model: 'onlyoffice' }).text;
// Before the page has a reader: absent, never an empty document.
globalThis.window = {}; globalThis.window.parent = globalThis.window;
out.absent = READ_EDITOR_DOCUMENT_TEXT({ kind: 'model', model: 'onlyoffice' });
out.models = Object.fromEntries(Object.entries(EDIT_SURFACES).map(([id, s]) => [id, s.model || null]));
out.text_models = Object.fromEntries(Object.entries(DOCUMENT_TEXT_SURFACES).map(([id, s]) => [id, s.model || null]));
process.stdout.write(JSON.stringify(out));
