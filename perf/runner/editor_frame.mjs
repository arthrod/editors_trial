/**
 * Editors whose whole application runs in a frame of their host page.
 *
 * OnlyOffice's DocsAPI builds its editor (toolbar, rulers, the canvas it draws
 * the document on, and the textarea that takes the keyboard) in an iframe of
 * the host page (harness/ui/onlyoffice); the host page itself holds only that
 * frame. Every page-context read a lane makes (keydown listeners, event
 * timing, the caret, the model, the document region) has to run in the
 * editor's document, where the events and the editor are.
 *
 * `editorPage(page, editorId)` returns the page itself for every editor not
 * listed here (a no-op: same object). For a listed editor it returns a view of
 * the page whose document calls (evaluate, waitForFunction, locator, ...) run
 * in the editor's frame once that frame exists, and in the main frame before
 * it does; input devices, navigation, screenshots, the context and CDP stay
 * the page's. Coordinates need no translation: the host page lays the frame
 * out at (0, 0) at the viewport's size with no border (checked in
 * test_e2_editor_frame), so a point in the frame is the same point on the page.
 * The frame is looked up on every call, so a reload's new frame is used.
 */

/** editor id -> the URL of its editor frame. */
export const EDITOR_FRAMES = {
  // OnlyOffice's document editor, as the CryptPad build serves it from vendor/.
  onlyoffice: /\/web-apps\/apps\/documenteditor\/main\/index\.html/,
};

/** Page methods that act on a document, run in the editor's frame. */
export const FRAME_METHODS = new Set([
  '$', '$$', '$eval', '$$eval',
  'evaluate', 'evaluateHandle', 'waitForFunction', 'waitForSelector',
  'locator', 'frameLocator',
  'getByText', 'getByRole', 'getByLabel', 'getByPlaceholder', 'getByTestId', 'getByAltText', 'getByTitle',
  'click', 'dblclick', 'tap', 'hover', 'focus', 'fill', 'type', 'press', 'check', 'uncheck', 'selectOption',
  'dispatchEvent', 'textContent', 'innerText', 'innerHTML', 'getAttribute', 'isVisible', 'isHidden',
  'addScriptTag', 'addStyleTag',
]);

export function editorFrame(page, editorId) {
  const pattern = EDITOR_FRAMES[editorId];
  if (!pattern || typeof page.frames !== 'function') return null;
  return page.frames().find((frame) => !frame.isDetached() && pattern.test(frame.url())) || null;
}

export function editorPage(page, editorId) {
  if (!page || !Object.prototype.hasOwnProperty.call(EDITOR_FRAMES, editorId || '')) return page;
  return new Proxy(page, {
    get(target, prop) {
      if (prop === '__editorFrameOf') return target;
      if (typeof prop === 'string' && FRAME_METHODS.has(prop)) {
        const frame = editorFrame(target, editorId) || target.mainFrame();
        const fn = frame[prop];
        return typeof fn === 'function' ? fn.bind(frame) : fn;
      }
      const value = Reflect.get(target, prop, target);
      return typeof value === 'function' ? value.bind(target) : value;
    },
  });
}

/** The real page behind a view (for APIs that compare page identity). */
export function rawPage(page) {
  return (page && page.__editorFrameOf) || page;
}
