/**
 * One Playwright launch for the browser resource lane.
 *
 * The Python sampler owns the clock. This process only drives the page and
 * answers newline JSON requests on stdin:
 *   {"id", "method", "params"} -> {"id", "result"} or {"id", "error"}
 *
 * Methods: launch, load, evaluate, cdp, events, edit, save, close.
 * The browser pid is the process Playwright spawned for this context.
 */
import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(here, '../../harness/ui');

let context = null;
let page = null;
let cdp = null;
let opts = {};
const networkEvents = [];
const seenRequests = new Set();
const requestState = new Map();
const pendingEnables = new Set();
let workerObservation = 'ok';
let workerObservationReason = null;
let cdpId = 1;

const WORKER_TYPES = new Set(['service_worker', 'worker', 'shared_worker']);
const WORKER_FILTER = [
  { type: 'service_worker' },
  { type: 'worker' },
  { type: 'shared_worker' },
];

function reply(id, result) {
  process.stdout.write(`${JSON.stringify({ id, result })}\n`);
}

function fail(id, error) {
  const text = error && error.stack ? String(error.stack) : String(error);
  process.stdout.write(`${JSON.stringify({ id, error: text.slice(0, 1200) })}\n`);
}

async function loadPlaywright() {
  const spec = path.join(uiRoot, 'node_modules/playwright/index.mjs');
  return import(pathToFileURL(spec).href);
}

function launchedBrowserPid(browserContext) {
  const viaPublic = typeof browserContext.browser === 'function' ? browserContext.browser() : null;
  const publicProc = viaPublic && typeof viaPublic.process === 'function' ? viaPublic.process() : null;
  if (publicProc && Number.isInteger(publicProc.pid) && publicProc.pid > 0) return publicProc.pid;
  // Playwright 1.64 hides ChildProcess on the client Browser. The in-process
  // connection still points at the server browser this call launched.
  const connection = browserContext._connection;
  const impl = connection && typeof connection.toImpl === 'function' ? connection.toImpl(browserContext) : null;
  const serverBrowser = impl && impl._browser;
  const proc = serverBrowser && serverBrowser.options && serverBrowser.options.browserProcess
    ? serverBrowser.options.browserProcess.process
    : null;
  if (proc && Number.isInteger(proc.pid) && proc.pid > 0) return proc.pid;
  return null;
}

async function onLaunch(params) {
  opts = params;
  const corpusBytes = fs.readFileSync(params.corpusPath);
  const { chromium } = await loadPlaywright();
  context = await chromium.launchPersistentContext(params.profileDir, {
    headless: true,
    viewport: { width: 1280, height: 900 },
    args: ['--font-render-hinting=none', '--disable-lcd-text'],
  });
  await context.addInitScript(() => {
    window.__resourceLongTasks = { count: 0, sum: 0, available: true };
    try {
      if (typeof PerformanceObserver !== 'function') {
        window.__resourceLongTasks = {
          available: false,
          reason: 'longtask_observer_failed',
          count: null,
          sum: null,
        };
      } else {
        const obs = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            window.__resourceLongTasks.count += 1;
            window.__resourceLongTasks.sum += entry.duration;
          }
        });
        obs.observe({ type: 'longtask', buffered: true });
      }
    } catch {
      window.__resourceLongTasks = {
        available: false,
        reason: 'longtask_observer_failed',
        count: null,
        sum: null,
      };
    }
  });
  const corpusRoute = params.corpusRoute || '/corpus.docx';
  await context.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === corpusRoute) {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: corpusBytes,
      });
      return;
    }
    await route.continue();
  });
  page = context.pages()[0] || await context.newPage();
  cdp = await context.newCDPSession(page);
  cdp.on('Network.responseReceived', (event) => {
    noteCdpEvent('Network.responseReceived', event, 'page');
  });
  cdp.on('Network.dataReceived', (event) => {
    noteCdpEvent('Network.dataReceived', event, 'page');
  });
  cdp.on('Network.loadingFinished', (event) => {
    noteCdpEvent('Network.loadingFinished', event, 'page');
  });
  await cdp.send('Performance.enable');
  await cdp.send('Network.enable');
  await watchWorkers(context, cdp);
  return { browserPid: launchedBrowserPid(context) };
}

function rememberRequest(requestId, patch) {
  const prior = requestState.get(requestId) || {};
  requestState.set(requestId, { ...prior, ...patch });
}

