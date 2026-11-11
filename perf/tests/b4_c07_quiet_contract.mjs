/**
 * r3c07b contract — one C07 sample definition for every editor:
 *
 *   the editor has had NO pointer or keyboard interaction and no focus on its
 *   document before the measured click (fresh state per point: a reload, or a
 *   state proven untouched); the watched box shows NO changed pixel for at
 *   least 1000 ms before the click (recorded on the witness); the sample is
 *   pointerdown -> first frame with a change inside that box. With a quiet
 *   box and an untouched editor the change is the caret arriving — DOM or
 *   canvas alike. A box that is not quiet before the click is a named refusal
 *   of that point.
 *
 * The reviewer plants — a blinking caret already in the box, a hover
 * highlight, a toolbar repaint inside the box, scroll jitter, and a
 * canvas-model paint without a readable caret — must refuse, never measure.
 */
import * as ci from '../runner/criteria_input.mjs';
import { publishableRecord } from './witness_records.mjs';

const { measureClicks, selectDistinctLinePoints } = ci;

let failed = 0;
let checks = 0;
function assert(cond, msg) {
  checks += 1;
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failed += 1;
  }
}

const WORDCRAFT_NOTE =
  "caret position not readable; sample is the first paint in a box proven quiet before an untouched editor's first click";

function quietWindow(over = {}) {
  return {
    required_ms: 1000,
    budget_ms: 8000,
    proven: true,
    observed_ms: 1240.5,
    start_page_ms: 2100,
    end_page_ms: 3340.5,
    changes_seen: 0,
    events: [],
    exhausted: false,
    violated: false,
    ...over,
  };
}

function quietRecord(frameMs, markerMs, quiet, outcome = 'witnessed') {
  const record = publishableRecord(frameMs, markerMs);
  const css = { x: 600, y: 185, width: 48, height: 34 };
  record.caret_masked = false;
  record.caret_mask_css = null;
  record.caret_mask_error = null;
  record.document_scoped = true;
  record.document_region = {
    source: 'rect',
    selector: null,
    rect_css_px: css,
    rect_device_px: { ...css },
    device_pixel_ratio: 1,
  };
  record.region_pixels = css.width * css.height;
  record.total_pixels = css.width * css.height;
  record.changed_pixels = 240;
  record.diff_ratio = 240 / (css.width * css.height);
  record.max_diff_ratio = record.diff_ratio;
  if (outcome === 'no_frame') {
    record.outcome = 'no_frame';
    record.frame_page_ms = null;
    record.frames_after = 6;
  }
  if (quiet) record.quiet_window = quiet;
  return record;
}

/**
 * A page double for the C07 loop: taps, untouched checks, state reads and
 * pointer targets. `clicked` flips the DOM state to focused/caret-placed;
 * a reload (the driver's fresh-state hook) resets it.
 */
function clickPage({ surfaceKind = 'dom', touchedAfterClick = false, pointerTimes = [40, 140, 190] } = {}) {
  const times = pointerTimes.slice();
  let pointerReads = 0;
  const mouseClicks = [];
  let baselineClicks = 0;
  let lastClick = null;
  const page = {
    mouseClicks,
    freshBaseline() {
      baselineClicks = mouseClicks.length;
    },
    mouse: {
      click: async (x, y) => {
        mouseClicks.push([x, y]);
        lastClick = { x, y };
      },
    },
    keyboard: { press: async () => {}, type: async () => {} },
    evaluate: async (fn, arg) => {
      const name = fn && fn.name;
      const clicked = mouseClicks.length > baselineClicks;
      if (name === 'DOCUMENT_UNTOUCHED') {
        const dirty = touchedAfterClick && clicked;
        return dirty
          ? { events: [{ index: 0, kind: 'pointerdown' }], anchor_inside: true, active_inside: true, tapped: 1 }
          : { events: [], anchor_inside: false, active_inside: false, tapped: 0 };
      }
      if (name === 'READ_SURFACE_STATE') {
        if (surfaceKind === 'flag') {
          return {
            text: '',
            text_length: 0,
            text_source: 'modified_flag',
            input_reachable: true,
            active_inside: false,
            anchor_inside: false,
            caret: null,
            flag: { title: 'doc', modified: clicked },
            box: { left: 0, top: 0, right: 1280, bottom: 900 },
          };
        }
        if (surfaceKind === 'model') {
          return {
            text: 'AB',
            text_length: 2,
            text_source: 'canvas_model',
            input_reachable: true,
            active_inside: false,
            anchor_inside: clicked,
            selection_offset: clicked ? 5 : null,
            caret: null,
            box: { left: 0, top: 0, right: 1280, bottom: 900 },
          };
        }
        return { error: 'editable_not_found' };
      }
      if (name === 'READ_EDITABLE_STATE') {
        return {
          text: 'AB',
          text_length: 2,
          text_source: 'dom',
          is_content_editable: true,
          input_reachable: true,
          read_only: false,
          active_inside: clicked,
          active_tag: clicked ? 'div' : null,
          anchor_inside: clicked,
          selection_expanded: false,
          caret:
            clicked && lastClick
              ? {
                  top: lastClick.y - 9,
                  bottom: lastClick.y + 9,
                  left: lastClick.x + 2,
                  right: lastClick.x + 4,
                  height: 18,
                  collapsed: true,
                }
              : null,
          box: { left: 0, top: 0, right: 1200, bottom: 900 },
        };
      }
      if (arg && arg.kind === 'pointerdown') {
        const t = times[Math.min(pointerReads, times.length - 1)];
        pointerReads += 1;
        return { t, target: {} };
      }
      if (arg && (arg.kind || arg.kinds)) return null;
      if (typeof arg === 'number') return 12;
      if (typeof arg === 'string') return { inside: true, reason: null };
      if (arg && typeof arg === 'object') return { inside: true, reason: null };
      return null;
    },
  };
  return page;
}

