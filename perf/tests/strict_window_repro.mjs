// #203: C14's damage witness accepted frames long after its 500 ms window. The window's deadline is
// wall-clock from the start of the scan loop, which runs only after the setup calls into the page
// (caret mask, baseline, region) return; a busy page delays them, and every frame recorded meanwhile
// is accepted from the buffer. GenOffice at 500k: window opened at 129 s, damage frame accepted at 289 s.
// A classifying witness (`strictWindow`) counts only frames whose page time is inside
// [afterPageMs, afterPageMs + windowMs + slack]; slack is the clock conversion's upper error bound.
// Invoked from test_strict_window.py; prints JSON.
import { deflateSync } from 'node:zlib';
import * as witness from '../runner/witness.mjs';

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
function png(probe) {
  const w = 16, h = 16, rows = [];
  for (let y = 0; y < h; y++) {
    const row = Buffer.alloc(1 + w * 4);
    for (let x = 0; x < w; x++) {
      const magenta = probe && x < 8 && y < 8;
      row.set(magenta ? [255, 0, 255, 255] : [255, 255, 255, 255], 1 + x * 4);
    }
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

// One witness call. The page answers its setup call (the caret-mask removal) only after
// `busyMs`; while it is busy the screencast records a changed frame `frameAfterMs` after the arm.
async function run({ frameAfterMs, strictWindow, busyMs = 1500, noArm = false }) {
  const cdp = fakeCdp();
  const recorder = getRecorder(cdp, { manageScreencast: false });
  const timeOrigin = Date.now() - 10000;
  const afterPageMs = Date.now() - timeOrigin;
  cdp.emit(png(false), (timeOrigin + afterPageMs - 100) / 1000);
  await sleep(5);
  const baseline = recorder.frames[0];
  const page = {
    evaluate: async (fn) => {
      const src = String(fn);
      if (src.includes('timeOrigin') && src.includes('userAgent')) {
        return { time_origin_ms: timeOrigin, now_ms: Date.now() - timeOrigin, date_now_ms: Date.now(), user_agent: 'fake' };
      }
      if (src.includes('devicePixelRatio')) return 1;
      // The busy page: the setup call returns late; the changed frame lands meanwhile.
      cdp.emit(png(true), (timeOrigin + afterPageMs + frameAfterMs) / 1000);
      await sleep(busyMs);
      return false;
    },
  };
  const clockCheck = {
    kind: 'clock_skew', acceptable: true, page_offset_ms: 0, method: 'fake', bound_ms: 5,
    lag_bound_ms: 250, conversion: { error_upper_ms: 250 },
  };
  const record = await witnessFrame(page, cdp, {
    afterPageMs: noArm ? null : afterPageMs, baseline, windowMs: 500, caretMask: false, settleMs: 0, recorder,
    clockCheck, minPixels: 4, strictWindow,
  });
  return {
    outcome: record.outcome,
    frame_after_ms: record.frame_page_ms === null ? null : Math.round(record.frame_page_ms - afterPageMs),
    strict_window: record.strict_window ?? null,
    window_end_page_ms: record.window_end_page_ms ?? null,
    window_end_after_ms: record.window_end_page_ms == null ? null : Math.round(record.window_end_page_ms - afterPageMs),
    frames_beyond_window: record.frames_beyond_window ?? null,
  };
}

const out = {
  // A frame 1,000 ms after the arm, recorded while the page was busy: outside 500 ms + 250 ms.
  late_strict: await run({ frameAfterMs: 1000, strictWindow: true }),
  // The same frame without strictWindow: the wait-budget lanes keep their first changed frame.
  late_loose: await run({ frameAfterMs: 1000, strictWindow: false }),
  // Inside the window: witnessed either way.
  inside_strict: await run({ frameAfterMs: 300, strictWindow: true }),
  // Past 500 ms but inside the clock's +250 ms conversion error: still counts.
  slack_strict: await run({ frameAfterMs: 650, strictWindow: true }),
  // GLM review: strict without an arm time has no window end, so it is not a strict record.
  strict_no_arm: await run({ frameAfterMs: 300, strictWindow: true, busyMs: 50, noArm: true }),
};
process.stdout.write(JSON.stringify(out));