function noteCdpEvent(method, params, targetType) {
  if (!params) return;
  const requestId = params.requestId;
  if (!requestId) return;
  if (method === 'Network.responseReceived') {
    const response = params.response || {};
    rememberRequest(requestId, {
      fromDiskCache: Boolean(response.fromDiskCache),
      fromServiceWorker: Boolean(response.fromServiceWorker),
      targetType,
    });
    return;
  }
  if (method === 'Network.dataReceived') {
    const prior = requestState.get(requestId) || {};
    const added = Number(params.dataLength);
    const body = Number.isFinite(added) ? added : 0;
    rememberRequest(requestId, {
      sawDecoded: true,
      decodedBodyBytes: Number(prior.decodedBodyBytes || 0) + body,
      targetType: prior.targetType || targetType,
    });
    return;
  }
  if (method !== 'Network.loadingFinished' || seenRequests.has(requestId)) return;
  seenRequests.add(requestId);
  const prior = requestState.get(requestId) || {};
  const encoded = Number(params.encodedDataLength);
  const row = {
    requestId,
    encodedDataLength: Number.isFinite(encoded) ? encoded : 0,
    fromDiskCache: Boolean(prior.fromDiskCache),
    fromServiceWorker: Boolean(prior.fromServiceWorker),
    targetType: targetType || prior.targetType || 'page',
  };
  if (prior.sawDecoded) row.decodedBodyBytes = prior.decodedBodyBytes;
  networkEvents.push(row);
}

function markWorkersUnobserved(reason) {
  workerObservation = 'failed';
  workerObservationReason = reason || 'worker_targets_unobserved';
}

async function sendToTarget(session, sessionId, method, params) {
  const id = cdpId;
  cdpId += 1;
  pendingEnables.add(id);
  await session.send('Target.sendMessageToTarget', {
    sessionId,
    message: JSON.stringify({ id, method, params: params || {} }),
  });
}

function consumeTargetMessage(payload) {
  let parsed = null;
  try {
    parsed = JSON.parse(payload && payload.message ? payload.message : '');
  } catch {
    parsed = null;
  }
  if (!parsed) return;
  if (parsed.id != null) pendingEnables.delete(parsed.id);
  if (!parsed.method) return;
  noteCdpEvent(parsed.method, parsed.params || {}, 'worker');
}

async function attachWorkers(session) {
  session.on('Target.attachedToTarget', (event) => {
    const info = event.targetInfo || {};
    if (!WORKER_TYPES.has(info.type)) return;
    const sessionId = event.sessionId;
    sendToTarget(session, sessionId, 'Network.enable')
      .then(() => {
        if (event.waitingForDebugger) {
          return sendToTarget(session, sessionId, 'Runtime.runIfWaitingForDebugger');
        }
        return null;
      })
      .catch(() => {
        markWorkersUnobserved('worker_targets_unobserved');
      });
  });
  session.on('Target.receivedMessageFromTarget', (event) => {
    consumeTargetMessage(event);
  });
  await session.send('Target.setAutoAttach', {
    autoAttach: true,
    waitForDebuggerOnStart: false,
    flatten: false,
    filter: WORKER_FILTER,
  });
}

async function watchWorkers(browserContext, pageSession) {
  // Non-flatten keeps worker Network events on this session. Playwright 1.64
  // drops flattened child events unless it already owns that child session.
  try {
    await attachWorkers(pageSession);
  } catch {
    /* a page session that rejects auto-attach still leaves the browser session */
  }
  try {
    const browser = typeof browserContext.browser === 'function' ? browserContext.browser() : null;
    if (!browser || typeof browser.newBrowserCDPSession !== 'function') {
      markWorkersUnobserved('worker_targets_unobserved');
      return;
    }
    const browserSession = await browser.newBrowserCDPSession();
    await browserSession.send('Target.setDiscoverTargets', { discover: true });
    await attachWorkers(browserSession);
  } catch {
    markWorkersUnobserved('worker_targets_unobserved');
  }
}

async function onLoad() {
  await page.goto(opts.url, { waitUntil: 'domcontentloaded', timeout: 120000 });
  if (opts.readyJs) {
    await page.waitForFunction(
      (expr) => {
        try {
          return Boolean(eval(expr));
        } catch {
          return false;
        }
      },
      opts.readyJs,
      { timeout: 120000 },
    );
  } else if (opts.readySelector) {
    await page.waitForSelector(opts.readySelector, { timeout: 120000, state: 'visible' });
  }
  const waitMs = Number(opts.waitAfterReadyMs || 0);
  if (waitMs > 0) await page.waitForTimeout(waitMs);
  return { ready: true };
}

