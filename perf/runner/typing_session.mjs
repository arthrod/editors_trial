// B9 witness bridge. One Chromium launch; Python connects to this same browser.
// JSON lines over stdin/stdout; only this file owns trusted sampled keystrokes.
// The shared edit adapter owns edit-mode entry, caret placement, and the
// non-DOM correctness reads (model text, modified flag, trusted key count).
import readline from 'node:readline';
import {loadPlaywright, witnessFrame, clockSkew, frameInterval, stopRecorder, getRecorder, CARET_MASK_CSS} from './witness.mjs';
import {startChromeTrace, stopChromeTrace} from './chrome_trace.mjs';
import {
  editSurface,
  prepareEditSurface,
  placeCaret,
  readModifiedFlag,
  usableExpression,
  READ_MODEL_DOCUMENT_TEXT,
  READ_DOM_TEXT_WITH_MARKERS,
  armTrustedKeyCounter,
  trustedKeyCount,
} from './edit_surface.mjs';
import {loadTimeoutMs} from './load_timeout.mjs';
// Lax layer (owner 2026-11-11): the editable can take minutes to mount on the
// big documents; Playwright's 30 s defaults refused loads that completed.
const loadTimeout = loadTimeoutMs();
const [port, profile, sessionKind = "latency"] = process.argv.slice(2);
const {chromium} = await loadPlaywright();
const context = await chromium.launchPersistentContext(profile, {
  headless:true, viewport:{width:1280,height:900},
  args:[`--remote-debugging-port=${port}`, '--font-render-hinting=none', '--disable-lcd-text'],
});
const traceBrowser = typeof context.browser === 'function' ? context.browser() : null;
process.on('SIGTERM', async () => { await context.close(); process.exit(0); });
const page = context.pages()[0] || await context.newPage();
const traceHandle = traceBrowser ? await startChromeTrace(traceBrowser, page, 'TYPING') : null;
page.on('console', message => console.error(`[browser ${message.type()}] ${message.text()}`));
page.on('pageerror', error => console.error(`[browser uncaught] ${error}`));
const cdp = await context.newCDPSession(page);
let clock, interval;
console.log(JSON.stringify({ready:true}));
const lines = readline.createInterface({input:process.stdin});
for await (const line of lines) {
  try {
    const command = JSON.parse(line);
    let result;
    if (command.op === 'load') {
      const baseline = (await page.screenshot()).toString('base64');
      const recorder = getRecorder(cdp);
      await cdp.send('Page.startScreencast', {format:'png', everyNthFrame:1, maxWidth:1280, maxHeight:900});
      recorder.started = true;
      const usableJs = command.usable_js || usableExpression(command.editor_id, command.selector);
      const usableSelector = command.usable_selector || null;
      await page.addInitScript(({usableJs, usableSelector}) => {
        window.__b9usable = null;
        const ready = () => {
          if (usableSelector) {
            const el = document.querySelector(usableSelector);
            return !!(el && el.getBoundingClientRect().height > 0);
          }
          try {
            return Boolean(eval(usableJs));
          } catch {
            return false;
          }
        };
        const probe = () => {
          if (window.__b9usable !== null) return;
          try {
            if (ready()) window.__b9usable = performance.now();
          } catch { /* the page is not far enough along to answer */ }
        };
        new MutationObserver(probe).observe(document, {subtree:true, childList:true, attributes:true});
        probe();
        // Wasm hosts set readiness on window without a matching DOM mutation.
        const tick = () => {
          probe();
          if (window.__b9usable === null) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }, {usableJs, usableSelector});
      await page.goto(command.url, {waitUntil:'domcontentloaded', timeout:loadTimeout});
      if (command.ready_js) await page.waitForFunction(command.ready_js, undefined, {timeout:loadTimeout});
      else if (command.ready_selector) await page.locator(command.ready_selector).first().waitFor({timeout:loadTimeout});
      // A lazy editable (folio's hidden ProseMirror) mounts on the first
      // document click; it cannot exist before, so `selector` alone would
      // never appear. Editors whose editable already exists get no click
      // inside the load measurement.
      if (command.load_click_selector) await page.locator(command.load_click_selector).first().click();
      const loadWaitSel = command.load_wait_selector || command.wait_selector
        || command.ready_selector || command.selector;
      await page.locator(loadWaitSel).first().waitFor({timeout:loadTimeout});
      const usable = await page.evaluate(() => window.__b9usable);
      if (usable === null) {
        result = {usable_ms:null, witness:null, frame_interval_ms:null, load_timeout_ms:loadTimeout, refusal:'no_correctness_adapter'};
      } else {
      interval = await frameInterval(page, {frames: 30, timeoutMs: 3000});
      if (typeof interval?.median_ms !== 'number' || !Number.isFinite(interval.median_ms)) {
        result = {usable_ms:usable, witness:null, frame_interval_ms:null, load_timeout_ms:loadTimeout,
          refusal:'frame_interval_unavailable'};
      } else {
      clock = await clockSkew(page, cdp);
      const witness = await witnessFrame(page, cdp, {baseline, afterPageMs:usable,
        region:{selector:command.present_selector || command.selector}, clockCheck:clock, settleMs:0});
      result = {usable_ms:usable, witness, frame_interval_ms:interval.median_ms, load_timeout_ms:loadTimeout};
      }
      }
    } else if (command.op === 'key') {
      if (sessionKind !== 'latency') throw Error('key witnesses forbidden in throughput sessions');
      if (typeof interval?.median_ms !== 'number' || !Number.isFinite(interval.median_ms)) {
        result = {witness:null, frame_interval_ms:null, outcome:'refused', refusal:'frame_interval_unavailable'};
      } else {
      // stopRecorder discarded the previous operation's frames. Calibrate on
      // this key's recorder before arming the measured action.
      clock = await clockSkew(page, cdp, {frameIntervalMs:interval.median_ms, settleMs:0, samples:9, sampleGapMs:5, changeWaitMs:150});
      await page.evaluate(() => {
        window.__b9key = null;
        document.addEventListener('keydown', e => { window.__b9key = e.timeStamp; }, {once:true, capture:true});
      });
      const witness = await witnessFrame(page, cdp, {
        region:{selector:command.selector}, clockCheck:clock, settleMs:0,
        arm: async () => {
          if (command.char === '\n') await page.keyboard.press('Enter');
          else await page.keyboard.type(command.char);
          return await page.evaluate(() => window.__b9key);
        },
      });
      result = {witness, frame_interval_ms:interval.median_ms};
      if (witness.after_page_ms === null) result = {...result, outcome:'no_frame', refusal:'no_keydown'};
      }
    } else if (command.op === 'enter_edit_mode') {
      const prepared = await prepareEditSurface(page, command.editor_id || '',
        {textLineTimeoutMs: command.text_line_timeout_ms ?? null});
      const surface = editSurface(command.editor_id || '');
      result = {...prepared, surface: surface.kind};
    } else if (command.op === 'place_caret') {
      const placed = await placeCaret(page, command.editor_id || '', command.selector,
        {focusTimeoutMs: command.focus_timeout_ms ?? 5000,
         emptyDocument: Boolean(command.empty_document)});
      const surface = editSurface(command.editor_id || '');
      result = {...placed, surface: surface.kind};
    } else if (command.op === 'read_document') {
      const surface = editSurface(command.editor_id || '');
      if (surface.kind === 'model') {
        const payload = await page.evaluate(READ_MODEL_DOCUMENT_TEXT, surface.model);
        result = payload
          ? {text: payload.text,
             absorbed_markers: (payload.absorbed_items || []).map((index) => ({index, marker: null}))}
          : {text: null, absorbed_markers: []};
      } else if (surface.kind === 'dom') {
        result = await page.evaluate(READ_DOM_TEXT_WITH_MARKERS, command.selector);
      } else {
        result = {text: null, absorbed_markers: []};
      }
    } else if (command.op === 'modified_flag') {
      result = await readModifiedFlag(page, command.editor_id || '');
    } else if (command.op === 'arm_trusted_keys') {
      await armTrustedKeyCounter(page);
      result = {armed: true};
    } else if (command.op === 'trusted_key_count') {
      result = {keys: await trustedKeyCount(page)};
    } else if (command.op === 'close') {
      await stopRecorder(cdp);
      await stopChromeTrace(traceBrowser, traceHandle);
      console.log(JSON.stringify({result: {closed: true}}));
      await context.close();
      break;
    } else throw Error('unknown operation');
    // B1 injects a fresh universal-selector mask each time. Hundreds of
    // duplicate sheets slow later, unwitnessed edits. Retain the newest mask
    // (preserving cascade order), and charge cleanup to this bridge operation.
    await page.evaluate(css => {
      const masks = [...document.querySelectorAll('style')].filter(el => el.textContent === css);
      for (const old of masks.slice(0, -1)) old.remove();
    }, CARET_MASK_CSS);
    await stopRecorder(cdp);
    console.log(JSON.stringify({result}));
  } catch (error) { console.log(JSON.stringify({error:String(error)})); }
}
await context.close();
