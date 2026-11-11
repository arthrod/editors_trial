// B9 witness bridge. One Chromium launch; Python connects to this same browser.
// JSON lines over stdin/stdout; only this file owns trusted sampled keystrokes.
import readline from 'node:readline';
import {loadPlaywright, witnessFrame, clockSkew, frameInterval, stopRecorder, getRecorder, CARET_MASK_CSS} from './witness.mjs';
import {startChromeTrace, stopChromeTrace} from './chrome_trace.mjs';
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
      await page.addInitScript(({selector}) => {
        window.__b9usable = null;
        new MutationObserver(() => {
          const el = document.querySelector(selector);
          if (window.__b9usable === null && el?.isContentEditable && el.getBoundingClientRect().height > 0)
            window.__b9usable = performance.now();
        }).observe(document, {subtree:true, childList:true, attributes:true});
      }, {selector:command.selector});
      await page.goto(command.url, {waitUntil:'domcontentloaded'});
      if (command.ready_js) await page.waitForFunction(command.ready_js);
      else if (command.ready_selector) await page.locator(command.ready_selector).first().waitFor();
      // A lazy editable (folio's hidden ProseMirror) mounts on the first
      // document click; it cannot exist before, so `selector` alone would
      // never appear.
      if (command.click_selector) await page.locator(command.click_selector).first().click();
      await page.locator(command.selector).first().waitFor();
      const usable = await page.evaluate(() => window.__b9usable);
      if (usable === null) {
        result = {usable_ms:null, witness:null, frame_interval_ms:null, refusal:'no_correctness_adapter'};
      } else {
      clock = await clockSkew(page, cdp);
      interval = await frameInterval(page);
      const witness = await witnessFrame(page, cdp, {baseline, afterPageMs:usable,
        region:{selector:command.present_selector || command.selector}, clockCheck:clock, settleMs:0});
      result = {usable_ms:usable, witness, frame_interval_ms:interval.median_ms};
      }
    } else if (command.op === 'key') {
      if (sessionKind !== 'latency') throw Error('key witnesses forbidden in throughput sessions');
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
    } else if (command.op === 'close') {
      await stopRecorder(cdp);
      await stopChromeTrace(traceBrowser, traceHandle);
      await context.close(); break;
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
