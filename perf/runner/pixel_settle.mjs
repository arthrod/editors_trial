/** Pure pixel-level settlement for canvas-drawn editors (issue #245).
 *
 * DOM editors expose glyph rects, so "the first frame that changed" finds the
 * typed character. An editor that draws its text on a <canvas> gives no such
 * rects, and its own caret — a blinking 1x24 column — is usually the first
 * changed frame after the key press. This module decides, from decoded
 * screencast frames alone, which frame first shows the typed character:
 *
 *  - pixels that moved BEFORE the key press (baseline vs the idle frames, and
 *    consecutive idle frames) are "blinkBefore" and never count as edits;
 *  - the picture must go quiet: walking back from the last eligible frame,
 *    every tail frame may differ from the last one only at at most
 *    max(|blinkBefore|, 64) pixels outside blinkBefore — a blink is that
 *    small, real content is not — and the tail must span quietMs;
 *  - pixels that toggle INSIDE that quiet tail are "blinkAfter" (the caret
 *    keeps blinking after the edit) and never count as edits either;
 *  - the edit region is where the settled (last) frame differs from the
 *    baseline, minus both blink masks; it must reach minPixels, else the only
 *    change was the caret and the sample refuses;
 *  - the match is the first eligible frame whose every edit-region pixel
 *    already equals the settled frame: the caret's phase cannot delay it.
 *
 * Frames are ~1280x900 RGBA, so every mask is a Uint8Array and every scan is
 * a flat integer loop; no per-pixel objects, no Set of a million numbers.
 */
export const PIXEL_EDIT_MIN_PIXELS = 100;

/** Settle a canvas edit from raw frames.
 * @param {Array<{pageMs:number,pixels:{width:number,height:number,data:(Uint8Array|Buffer)}}>} frames
 *   decoded frames in any order; data is RGBA, width*height*4 bytes.
 * @param {object} options
 *   baseline {width,height,data} (pre-key picture), idle [] (frames recorded
 *   before the key press while nothing was typed), markerMs 0 (key press
 *   time), maxWaitMs 3000, quietMs 300, tolerance 8 (per R/G/B channel,
 *   alpha ignored), minPixels PIXEL_EDIT_MIN_PIXELS.
 * @returns the failure reason on refusal, else the match and its timings.
 *   match_index and reference_index index the ORIGINAL frames array.
 */
