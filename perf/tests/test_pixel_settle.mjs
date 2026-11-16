import { test } from 'node:test';
import assert from 'node:assert/strict';
import { settlePixels, PIXEL_EDIT_MIN_PIXELS } from '../runner/pixel_settle.mjs';

// Small synthetic canvases: 64x48, a light background, a dark text block
// (168 px >= 150) and a 1x24 caret column, as a canvas editor draws them.
const W = 64, H = 48;
const BG = [248, 248, 248], FG = [20, 20, 20], CARET = [180, 0, 0];
const MARKER = 1000; // key press
const CARET_BLOCK = { x: 20, y: 10, w: 1, h: 24, color: CARET };
const TEXT = { x: 22, y: 12, w: 12, h: 14, color: FG }; // 168 px
const blank = () => {
  const data = new Uint8Array(W * H * 4);
  for (let i = 0; i < W * H; i++) data.set([...BG, 255], i * 4);
  return { width: W, height: H, data };
};
const withBlocks = (base, blocks) => {
  const p = { width: W, height: H, data: new Uint8Array(base.data) };
  for (const b of blocks)
    for (let y = b.y; y < b.y + b.h; y++)
      for (let x = b.x; x < b.x + b.w; x++) p.data.set([...b.color, 255], (y * W + x) * 4);
  return p;
};
const frame = (pageMs, pixels) => ({ pageMs, pixels });
const series = (from, to, stepMs, paint) => {
  const out = [];
  for (let k = 0; from + k * stepMs <= to; k++) out.push(frame(from + k * stepMs, paint(from + k * stepMs, k)));
  return out;
};
const caretOn = k => k % 2 === 0;

test('a: a caret-only blink after the key press is pixel_edit_region_too_small', () => {
  const base = blank();
  const idle = [withBlocks(base, [CARET_BLOCK]), blank()];
  const frames = series(MARKER, 1500, 32, (t, k) => withBlocks(base, caretOn(k) ? [CARET_BLOCK] : []));
  const r = settlePixels(frames, { baseline: base, idle, markerMs: MARKER });
  assert.equal(r.failure_reason, 'pixel_edit_region_too_small');
  assert.equal(r.edit_pixels, 0);
  assert.equal(r.blink_before_pixels, 24);
  assert.equal(r.blink_after_pixels, 24);
});

test('b: match is the frame where the text appears, not the first changed frame', () => {
  const base = blank();
  const idle = [withBlocks(base, [CARET_BLOCK]), blank()];
  const frames = series(MARKER, 1400, 16, (t, k) => {
    const blocks = caretOn(k) ? [CARET_BLOCK] : [];
    if (t >= MARKER + 32) blocks.unshift(TEXT);
    return withBlocks(base, blocks);
  });
  const r = settlePixels(frames, { baseline: base, idle, markerMs: MARKER });
  assert.equal(r.failure_reason, null);
  assert.equal(r.match_page_ms, MARKER + 32);
  assert.equal(r.delay_ms, 32);
  assert.notEqual(r.match_page_ms, MARKER); // the first changed frame is the caret at MARKER
  assert.ok(r.edit_pixels >= 150);
});

test('c: text arriving in the opposite caret phase still matches that frame', () => {
  const base = blank();
  // No idle frames: the caret is learned only from the quiet tail. The text
  // frame (k=2, caret on) sits in the opposite phase from the settled frame
  // (k=25, caret off).
  const frames = series(MARKER, 1400, 16, (t, k) => {
    const blocks = caretOn(k) ? [CARET_BLOCK] : [];
    if (t >= MARKER + 32) blocks.unshift(TEXT);
    return withBlocks(base, blocks);
  });
  const r = settlePixels(frames, { baseline: base, markerMs: MARKER });
  assert.equal(r.failure_reason, null);
  assert.equal(r.blink_before_pixels, 0);
  assert.equal(r.blink_after_pixels, 24);
  assert.equal(r.match_page_ms, MARKER + 32);
  assert.equal(r.delay_ms, 32);
});

test('d: text painted in two steps matches the whole-block frame', () => {
  const base = blank();
  const half = { x: 22, y: 12, w: 6, h: 14, color: FG };
  const frames = series(MARKER, 1400, 16, t =>
    t < MARKER + 16 ? base : t < MARKER + 32 ? withBlocks(base, [half]) : withBlocks(base, [TEXT]));
  const r = settlePixels(frames, { baseline: base, markerMs: MARKER });
  assert.equal(r.failure_reason, null);
  assert.equal(r.match_page_ms, MARKER + 32);
  assert.equal(r.edit_pixels, 168);
});

