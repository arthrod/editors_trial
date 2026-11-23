// E2 OpenDoc: every reader of OpenDoc's engine (opendoc.ai.read, paged) returns the whole
// document or nothing. Invoked from test_e2_opendoc_readers.py; prints JSON.
//   state:  READ_SURFACE_STATE (C07/C08 snapshots, criteria_input.mjs)
//   oracle: READ_EDITOR_DOCUMENT_TEXT (the text oracle, edit_surface.mjs)
//   census: LIST_MODEL_PARAGRAPHS (C12, lane_edit_burst.mjs)
//   typing: READ_MODEL_DOCUMENT_TEXT (the typing check's read, edit_surface.mjs)
import { READ_SURFACE_STATE } from '../runner/criteria_input.mjs';
import { READ_EDITOR_DOCUMENT_TEXT, READ_MODEL_DOCUMENT_TEXT } from '../runner/edit_surface.mjs';
import { LIST_MODEL_PARAGRAPHS } from '../runner/lane_edit_burst.mjs';

const ok = (value) => ({ ok: true, value });
const BAD_CURSOR = { ok: false, refusal: { code: 'bad_cursor' } };
// Each case: the engine's pages for the block reads and for each table's row reads.
// `endless` keeps every block page truncated, each with a fresh cursor.
const CASES = {
  // A paragraph, a two-page table, a paragraph: the whole text, cells included.
  whole: {
    read: [ok({ blocks: [{ text: 'Alpha' }, { kind: 'table', id: 't1' }], truncated: true, nextCursor: 'c1' }),
           ok({ blocks: [{ text: 'Omega' }], truncated: false })],
    table: { t1: [ok({ rows: [{ cells: [{ text: 'A1' }, { text: 'B1' }] }], nextCursor: 'r1' }),
                  ok({ rows: [{ cells: [{ text: 'A2' }, { text: 'B2' }] }] })] },
  },
  // Two plain pages: the typing check's read returns both.
  two_pages: {
    read: [ok({ blocks: [{ text: 'Alpha' }], truncated: true, nextCursor: 'c1' }),
           ok({ blocks: [{ text: 'Omega' }], truncated: false })],
    table: {},
  },
  // A truncated page that gives no cursor to continue.
  no_cursor: { read: [ok({ blocks: [{ text: 'Alpha' }], truncated: true })], table: {} },
  // Every page truncated: the page cap is reached before the last page.
  endless: { read: 'endless', table: {} },
  // The table's second page is refused.
  table_refused: {
    read: [ok({ blocks: [{ text: 'Alpha' }, { kind: 'table', id: 't1' }], truncated: false })],
    table: { t1: [ok({ rows: [{ cells: [{ text: 'A1' }] }], nextCursor: 'r1' }), { ok: false, refusal: { code: 'busy' } }] },
  },
  // The engine's read rejects.
  rejected: { read: 'reject', table: {} },
};

// A pager answers only the request the engine expects: the first page without a
// cursor, each later page with the cursor the previous page gave. Any other
// request (a repeated, missing or invented cursor) is refused, so a reader that
// does not follow the cursors gets no document.
function pager(pages) {
  let n = 0;
  let expect = null;
  return (cursor) => {
    if ((cursor ?? null) !== expect) return BAD_CURSOR;
    const page = pages === 'endless'
      ? ok({ blocks: [{ text: 'x' }], truncated: true, nextCursor: 'e' + (n + 1) })
      : pages[n];
    n += 1;
    expect = page && page.ok && page.value ? (page.value.nextCursor ?? null) : null;
    return page;
  };
}

function engine(c) {
  const blocks = pager(c.read);
  const tables = {};
  return async (req) => {
    if (c.read === 'reject') throw new Error('read rejected');
    if (req.tool === 'table') {
      if (!c.table[req.table]) return BAD_CURSOR;
      tables[req.table] = tables[req.table] || pager(c.table[req.table]);
      return tables[req.table](req.cursor);
    }
    if (req.start !== undefined) return ok({ blocks: [], truncated: false });
    return blocks(req.cursor);
  };
}

function install(name) {
  const el = { getBoundingClientRect: () => ({ left: 0, top: 0, right: 10, bottom: 10, height: 10 }), contains: () => false, getAttribute: () => null };
  globalThis.window = {
    scrollX: 0, scrollY: 0, __host: { selection: null },
    opendoc: { ai: { read: engine(CASES[name]) } },
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
  install(name);
  let typing;
  try { typing = await READ_MODEL_DOCUMENT_TEXT('opendoc'); } catch (e) { typing = 'threw: ' + e.message; }
  out[name] = {
    state: { text: state.text, error: state.error || null },
    oracle: { text: oracle.text, oracle: oracle.oracle, error: oracle.error || null },
    census,
    typing,
  };
}

// The mock itself: a client that repeats the first request, or invents a
// cursor, is refused; one that follows the cursors reads every page.
{
  const read = engine(CASES.two_pages);
  const first = await read({ tool: 'read' });
  const repeated = await read({ tool: 'read' });
  const read2 = engine(CASES.two_pages);
  await read2({ tool: 'read' });
  const invented = await read2({ tool: 'read', cursor: 'zz' });
  const read3 = engine(CASES.two_pages);
  const a = await read3({ tool: 'read' });
  const b = await read3({ tool: 'read', cursor: a.value.nextCursor });
  const t = engine(CASES.whole);
  const t1 = await t({ tool: 'table', table: 't1' });
  const tableRepeated = await t({ tool: 'table', table: 't1' });
  out.mock = {
    first_ok: first.ok, repeated_ok: repeated.ok, invented_ok: invented.ok,
    followed_ok: a.ok && b.ok && b.value.truncated === false,
    table_first_ok: t1.ok, table_repeated_ok: tableRepeated.ok,
  };
}
process.stdout.write(JSON.stringify(out));
