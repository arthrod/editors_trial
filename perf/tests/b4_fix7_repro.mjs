/**
 * B4 fix round 7: frame-interval witness setup and harness_error vs page_lost; extra suite phases.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { quietWindow, noFrameRecord } from './witness_records.mjs';

const repo = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const moduleUrl = pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href;
const { runCriteriaSuite } = await import(moduleUrl);
const INK_PNG = readFileSync(fileURLToPath(new URL('./fixtures/ink/plate_clip.png', import.meta.url)));

const QUIESCENT = {
  quiescent: true,
  quiet_at: 300,
  quiet_window_ms: 400,
  quiescence_confirmed_ms: 600,
  deferred_work_seen: true,
  observed_for_ms: 600,
  activity_count: 1,
  long_tasks: [],
  max_raf_gap_ms: 10,
  activities: [{ kind: 'mutation', t: 200 }],
  quiescence_event: 'mutation',
};

function makeHost(deathAt) {
  let body = 'ORIGINAL';
  let dead = false;
  let undos = 0;
  let reloaded = false;
  let resolveCalls = 0;
  let typedReads = 0;
  let editableReads = 0;
  let postRefreshResolve = false;
  let stopCalls = 0;
  let offCalls = 0;
  const clicks = [];
  const die = () => {
    dead = true;
  };
  const page = {
    isClosed: () => dead,
    mouse: {
      click: async (x, y) => {
        clicks.push([x, y]);
      },
    },
    keyboard: {
      type: async () => {
        body = 'ORIGxINAL';
      },
      press: async (k) => {
        if (!k.endsWith('+Z')) {
          if (k.endsWith('+V')) body += 'BLOCK';
          return;
        }
        undos += 1;
        if (
          deathAt === 'c09_overshoot' ||
          deathAt === 'c08_refresh' ||
          deathAt === 'c08_refresh_read'
        ) {
          body = undos === 1 ? 'OLDER' : 'ANCIENT';
        } else body = 'ORIGINAL';
      },
    },
    reload: async () => {
      body = 'ORIGINAL';
      reloaded = true;
    },
    screenshot: async () => INK_PNG,
    evaluate: async (fn, arg) => {
      if (dead) throw new Error('Execution context was destroyed');
      const name = fn.name;
      if (deathAt === 'alive_boundary' && name === 'RESOLVE_CLICK_CLIP') {
        throw new TypeError('synthetic live-page harness bug');
      }
      if (deathAt === 'alive_c04' && name === 'OBSERVE_QUIESCENCE') {
        throw new TypeError('synthetic live-page criterion bug');
      }
      const src = fn.toString();
      if (deathAt === 'input_tap' && src.includes('__perfCriteria')) {
        die();
        throw new Error('Execution context was destroyed');
      }
      if (deathAt === 'ready_ms' && src.includes('performance.now') && !src.includes('timeOrigin')) {
        die();
        throw new Error('Execution context was destroyed');
      }
      if (name === 'READ_EDITABLE_STATE') {
        editableReads += 1;
        if (deathAt === 'initial_read_state' && editableReads === 1) {
          die();
          throw new Error('Execution context was destroyed');
        }
        if (deathAt === 'c08_refresh_read' && postRefreshResolve) {
          die();
          throw new Error('Execution context was destroyed');
        }
        postRefreshResolve = false;
        if (deathAt === 'c09_mid' && body === 'ORIGxINAL' && !reloaded) {
          typedReads += 1;
          if (typedReads >= 1) {
            die();
            throw new Error('Execution context was destroyed');
          }
        }
        return {
          text: body,
          text_length: reloaded ? 20 : body.length,
          selection_offset: 4,
          is_content_editable: true,
          anchor_inside: true,
          active_inside: true,
          caret: { top: 1, bottom: 2, height: 1 },
        };
      }
      if (name === 'RESOLVE_CLICK_CLIP') {
        resolveCalls += 1;
        // Resolve 1 is the post-C04 ink scan. C09 reuses those points; the
        // C08 refresh resolve is the second; the next editable read is the
        // one the c08_refresh_read death is about.
        if (deathAt === 'c08_refresh_read' && resolveCalls === 2) {
          postRefreshResolve = true;
        }
        if (deathAt === 'after_c04' && resolveCalls === 1) {
          die();
          throw new Error('Execution context was destroyed');
        }
        if (deathAt === 'c08_refresh' && resolveCalls === 2) {
          die();
          throw new Error('Execution context was destroyed');
        }
        return {
          clip: { left: 0, top: 0, right: 640, bottom: 900 },
          box: { x: 0, y: 0, width: 640, height: 900 },
          viewport: { width: 1280, height: 900 },
        };
      }
      if (name === 'CHECK_CLICK_HITS') {
        return { points: ((arg && arg.points) || []).map(() => ({ hit_inside_editable: true })) };
      }
      if (name === 'DOCUMENT_UNTOUCHED') {
        return { events: [], anchor_inside: false, active_inside: false, tapped: 0 };
      }
      if (name === 'OBSERVE_QUIESCENCE') {
        if (deathAt === 'c04_mid') {
          die();
          throw new Error('Execution context was destroyed');
        }
        return QUIESCENT;
      }
      if (src.includes('el.contains(target)')) {
        if (
          (deathAt === 'c07_mid' && clicks.length >= 1) ||
          (deathAt === 'partial_c07' && clicks.length >= 2)
        ) {
          die();
          throw new Error('Execution context was destroyed');
        }
        return { inside: true, reason: null };
      }
      if (src.includes('writeText')) {
        if (deathAt === 'c08_mid') {
          die();
          throw new Error('Execution context was destroyed');
        }
        return undefined;
      }
      if (src.includes('execCommand')) {
        body += 'BLOCK';
        return { start: 100, ok: true, error: null };
      }
      if (arg && (arg.kind || arg.kinds)) return { t: 100, target: null };
      if (arg?.count) {
        if (deathAt === 'frame_interval') {
          die();
          throw new Error('Execution context was destroyed');
        }
        return [16.667, 16.667];
      }
      if (typeof arg === 'number') return 40.0;
      if (src.includes('performance.now')) return 176.6;
      return undefined;
    },
  };
  const cdp = {
    on() {},
    off() {
      offCalls += 1;
      if (deathAt === 'after_c08') die();
    },
    async send(method) {
      if (method === 'Page.stopScreencast') {
        stopCalls += 1;
        if (deathAt === 'stop_send') {
          die();
          throw new Error('Target closed');
        }
      }
    },
  };
  const witness = {
    frameIntervalMs: 16.667,
    paintAfter: async (t, o = {}) => {
      if (o.arm) await o.arm();
      const record = noFrameRecord();
      record.frames_total = 1;
      record.quiet_window = quietWindow();
      return record;
    },
  };
  return {
    page,
    cdp,
    witness,
    state: () => ({ dead, undos, reloaded, clicks: clicks.length, stopCalls, offCalls }),
  };
}

async function scenario(deathAt) {
  const host = makeHost(deathAt);
  let thrown = null;
  let payload = null;
  try {
    payload = await runCriteriaSuite({
      page: host.page,
      frameTimeoutMs: 1,
      cdp: host.cdp,
      editSelector: '#doc',
      criteria: ['C04', 'C07', 'C09', 'C08'],
      expectedBodyText: 'ORIGINAL',
      correctnessAdapter: 'dom_innerText',
      witness: host.witness,
    });
  } catch (error) {
    thrown = String(error);
  }
  const summarizeEntry = (entry) =>
    entry && {
      outcome: entry.outcome,
      reason: entry.failure_reason,
      samples: entry.samples_ms ?? [],
      observations: (entry.observations || []).length,
      fixture_reset: entry.fixture_reset ?? null,
    };
  return {
    deathAt,
    thrown,
    returned: payload !== null,
    state: host.state(),
    C04: summarizeEntry(payload?.criteria?.C04),
    C07: summarizeEntry(payload?.criteria?.C07),
    C09: summarizeEntry(payload?.criteria?.C09),
    C08: summarizeEntry(payload?.criteria?.C08),
  };
}

const order = [
  'frame_interval',
  'alive_boundary',
  'alive_c04',
  'partial_c07',
  'stop_send',
  'after_c08',
  'input_tap',
  'ready_ms',
  'initial_read_state',
  'c08_refresh_read',
];
const results = {};
for (const deathAt of order) results[deathAt] = await scenario(deathAt);

console.log(JSON.stringify(results, null, 0));
