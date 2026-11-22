/**
 * C10 by pixels, for an editor that has no DOM scroller at all.
 *
 * The C10 probe (adversarial_c10_scroll.mjs) times a scroll through the DOM:
 * it sets a scroller's `scrollTop` and witnesses the first presented frame
 * whose pixels changed inside that scroller. OnlyOffice has no such scroller.
 * Its scrollbar is its own canvas widget (sdkjs's ScrollObject, position in
 * `scrollVCurrentY`), the wheel is handled in its own JavaScript, and the page
 * is redrawn on a canvas (#id_viewer): no `scrollTop` and no element box ever
 * moves, so the DOM probe finds no container and records "does not apply"
 * (owner's decision 2026-11-22: build a pixel probe instead).
 *
 * The pixel path keeps C10's two ends and changes only how the move is seen:
 *
 *   - start: the instant the page's own JavaScript begins applying the scroll,
 *     in the page's clock. For a DOM editor that is `performance.now()` just
 *     before `scrollTop` is set; here it is `performance.now()` in a
 *     capture-phase `wheel` listener on the editor frame's window, which runs
 *     before OnlyOffice's own wheel handler. The input is one real wheel notch
 *     (CDP `Input.dispatchMouseEvent`) over the canvas: OnlyOffice turns every
 *     notch into a fixed step of its own (45 px at 100 %), whatever the delta.
 *   - end: the same witness every C10 sample uses (witness.mjs `witnessFrame`,
 *     the run's clock check and pixel anchor): the first presented frame at or
 *     after the start whose pixels changed inside the document canvas.
 *
 * What the pixels must then prove (the DOM path's "scrollTop moved" and
 * "the content moved with it"):
 *
 *   - the editor's own scroll position moved (`m_dScrollY`, read before the
 *     wheel and after the witness);
 *   - the witnessed frame shows the baseline's canvas *shifted up* by that
 *     move, not merely repainted: `canvasShift` finds the vertical offset at
 *     which the witnessed frame best matches the baseline, and the sample is
 *     refused unless that offset is the scroll's and the match is far better
 *     than at no offset.
 *
 * OnlyOffice's caret is a DOM div (#id_target_cursor) blinking over the
 * canvas every 500 ms; `caret-color` does not reach it, so it is hidden for
 * the sample (and the record says so), as the witness hides a DOM caret.
 *
 * Every editor not listed in CANVAS_PIXEL_SCROLL gets `null` from
 * `canvasPixelScroll` and keeps the DOM probe, unchanged.
 */

/** editor id -> how its document canvas and scroll position are read. */
export const CANVAS_PIXEL_SCROLL = {
  // OnlyOffice (CryptPad build), in its editor frame (editor_frame.mjs).
  onlyoffice: {
    canvas: '#id_viewer',
    caret: '#id_target_cursor',
    scroll_y_js: 'window.editor.WordControl.m_dScrollY',
    scroll_max_js: 'window.editor.WordControl.m_dScrollY_max',
    scroll_to_top_js: 'window.editor.WordControl.m_oScrollVerApi.scrollToY(0)',
  },
};

/** The pixel spec for an editor, or null: only listed editors leave the DOM probe. */
export function canvasPixelScroll(editorId) {
  if (!Object.prototype.hasOwnProperty.call(CANVAS_PIXEL_SCROLL, editorId || '')) return null;
  return CANVAS_PIXEL_SCROLL[editorId];
}

/** The detection name the sample, the diagnostic and the note carry. */
export const DETECTION = 'canvas_pixels';

/** The shifted match must be at least this much better than no shift. */
export const SHIFT_GAIN_MIN = 4;
/** The found offset may differ from the editor's own move by this many device px. */
export const SHIFT_TOLERANCE_PX = 2;

const CHANNEL_TOLERANCE = 8;

