/**
 * One smoke open of the WordCraft browser perf host — same shape as perf/runner/warm_cold_browser.mjs:
 * same chromium args, same /corpus.docx interception, same ready/edit contract. It answers one
 * question: does the host reach "document rendered", and does typing one character keep it rendered?
 *
 *   cd harness/ui/wordcraft-host && node smoke.mjs [--url http://127.0.0.1:5219/]
 *
 * Writes to /tmp/perf-run-logs/: two canvas PNGs (before/after typing), the console log, and a JSON
 * report with the host's own readiness samples.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(here, "../../..");
const UI = path.join(REPO, "harness/ui");
const OUT = process.env.SMOKE_OUT || "/tmp/perf-run-logs";
const CORPUS = process.env.CORPUS_DOCX || path.join(REPO, "fixture/complex.docx");
const READY_JS = "window.__WORDCRAFT_READY__ === true";
const EDIT_SELECTOR = "#wordcraft_canvas";

const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i += 1) {
  if (!argv[i].startsWith("--")) continue;
  const next = argv[i + 1];
  if (next === undefined || next.startsWith("--")) opt[argv[i].slice(2)] = true;
  else {
    opt[argv[i].slice(2)] = next;
    i += 1;
  }
}
const url = opt.url || "http://127.0.0.1:5219/";

fs.mkdirSync(OUT, { recursive: true });
const corpusBytes = fs.readFileSync(CORPUS);
const { chromium } = await import(pathToFileURL(path.join(UI, "node_modules/playwright/index.mjs")).href);

const report = {
  url,
  corpus: CORPUS,
  corpus_bytes: corpusBytes.byteLength,
  ready_js: READY_JS,
  edit_selector: EDIT_SELECTOR,
  console: [],
  page_errors: [],
};

function log(line) {
  report.console.push(`${new Date().toISOString()} ${line}`);
}

const browser = await chromium.launch({
  headless: true,
  args: ["--font-render-hinting=none", "--disable-lcd-text"],
});
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await context.route("**/*", async (route) => {
  const u = new URL(route.request().url());
  if (u.pathname === "/corpus.docx") {
    await route.fulfill({
      status: 200,
      contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      body: corpusBytes,
    });
    return;
  }
  await route.continue();
});

const page = await context.newPage();
page.on("console", (m) => log(`console.${m.type()}: ${m.text()}`));
page.on("pageerror", (e) => {
  report.page_errors.push(String(e));
  log(`pageerror: ${e}`);
});

const t0 = Date.now();
await page.goto(url, { waitUntil: "domcontentloaded", timeout: 120_000 });
report.navigation_ms = Date.now() - t0;

try {
  await page.waitForFunction(
    (expr) => {
      try {
        return Boolean(eval(expr));
      } catch {
        return false;
      }
    },
    READY_JS,
    { timeout: 120_000 },
  );
  report.ready = true;
} catch (e) {
  report.ready = false;
  report.ready_error = String(e).slice(0, 600);
}
report.first_usable_ms = Date.now() - t0;
report.host = await page.evaluate(() => window.__WORDCRAFT_HOST__ || null);

if (report.ready) {
  const canvas = page.locator(EDIT_SELECTOR).first();
  report.canvas_box = await canvas.boundingBox();
  const before = await canvas.screenshot();
  fs.writeFileSync(path.join(OUT, "wordcraft-smoke-before-typing.png"), before);

  const editT0 = Date.now();
  await canvas.click({ timeout: 30_000 });
  await page.keyboard.type("x", { delay: 12 });
  report.edit_ms = Date.now() - editT0;
  report.paint_ms = await page.evaluate(async () => {
    const t = performance.now();
    await new Promise((r) => requestAnimationFrame(() => r(null)));
    await new Promise((r) => requestAnimationFrame(() => r(null)));
    return performance.now() - t;
  });
  const after = await canvas.screenshot();
  fs.writeFileSync(path.join(OUT, "wordcraft-smoke-after-typing.png"), after);
  report.canvas_changed_after_typing = !before.equals(after);
  report.canvas_png_bytes = { before: before.length, after: after.length };

  await page.waitForTimeout(400);
  report.still_rendered = await page.evaluate(
    (expr) => Boolean(eval(expr)) && document.querySelector("#wc-ready")?.dataset.state === "rendered",
    READY_JS,
  );
  report.focused_element = await page.evaluate(() => {
    const el = document.activeElement;
    return el ? `${el.tagName.toLowerCase()}#${el.id}` : null;
  });
  report.host_after = await page.evaluate(() => window.__WORDCRAFT_HOST__ || null);
  await page.screenshot({ path: path.join(OUT, "wordcraft-smoke-page.png") });
}

fs.writeFileSync(path.join(OUT, "wordcraft-smoke-console.log"), report.console.join("\n") + "\n");
fs.writeFileSync(path.join(OUT, "wordcraft-smoke.json"), `${JSON.stringify(report, null, 2)}\n`);
await context.close();
await browser.close();

console.log(
  JSON.stringify({
    ready: report.ready,
    first_usable_ms: report.first_usable_ms,
    readback: report.host?.readback,
    state: report.host?.state,
    errors: report.host?.errors,
    edit_ms: report.edit_ms,
    paint_ms: report.paint_ms,
    canvas_changed_after_typing: report.canvas_changed_after_typing,
    still_rendered: report.still_rendered,
    focused_element: report.focused_element,
    out: OUT,
  }),
);
