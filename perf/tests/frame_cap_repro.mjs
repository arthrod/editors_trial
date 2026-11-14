// #202: the screencast recorder keeps the last 1,200 frames. Past that cap an index cursor into
// recorder.frames never moves (the array length stays 1,200), so the clock anchor found no frame and
// Docen's C11 at 500k was refused as anchor_missing. Invoked from test_frame_cap.py; prints JSON.
import { deflateSync } from 'node:zlib';
import * as witness from '../runner/witness.mjs';

const { getRecorder } = witness;

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
// A 16x16 RGBA PNG, white, with the top-left 8x8 corner magenta when `probe` is set.
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
    emit: (data) => listeners['Page.screencastFrame']({ data, sessionId: 1, metadata: { timestamp: Date.now() / 1000 } }),
  };
}
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const out = {};

// 1. Sequence numbers stay unique past the cap.
{
  const cdp = fakeCdp();
  const recorder = getRecorder(cdp, { manageScreencast: false });
  const white = png(false);
  for (let i = 0; i < 1300; i++) cdp.emit(white);
  await sleep(10);
  const seqs = recorder.frames.map((f) => f.seq);
  out.kept = recorder.frames.length;
  out.last_seq = seqs[seqs.length - 1];
  out.first_seq = seqs[0];
  out.seqs_increasing = seqs.every((s, i) => i === 0 || s === seqs[i - 1] + 1);
  // 2. A sequence cursor keeps finding new frames after the cap.
  const cursor = witness.nextFrameSeq ? witness.nextFrameSeq(recorder) : recorder.frames.length;
  for (let i = 0; i < 5; i++) cdp.emit(white);
  out.new_after_cap = witness.framesFrom ? witness.framesFrom(recorder, cursor).length : 0;
  out.all_retained = witness.framesFrom ? witness.framesFrom(recorder, 0).length : 0;
}

// 3. The clock anchor finds its probe frame after 1,200 earlier frames.
{
  const cdp = fakeCdp();
  const recorder = getRecorder(cdp, { manageScreencast: false });
  const white = png(false);
  for (let i = 0; i < 1200; i++) cdp.emit(white);
  await sleep(10);
  const page = {
    evaluate: async (fn) => {
      const src = String(fn);
      if (src.includes('__witness_probe__') && src.includes('createElement')) {
        setTimeout(() => cdp.emit(png(true)), 20);
        return 1000;
      }
      if (src.includes('devicePixelRatio')) return 1;
      return undefined;
    },
  };
  const clock = { time_origin_ms: Date.now() - 1000 };
  const anchor = witness.anchorFrame ? await witness.anchorFrame(page, recorder, clock, { waitMs: 600 }) : null;
  out.anchor_found = Boolean(anchor && anchor.frame);
}
process.stdout.write(JSON.stringify(out));