test('e: a large region changing in every frame refuses not_settled', () => {
  const base = blank();
  const frames = series(MARKER, 1400, 16, (t, k) =>
    withBlocks(base, [{ x: 2, y: 2, w: 30, h: 30, color: [(k * 40) % 256, (k * 40 + 100) % 256, 60] }]));
  const r = settlePixels(frames, { baseline: base, markerMs: MARKER });
  assert.equal(r.failure_reason, 'not_settled');
});

test('f: a block under minPixels refuses pixel_edit_region_too_small', () => {
  const base = blank();
  const small = { x: 22, y: 12, w: 10, h: 8, color: FG }; // 80 px < 100
  const frames = series(MARKER, 1400, 16, t => (t < MARKER + 16 ? base : withBlocks(base, [small])));
  const r = settlePixels(frames, { baseline: base, markerMs: MARKER });
  assert.equal(r.failure_reason, 'pixel_edit_region_too_small');
  assert.equal(r.edit_pixels, 80);
  assert.ok(80 < PIXEL_EDIT_MIN_PIXELS);
});

test('g: out-of-window frames are ignored; no eligible frame is no_frames', () => {
  const base = blank();
  const none = settlePixels(
    [frame(MARKER - 10, withBlocks(base, [TEXT])), frame(MARKER + 3020, withBlocks(base, [TEXT]))],
    { baseline: base, markerMs: MARKER });
  assert.equal(none.failure_reason, 'no_frames');
  // The same run with one in-window frame measures; late garbage is ignored.
  const frames = [
    frame(MARKER - 10, withBlocks(base, [TEXT])),
    ...series(MARKER, 1400, 16, () => withBlocks(base, [TEXT])),
    frame(MARKER + 3020, withBlocks(base, [{ x: 0, y: 0, w: W, h: H, color: FG }])),
  ];
  const r = settlePixels(frames, { baseline: base, markerMs: MARKER });
  assert.equal(r.failure_reason, null);
  assert.equal(r.frames_read, 26);
  assert.equal(r.match_page_ms, MARKER);
});

test('h: a frame of another size is frame_size_changed', () => {
  const base = blank();
  const other = { width: 32, height: 32, data: new Uint8Array(32 * 32 * 4) };
  const r = settlePixels([frame(MARKER, base), frame(MARKER + 16, other)],
    { baseline: base, markerMs: MARKER });
  assert.equal(r.failure_reason, 'frame_size_changed');
});

test('i: a moving caret does not delay the match or prevent settling', () => {
  const base = blank(); // old caret column clean in the baseline
  const idle = [withBlocks(base, [CARET_BLOCK]), blank()]; // blinking at x=20 before the key
  const glyph = { x: 20, y: 10, w: 8, h: 16, color: FG }; // 128 px typed character
  const newCaret = { x: 28, y: 10, w: 1, h: 24, color: CARET }; // drawn 8 px right of the old one
  const frames = series(MARKER, 1400, 16, (t, k) => {
    if (k === 0) return base; // old caret erased, nothing drawn yet
    return withBlocks(base, caretOn(k - 1) ? [glyph, newCaret] : [glyph]);
  });
  const r = settlePixels(frames, { baseline: base, idle, markerMs: MARKER });
  assert.equal(r.failure_reason, null);
  assert.equal(r.match_page_ms, MARKER + 16);
  assert.equal(r.delay_ms, 16);
  // The character's first column lies where the old caret blinked before the key: those 16 pixels are in the
  // blink mask and are not counted as the edit, which leaves 128 - 16.
  assert.equal(r.edit_pixels, 112);
  assert.ok(r.blink_after_pixels >= 24); // the new caret's blink, masked out
});

test('j: indexes refer to the original, unsorted frames array', () => {
  const base = blank();
  const idle = [withBlocks(base, [CARET_BLOCK]), blank()];
  const ordered = series(MARKER, 1400, 16, (t, k) => {
    const blocks = caretOn(k) ? [CARET_BLOCK] : [];
    if (t >= MARKER + 32) blocks.unshift(TEXT);
    return withBlocks(base, blocks);
  });
  const shuffled = [...ordered].reverse(); // 26 frames: settled (t=1400) first
  const r = settlePixels(shuffled, { baseline: base, idle, markerMs: MARKER });
  assert.equal(r.failure_reason, null);
  assert.equal(r.settled_page_ms, 1400);
  assert.equal(r.reference_index, 0); // t=1400 sits at index 0 after the reverse
  assert.ok(Number.isInteger(r.match_index) && r.match_index >= 0 && r.match_index < shuffled.length);
  assert.equal(shuffled[r.match_index].pageMs, r.match_page_ms);
  assert.equal(shuffled[r.reference_index].pageMs, r.settled_page_ms);
  assert.equal(r.match_index, 23); // t=1032: ordered index 2 -> 25 - 2
  assert.equal(r.match_page_ms, MARKER + 32);
  assert.equal(r.delay_ms, 32);
  assert.notEqual(r.match_index, r.reference_index);
});
