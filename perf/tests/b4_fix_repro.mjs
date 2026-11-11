import { publishableRecord, quietWindow, refusedRecord } from './witness_records.mjs';
/**
 * Isolated reproducers for B4 review findings (#131). Invoked from test_b4_fix.py.
 */
import fs from 'node:fs';
import vm from 'node:vm';
import { pathToFileURL } from 'node:url';

const repo = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const moduleUrl = pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href;

const {
  measureBulkInsert,
  measureUndo,
  sampleAfterInput,
  validateWitnessRecord,
  OBSERVE_QUIESCENCE,
  measureClicks,
} = await import(moduleUrl);

function fakeWitness(framePageMs) {
  return {
    frameIntervalMs: 16.667,
    paintAfter: async (pageMs, callOptions = {}) => {
      let inputT = typeof pageMs === 'number' ? pageMs : null;
      if (callOptions.arm) {
        inputT = await callOptions.arm();
      }
      if (inputT === null) {
        return publishableRecord(framePageMs, framePageMs - 40);
      }
      return publishableRecord(inputT + 40, inputT);
    },
  };
}

const witness = fakeWitness(140);

const corrupt = await (async () => {
  let reads = 0;
  const page = {
    mouse: { click: async () => {} },
    keyboard: { press: async () => {} },
    locator: () => ({
      first: () => ({
        boundingBox: async () => ({ x: 1, y: 1, width: 120, height: 40 }),
      }),
    }),
    evaluate: async (fn, arg) => {
      if (fn.name === 'READ_EDITABLE_STATE') {
        reads += 1;
        const text = reads >= 2 ? 'CORRUPTDBLOCK' : 'ORIGINAL';
        return {
          text,
          text_length: text.length,
          selection_offset: 8,
          is_content_editable: true,
          active_inside: true,
          anchor_inside: true,
        };
      }
      if (arg && typeof arg === 'object' && arg.kinds) return { t: 100 };
      if (arg && typeof arg === 'object' && arg.quietMs !== undefined) return null;
      return null;
    },
  };
  return measureBulkInsert(
    page,
    witness,
    {
      bulkChars: 5,
      block: 'BLOCK',
      modifier: 'Control',
      expectedBodyText: 'ORIGINAL',
    },
    {
      editable: { selector: '#doc', is_content_editable: true, text_length: 8 },
      points: [{ point: 'last_text_line', x: 1, y: 1 }],
    },
  );
})();

const rounding = await sampleAfterInput(
  {
    frameIntervalMs: 16.667,
    paintAfter: async (pageMs) => publishableRecord(118, pageMs),
  },
  100,
  {},
);

let now = 0;
let mutation;
const sandbox = {
  performance: { now: () => now },
  document: { documentElement: {} },
  MutationObserver: class {
    constructor(cb) {
      mutation = cb;
    }
    observe() {}
    disconnect() {}
  },
  PerformanceObserver: class {
    observe() {}
    disconnect() {}
  },
  requestAnimationFrame: () => {},
  setTimeout: (cb) => {
    now += 50;
    if (now === 50) mutation([{}]);
    cb();
  },
  Set,
};
const quietMs = 200;
const c04 = await vm.runInNewContext(`(${OBSERVE_QUIESCENCE.toString()})({quietMs:${quietMs},timeoutMs:1000})`, sandbox);

const refusedWitness = await sampleAfterInput(
  {
    frameIntervalMs: 8.333,
    paintAfter: async () => refusedRecord(),
  },
  100,
  {},
);

const c09AtOffset = await (async () => {
  let reads = 0;
  const page = {
    mouse: { click: async () => {} },
    keyboard: {
      type: async () => {},
      press: async () => {},
    },
    evaluate: async (fn, arg) => {
      if (fn.name === 'READ_EDITABLE_STATE') {
        reads += 1;
        let text = 'ORIGINAL';
        if (reads === 2) text = 'ORIGxINAL';
        return {
          text,
          text_length: text.length,
          selection_offset: 4,
          is_content_editable: true,
          active_inside: true,
          anchor_inside: true,
        };
      }
      if (arg && typeof arg === 'object' && (arg.kinds || arg.kind)) {
        return { t: 100 };
      }
      return null;
    },
  };
  return measureUndo(
    page,
    witness,
    { modifier: 'Control', expectedBodyText: 'ORIGINAL' },
    {
      editable: { selector: '#doc', is_content_editable: true, text_length: 8 },
      points: [{ point: 'last_text_line', x: 1, y: 1 }],
    },
  );
})();

const nonDom = await (async () => {
  const page = {
    mouse: { click: async () => {} },
    evaluate: async (fn, arg) => {
      if (fn.name === 'DOCUMENT_UNTOUCHED') {
        return { events: [], anchor_inside: false, active_inside: false, tapped: 0 };
      }
      if (fn.name === 'READ_EDITABLE_STATE') {
        return { text: 'WRONG', text_length: 5, anchor_inside: false };
      }
      if (arg && typeof arg === 'object' && arg.kind) return { t: 100 };
      if (typeof arg === 'string') return { inside: true };
      return null;
    },
  };
  const clickWitness = {
    frameIntervalMs: witness.frameIntervalMs,
    paintAfter: async (t, callOptions) => {
      const record = await witness.paintAfter(t, callOptions);
      record.quiet_window = quietWindow();
      return record;
    },
  };
  return measureClicks(
    page,
    {
      editable: { selector: '#doc', is_content_editable: false },
      points: [1, 2, 3].map((i) => ({ point: `point${i}`, x: i, y: i, line: null })),
    },
    { expectedBodyText: 'ORIGINAL', witness: clickWitness },
  );
})();

console.log(
  JSON.stringify({
    corrupt_prefix: {
      outcome: corrupt.outcome,
      samples_ms: corrupt.samples_ms,
      failure_reason: corrupt.failure_reason,
    },
    rounding: { ok: rounding.ok, sampleMs: rounding.sampleMs, sample_ms: rounding.sampleMs },
    c04: {
      quiescence_event: c04.quiescence_event,
      quiet_at: c04.quiet_at,
      quiet_window_ms: c04.quiet_window_ms,
      quiescence_confirmed_ms: c04.quiescence_confirmed_ms,
    },
    refused_witness: {
      ok: refusedWitness.ok,
      reason: refusedWitness.reason,
      witness_refusal: refusedWitness.witness_refusal,
    },
    c09_at_offset: {
      outcome: c09AtOffset.outcome,
      samples_ms: c09AtOffset.samples_ms,
      failure_reason: c09AtOffset.failure_reason,
      witness: Boolean(c09AtOffset.observations?.[0]?.witness),
    },
    validator: validateWitnessRecord(refusedRecord()),
    non_dom: {
      outcome: nonDom.outcome,
      samples_ms: nonDom.samples_ms,
      scope: nonDom.assertion.scope,
      failure_reason: nonDom.failure_reason,
    },
  }),
);
