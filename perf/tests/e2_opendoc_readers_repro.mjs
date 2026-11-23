// E2 OpenDoc: every reader of OpenDoc's engine (opendoc.ai.read, paged) returns the whole
// document or nothing. Invoked from test_e2_opendoc_readers.py; prints JSON.
//   state:  READ_SURFACE_STATE (C07/C08 snapshots, criteria_input.mjs)
//   oracle: READ_EDITOR_DOCUMENT_TEXT (the text oracle, edit_surface.mjs)
//   census: LIST_MODEL_PARAGRAPHS (C12, lane_edit_burst.mjs)
import { READ_SURFACE_STATE } from '../runner/criteria_input.mjs';
import { READ_EDITOR_DOCUMENT_TEXT } from '../runner/edit_surface.mjs';
import { LIST_MODEL_PARAGRAPHS } from '../runner/lane_edit_burst.mjs';

const ok = (value) => ({ ok: true, value });
// Each case: the engine's answer to the n-th block read and to the table reads.
const CASES = {
  // A paragraph, a two-page table, a paragraph: the whole text, cells included.
  whole: {
    read: [ok({ blocks: [{ text: 'Alpha' }, { kind: 'table', id: 't1' }], truncated: true, nextCursor: 'c1' }),
           ok({ blocks: [{ text: 'Omega' }], truncated: false })],
    table: [ok({ rows: [{ cells: [{ text: 'A1' }, { text: 'B1' }] }], nextCursor: 'r1' }),
            ok({ rows: [{ cells: [{ text: 'A2' }, { text: 'B2' }] }] })],
  },
  // A truncated page that gives no cursor to continue.
  no_cursor: { read: [ok({ blocks: [{ text: 'Alpha' }], truncated: true })], table: [] },
  // The table's second page is refused.
  table_refused: {
    read: [ok({ blocks: [{ text: 'Alpha' }, { kind: 'table', id: 't1' }], truncated: false })],
    table: [ok({ rows: [{ cells: [{ text: 'A1' }] }], nextCursor: 'r1' }), { ok: false, refusal: { code: 'busy' } }],
  },
  // The engine's read rejects.
  rejected: { read: 'reject', table: [] },
};

function install(name) {
  const c = CASES[name];
  let r = 0;
  let t = 0;
  const el = { getBoundingClientRect: () => ({ left: 0, top: 0, right: 10, bottom: 10, height: 10 }), contains: () => false, getAttribute: () => null };
  globalThis.window = {
    scrollX: 0, scrollY: 0, __host: { selection: null },
    opendoc: { ai: { read: async (req) => {
      if (c.read === 'reject') throw new Error('read rejected');
      if (req.tool === 'table') return c.table[t++];
      return c.read[r++];
    } } },
  };
  globalThis.document = {
    querySelector: () => el, querySelectorAll: () => [], getElementById: () => null, activeElement: null,
  };
  globalThis.getComputedStyle = () => ({ display: 'block', visibility: 'visible' });
}

const out = {};
for (const name of Object.keys(CASES)) {
  install(name);
  const state = await READ_SURFACE_STATE({ kind: 'model', model: 'opendoc', pageRoot: '#pages', inputHost: '#viewport' });
  install(name);
  const oracle = await READ_EDITOR_DOCUMENT_TEXT({ kind: 'model', model: 'opendoc' });
  install(name);
  let census;
  try { census = await LIST_MODEL_PARAGRAPHS('opendoc'); } catch (e) { census = 'threw: ' + e.message; }
  out[name] = {
    state: { text: state.text, error: state.error || null },
    oracle: { text: oracle.text, oracle: oracle.oracle, error: oracle.error || null },
    census,
  };
}
process.stdout.write(JSON.stringify(out));