const FIRST = { point: 'first_text_line', x: 640, y: 200, line: { top: 190, bottom: 210 }, hit_inside_editable: true };
const MIDDLE = { point: 'page_centre', x: 640, y: 450, line: { top: 440, bottom: 460 }, hit_inside_editable: true };
const LAST = { point: 'last_text_line', x: 640, y: 700, line: { top: 690, bottom: 710 }, hit_inside_editable: true };

function domMeta(points, surface) {
  return {
    editable: { selector: '#doc', is_content_editable: true, input_reachable: true },
    points,
    surface: surface || { kind: 'dom' },
  };
}

/**
 * The witness stub mirrors witnessFrame's quiet contract: the arm only fires
 * when the quiet window was proven — a non-quiet box never reaches the click.
 */
function quietWitness(record) {
  const seen = [];
  return {
    seen,
    frameIntervalMs: 16.667,
    paintAfter: async (_t, callOptions = {}) => {
      seen.push(callOptions);
      const result = typeof record === 'function' ? record(seen.length) : record;
      const quiet = result && result.quiet_window;
      const mayArm = !quiet || quiet.proven === true;
      if (callOptions.arm && mayArm) await callOptions.arm();
      return result;
    },
  };
}

function opts(page, extra = {}) {
  return {
    frameTimeoutMs: 2000,
    expectedBodyText: null,
    quietMs: 1000,
    ...extra,
  };
}

// -- the quiet window is required -------------------------------------------
{
  const page = clickPage();
  const witness = quietWitness(quietRecord(180, 40, null));
  const entry = await measureClicks(
    page,
    domMeta([FIRST, LAST]),
    opts(page, { witness }),
  );
  assert(entry.outcome !== 'measured', 'a painted frame without quiet-window evidence is not a C07 sample');
  assert(
    String(entry.failure_reason || '').includes('quiet'),
    `the refusal names the quiet box (got ${entry.failure_reason})`,
  );
}

// -- a proven quiet box measures ---------------------------------------------
{
  const page = clickPage();
  const witness = quietWitness(quietRecord(180, 40, quietWindow()));
  const entry = await measureClicks(
    page,
    domMeta([FIRST, LAST]),
    opts(page, {
      witness,
      reloadPage: async () => {
        page.freshBaseline();
        return true;
      },
    }),
  );
  assert(entry.outcome === 'measured', `a quiet-box click measures (got ${entry.outcome}: ${entry.failure_reason})`);
  assert(
    witness.seen.every((o) => o.quietMs >= 1000),
    'every C07 witness call asks for a >=1000 ms quiet box',
  );
  assert(
    entry.observations.every(
      (o) => o.quiet_window && o.quiet_window.observed_ms >= 1000 && o.quiet_window.proven === true,
    ),
    'every sampled observation records the quiet window it proved',
  );
  assert(entry.samples_ms.length === 2, 'two distinct lines measure two samples');
  assert(entry.observations.every((o) => o.fresh_state && o.fresh_state.state), 'every point records its fresh state');
  assert(
    entry.observations[1] && entry.observations[1].fresh_state && entry.observations[1].fresh_state.state === 'reloaded',
    'the second point is measured on a fresh load',
  );
}

