import { publishableRecord, refusedRecord } from './witness_records.mjs';
/**
 * Reproducers for B4 fix round 3 (re-review R1–R4). Invoked from test_b4_fix3.py.
 */
import { pathToFileURL } from 'node:url';

const repo = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const moduleUrl = pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href;

const { measureBulkInsert, measureUndo, validateWitnessRecord, sampleAfterInput } =
  await import(moduleUrl);

const good = publishableRecord();
const bad = refusedRecord();

function fakePage(mode) {
  let body = 'ORIGINAL';
  let undos = 0;
  const page = {
    mouse: { click: async () => {} },
    keyboard: {
      type: async () => {
        body = mode === 'c09_wrong_text' ? 'ORIGyINAL' : 'ORIGxINAL';
      },
      press: async (key) => {
        if (key.endsWith('+Z')) {
          undos += 1;
          body = 'ORIGINAL';
        }
        if (key.endsWith('+V')) body += 'BLOCK';
      },
    },
    evaluate: async (fn, arg) => {
      if (fn.name === 'READ_EDITABLE_STATE') {
        return { text: body, text_length: body.length, selection_offset: 4, active_inside: true, anchor_inside: true };
      }
      if (arg && typeof arg === 'object' && (arg.kind || arg.kinds)) {
        return mode === 'c09_missing_input' ? null : { t: 100 };
      }
      if (typeof arg === 'string' && fn.toString().includes('writeText')) {
        return undefined;
      }
      if (typeof arg === 'string' && fn.toString().includes('execCommand')) {
        body += 'BLOCK';
        return { start: 100, ok: true, error: null };
      }
      return null;
    },
  };
  const witness = {
    frameIntervalMs: 16.667,
    paintAfter: async (t, o = {}) => {
      if (o.arm) await o.arm();
      return bad;
    },
  };
  return { page, witness, getBody: () => body, getUndos: () => undos };
}

async function c09Refused() {
  const { page, witness } = fakePage('c09_refused');
  const result = await measureUndo(
    page,
    witness,
    { modifier: 'Control', expectedBodyText: 'ORIGINAL' },
    {
      editable: { selector: '#doc', is_content_editable: true, text_length: 8 },
      points: [{ point: 'last_text_line', x: 1, y: 1 }],
    },
  );
  const obs = result.observations?.[0] || {};
  return {
    outcome: result.outcome,
    failure_reason: result.failure_reason,
    witness: obs.witness ?? null,
    witness_refusal: obs.witness_refusal ?? null,
    witness_errors: obs.witness_errors ?? null,
    sentinel: obs.witness?.clock_check?.notes.at(-1) ?? null,
  };
}

async function c08Refused() {
  const { page, witness } = fakePage('c08_refused');
  const result = await measureBulkInsert(
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
  const pasteObs = (result.observations || []).find((o) => o.method === 'clipboard_paste_keyboard') || {};
  const fallback = (result.observations || []).find((o) => o.method === 'exec_command_insert_text') || {};
  return {
    paste_witness: pasteObs.witness ?? null,
    fallback_witness: fallback.witness,
    fallback_refusal: fallback.witness_refusal ?? null,
    fallback_errors: fallback.witness_errors ?? null,
  };
}

async function c09MissingInput() {
  const { page, witness, getBody, getUndos } = fakePage('c09_missing_input');
  const result = await measureUndo(
    page,
    witness,
    { modifier: 'Control', expectedBodyText: 'ORIGINAL' },
    {
      editable: { selector: '#doc', is_content_editable: true, text_length: 8 },
      points: [{ point: 'last_text_line', x: 1, y: 1 }],
    },
  );
  return {
    failure_reason: result.failure_reason,
    body: getBody(),
    undos: getUndos(),
  };
}

function tmpdirMissing() {
  const old = process.env.TMPDIR;
  process.env.TMPDIR = '/tmp/rerev-b4-2/no-directory';
  try {
    return validateWitnessRecord(good);
  } catch (err) {
    return { thrown: err.code };
  } finally {
    process.env.TMPDIR = old;
  }
}

console.log(
  JSON.stringify({
    c09_refused: await c09Refused(),
    c08_refused: await c08Refused(),
    c09_missing_input: await c09MissingInput(),
    tmp_missing: tmpdirMissing(),
    spawn_missing: await sampleAfterInput(
      { frameIntervalMs: 16.667, paintAfter: async () => good },
      100,
      {},
    ),
  }),
);
