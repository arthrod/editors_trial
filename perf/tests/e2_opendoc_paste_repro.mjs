// E2 OpenDoc: the C08 paste input. OpenDoc pastes from its own keydown handler through the async
// Clipboard API, so no paste or beforeinput event reaches the page; on OpenDoc's surface the paste
// input is that keydown. Every other surface keeps the paste/beforeinput event: with no such event
// its paste is still "the keystroke did not reach the page". Invoked from test_e2_opendoc_lanes.py;
// prints JSON.
import * as ci from '../runner/criteria_input.mjs';
import { publishableRecord } from './witness_records.mjs';

function witness() {
  return {
    frameIntervalMs: 16.667,
    paintAfter: async (pageMs, callOptions = {}) => {
      let inputT = typeof pageMs === 'number' ? pageMs : null;
      if (callOptions.arm) inputT = await callOptions.arm();
      return inputT === null ? publishableRecord(140, 100) : publishableRecord(inputT + 40, inputT);
    },
  };
}

// The page saw keydown V (t = 100) and no paste or beforeinput event; the text grows on the paste.
function fakePage() {
  let pasted = false;
  const state = () => {
    const text = pasted ? 'ORIGBLOCKINAL' : 'ORIGINAL';
    return { text, text_length: text.length, selection_offset: 4, is_content_editable: true,
      input_reachable: true, active_inside: true, anchor_inside: true };
  };
  return {
    mouse: { click: async () => {} },
    keyboard: { press: async (keys) => { if (/\+V$/.test(keys)) pasted = true; }, type: async () => {} },
    locator: () => ({ first: () => ({ boundingBox: async () => ({ x: 1, y: 1, width: 120, height: 40 }) }) }),
    evaluate: async (fn, arg) => {
      if (fn.name === 'READ_EDITABLE_STATE' || fn.name === 'READ_SURFACE_STATE') return state();
      if (arg && typeof arg === 'object' && (arg.kinds || arg.kind)) {
        const kinds = arg.kinds || [arg.kind];
        return kinds.includes('keydown') && arg.key === 'V' ? { kind: 'keydown', key: 'V', t: 100 } : null;
      }
      if (fn.name === 'POINTER_TARGET_SURFACE') return { inside: true, reason: null };
      return null;
    },
  };
}

const run = async (surface) => {
  const meta = {
    surface,
    editable: { selector: '#doc', is_content_editable: true, input_reachable: true, text_length: 8 },
    points: [{ point: 'page_centre', x: 1, y: 1 }],
  };
  const entry = await ci.measureBulkInsert(fakePage(), witness(),
    { bulkChars: 5, block: 'BLOCK', modifier: 'Control', expectedBodyText: 'ORIGINAL' }, meta);
  const paste = (entry.observations || []).find((o) => o.observation_id === 'paste') || {};
  return { outcome: entry.outcome, failure_reason: entry.failure_reason, paste_failure: paste.failure || null,
    paste_input: paste.paste_input || null, input_ms: paste.input_ms ?? null };
};

process.stdout.write(JSON.stringify({
  opendoc: await run({ kind: 'model', model: 'opendoc', pageRoot: '#doc', inputHost: '#doc' }),
  dom: await run({ kind: 'dom', root: '#doc' }),
  docen: await run({ kind: 'model', model: 'docen', shadow: 'docen-document', pageRoot: '#doc' }),
}));
