/**
 * B4 fix round 8: crash event without isClosed → page_lost via target state.
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

function makeCrashHost() {
  let crashed = false;
  const listeners = { crash: [] };
  const page = {
    isClosed: () => false,
    on(event, handler) {
      if (event === 'crash' || event === 'close') listeners.crash.push(handler);
    },
    mouse: { click: async () => {} },
    keyboard: {
      type: async () => {},
      press: async () => {},
    },
    reload: async () => {},
    evaluate: async (fn) => {
      const name = fn.name;
      if (name === 'OBSERVE_QUIESCENCE') return QUIESCENT;
      if (name === 'RESOLVE_CLICK_CLIP') {
        for (const handler of listeners.crash) handler();
        crashed = true;
        throw new Error('renderer process unavailable [unusual wrapper message]');
      }
      if (fn.toString().includes('performance.now')) return 176.6;
      if (fn.toString() === '() => true') return true;
      return undefined;
    },
  };
  const cdp = { on() {}, off() {}, async send() {} };
  return {
    page,
    cdp,
    state: () => ({ crashed, dead: false }),
  };
}

async function crashScenario() {
  const host = makeCrashHost();
  const payload = await runCriteriaSuite({
    page: host.page,
    cdp: host.cdp,
    editSelector: '#doc',
    criteria: ['C04', 'C07'],
    quiescenceMs: 20,
    quiescenceTimeoutMs: 200,
  });
  return {
    state: host.state(),
    C04: {
      outcome: payload.criteria.C04.outcome,
      reason: payload.criteria.C04.failure_reason,
    },
    C07: {
      outcome: payload.criteria.C07.outcome,
      reason: payload.criteria.C07.failure_reason,
    },
  };
}

const results = { crash_alive: await crashScenario() };
console.log(JSON.stringify(results, null, 0));
