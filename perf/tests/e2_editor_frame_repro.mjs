// editor_frame.mjs on fake pages: which object each call reaches (test_e2_editor_frame.py).
import { EDITOR_FRAMES, editorPage, rawPage } from '../runner/editor_frame.mjs';
// argv: every browser target's editor id (benchmark_warm_cold.BROWSER_TARGETS).
const BROWSER_EDITOR_IDS = process.argv.slice(2);

function fakeFrame(name, url) {
  return {
    name, url: () => url, isDetached: () => false,
    evaluate(fn) { return `${this.name}:evaluate`; },
    waitForFunction() { return `${this.name}:waitForFunction`; },
    locator(sel) { return `${this.name}:locator:${sel}`; },
  };
}
function fakePage(frames) {
  const main = fakeFrame('main', 'http://127.0.0.1:5223/');
  const page = {
    mouse: { click: () => 'page:mouse' }, keyboard: { press: () => 'page:keyboard' },
    frames: () => [main, ...frames], mainFrame: () => main,
    evaluate() { return 'page:evaluate'; },
    reload() { return 'page:reload'; },
    viewportSize() { return { width: 1280, height: 900 }; },
  };
  return page;
}
const out = {};
// Every other editor: the very same object.
const plain = fakePage([]);
out.others_same_object = BROWSER_EDITOR_IDS.filter((id) => id !== 'onlyoffice').every((id) => editorPage(plain, id) === plain);
out.null_editor_same_object = editorPage(plain, null) === plain && editorPage(plain, '') === plain;
out.listed = Object.keys(EDITOR_FRAMES);
// OnlyOffice before its frame exists: the main frame.
const early = editorPage(fakePage([]), 'onlyoffice');
out.before_frame = early.evaluate(() => 1);
// With its editor frame: document calls there, devices and navigation on the page.
const withFrame = fakePage([fakeFrame('editor', 'http://127.0.0.1:5223/vendor/editor/web-apps/apps/documenteditor/main/index.html?_dc=0')]);
const view = editorPage(withFrame, 'onlyoffice');
out.evaluate = view.evaluate(() => 1);
out.waitForFunction = view.waitForFunction('1');
out.locator = view.locator('#id_viewer');
out.mouse = view.mouse.click();
out.reload = view.reload();
out.viewport = view.viewportSize().width;
out.raw = rawPage(view) === withFrame && rawPage(withFrame) === withFrame;
process.stdout.write(JSON.stringify(out));
