// E2 OpenDoc: the C12 census lists OpenDoc's paragraphs through its host contract (paged
// opendoc.ai.read, a promise); docen and canvas-editor still return their arrays synchronously.
// Invoked from test_e2_opendoc_lanes.py; prints JSON.
import { LIST_MODEL_PARAGRAPHS } from '../runner/lane_edit_burst.mjs';

const pages = [
  { ok: true, value: { blocks: [{ text: 'First' }, { text: '  ' }, { text: 'Second' }], truncated: true, nextCursor: 'c1' } },
  { ok: true, value: { blocks: [{ type: 'table' }, { text: 'Third ' }], truncated: false } },
];
const calls = [];
globalThis.window = {
  opendoc: { ai: { read: async (req) => { calls.push(req); return pages[req.cursor ? 1 : 0]; } } },
  __DOCEN__: { editor: { state: { doc: { descendants: (fn) => [{ isTextblock: true, textContent: 'D1' }].forEach(fn) } } } },
  __CANVAS_EDITOR_INSTANCE__: { command: { getValue: () => ({ data: { main: [{ value: 'C1' }] } }) } },
};
const opendoc = LIST_MODEL_PARAGRAPHS('opendoc');
const docen = LIST_MODEL_PARAGRAPHS('docen');
const canvas = LIST_MODEL_PARAGRAPHS('canvas_editor');
process.stdout.write(JSON.stringify({
  opendoc_is_promise: typeof (opendoc && opendoc.then) === 'function',
  opendoc: await opendoc,
  opendoc_calls: calls,
  docen_is_array: Array.isArray(docen), docen,
  canvas_is_array: Array.isArray(canvas), canvas,
  unknown: LIST_MODEL_PARAGRAPHS('plate'),
}));