/**
 * Where did the canvas's content go? `before` and `after` are decoded frames
 * (decodePng: {width, height, data RGBA}); `region` is the canvas in device
 * pixels. For every vertical offset dy in [0, maxShiftPx] it counts the
 * sampled pixels of `after` that differ from `before` moved up by dy
 * (after(x, y) vs before(x, y + dy), every `stride`-th pixel, rows the shift
 * keeps on screen), and returns the best offset with its mismatch ratio and
 * the ratio at dy = 0.
 *
 * `shifted` is true only when something changed (the ratio at 0 is above 0),
 * the best offset is above 0, it is the editor's own move within
 * SHIFT_TOLERANCE_PX (when `expectedPx` is given), and the match there is at
 * least SHIFT_GAIN_MIN times better than at 0: a frame that is repainted, not
 * moved, has no such offset.
 */
export function canvasShift(before, after, region, { expectedPx = null, maxShiftPx = null, stride = 2 } = {}) {
  const fail = (reason, extra = {}) => ({ shifted: false, reason, ...extra });
  if (!before || !after) return fail('a frame could not be decoded');
  if (before.width !== after.width || before.height !== after.height) {
    return fail('the two frames differ in size');
  }
  const x0 = Math.max(0, Math.floor(region.x));
  const y0 = Math.max(0, Math.floor(region.y));
  const x1 = Math.min(before.width, Math.ceil(region.x + region.width));
  const y1 = Math.min(before.height, Math.ceil(region.y + region.height));
  const height = y1 - y0;
  if (x1 <= x0 || height <= 4) return fail('the canvas region is empty in the frame');
  const wanted = typeof expectedPx === 'number' && Number.isFinite(expectedPx) ? expectedPx : null;
  let limit = maxShiftPx ?? Math.max(64, wanted === null ? 0 : Math.ceil(wanted * 2));
  limit = Math.min(limit, Math.floor(height / 2));
  const a = before.data;
  const b = after.data;
  const w = before.width;
  const mismatch = (dy) => {
    let compared = 0;
    let differ = 0;
    for (let y = y0; y + dy < y1; y += stride) {
      const rowA = (y + dy) * w;
      const rowB = y * w;
      for (let x = x0; x < x1; x += stride) {
        const p = (rowA + x) * 4;
        const q = (rowB + x) * 4;
        compared += 1;
        if (
          Math.abs(a[p] - b[q]) > CHANNEL_TOLERANCE ||
          Math.abs(a[p + 1] - b[q + 1]) > CHANNEL_TOLERANCE ||
          Math.abs(a[p + 2] - b[q + 2]) > CHANNEL_TOLERANCE
        ) {
          differ += 1;
        }
      }
    }
    return compared ? differ / compared : 1;
  };
  const atZero = mismatch(0);
  let best = { dy: 0, ratio: atZero };
  for (let dy = 1; dy <= limit; dy++) {
    const ratio = mismatch(dy);
    if (ratio < best.ratio) best = { dy, ratio };
  }
  const record = {
    best_dy_px: best.dy,
    mismatch_at_best: Math.round(best.ratio * 1e6) / 1e6,
    mismatch_at_zero: Math.round(atZero * 1e6) / 1e6,
    expected_dy_px: wanted,
    searched_up_to_px: limit,
    stride_px: stride,
    region_px: { x: x0, y: y0, width: x1 - x0, height },
  };
  if (!(atZero > 0)) return fail('the canvas did not change', record);
  if (!(best.dy > 0)) return fail('the canvas changed but is not shifted (best match at no offset)', record);
  if (wanted !== null && Math.abs(best.dy - wanted) > SHIFT_TOLERANCE_PX) {
    return fail(
      'the canvas is shifted by ' + best.dy + ' px, not by the scroll of ' + wanted + ' px',
      record,
    );
  }
  if (!(best.ratio * SHIFT_GAIN_MIN <= atZero)) {
    return fail(
      'the shifted match (' + record.mismatch_at_best + ') is not ' + SHIFT_GAIN_MIN +
        'x better than no shift (' + record.mismatch_at_zero + ')',
      record,
    );
  }
  return { shifted: true, reason: null, ...record };
}
