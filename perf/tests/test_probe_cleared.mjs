// #247: the clock check's own mark must be off the page before a baseline frame is taken.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {deflateSync} from 'node:zlib';
import {awaitProbeCleared} from '../runner/witness.mjs';

function png(mark) {
  const width = 20, height = 20;
  const chunk = (type, data) => {
    const body = Buffer.concat([Buffer.from(type), data]); let crc = 0xffffffff;
    for (const b of body) { crc ^= b; for (let j = 0; j < 8; j++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0); }
    const out = Buffer.alloc(data.length + 12); out.writeUInt32BE(data.length); body.copy(out, 4);
    out.writeUInt32BE((crc ^ 0xffffffff) >>> 0, out.length - 4); return out;
  };
  const header = Buffer.alloc(13); header.writeUInt32BE(width); header.writeUInt32BE(height, 4); header[8] = 8; header[9] = 2;
  const raw = Buffer.alloc(height * (1 + width * 3), 255);
  for (let y = 0; y < height; y++) {
    raw[y * (1 + width * 3)] = 0;
    if (mark && y < 8) for (let x = 0; x < 8; x++) { const o = y * (1 + width * 3) + 1 + x * 3; raw[o] = 255; raw[o + 1] = 0; raw[o + 2] = 255; }
  }
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', header), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]).toString('base64');
}
const REGION = {x: 0, y: 0, width: 8, height: 8};
function recorder(frames) {
  return {frames: frames.map((data, seq) => ({data, seq, ack: 'acked'})), nextSeq: frames.length, decoded: new Map()};
}

test('the frame that still shows the mark is not the one the check ends on', async () => {
  const rec = recorder([png(false), png(true)]); // baseline, then the frame that proved the anchor
  setTimeout(() => { rec.frames.push({data: png(false), seq: 2, ack: 'acked'}); rec.nextSeq = 3; }, 30);
  const cleared = await awaitProbeCleared(rec, rec.frames[0], 2, REGION, {waitMs: 1000});
  assert.equal(cleared.cleared, true);
  assert.equal(cleared.frame_seq, 2);
  assert.equal(rec.frames[rec.frames.length - 1].seq, 2); // the recorder's last frame, the next baseline, is clean
});

test('a later frame that still shows the mark does not count', async () => {
  const rec = recorder([png(false), png(true)]);
  setTimeout(() => { rec.frames.push({data: png(true), seq: 2, ack: 'acked'}); rec.nextSeq = 3; }, 10);
  setTimeout(() => { rec.frames.push({data: png(false), seq: 3, ack: 'acked'}); rec.nextSeq = 4; }, 40);
  const cleared = await awaitProbeCleared(rec, rec.frames[0], 2, REGION, {waitMs: 1000});
  assert.equal(cleared.frame_seq, 3);
});

test('no frame without the mark in the time allowed is said, not hidden', async () => {
  const rec = recorder([png(false), png(true)]);
  const cleared = await awaitProbeCleared(rec, rec.frames[0], 2, REGION, {waitMs: 60});
  assert.deepEqual(cleared, {cleared: false, frame_seq: null, waited_ms: cleared.waited_ms});
  assert.ok(cleared.waited_ms >= 60);
});