async function pageSnapshot() {
  return page.evaluate(async () => {
    let est = null;
    if (navigator.storage && navigator.storage.estimate) {
      try {
        est = await navigator.storage.estimate();
      } catch {
        est = null;
      }
    }
    const details = est && est.usageDetails ? est.usageDetails : null;
    const member = (source, name, alias) => {
      if (!source) return null;
      if (Object.prototype.hasOwnProperty.call(source, name)) return source[name];
      if (alias && Object.prototype.hasOwnProperty.call(source, alias)) return source[alias];
      return null;
    };
    let localStorageBytes = null;
    try {
      localStorageBytes = 0;
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        const value = localStorage.getItem(key) || '';
        localStorageBytes += (String(key).length + String(value).length) * 2;
      }
    } catch {
      localStorageBytes = null;
    }
    const tasks = window.__resourceLongTasks;
    const longtaskKnown = Boolean(tasks && tasks.available !== false && tasks.count != null && tasks.sum != null);
    return {
      usage: est && est.usage != null ? est.usage : null,
      usageDetails: details ? {
        indexedDB: member(details, 'indexedDB'),
        caches: member(details, 'caches', 'cacheStorage'),
        serviceWorkerRegistrations: member(details, 'serviceWorkerRegistrations', 'serviceWorker'),
      } : null,
      localStorageBytes,
      longtaskCount: longtaskKnown ? tasks.count : null,
      longtaskSumMs: longtaskKnown ? tasks.sum : null,
      longtaskReason: longtaskKnown ? null : ((tasks && tasks.reason) || 'longtask_unavailable'),
    };
  });
}

async function onEvaluate(params) {
  const expression = params.expression || '';
  if (expression.includes('navigator.storage') && expression.includes('longtask')) {
    return pageSnapshot();
  }
  return page.evaluate(expression);
}

async function onCdp(params) {
  return cdp.send(params.method, params.params || {});
}

async function onEvents(params) {
  if (params.method !== 'Network.loadingFinished') return [];
  const pending = pendingEnables.size > 0;
  const failed = workerObservation !== 'ok' || pending;
  return {
    events: networkEvents.slice(),
    worker_observation: failed ? 'failed' : 'ok',
    worker_observation_reason: failed
      ? (workerObservationReason || 'worker_targets_unobserved')
      : null,
  };
}

async function readEditorText(selector) {
  if (!selector) return '';
  return page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return '';
    const tag = String(el.tagName || '').toUpperCase();
    if ((tag === 'INPUT' || tag === 'TEXTAREA') && 'value' in el) return String(el.value || '');
    return String(el.innerText || el.textContent || '');
  }, selector);
}

async function onEdit(params) {
  const repetitions = Math.max(0, Number(params.repetitions || 0));
  const text = params.text || '';
  if (params.selector) {
    await page.locator(params.selector).first().click({ timeout: 30000 });
  }
  for (let i = 0; i < repetitions; i++) {
    await page.keyboard.insertText(text);
  }
  let editorText = '';
  let applied = false;
  if (!params.selector) {
    editorText = '';
    applied = false;
  } else if (params.checkJs) {
    const hostResult = await page.evaluate((source) => {
      try {
        return eval(source);
      } catch (err) {
        return { applied: false, error: String(err) };
      }
    }, params.checkJs);
    if (hostResult && typeof hostResult === 'object') {
      applied = Boolean(hostResult.applied);
      if (hostResult.editorText != null) editorText = String(hostResult.editorText);
      else editorText = await readEditorText(params.selector);
    } else {
      applied = Boolean(hostResult);
      editorText = await readEditorText(params.selector);
    }
  } else {
    editorText = await readEditorText(params.selector);
    const expected = text.repeat(repetitions);
    applied = expected.length > 0 && editorText.includes(expected);
  }
  return { applied, editorText, kind: 'keyboard.insertText', text, repetitions };
}

async function onSave(params) {
  if (!params.selector) return { saved: false, reason: 'host_has_no_save' };
  await page.locator(params.selector).first().click({ timeout: 30000 });
  return { saved: true };
}

async function onClose() {
  try {
    if (context) await context.close();
  } catch {
    /* the browser may already have exited */
  }
  context = null;
  page = null;
  cdp = null;
  return { closed: true };
}

const handlers = {
  launch: onLaunch,
  load: onLoad,
  evaluate: onEvaluate,
  cdp: onCdp,
  events: onEvents,
  edit: onEdit,
  save: onSave,
  close: onClose,
};

const rl = readline.createInterface({ input: process.stdin, terminal: false });
rl.on('line', (line) => {
  const trimmed = line.trim();
  if (!trimmed) return;
  let message;
  try {
    message = JSON.parse(trimmed);
  } catch (error) {
    fail(null, error);
    return;
  }
  const handler = handlers[message.method];
  if (!handler) {
    fail(message.id, `unknown method ${message.method}`);
    return;
  }
  Promise.resolve()
    .then(() => handler(message.params || {}))
    .then((result) => reply(message.id, result == null ? {} : result))
    .catch((error) => fail(message.id, error));
});
