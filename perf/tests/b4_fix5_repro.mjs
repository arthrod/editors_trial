import { publishableRecord, refusedRecord } from './witness_records.mjs';
/**
 * B4 fix round 5 probes (F1, m1–m3). Invoked from test_b4_fix5.py.
 */
import { pathToFileURL } from 'node:url';

const repo = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const moduleUrl = pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href;

const { measureUndo, runCriteriaSuite } = await import(moduleUrl);

const good = publishableRecord();
const bad = refusedRecord();

const meta = {
  editable: { selector: '#doc', is_content_editable: true, text_length: 8 },
  points: [{ point: 'last_text_line', x: 1, y: 1 }],
};

async function a10RefusedPaintPageDiesInFinally() {
  let body = 'ORIGINAL';
  let broken = false;
  const page = {
    mouse: { click: async () => {} },
    keyboard: {
      type: async () => {
        body = 'ORIGxINAL';
      },
      press: async (k) => {
        if (k.endsWith('+Z')) body = 'ORIGINAL';
      },
    },
    evaluate: async (fn, arg) => {
      if (broken) throw new Error('Execution context was destroyed');
      if (fn.name === 'READ_EDITABLE_STATE')
        return { text: body, text_length: body.length, selection_offset: 4, active_inside: true, anchor_inside: true };
      if (arg && (arg.kind || arg.kinds)) return { t: 100 };
      return null;
    },
  };
  const witness = {
    frameIntervalMs: 16.667,
    paintAfter: async (t, o) => {
      if (o.arm) await o.arm();
      broken = true;
      return bad;
    },
  };
  let thrown = null;
  let entry = null;
  try {
    entry = await measureUndo(page, witness, { modifier: 'Control', expectedBodyText: 'ORIGINAL' }, meta);
  } catch (error) {
    thrown = String(error);
  }
  return {
    thrown,
    kept_reason: entry?.failure_reason ?? null,
    kept_refusal: entry?.observations?.[0]?.witness_refusal ?? null,
    fixture_reset: entry?.fixture_reset ?? null,
  };
}

async function a11MeasuredPageDiesInFinally() {
  let body = 'ORIGINAL';
  let reads = 0;
  const page = {
    mouse: { click: async () => {} },
    keyboard: {
      type: async () => {
        body = 'ORIGxINAL';
      },
      press: async (k) => {
        if (k.endsWith('+Z')) body = 'ORIGINAL';
      },
    },
    evaluate: async (fn, arg) => {
      // ae64d81a (2026-11-10, "Fix input harness click paint") added the
      // click-point resolve and the focus read; the fake answers both.
      if (fn.name === 'READ_EDITABLE_STATE') {
        reads += 1;
        if (reads > 3) throw new Error('Execution context was destroyed');
        return { text: body, text_length: body.length, selection_offset: 4, active_inside: true, anchor_inside: true };
      }
      if (arg && (arg.kind || arg.kinds)) return { t: 100 };
      return null;
    },
  };
  const witness = {
    frameIntervalMs: 16.667,
    paintAfter: async (t, o) => {
      if (o.arm) await o.arm();
      return good;
    },
  };
  let thrown = null;
  let entry = null;
  try {
    entry = await measureUndo(page, witness, { modifier: 'Control', expectedBodyText: 'ORIGINAL' }, meta);
  } catch (error) {
    thrown = String(error);
  }
  return {
    thrown,
    outcome: entry?.outcome ?? null,
    samples: entry?.samples_ms ?? null,
    fixture_reset: entry?.fixture_reset ?? null,
  };
}

async function c09OnlySkipsLongResetWait() {
  let body = 'ORIGINAL';
  let reloaded = false;
  let readsAfterReload = 0;
  const page = {
    mouse: { click: async () => {} },
    keyboard: {
      type: async () => {
        body = 'ORIGxINAL';
      },
      press: async () => {},
    },
    reload: async () => {
      body = 'STUCK';
      reloaded = true;
    },
    evaluate: async (fn, arg) => {
      if (fn.name === 'READ_EDITABLE_STATE') {
        if (reloaded) readsAfterReload += 1;
        return { text: body, text_length: body.length, selection_offset: 4, active_inside: true, anchor_inside: true, is_content_editable: true };
      }
      if (arg && (arg.kind || arg.kinds)) return { t: 100 };
      if (arg?.count) return [16.667, 16.667];
      return null;
    },
  };
  const cdp = { on() {}, off() {}, async send() {} };
  const payload = await runCriteriaSuite({
    page,
    cdp,
    editSelector: '#doc',
    criteria: ['C09'],
    expectedBodyText: 'ORIGINAL',
    correctnessAdapter: 'dom_innerText',
    // The double's cdp never emits screencast frames; keep the frame wait
    // short so this probe measures the fixture wait, not frame timeouts.
    frameTimeoutMs: 120,
    resolvedPoints: [{ point: 'last_text_line', x: 1, y: 1, hit_inside_editable: true }],
  });
  return {
    // The long restore wait polls the document ~100 times; a skipped wait
    // reads once. That is the assertion the wall-clock bound approximated.
    reads_after_reload: readsAfterReload,
    fixture_reset: payload.criteria.C09?.fixture_reset ?? null,
  };
}

async function metaEditableRefreshedAfterReset() {
  let body = 'ORIGINAL';
  let undos = 0;
  let reloaded = false;
  const page = {
    mouse: { click: async () => {} },
    keyboard: {
      type: async () => {
        body = 'ORIGxINAL';
      },
      press: async (k) => {
        if (!k.endsWith('+Z')) return;
        undos += 1;
        body = undos === 1 ? 'OLDER' : 'ANCIENT';
      },
    },
    reload: async () => {
      body = 'ORIGINAL';
      reloaded = true;
    },
    evaluate: async (fn, arg) => {
      if (fn.name === 'READ_EDITABLE_STATE') {
        const len = reloaded ? 20 : body.length;
        return { text: body, text_length: len, selection_offset: 4, active_inside: true, anchor_inside: true, is_content_editable: true };
      }
      if (arg && (arg.kind || arg.kinds)) return { t: 100 };
      if (arg?.count) return [16.667, 16.667];
      if (typeof arg === 'number') return 40.0;
      return undefined;
    },
  };
  const cdp = { on() {}, off() {}, async send() {} };
  const payload = await runCriteriaSuite({
    page,
    cdp,
    editSelector: '#doc',
    criteria: ['C09', 'C08'],
    expectedBodyText: 'ORIGINAL',
    correctnessAdapter: 'dom_innerText',
    resolvedPoints: [{ point: 'after_reload', x: 2, y: 1, hit_inside_editable: true }],
  });
  return {
    payload_text_length: payload.editable?.text_length ?? null,
    c09_reset: payload.criteria.C09?.fixture_reset ?? null,
  };
}

console.log(
  JSON.stringify({
    a10: await a10RefusedPaintPageDiesInFinally(),
    a11: await a11MeasuredPageDiesInFinally(),
    m2_skip_wait: await c09OnlySkipsLongResetWait(),
    m1_meta_refresh: await metaEditableRefreshedAfterReset(),
  }),
);
