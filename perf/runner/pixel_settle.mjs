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
 *    Where a caret blinks after the edit, no more pixels than that caret has
 *    may still be missing, as long as minPixels of the edit are in place.
 *
 * Frames are ~1280x900 RGBA, so every mask is a Uint8Array and every scan is
 * a flat integer loop; no per-pixel objects, no Set of a million numbers.
 * A frame's `pixels` may be a function that decodes it on demand: an editor
 * that repaints all the time delivers a couple of hundred frames in the
 * window, and holding them all decoded is close to a gigabyte. Only the
 * settled frame and the one being read are held; the walk back from the end
 * stops after `tailMaxMs`, which is long enough to see a caret blink both ways.
 * `region` (device pixels) limits everything to the document: a toolbar that
 * repaints outside it is neither the edit nor a reason not to settle.
 */
export const PIXEL_EDIT_MIN_PIXELS = 100;

/** Settle a canvas edit from raw frames.
 * @param {Array<{pageMs:number,pixels:{width:number,height:number,data:(Uint8Array|Buffer)}}>} frames
 *   decoded frames in any order; data is RGBA, width*height*4 bytes.
 * @param {object} options
 *   baseline {width,height,data} (pre-key picture), idle [] (frames recorded
 *   before the key press while nothing was typed), markerMs 0 (key press
 *   time), maxWaitMs 3000, quietMs 300, tolerance 8 (per R/G/B channel,
 *   alpha ignored), minPixels PIXEL_EDIT_MIN_PIXELS, tailMaxMs 1200,
 *   region {x,y,width,height} or null (the whole frame), exclude [] (rects
 *   the harness itself draws in).
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
    tailMaxMs = 1200,
    region = null,
    exclude = [],
  } = options || {};
  // Step 1: eligible frames, in time order.
  const eligible = frames
    .filter(f => Number.isFinite(f.pageMs) && f.pageMs >= markerMs && f.pageMs <= markerMs + maxWaitMs)
    .sort((a, b) => a.pageMs - b.pageMs);
  if (!eligible.length) return { failure_reason: 'no_frames' };
  const w = baseline.width, h = baseline.height, n = w * h;
  const SIZE = Symbol('size');
  const read = f => {
    const p = typeof f.pixels === 'function' ? f.pixels() : f.pixels;
    if (!p || p.width !== w || p.height !== h || p.data.length !== n * 4) throw SIZE;
    return p.data;
  };
  // The document region, as a row and column range; outside it nothing is read.
  const x0 = region ? Math.max(0, Math.floor(region.x)) : 0;
  const y0 = region ? Math.max(0, Math.floor(region.y)) : 0;
  const x1 = region ? Math.min(w, Math.ceil(region.x + region.width)) : w;
  const y1 = region ? Math.min(h, Math.ceil(region.y + region.height)) : h;
  // Two pixels are equal when every channel differs by at most tolerance.
  const eq = (a, b, o) => {
    let d = a[o] - b[o]; if (d > tolerance || d < -tolerance) return false;
    d = a[o + 1] - b[o + 1]; if (d > tolerance || d < -tolerance) return false;
    d = a[o + 2] - b[o + 2]; if (d > tolerance || d < -tolerance) return false;
    return true;
  };
  try {
    // Step 2: blinkBefore — pixels that move with nothing typed. The harness's
    // own marks on the page (`exclude`) are put in the same mask without being
    // counted: they are never the edit and never a reason not to settle.
    const blinkBefore = new Uint8Array(n);
    let blinkBeforeCount = 0;
    for (const rect of exclude || []) {
      const ex1 = Math.min(w, Math.ceil(rect.x + rect.width)), ey1 = Math.min(h, Math.ceil(rect.y + rect.height));
      for (let y = Math.max(0, Math.floor(rect.y)); y < ey1; y++)
        for (let x = Math.max(0, Math.floor(rect.x)); x < ex1; x++) blinkBefore[y * w + x] = 2;
    }
    const markBefore = (da, db) => {
      for (let y = y0; y < y1; y++) for (let j = y * w + x0, end = y * w + x1; j < end; j++) {
        if (!blinkBefore[j] && !eq(da, db, j * 4)) { blinkBefore[j] = 1; blinkBeforeCount++; }
      }
    };
    let prevIdle = null;
    for (const p of idle) {
      if (!p || p.width !== w || p.height !== h || p.data.length !== n * 4) continue;
      markBefore(baseline.data, p.data);
      if (prevIdle) markBefore(prevIdle.data, p.data);
      prevIdle = p;
    }
    // Step 3: quiet tail. Walk back from the last eligible frame, no further
    // than tailMaxMs; a frame joins the tail while it differs from the last
    // frame at at most `allowance` pixels outside blinkBefore. The lowest and
    // highest value of each channel over the tail tell which pixels toggle.
    const last = eligible[eligible.length - 1];
    const lastData = read(last);
    const allowance = Math.max(blinkBeforeCount, 64);
    const lo = new Uint8Array(n * 3), hi = new Uint8Array(n * 3);
    for (let j = 0; j < n; j++) {
      lo[j * 3] = hi[j * 3] = lastData[j * 4];
      lo[j * 3 + 1] = hi[j * 3 + 1] = lastData[j * 4 + 1];
      lo[j * 3 + 2] = hi[j * 3 + 2] = lastData[j * 4 + 2];
    }
    let tailStart = eligible.length - 1;
    for (let i = eligible.length - 2; i >= 0; i--) {
      if (last.pageMs - eligible[i].pageMs > tailMaxMs && last.pageMs - eligible[tailStart].pageMs >= quietMs) break;
      const d = read(eligible[i]);
      let outside = 0;
      scan: for (let y = y0; y < y1; y++) for (let j = y * w + x0, end = y * w + x1; j < end; j++) {
        if (!blinkBefore[j] && !eq(d, lastData, j * 4) && ++outside > allowance) break scan;
      }
      if (outside > allowance) break; // first frame outside the tail ends it
      for (let y = y0; y < y1; y++) for (let j = y * w + x0, end = y * w + x1; j < end; j++) {
        for (let c = 0; c < 3; c++) {
          const v = d[j * 4 + c], k = j * 3 + c;
          if (v < lo[k]) lo[k] = v; else if (v > hi[k]) hi[k] = v;
        }
      }
      tailStart = i;
    }
    const tailFrames = eligible.length - tailStart;
    if (last.pageMs - eligible[tailStart].pageMs < quietMs)
      return { failure_reason: 'not_settled', frames_read: eligible.length, tail_frames: tailFrames };
    // Steps 4 and 5: blinkAfter is what toggles inside the tail; the edit
    // region is where the settled picture differs from the baseline, outside
    // both blink masks.
    const edit = [];
    let blinkAfterCount = 0;
    let bx0 = w, by0 = h, bx1 = -1, by1 = -1;
    for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
      const j = y * w + x, k = j * 3;
      const toggles = hi[k] - lo[k] > tolerance || hi[k + 1] - lo[k + 1] > tolerance || hi[k + 2] - lo[k + 2] > tolerance;
      if (toggles && blinkBefore[j] !== 2) blinkAfterCount++;
      if (toggles || blinkBefore[j] || eq(lastData, baseline.data, j * 4)) continue;
      edit.push(j);
      if (x < bx0) bx0 = x; if (x > bx1) bx1 = x;
      if (y < by0) by0 = y; if (y > by1) by1 = y;
    }
    // Step 6: a caret-only change never reaches minPixels.
    if (edit.length < minPixels)
      return {
        failure_reason: 'pixel_edit_region_too_small',
        edit_pixels: edit.length,
        blink_before_pixels: blinkBeforeCount,
        blink_after_pixels: blinkAfterCount,
        frames_read: eligible.length,
        tail_frames: tailFrames,
      };
    // Step 7: the first eligible frame whose every edit pixel is already in
    // place — blink phases are excluded, so they cannot delay the match.
    // The frames before it are kept as evidence of how the edit arrived: how
    // many edit pixels were still missing in each, and where (at most twelve).
    let match = last, matchMissing = 0;
    const progress = [];
    for (let i = 0; i < eligible.length - 1; i++) {
      const d = read(eligible[i]);
      let missing = 0, mx0 = w, my0 = h, mx1 = -1, my1 = -1;
      for (let k = 0; k < edit.length; k++) {
        const j = edit[k];
        if (eq(d, lastData, j * 4)) continue;
        missing++;
        const x = j % w, y = (j - x) / w;
        if (x < mx0) mx0 = x; if (x > mx1) mx1 = x;
        if (y < my0) my0 = y; if (y > my1) my1 = y;
      }
      // In place: nothing missing, or no more missing than the caret that blinks after the edit has pixels
      // (its own fade can leave a few beside it unsettled) while at least minPixels of the edit are there.
      if (!missing || (missing <= blinkAfterCount && edit.length - missing >= minPixels)) {
        match = eligible[i];
        matchMissing = missing;
        break;
      }
      const entry = { page_ms: eligible[i].pageMs, missing_pixels: missing,
        missing_bbox: { x: mx0, y: my0, width: mx1 - mx0 + 1, height: my1 - my0 + 1 } };
      const before = progress[progress.length - 1];
      // Only a frame that changed what is missing is worth a line.
      if (!before || before.missing_pixels !== missing || JSON.stringify(before.missing_bbox) !== JSON.stringify(entry.missing_bbox)) {
        if (progress.length < 12) progress.push(entry);
      }
    }
    // Step 8: timings; indexes point into the frames array as passed.
    return {
      failure_reason: null,
      match_index: frames.indexOf(match),
      reference_index: frames.indexOf(last),
      match_page_ms: match.pageMs,
      settled_page_ms: last.pageMs,
      delay_ms: match.pageMs - markerMs,
      match_missing_pixels: matchMissing,
      edit_pixels: edit.length,
      edit_bbox: { x: bx0, y: by0, width: bx1 - bx0 + 1, height: by1 - by0 + 1 },
      blink_before_pixels: blinkBeforeCount,
      blink_after_pixels: blinkAfterCount,
      frames_read: eligible.length,
      tail_frames: tailFrames,
      progress,
    };
  } catch (error) {
    if (error === SIZE) return { failure_reason: 'frame_size_changed' };
    throw error;
  }
}
