/**
 * B4 fix round 6: F2 suite isolation at phase boundaries; invoked from test_b4_fix6.py.
 */
import { pathToFileURL } from 'node:url';

const repo = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const moduleUrl = pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href;
const { runCriteriaSuite } = await import(moduleUrl);

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
  const clicks = [];
  const listeners = { crash: [], close: [] };
  const die = () => {
    dead = true;
    for (const handler of listeners.crash) handler();
    for (const handler of listeners.close) handler();
  };
  const page = {
    isClosed: () => dead,
    on(event, handler) {
      if (event === 'crash') listeners.crash.push(handler);
      if (event === 'close') listeners.close.push(handler);
    },
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
        if (deathAt === 'c09_overshoot' || deathAt === 'c08_refresh') {
          body = undos === 1 ? 'OLDER' : 'ANCIENT';
        } else body = 'ORIGINAL';
      },
    },
    reload: async () => {
      body = 'ORIGINAL';
      reloaded = true;
    },
    evaluate: async (fn, arg) => {
      if (dead) throw new Error('Execution context was destroyed');
      const name = fn.name;
      const src = fn.toString();
      if (name === 'READ_EDITABLE_STATE') {
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
      if (name === 'RESOLVE_CLICK_POINTS') {
        resolveCalls += 1;
        if (deathAt === 'after_c04' && resolveCalls === 1) {
          die();
          throw new Error('Execution context was destroyed');
        }
        if (deathAt === 'c08_refresh' && resolveCalls === 2) {
          die();
          throw new Error('Execution context was destroyed');
        }
        return {
          points: [
            { point: 'last_text_line', x: 1, y: 1, line: { top: 1, bottom: 2 } },
            { point: 'mid_text_line', x: 2, y: 2, line: { top: 1, bottom: 2 } },
            { point: 'first_text_line', x: 3, y: 3, line: { top: 1, bottom: 2 } },
          ],
          source: 'text_lines',
        };
      }
      if (name === 'OBSERVE_QUIESCENCE') {
        if (deathAt === 'c04_mid') {
          die();
          throw new Error('Execution context was destroyed');
        }
        return QUIESCENT;
      }
      if (src.includes('el.contains(target)')) {
        if (deathAt === 'c07_mid' && clicks.length >= 1) {
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
      if (arg?.count) return [16.667, 16.667];
      if (typeof arg === 'number') return 40.0;
      if (src.includes('performance.now')) return 176.6;
      return undefined;
    },
  };
  const cdp = { on() {}, off() {}, async send() {} };
  return { page, cdp, state: () => ({ dead, undos, reloaded, clicks: clicks.length }) };
}

async function scenario(deathAt) {
  const host = makeHost(deathAt);
  let thrown = null;
  let payload = null;
  try {
    payload = await runCriteriaSuite({
      page: host.page,
      cdp: host.cdp,
      editSelector: '#doc',
      criteria: ['C04', 'C07', 'C09', 'C08'],
      expectedBodyText: 'ORIGINAL',
      correctnessAdapter: 'dom_innerText',
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

const order = ['c04_mid', 'after_c04', 'c07_mid', 'c09_mid', 'c08_refresh', 'c08_mid'];
const results = {};
for (const deathAt of order) results[deathAt] = await scenario(deathAt);

console.log(JSON.stringify(results, null, 0));