// -- an exhausted quiet budget is a named refusal, not a click ---------------
{
  const page = clickPage();
  const witness = quietWitness(
    quietRecord(180, 40, quietWindow({ proven: false, exhausted: true, observed_ms: 7990 }), 'no_frame'),
  );
  const entry = await measureClicks(page, domMeta([FIRST, LAST]), opts(page, { witness }));
  assert(entry.outcome === 'failed', 'a box that never goes quiet refuses the criterion');
  assert(
    String(entry.failure_reason || '').includes('quiet'),
    `the exhaustion is named (got ${entry.failure_reason})`,
  );
  assert(page.mouseClicks.length === 0, 'a non-quiet box is never clicked');
}

// -- a quiet-window violation inside the arm gap refuses ---------------------
{
  const page = clickPage();
  const witness = quietWitness(
    quietRecord(
      180,
      40,
      quietWindow({
        proven: false,
        exhausted: true,
        violated: true,
        changes_seen: 2,
        observed_ms: 7990,
        events: [
          { frame_page_ms: 2500, changed: 60, ratio: 0.02 },
          { frame_page_ms: 3100, changed: 60, ratio: 0.02 },
        ],
      }),
      'no_frame',
    ),
  );
  const entry = await measureClicks(page, domMeta([FIRST, LAST]), opts(page, { witness }));
  assert(entry.outcome === 'failed', 'a change inside the quiet window before the click refuses');
  assert(
    String(entry.failure_reason || '').includes('quiet'),
    `the violation is named (got ${entry.failure_reason})`,
  );
  assert(page.mouseClicks.length === 0, 'a violated box is never clicked');
}

// -- a flag surface (WordCraft): quiet-box proof, not a caret exception ------
{
  const page = clickPage({ surfaceKind: 'flag' });
  const witness = quietWitness(quietRecord(180, 40, quietWindow()));
  const entry = await measureClicks(
    page,
    domMeta([FIRST, LAST], { kind: 'flag', pageRoot: '#wc', selector: '#wc' }),
    opts(page, {
      witness,
      reloadPage: async () => {
        page.freshBaseline();
        return true;
      },
    }),
  );
  assert(entry.outcome === 'measured', `a quiet flag-surface click measures (got ${entry.outcome}: ${entry.failure_reason})`);
  const sample = entry.observations.find((o) => o.sample_ms !== undefined);
  assert(sample && sample.caret_note === WORDCRAFT_NOTE, 'the flag surface records the unreadable-caret note verbatim');
  assert(sample && sample.caret_evidence === 'unreadable', 'the unreadable caret is named evidence');
}

// -- the flag plant without a quiet box refuses -------------------------------
{
  const page = clickPage({ surfaceKind: 'flag' });
  const witness = quietWitness(quietRecord(180, 40, null));
  const entry = await measureClicks(
    page,
    domMeta([FIRST, LAST], { kind: 'flag', pageRoot: '#wc', selector: '#wc' }),
    opts(page, {
      witness,
      reloadPage: async () => {
        page.freshBaseline();
        return true;
      },
    }),
  );
  assert(entry.outcome === 'failed', 'a flag surface painting inside a non-quiet box refuses');
}

// -- a canvas model places its selection; the quiet box proves the paint -----
{
  const page = clickPage({ surfaceKind: 'model' });
  const witness = quietWitness(quietRecord(180, 40, quietWindow()));
  const entry = await measureClicks(
    page,
    domMeta([FIRST, LAST], { kind: 'model', model: 'canvas_editor', pageRoot: '#cv', selector: '#cv' }),
    opts(page, {
      witness,
      reloadPage: async () => {
        page.freshBaseline();
        return true;
      },
    }),
  );
  assert(entry.outcome === 'measured', `a canvas-model quiet click measures (got ${entry.outcome}: ${entry.failure_reason})`);
  assert(
    entry.observations.some((o) => o.model_selection_offset === 5),
    'the canvas model selection offset is recorded as caret evidence',
  );
}

// -- the same coordinates are never measured twice ---------------------------
{
  const page = clickPage();
  const witness = quietWitness(quietRecord(180, 40, quietWindow()));
  const dup = { ...MIDDLE, x: FIRST.x, y: FIRST.y, line: { ...FIRST.line } };
  const entry = await measureClicks(
    page,
    domMeta([FIRST, dup, LAST]),
    opts(page, {
      witness,
      reloadPage: async () => {
        page.freshBaseline();
        return true;
      },
    }),
  );
  const coords = entry.observations.filter((o) => o.sample_ms !== undefined).map((o) => `${o.x},${o.y}`);
  assert(new Set(coords).size === coords.length, 'no two measured points share coordinates');
  assert(
    entry.outcome === 'measured' && entry.samples_ms.length === 2,
    `a collapsed middle point is dropped (got ${entry.outcome}, ${entry.samples_ms.length} samples)`,
  );
  assert(
    entry.assertion.checks.distinct_line_points === 2,
    `the distinct-line count is recorded (got ${JSON.stringify(entry.assertion.checks)})`,
  );
}

