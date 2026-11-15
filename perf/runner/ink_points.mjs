/**
 * Ink-run click points (r3c07): resolve C07's three click points from the
 * pixels the editor actually painted, so every editor is aimed at a point on
 * a painted text line, never at page whitespace.
 *
 * One routine serves all nine editors. DOM-text editors' points used to come
 * from DOM line rects (fine for first/last line, but page_centre was the
 * geometric clip centre — often an inter-paragraph gap); canvas, docen and
 * wordcraft had no DOM text at all and used surface-box fractions. Both left
 * clicks on whitespace, where the caret snaps to a line end outside the
 * watched click box.
 *
 * The scan runs on a screenshot of the same clip the page-side resolver
 * reports (the editable box for DOM surfaces, the painted surface box for
 * model/flag surfaces):
 *   1. each clip row's ink runs (dark pixels, run >= INK_MIN_RUN_PX) merge
 *      into line bands (INK_LINE_GAP_PX rows of slack inside a line);
 *   2. bands shorter than INK_MIN_LINE_HEIGHT_PX are ruler ticks and scanline
 *      noise, not text lines;
 *   3. each band's runs cluster by x (INK_RUN_JOIN_PX); the biggest cluster
 *      is the band's extent — a stray margin tick beside a text line is a
 *      separate cluster and does not move the extent;
 *   4. with enough bands, bands whose extent escapes the shared text column
 *      by more than INK_COLUMN_EDGE_PX are chrome that spans the clip
 *      (ribbons, rulers, status bars); the column is the percentile span of
 *      the band extents;
 *   5. the column's bands chain into bodies at paragraph spacing (a
 *      paragraph-per-line layout like eigenpal's merges into one body; a
 *      ribbon or status bar separated by a real page gap stays its own
 *      chain); the chain with the most lines is the document body;
 *   6. first_text_line / last_text_line are the body's first/last band;
 *      page_centre is the band nearest the body's vertical centre.
 *
 * A click point sits at the centre of the ink run nearest the line's extent
 * centre on the band's middle row — a painted glyph, so the editor's hit
 * test places the caret beside the click, inside the watched box. `line` is
 * the band grown by half the median inter-line gap, i.e. the painted line's
 * box, so clickPaintRegion's line-box-plus-padding region contains the
 * clicked line's caret.
 *
 * Pure functions: no page objects here. The caller decodes the screenshot
 * and hands over image coordinates plus the CSS rect they map to.
 */

export const INK_DARK_LUMA = 120;
export const INK_MIN_RUN_PX = 2;
export const INK_LINE_GAP_PX = 3;
export const INK_MIN_LINE_HEIGHT_PX = 4;
export const INK_RUN_JOIN_PX = 24;
export const INK_COLUMN_EDGE_PX = 8;
export const INK_MIN_COLUMN_BANDS = 6;
export const INK_LINE_PAD_MAX_PX = 16;
export const INK_CANDIDATES_PER_SLOT = 4;

const round1 = (value) => Math.round(value * 10) / 10;

function lumaAt(data, width, x, y) {
  const p = (y * width + x) * 4;
  return 0.299 * data[p] + 0.587 * data[p + 1] + 0.114 * data[p + 2];
}

/** Dark run lengths >= minRun on one row of img inside [x0, x1). */
function rowRuns(img, y, x0, x1, dark, minRun) {
  const runs = [];
  let x = x0;
  while (x < x1) {
    while (x < x1 && lumaAt(img.data, img.width, x, y) >= dark) x += 1;
    const start = x;
    while (x < x1 && lumaAt(img.data, img.width, x, y) < dark) x += 1;
    if (x - start >= minRun) runs.push([start, x]);
  }
  return runs;
}

function percentile(sorted, q) {
  if (!sorted.length) return null;
  const i = Math.min(sorted.length - 1, Math.max(0, Math.floor(sorted.length * q)));
  return sorted[i];
}

/**
 * Scan a decoded RGBA image ({width, height, data}) for painted text lines
 * inside clipImg ({left, top, right, bottom}, image pixels) and return click
 * points in CSS coordinates (clipCss maps clipImg onto the page).
 */
