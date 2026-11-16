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

// Integration needs (#245): a document region, frames decoded on demand, and a bounded walk back.

test('k: changes outside the document region neither count as the edit nor prevent settling', () => {
  const base = blank();
  const region = { x: 16, y: 8, width: 32, height: 32 }; // holds TEXT and the caret
  const noise = k => ({ x: 0, y: 0, w: 14, h: 6, color: k % 2 ? FG : CARET }); // 84 px, changes every frame, outside
  const frames = series(MARKER, 1400, 16, (t, k) => withBlocks(base, t >= MARKER + 32 ? [TEXT, noise(k)] : [noise(k)]));
  const inside = settlePixels(frames, { baseline: base, markerMs: MARKER, region });
  assert.equal(inside.failure_reason, null);
  assert.equal(inside.match_page_ms, MARKER + 32);
  assert.equal(inside.edit_pixels, 168);
  // The same frames with the edit outside the region: nothing to witness there.
  const away = settlePixels(frames, { baseline: base, markerMs: MARKER, region: { x: 40, y: 30, width: 20, height: 16 } });
  assert.equal(away.failure_reason, 'pixel_edit_region_too_small');
});

test('l: frames may be decoded on demand, and no more than a few are held at once', () => {
  const base = blank();
  let live = 0, peak = 0, decodes = 0;
  const lazy = series(MARKER, 1400, 16, (t, k) => withBlocks(base, t >= MARKER + 32 ? [TEXT] : []))
    .map(f => ({ pageMs: f.pageMs, pixels: () => { decodes++; return f.pixels; } }));
  const r = settlePixels(lazy, { baseline: base, markerMs: MARKER });
  assert.equal(r.failure_reason, null);
  assert.equal(r.match_page_ms, MARKER + 32);
  assert.ok(decodes <= 2 * lazy.length + 2, `decoded ${decodes} times for ${lazy.length} frames`);
  void live; void peak;
});

test('m: the walk back is bounded, so a long quiet period is not read whole', () => {
  const base = blank();
  let decodes = 0;
  const lazy = series(MARKER, 3000, 16, (t, k) => withBlocks(base, t >= MARKER + 32 ? [TEXT] : []))
    .map(f => ({ pageMs: f.pageMs, pixels: () => { decodes++; return f.pixels; } }));
  const r = settlePixels(lazy, { baseline: base, markerMs: MARKER, tailMaxMs: 600 });
  assert.equal(r.failure_reason, null);
  assert.equal(r.match_page_ms, MARKER + 32);
  // 600 ms of tail at 16 ms a frame is about 38 frames, plus the three read forward to the match.
  assert.ok(decodes < 60, `decoded ${decodes} frames`);
  assert.ok(r.tail_frames <= 39 && r.settled_page_ms - 600 <= MARKER + 2000);
});

test('n: a caret that blinks only once in the tail is still masked, whichever phase the settled picture has', () => {
  const base = blank();
  const newCaret = { x: 36, y: 10, w: 1, h: 24, color: CARET };
  for (const lastOn of [true, false]) {
    // Caret phases of 500 ms; the text arrives at +32 ms while the caret is in the other phase than at the end.
    const frames = series(MARKER, 2000, 16, (t, k) => {
      const on = (Math.floor((t - MARKER) / 500) % 2 === 0) !== lastOn ? false : true;
      const blocks = t >= MARKER + 32 ? [TEXT] : [];
      if (t >= MARKER + 32 && on) blocks.push(newCaret);
      return withBlocks(base, blocks);
    });
    const r = settlePixels(frames, { baseline: base, markerMs: MARKER });
    assert.equal(r.failure_reason, null, `lastOn=${lastOn}`);
    assert.equal(r.match_page_ms, MARKER + 32, `lastOn=${lastOn}`);
    assert.equal(r.edit_pixels, 168, `lastOn=${lastOn}`);
  }
});

test('o: the frames before the match are kept as evidence of how the edit arrived', () => {
  const base = blank();
  const half = { x: TEXT.x, y: TEXT.y, w: TEXT.w / 2, h: TEXT.h, color: FG };
  const frames = series(MARKER, 1400, 16, (t) =>
    withBlocks(base, t >= MARKER + 64 ? [TEXT] : t >= MARKER + 32 ? [half] : []));
  const r = settlePixels(frames, { baseline: base, markerMs: MARKER });
  assert.equal(r.match_page_ms, MARKER + 64);
  assert.deepEqual(r.progress.map(p => [p.page_ms, p.missing_pixels]), [[MARKER, 168], [MARKER + 32, 84]]);
  assert.deepEqual(r.progress[1].missing_bbox, { x: TEXT.x + 6, y: TEXT.y, width: 6, height: TEXT.h });
});