// -- one painted line can never be a measured C07 ----------------------------
{
  const page = clickPage();
  const witness = quietWitness(quietRecord(180, 40, quietWindow()));
  const entry = await measureClicks(page, domMeta([FIRST]), opts(page, { witness }));
  assert(entry.outcome === 'failed', 'fewer than two distinct painted lines is not a measured C07');
  assert(
    String(entry.failure_reason || '').includes('fewer_than_two'),
    `the shortfall is named (got ${entry.failure_reason})`,
  );
}

// -- a touched editor state is a named refusal of the point -------------------
{
  const page = clickPage({ touchedAfterClick: true });
  const witness = quietWitness(quietRecord(180, 40, quietWindow()));
  const entry = await measureClicks(page, domMeta([FIRST, MIDDLE, LAST]), opts(page, { witness }));
  assert(entry.outcome === 'failed', 'an editor already carrying our input cannot measure the next point');
  assert(
    String(entry.failure_reason || '').includes('untouched'),
    `the touched state is named (got ${entry.failure_reason})`,
  );
  const refused = entry.observations.filter((o) => o.failure);
  assert(
    refused.some((o) => String(o.failure).includes('untouched')),
    'the touched point is refused by name',
  );
}

// -- fresh state per point goes through the reload hook ----------------------
{
  const page = clickPage();
  const witness = quietWitness(quietRecord(180, 40, quietWindow()));
  const reloads = [];
  const entry = await measureClicks(
    page,
    domMeta([FIRST, MIDDLE, LAST]),
    opts(page, {
      witness,
      reloadPage: async () => {
        reloads.push(page.mouseClicks.length);
        page.freshBaseline();
        return true;
      },
    }),
  );
  assert(entry.outcome === 'measured', `three distinct lines measure (got ${entry.outcome}: ${entry.failure_reason})`);
  assert(reloads.length === 2, `points two and three each get a fresh load (got ${reloads.length})`);
  assert(reloads.every((n, i) => n === i + 1), 'each reload lands after the previous click');
}

// -- selectDistinctLinePoints: three DISTINCT painted text lines --------------
{
  assert(typeof selectDistinctLinePoints === 'function', 'selectDistinctLinePoints is exported');
  const slots = {
    first_text_line: [{ point: 'first_text_line', x: 10, y: 20, line: { top: 14, bottom: 30 } }],
    page_centre: [
      { point: 'page_centre', x: 10, y: 22, line: { top: 14, bottom: 30 } },
      { point: 'page_centre', x: 10, y: 50, line: { top: 44, bottom: 60 } },
    ],
    last_text_line: [{ point: 'last_text_line', x: 10, y: 80, line: { top: 74, bottom: 90 } }],
  };
  const plan = await selectDistinctLinePoints(slots);
  assert(plan.length === 3, `three distinct bands keep three points (got ${plan.length})`);
  assert(
    plan[1] && plan[1].line.top === 44,
    'a centre slot sharing the first band falls back to its next distinct line',
  );
  const single = await selectDistinctLinePoints({
    first_text_line: [{ point: 'first_text_line', x: 10, y: 20, line: { top: 14, bottom: 30 } }],
    page_centre: [{ point: 'page_centre', x: 10, y: 22, line: { top: 14, bottom: 30 } }],
    last_text_line: [{ point: 'last_text_line', x: 10, y: 24, line: { top: 14, bottom: 30 } }],
  });
  assert(single.length === 1, `one painted line yields one point (got ${single.length})`);
  const vetoed = await selectDistinctLinePoints(
    {
      first_text_line: [{ point: 'first_text_line', x: 10, y: 20, line: { top: 14, bottom: 30 } }],
      page_centre: [{ point: 'page_centre', x: 10, y: 50, line: { top: 44, bottom: 60 } }],
      last_text_line: [{ point: 'last_text_line', x: 10, y: 80, line: { top: 74, bottom: 90 } }],
    },
    async (slot) => (slot === 'page_centre' ? null : undefined),
  );
  assert(vetoed.length === 2, `a hit-vetoed slot is skipped, not defaulted (got ${vetoed.length})`);
}

if (failed) process.exit(1);
console.log(`b4_c07_quiet_contract: ${checks} checks ok`);