export function inkClickPoints(img, clipImg, clipCss = clipImg) {
  const empty = { points: [], slots: {}, bands: [], column: null, line_height_px: null, source: 'ink_runs' };
  if (!img || !img.data || !img.width || !img.height) return empty;
  const x0 = Math.max(0, Math.floor(Math.min(clipImg.left, clipImg.right)));
  const y0 = Math.max(0, Math.floor(Math.min(clipImg.top, clipImg.bottom)));
  const x1 = Math.min(img.width, Math.ceil(Math.max(clipImg.left, clipImg.right)));
  const y1 = Math.min(img.height, Math.ceil(Math.max(clipImg.top, clipImg.bottom)));
  const clipW = clipImg.right - clipImg.left;
  const clipH = clipImg.bottom - clipImg.top;
  if (!(x1 - x0 >= 8 && y1 - y0 >= 8) || !(clipW > 0) || !(clipH > 0)) return empty;
  const scaleX = (clipCss.right - clipCss.left) / clipW;
  const scaleY = (clipCss.bottom - clipCss.top) / clipH;
  const toCssX = (ix) => clipCss.left + (ix - clipImg.left) * scaleX;
  const toCssY = (iy) => clipCss.top + (iy - clipImg.top) * scaleY;
  const dpi = Math.max(scaleX, scaleY);
  const scale = (px) => px * dpi;
  const minRun = Math.max(INK_MIN_RUN_PX, Math.round(scale(INK_MIN_RUN_PX)));
  const lineGap = Math.max(1, Math.round(scale(INK_LINE_GAP_PX)));
  const minLineHeight = Math.max(2, Math.round(scale(INK_MIN_LINE_HEIGHT_PX)));
  const runJoin = Math.max(4, Math.round(scale(INK_RUN_JOIN_PX)));
  const columnEdge = Math.max(2, Math.round(scale(INK_COLUMN_EDGE_PX)));
  const padMax = Math.max(4, Math.round(scale(INK_LINE_PAD_MAX_PX)));

  const rows = [];
  for (let y = y0; y < y1; y += 1) {
    const runs = rowRuns(img, y, x0, x1, INK_DARK_LUMA, minRun);
    if (runs.length) rows.push({ y, runs });
  }
  if (!rows.length) return empty;

  // Rows to line bands: intra-line row gaps of <= lineGap stay in the band.
  const raw = [];
  for (const row of rows) {
    const last = raw[raw.length - 1];
    if (last && row.y - last.inkBottom <= lineGap) {
      last.bottom = row.y;
      last.inkBottom = row.y;
      last.rows.push(row);
    } else {
      raw.push({ top: row.y, bottom: row.y, inkBottom: row.y, rows: [row] });
    }
  }
  const bands = [];
  for (const band of raw) {
    band.height = band.bottom - band.top + 1;
    if (band.height < minLineHeight) continue;
    // The band's x clusters: runs joined horizontally with runJoin of slack;
    // the cluster holding the most ink is this line's extent. A margin tick
    // or a floating overlay beside the line is another cluster and ignored.
    const runs = [];
    for (const row of band.rows) for (const run of row.runs) runs.push({ x0: run[0], x1: run[1], w: run[1] - run[0] });
    runs.sort((a, b) => a.x0 - b.x0);
    const clusters = [];
    for (const run of runs) {
      const cluster = clusters[clusters.length - 1];
      if (cluster && run.x0 - cluster.x1 <= runJoin) {
        cluster.x1 = Math.max(cluster.x1, run.x1);
        cluster.mass += run.w;
      } else {
        clusters.push({ x0: run.x0, x1: run.x1, mass: run.w });
      }
    }
    const biggest = clusters.reduce((a, b) => (b.mass > a.mass ? b : a));
    band.extent = { x0: biggest.x0, x1: biggest.x1 };
    band.inkRows = band.rows.length;
    band.midRow =
      band.rows.reduce((a, b) =>
        Math.abs(b.y - (band.top + band.bottom) / 2) < Math.abs(a.y - (band.top + band.bottom) / 2) ? b : a,
      );
    bands.push(band);
  }
  if (!bands.length) return empty;

  // The document column: the percentile span of the line extents. Bands that
  // span wider than that are chrome crossing the clip, not text in the
  // column; too few bands cannot tell a column from the clip, so skip.
  let column = null;
  let columnBands = bands;
  if (bands.length >= INK_MIN_COLUMN_BANDS) {
    const x0s = bands.map((b) => b.extent.x0).sort((a, b) => a - b);
    const x1s = bands.map((b) => b.extent.x1).sort((a, b) => a - b);
    column = { x0: percentile(x0s, 0.1), x1: percentile(x1s, 0.9) };
    columnBands = bands.filter(
      (b) => b.extent.x0 >= column.x0 - columnEdge && b.extent.x1 <= column.x1 + columnEdge,
    );
    if (!columnBands.length) columnBands = bands;
  }

  // r3c07b ruling #3: the body is the chain of lines linked at paragraph
  // spacing (mergeGap). A paragraph-per-line layout — eigenpal's one-line
  // caret roots — merges into one body; a ribbon or status bar cut off by
  // a real page gap stays its own chain and never wins the line count.
  const heights = columnBands.map((b) => b.height).sort((a, b) => a - b);
  const medianHeight = heights[Math.floor(heights.length / 2)];
  const mergeGap = Math.max(Math.round(medianHeight * 3), Math.round(scale(48)));
  const chains = [];
  for (const band of columnBands) {
    const chain = chains[chains.length - 1];
    if (chain && band.top - chain.bottom <= mergeGap) {
      chain.bands.push(band);
      chain.bottom = band.bottom;
      chain.inkRows += band.inkRows;
    } else {
      chains.push({ top: band.top, bottom: band.bottom, bands: [band], inkRows: band.inkRows });
    }
  }
  const chain = chains.length
    ? chains.reduce((a, b) =>
        b.bands.length > a.bands.length ||
        (b.bands.length === a.bands.length && b.inkRows > a.inkRows)
          ? b
          : a,
      )
    : null;
  if (!chain || !chain.bands.length) return empty;
  const bodyBands = chain.bands;

  // The painted line's box: the band grown by half the median gap between
  // neighbouring bands, so it approximates the line pitch the caret spans.
  const gaps = [];
  for (let i = 1; i < bodyBands.length; i += 1) {
    const gap = bodyBands[i].top - bodyBands[i - 1].bottom - 1;
    if (gap > 0) gaps.push(gap);
  }
  gaps.sort((a, b) => a - b);
  const medianGap = gaps.length ? gaps[Math.floor(gaps.length / 2)] : Math.round(medianHeight * 0.4);
  const linePad = Math.min(padMax, Math.max(2, Math.round(medianGap / 2)));

  const pointFor = (band) => {
    const centre = (band.extent.x0 + band.extent.x1) / 2;
    const inExtent = band.midRow.runs.filter(
      (run) => run[0] <= band.extent.x1 + 1 && run[1] >= band.extent.x0 - 1,
    );
    const pool = inExtent.length ? inExtent : band.midRow.runs;
    let run = null;
    let best = Infinity;
    for (const candidate of pool) {
      const distance =
        candidate[0] <= centre && centre <= candidate[1]
          ? 0
          : Math.min(Math.abs(candidate[0] - centre), Math.abs(candidate[1] - centre));
      if (distance < best) {
        best = distance;
        run = candidate;
      }
    }
    if (!run) return null;
    const ix = Math.min(Math.max(Math.round((run[0] + run[1]) / 2), x0 + 2), x1 - 2);
    const iy = Math.min(Math.max(band.midRow.y, y0 + 2), y1 - 2);
    return {
      x: round1(toCssX(ix)),
      y: round1(toCssY(iy)),
      line: {
        top: round1(toCssY(Math.max(clipImg.top, band.top - linePad))),
        bottom: round1(toCssY(Math.min(clipImg.bottom, band.bottom + linePad))),
      },
      ink: {
        run: [round1(toCssX(run[0])), round1(toCssX(run[1]))],
        extent: [round1(toCssX(band.extent.x0)), round1(toCssX(band.extent.x1))],
      },
    };
  };

  const blockCentre = (chain.top + chain.bottom) / 2;
  const byDistance = [...bodyBands].sort(
    (a, b) => Math.abs((a.top + a.bottom) / 2 - blockCentre) - Math.abs((b.top + b.bottom) / 2 - blockCentre),
  );
  const slotBands = {
    first_text_line: bodyBands.slice(0, INK_CANDIDATES_PER_SLOT),
    page_centre: byDistance.slice(0, INK_CANDIDATES_PER_SLOT),
    last_text_line: bodyBands.slice(-INK_CANDIDATES_PER_SLOT).reverse(),
  };
  const slots = {};
  const points = [];
  for (const name of ['page_centre', 'first_text_line', 'last_text_line']) {
    const candidates = [];
    for (const band of slotBands[name]) {
      const point = pointFor(band);
      if (point) candidates.push({ point: name, ...point });
    }
    slots[name] = candidates;
    if (candidates.length) points.push(candidates[0]);
  }
  return {
    points,
    slots,
    bands: bodyBands.length,
    column: column ? { x0: round1(toCssX(column.x0)), x1: round1(toCssX(column.x1)) } : null,
    line_height_px: round1(scale(medianHeight)),
    source: 'ink_runs',
  };
}