// What WordCraft showed (16 Nov): the text was in place 100 ms before the last few pixels beside its fading
// caret settled. A caret's worth of stragglers must not move the end event.

test('p: stragglers no more numerous than the blinking caret do not delay the match', () => {
  const base = blank();
  const caret = { x: 40, y: 10, w: 1, h: 24, color: CARET }; // blinks after the edit: 24 px
  const straggler = { x: 41, y: 20, w: 1, h: 10, color: FG }; // 10 px beside it that settle late
  const frames = series(MARKER, MARKER + 2400, 16, (t, k) => {
    const blocks = [];
    if (t >= MARKER + 32) blocks.push(TEXT);
    if (t >= MARKER + 160) blocks.push(straggler);
    if (t >= MARKER + 32 && Math.floor((t - MARKER) / 500) % 2 === 0) blocks.push(caret);
    return withBlocks(base, blocks);
  });
  const r = settlePixels(frames, { baseline: base, markerMs: MARKER });
  assert.equal(r.failure_reason, null);
  assert.equal(r.blink_after_pixels, 24);
  assert.equal(r.edit_pixels, 178);
  assert.equal(r.match_page_ms, MARKER + 32);
  assert.equal(r.match_missing_pixels, 10);
});

test('q: without a blinking caret every edit pixel must be in place', () => {
  const base = blank();
  const straggler = { x: 41, y: 20, w: 1, h: 10, color: FG };
  const frames = series(MARKER, MARKER + 2400, 16, (t) =>
    withBlocks(base, t >= MARKER + 160 ? [TEXT, straggler] : t >= MARKER + 32 ? [TEXT] : []));
  const r = settlePixels(frames, { baseline: base, markerMs: MARKER });
  assert.equal(r.blink_after_pixels, 0);
  assert.equal(r.match_page_ms, MARKER + 160);
  assert.equal(r.match_missing_pixels, 0);
});

test('r: stragglers are allowed only while at least minPixels of the edit are in place', () => {
  const base = blank();
  const caret = { x: 40, y: 10, w: 1, h: 24, color: CARET };
  const small = { x: 22, y: 12, w: 10, h: 10, color: FG }; // 100 px
  const late = { x: 22, y: 30, w: 10, h: 2, color: FG }; // 20 px more, later
  const frames = series(MARKER, MARKER + 2400, 16, (t) => {
    const blocks = [];
    if (t >= MARKER + 32) blocks.push({ ...small, h: 9 }); // 90 px in place first
    if (t >= MARKER + 96) blocks.push(small, late);
    if (t >= MARKER + 32 && Math.floor((t - MARKER) / 500) % 2 === 0) blocks.push(caret);
    return withBlocks(base, blocks);
  });
  const r = settlePixels(frames, { baseline: base, markerMs: MARKER });
  assert.equal(r.edit_pixels, 120);
  // At +32 ms 90 pixels are in place and 30 are missing: more than the caret's 24, and fewer than 100 in place.
  assert.equal(r.match_page_ms, MARKER + 96);
});

test('s: rectangles the harness draws in (its clock and baseline marks) are never part of the edit', () => {
  const base = blank();
  const mark = { x: 0, y: 0, w: 10, h: 10, color: [255, 0, 255] }; // 100 px, appears with the key and stays
  const frames = series(MARKER, MARKER + 1400, 16, (t) => withBlocks(base, t >= MARKER + 32 ? [mark, TEXT] : [mark]));
  const all = settlePixels(frames, { baseline: base, markerMs: MARKER });
  assert.equal(all.edit_pixels, 268);
  assert.equal(all.match_page_ms, MARKER + 32);
  const r = settlePixels(frames, { baseline: base, markerMs: MARKER, exclude: [{ x: 0, y: 0, width: 10, height: 10 }] });
  assert.equal(r.edit_pixels, 168);
  assert.deepEqual(r.edit_bbox, { x: TEXT.x, y: TEXT.y, width: TEXT.w, height: TEXT.h });
  // Only the mark changes: nothing to witness.
  const only = series(MARKER, MARKER + 1400, 16, () => withBlocks(base, [mark]));
  assert.equal(settlePixels(only, { baseline: base, markerMs: MARKER, exclude: [{ x: 0, y: 0, width: 10, height: 10 }] }).failure_reason,
    'pixel_edit_region_too_small');
});