export function settlePixels(frames, options = {}) {
  const {
    baseline,
    idle = [],
    markerMs = 0,
    maxWaitMs = 3000,
    quietMs = 300,
    tolerance = 8,
    minPixels = PIXEL_EDIT_MIN_PIXELS,
  } = options || {};
  // Step 1: eligible frames, in time order.
  const eligible = frames
    .filter(f => Number.isFinite(f.pageMs) && f.pageMs >= markerMs && f.pageMs <= markerMs + maxWaitMs)
    .sort((a, b) => a.pageMs - b.pageMs);
  if (!eligible.length) return { failure_reason: 'no_frames' };
  const w = baseline.width, h = baseline.height, n = w * h;
  for (const f of eligible)
    if (f.pixels.width !== w || f.pixels.height !== h || f.pixels.data.length !== n * 4)
      return { failure_reason: 'frame_size_changed' };
  // Two pixels are equal when every channel differs by at most tolerance.
  const eq = (a, ao, b, bo) => {
    let d = a[ao] - b[bo]; if (d > tolerance || d < -tolerance) return false;
    d = a[ao + 1] - b[bo + 1]; if (d > tolerance || d < -tolerance) return false;
    d = a[ao + 2] - b[bo + 2]; if (d > tolerance || d < -tolerance) return false;
    return true;
  };
  // Step 2: blinkBefore — pixels that move with nothing typed.
  const blinkBefore = new Uint8Array(n);
  let blinkBeforeCount = 0;
  const markBefore = (da, db) => {
    for (let i = 0; i < n; i++) {
      if (blinkBefore[i]) continue;
      const o = i * 4;
      if (!eq(da, o, db, o)) { blinkBefore[i] = 1; blinkBeforeCount++; }
    }
  };
  let prevIdle = null;
  for (const p of idle) {
    if (!p || p.width !== w || p.height !== h || p.data.length !== n * 4) continue;
    markBefore(baseline.data, p.data);
    if (prevIdle) markBefore(prevIdle.data, p.data);
    prevIdle = p;
  }
  // Step 3: quiet tail. Walk back from the last eligible frame; a frame joins
  // the tail while it differs from the last frame at at most `allowance`
  // pixels outside blinkBefore. Pixels differing inside the walk (blink
  // columns included) are remembered as blinkAfter candidates.
  const last = eligible[eligible.length - 1];
  const lastData = last.pixels.data;
  const allowance = Math.max(blinkBeforeCount, 64);
  const candMask = new Uint8Array(n);
  const candList = [];
  let tailStart = eligible.length - 1;
  for (let i = eligible.length - 2; i >= 0; i--) {
    const d = eligible[i].pixels.data;
    const frameDiffs = [];
    let outside = 0;
    for (let j = 0; j < n; j++) {
      const o = j * 4;
      if (eq(d, o, lastData, o)) continue;
      frameDiffs.push(j);
      if (!blinkBefore[j] && ++outside > allowance) break;
    }
    if (outside > allowance) break; // first frame outside the tail ends it
    for (const j of frameDiffs) if (!candMask[j]) { candMask[j] = 1; candList.push(j); }
    tailStart = i;
  }
  if (last.pageMs - eligible[tailStart].pageMs < quietMs)
    return { failure_reason: 'not_settled', frames_read: eligible.length, tail_frames: eligible.length - tailStart };
  const tail = eligible.slice(tailStart);
  // Step 4: blinkAfter — pixels not equal between any two tail frames. Any
  // two frames can differ only where at least one differs from the last
  // frame, so the candidates above suffice; a channel whose spread across
  // the tail exceeds tolerance separates some pair.
  const blinkAfter = new Uint8Array(n);
  let blinkAfterCount = 0;
  for (const j of candList) {
    const o = j * 4;
    let minR = 255, maxR = 0, minG = 255, maxG = 0, minB = 255, maxB = 0;
    for (const f of tail) {
      const d = f.pixels.data;
      const r = d[o], g = d[o + 1], b = d[o + 2];
      if (r < minR) minR = r; if (r > maxR) maxR = r;
      if (g < minG) minG = g; if (g > maxG) maxG = g;
      if (b < minB) minB = b; if (b > maxB) maxB = b;
    }
    if (maxR - minR > tolerance || maxG - minG > tolerance || maxB - minB > tolerance) {
      blinkAfter[j] = 1;
      blinkAfterCount++;
    }
  }
  // Step 5: the settled edit region, minus both blink masks, with its bbox.
  const settledData = last.pixels.data;
  const editIdx = [];
  let bx0 = w, by0 = h, bx1 = -1, by1 = -1;
  for (let y = 0; y < h; y++) {
    const row = y * w;
    for (let x = 0; x < w; x++) {
      const j = row + x;
      if (blinkBefore[j] || blinkAfter[j]) continue;
      const o = j * 4;
      if (eq(settledData, o, baseline.data, o)) continue;
      editIdx.push(j);
      if (x < bx0) bx0 = x; if (x > bx1) bx1 = x;
      if (y < by0) by0 = y; if (y > by1) by1 = y;
    }
  }
  // Step 6: a caret-only change never reaches minPixels.
  if (editIdx.length < minPixels)
    return {
      failure_reason: 'pixel_edit_region_too_small',
      edit_pixels: editIdx.length,
      blink_before_pixels: blinkBeforeCount,
      blink_after_pixels: blinkAfterCount,
      frames_read: eligible.length,
      tail_frames: tail.length,
    };
  // Step 7: the first eligible frame whose every edit pixel is already in
  // place — blink phases are excluded, so they cannot delay the match.
  let match = last;
  for (let i = 0; i < eligible.length; i++) {
    const d = eligible[i].pixels.data;
    let ok = true;
    for (let k = 0; k < editIdx.length; k++) {
      const o = editIdx[k] * 4;
      if (!eq(d, o, settledData, o)) { ok = false; break; }
    }
    if (ok) { match = eligible[i]; break; }
  }
  // Step 8: timings; indexes point into the frames array as passed.
  return {
    failure_reason: null,
    match_index: frames.indexOf(match),
    reference_index: frames.indexOf(last),
    match_page_ms: match.pageMs,
    settled_page_ms: last.pageMs,
    delay_ms: match.pageMs - markerMs,
    edit_pixels: editIdx.length,
    edit_bbox: { x: bx0, y: by0, width: bx1 - bx0 + 1, height: by1 - by0 + 1 },
    blink_before_pixels: blinkBeforeCount,
    blink_after_pixels: blinkAfterCount,
    frames_read: eligible.length,
    tail_frames: tail.length,
  };
}
