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
    window.__resourceLongTasks = { count: 0, sum: 0 };
    try {
      const obs = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          window.__resourceLongTasks.count += 1;
          window.__resourceLongTasks.sum += entry.duration;
        }
      });
      obs.observe({ type: 'longtask', buffered: true });
    } catch {
      /* longtask is not implemented in every engine */
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
  cdp.on('Network.loadingFinished', (event) => {
    const requestId = event.requestId;
    if (!requestId || seenRequests.has(requestId)) return;
    seenRequests.add(requestId);
    networkEvents.push({
      requestId,
      encodedDataLength: event.encodedDataLength || 0,
    });
  });
  await cdp.send('Performance.enable');
  await cdp.send('Network.enable');
  return { browserPid: launchedBrowserPid(context) };
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
    const est = (navigator.storage && navigator.storage.estimate)
      ? await navigator.storage.estimate()
      : { usage: 0, usageDetails: {} };
    const details = est.usageDetails || {};
    let localStorageBytes = 0;
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        const value = localStorage.getItem(key) || '';
        localStorageBytes += (String(key).length + String(value).length) * 2;
      }
    } catch {
      localStorageBytes = null;
    }
    const tasks = window.__resourceLongTasks || { count: 0, sum: 0 };
    return {
      usage: est.usage || 0,
      usageDetails: {
        indexedDB: details.indexedDB || 0,
        caches: details.caches || details.cacheStorage || 0,
        serviceWorkerRegistrations: details.serviceWorkerRegistrations || details.serviceWorker || 0,
      },
      localStorageBytes,
      longtaskCount: tasks.count || 0,
      longtaskSumMs: tasks.sum || 0,
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
  return networkEvents.slice();
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
  return { kind: 'keyboard.insertText', text, repetitions };
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
