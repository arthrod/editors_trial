// #207: C08 and WordCraft's C09 accepted a caret-only frame (16-58 changed pixels) as the response.
// Editors that draw their own caret show or move it as soon as a key arrives; the pasted text is
// painted in a later frame (677 pixels and up). The content criteria pass the witness a floor of
// 100 changed pixels. Invoked from test_b4_content_floor.py; prints JSON.
import { deflateSync } from 'node:zlib';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import * as witness from '../runner/witness.mjs';
import * as ci from '../runner/criteria_input.mjs';
import { publishableRecord } from './witness_records.mjs';

const { getRecorder, witnessFrame } = witness;

function crc32(buf) {
  let c, crc = 0xffffffff;
  for (let n = 0; n < buf.length; n++) {
    c = (crc ^ buf[n]) & 0xff;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    crc = (crc >>> 8) ^ c;
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td));
  return Buffer.concat([len, td, crc]);
}
// A white 64 x 64 page with a black box of boxW x boxH at the top left.
function png(boxW, boxH) {
  const w = 64, h = 64, rows = [];
  for (let y = 0; y < h; y++) {
    const row = Buffer.alloc(1 + w * 4);
    for (let x = 0; x < w; x++) row.set(x < boxW && y < boxH ? [0, 0, 0, 255] : [255, 255, 255, 255], 1 + x * 4);
    rows.push(row);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 6;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(Buffer.concat(rows))), chunk('IEND', Buffer.alloc(0))]).toString('base64');
}
function fakeCdp() {
  const listeners = {};
  return {
    on: (event, fn) => { listeners[event] = fn; },
    send: async () => ({}),
    emit: (data, tsSeconds) => listeners['Page.screencastFrame']({ data, sessionId: 1, metadata: { timestamp: tsSeconds } }),
  };
}
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// A caret frame (2 x 23 = 46 pixels) 5 ms after the input, the text (40 x 40 = 1,600) at 150 ms.
async function caretThenText(minPixels, { live = false } = {}) {
  const cdp = fakeCdp();
  const recorder = getRecorder(cdp, { manageScreencast: false });
  const timeOrigin = Date.now() - 10000;
  const afterPageMs = Date.now() - timeOrigin;
  cdp.emit(png(0, 0), (timeOrigin + afterPageMs - 100) / 1000);
  await sleep(5);
  const baseline = recorder.frames[0];
  const emitBoth = () => {
    cdp.emit(png(2, 23), (timeOrigin + afterPageMs + 5) / 1000);
    cdp.emit(png(40, 40), (timeOrigin + afterPageMs + 150) / 1000);
  };
  // live: the frames arrive while the witness is already waiting, not from its buffer.
  if (live) setTimeout(emitBoth, 120);
  else { emitBoth(); await sleep(5); }
  const page = {
    evaluate: async (fn) => {
      const src = String(fn);
      if (src.includes('timeOrigin') && src.includes('userAgent')) {
        return { time_origin_ms: timeOrigin, now_ms: Date.now() - timeOrigin, date_now_ms: Date.now(), user_agent: 'fake' };
      }
      if (src.includes('devicePixelRatio')) return 1;
      return false;
    },
  };
  const clockCheck = {
    kind: 'clock_skew', acceptable: true, page_offset_ms: 0, method: 'fake', bound_ms: 5,
    lag_bound_ms: 250, conversion: { error_upper_ms: 250 },
  };
  const options = { afterPageMs, baseline, windowMs: 500, caretMask: false, settleMs: 0, recorder, clockCheck };
  if (minPixels !== undefined) options.minPixels = minPixels;
  const record = await witnessFrame(page, cdp, options);
  return {
    outcome: record.outcome,
    frame_after_ms: record.frame_page_ms === null ? null : Math.round(record.frame_page_ms - afterPageMs),
    changed_pixels: record.changed_pixels ?? null,
    min_pixels: record.min_pixels ?? null,
  };
}

// What the criteria ask of the witness.
function recordingWitness(calls) {
  return {
    frameIntervalMs: 16.667,
    paintAfter: async (pageMs, callOptions = {}) => {
      calls.push(callOptions.minPixels ?? null);
      let inputT = typeof pageMs === 'number' ? pageMs : null;
      if (callOptions.arm) inputT = await callOptions.arm();
      return inputT === null ? publishableRecord(140, 100) : publishableRecord(inputT + 40, inputT);
    },
  };
}
function fakePage(texts) {
  let reads = 0;
  return {
    mouse: { click: async () => {} },
    keyboard: { press: async () => {}, type: async () => {} },
    locator: () => ({ first: () => ({ boundingBox: async () => ({ x: 1, y: 1, width: 120, height: 40 }) }) }),
    evaluate: async (fn, arg) => {
      if (fn.name === 'READ_EDITABLE_STATE') {
        reads += 1;
        const text = texts(reads);
        return { text, text_length: text.length, selection_offset: 4, is_content_editable: true, active_inside: true, anchor_inside: true };
      }
      if (arg && typeof arg === 'object' && (arg.kinds || arg.kind)) return { t: 100 };
      return null;
    },
  };
}
const meta = () => ({
  editable: { selector: '#doc', is_content_editable: true, text_length: 8 },
  points: [{ point: 'last_text_line', x: 1, y: 1 }],
});

const pasteCalls = [];
await ci.measureBulkInsert(fakePage((n) => (n >= 2 ? 'ORIGBLOCKINAL' : 'ORIGINAL')), recordingWitness(pasteCalls),
  { bulkChars: 5, block: 'BLOCK', modifier: 'Control', expectedBodyText: 'ORIGINAL' }, meta());
const undoCalls = [];
await ci.measureUndo(fakePage((n) => (n === 2 ? 'ORIGxINAL' : 'ORIGINAL')), recordingWitness(undoCalls),
  { modifier: 'Control', expectedBodyText: 'ORIGINAL' }, meta());

// The two WordCraft paths and the witness wrapper are not reachable without a browser: read them.
const source = readFileSync(fileURLToPath(new URL('../runner/criteria_input.mjs', import.meta.url)), 'utf8');
const body = (name) => {
  const start = source.indexOf(`async function ${name}(`);
  const end = source.indexOf('\nasync function ', start + 1);
  return start < 0 ? '' : source.slice(start, end < 0 ? undefined : end);
};
const floors = (name) => (body(name).match(/minPixels: CONTENT_MIN_CHANGED_PIXELS/g) || []).length;
const samples = (name) => (body(name).match(/await sampleAfterInput\(/g) || []).length;

process.stdout.write(JSON.stringify({
  floor: ci.CONTENT_MIN_CHANGED_PIXELS ?? null,
  default_floor: await caretThenText(undefined),
  content_floor: await caretThenText(100),
  content_floor_live: await caretThenText(100, { live: true }),
  default_floor_live: await caretThenText(undefined, { live: true }),
  paste_calls: pasteCalls,
  undo_calls: undoCalls,
  source: {
    measureBulkInsert: [floors('measureBulkInsert'), samples('measureBulkInsert')],
    measureBulkInsertCopyOracle: [floors('measureBulkInsertCopyOracle'), samples('measureBulkInsertCopyOracle')],
    measureUndoCopyOracle: [floors('measureUndoCopyOracle'), samples('measureUndoCopyOracle')],
    measureUndo: [floors('measureUndo'), samples('measureUndo')],
    wrapper_forwards: /minPixels: callOptions\.minPixels/.test(source),
  },
}));
