import { publishableRecord, quietWindow, refusedRecord, noFrameRecord } from './witness_records.mjs';
/**
 * Reproducers for B4 fix round 3 (re-review R1–R4). Invoked from test_b4_fix3.py.
 */
import { pathToFileURL } from 'node:url';

const repo = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const moduleUrl = pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href;

const { measureBulkInsert, measureUndo, measureClicks, runCriteriaSuite, validateWitnessRecord, sampleAfterInput } =
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
          body = mode === 'c09_missing_input' && undos > 1 ? 'OLDER' : 'ORIGINAL';
        }
        if (key.endsWith('+V')) body += 'BL';
      },
    },
    evaluate: async (fn, arg) => {
      if (fn.name === 'DOCUMENT_UNTOUCHED')
        return { events: [], anchor_inside: false, active_inside: false, tapped: 0 };
      if (fn.name === 'READ_EDITABLE_STATE') {
        return {
          text: body,
          text_length: body.length,
          selection_offset: 4,
          active_inside: true,
          anchor_inside: true,
        };
      }
      if (arg && typeof arg === 'object' && (arg.kind || arg.kinds)) {
        return mode === 'missing_paste' || mode === 'c09_missing_input' && (arg.key === 'z' || arg.key === 'Z') ? null : { t: 100 };
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
      return mode === 'positive' ? good : bad;
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

async function c08Refused(mode = 'c08_refused') {
  const { page, witness } = fakePage(mode);
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
    observations: result.observations, paste_witness: pasteObs.witness ?? null,
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
    observations: result.observations, body: getBody(),
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

async function clickMissing() {
  const {page, witness} = fakePage('missing_paste');
  const quietWitness = {
    frameIntervalMs: witness.frameIntervalMs,
    paintAfter: async (t, o = {}) => {
      const record = await witness.paintAfter(t, o);
      record.quiet_window = quietWindow();
      return record;
    },
  };
  return measureClicks(page,
    {editable: {selector: '#doc', is_content_editable: true},
     points: [{point: 'first_text_line', x: 5, y: 5}, {point: 'last_text_line', x: 1, y: 1}]},
    {witness: quietWitness});
}
async function positiveUndo() {
  const {page, witness} = fakePage('positive');
  return measureUndo(page, witness, {modifier: 'Control', expectedBodyText: 'ORIGINAL'}, {editable: {selector: '#doc', is_content_editable: true, text_length: 8}, points: [{point: 'last_text_line', x: 1, y: 1}]});
}
async function failedResetSuite() {
  let body = 'ORIGINAL';
  const page = { mouse: {click: async () => {}},
    keyboard: {type: async () => {body = 'ORIGxINAL'}, press: async () => {}},
    reload: async () => {throw new Error('reload refused')},
    evaluate: async (fn, arg) => {
      if (fn.name === 'READ_EDITABLE_STATE') return {text: body, text_length: body.length, selection_offset: 4, is_content_editable: true, active_inside: true, anchor_inside: true};
      if (arg?.count) return [16.667, 16.667];
      return null;
    }};
  const cdp = {on() {}, off() {}, async send() {}};
  return runCriteriaSuite({page, cdp, editSelector: '#doc', criteria: ['C09'], expectedBodyText: 'ORIGINAL', correctnessAdapter: 'dom_innerText',
    resolvedPoints: [{point: 'last_text_line', x: 1, y: 1, hit_inside_editable: true}]});
}
async function cleanupProbe() {
let body='ORIGINAL', undos=0;
const page={reload:async()=>{body='ORIGINAL'},mouse:{click:async()=>{}}, keyboard:{type:async()=>{body='ORIGxINAL'},press:async()=>{undos++; if(undos>1)body='ORIGINAL'}},evaluate:async(fn,arg)=>{if(fn.name==='READ_EDITABLE_STATE')return {text:body,text_length:body.length,selection_offset:4,active_inside:true,anchor_inside:true}; if(arg && (arg.kind||arg.kinds))return {t:100}; return null;}};
const witness={frameIntervalMs:16.667,paintAfter:async(t,o)=>{await o.arm(); return noFrameRecord();}};
const result=await measureUndo(page,witness,{modifier:'Control',expectedBodyText:'ORIGINAL'},{editable:{selector:'#doc',is_content_editable:true,text_length:8},points:[{point:'last_text_line',x:1,y:1}]});
return {reason:result.failure_reason,body,undos,fixture_reset:result.fixture_reset};

}
async function cleanupFailure() {
  const fs = (await import('node:fs')).default;
  const { syncBuiltinESMExports } = await import('node:module');
  const original = fs.rmSync;
  fs.rmSync = () => { throw new Error('cleanup denied'); };
  syncBuiltinESMExports();
  try { return validateWitnessRecord(good); }
  catch (error) { return {thrown: error.message}; }
  finally { fs.rmSync = original; syncBuiltinESMExports(); }
}
console.log(
  JSON.stringify({
    failed_reset_suite: await failedResetSuite(), positive_undo: await positiveUndo(), missing_click: await clickMissing(), cleanup: await cleanupProbe(), cleanup_failure: await cleanupFailure(), missing_paste: await c08Refused('missing_paste'), c09_refused: await c09Refused(),
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
