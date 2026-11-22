/*
 * OpenDoc host shim (harness/ui/opendoc/host.mjs puts it in editor.html, before
 * the editor's own scripts). It publishes synchronous signals for the lanes:
 *
 *   window.__host.ready      true once the document is open, laid out and painted
 *   window.__host.error      a string once the editor says it cannot get there
 *   window.__host.settled    true once the editor's font upgrade has repainted it
 *   window.__host.selection  the last caret/selection the editor announced
 *
 * Every one is OpenDoc's own word, read off the page, never inferred from time.
 *
 * Ready: `body.doc-loaded` (openBytes finished the open, editor_file_open.mjs)
 * and page 1's sheet holding its raster canvas (`.page-wrap canvas.page`, mounted
 * only after the engine's RGBA was blitted into it, editor_paint.mjs), then two
 * animation frames so that canvas has reached a presented frame. This is the
 * editor's first render: laid out on its bundled metric-compatible faces, with
 * the caret's input focused ("open ready to type"). The host contract's own
 * `ready` event (window.opendoc) is not used: it fires before that render.
 *
 * Settled: `body[data-fonts-ready="true"]`, the editor's signal that "the
 * document is now painted with its real faces" after it fetched and registered
 * them in the background (its own browser suite waits on it). The fetch includes
 * script fallbacks from a CDN (cdn.jsdelivr.net) whenever the engine reports
 * missing coverage, so it is network-bound; it is kept apart from `ready` so a
 * first-usable time never includes a download the editor does not wait for.
 *
 * Error: the engine failed to start (`html.engine-failed`, engine_boot.mjs), or
 * the startup document was tried and did not open (the editor takes back its
 * `html.doc-expected` promise without `body.doc-loaded`, editor_file_open.mjs);
 * the editor's status line is kept as the reason.
 *
 * Selection: the payload of the host contract's `selection` event
 * (`{anchor: {node, offset}, focus, hasRange}`, host_session.mjs), whose node is
 * the block id `opendoc.ai.read` reports. The contract has the event and no
 * getter, so the last one is kept here.
 *
 * Apart from the capitalisation preference below, nothing here changes the
 * editor: it reads classes and attributes, listens to one documented event, and
 * stops observing once it has its answers.
 */
(function () {
  // The one setting changed (owner's decision, 2026-11-22, disclosed in Report
  // E2): OpenDoc's own preference for capitalising the first letter of a
  // sentence, set to "off" before the editor reads it, as its Settings switch
  // would (webapp/src/autocorrect.mjs, pref opendoc.autoCapitalise). Its default
  // turned the typed "PETITIONER v." into "V." and failed the typing lane's text
  // check although every key arrived.
  try { window.localStorage.setItem('opendoc.autoCapitalise', 'off'); } catch (e) { /* storage disabled */ }
  var host = (window.__host = { ready: false, error: null, settled: false, selection: null, readyAt: null, settledAt: null,
    autocorrect: { capitalise: 'off' } });
  var root = document.documentElement;
  var observer = null;
  var readyArmed = false;

  function status() {
    var el = document.getElementById('status');
    return el ? String(el.textContent || '').trim().slice(0, 300) : '';
  }

  function painted() {
    var body = document.body;
    if (!body || !body.classList.contains('doc-loaded')) return false;
    var canvas = document.querySelector('#pages .page-wrap[data-page-number="1"] canvas.page');
    return !!(canvas && canvas.width > 0 && canvas.height > 0 && canvas.getBoundingClientRect().height > 0);
  }

  function listen() {
    var session = window.opendoc;
    if (!session || typeof session.on !== 'function' || host.__listening) return;
    host.__listening = true;
    session.on('selection', function (event) {
      host.selection = event && event.detail ? event.detail : event;
    });
  }

  function done() {
    if ((host.ready || host.error) && (host.settled || host.error) && observer) {
      observer.disconnect();
      observer = null;
    }
  }

  function check() {
    listen();
    if (host.error) return;
    if (root.classList.contains('engine-failed')) {
      host.error = 'OpenDoc engine failed to start: ' + (status() || 'no status');
      done();
      return;
    }
    var body = document.body;
    if (root.classList.contains('engine-ready') && !root.classList.contains('doc-expected')
        && body && !body.classList.contains('doc-loaded')) {
      host.error = 'OpenDoc did not open the document: ' + (status() || 'no status');
      done();
      return;
    }
    if (!readyArmed && painted()) {
      readyArmed = true;
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          host.readyAt = performance.now();
          host.ready = true;
          done();
        });
      });
    }
    if (!host.settled && body && body.dataset.fontsReady === 'true') {
      host.settled = true;
      host.settledAt = performance.now();
      done();
    }
  }

  function watch() {
    observer = new MutationObserver(check);
    // Classes and data attributes on <html> and <body>, and the sheets arriving
    // in the page band (a canvas is inserted after the attributes are set).
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    observer.observe(document.body, { attributes: true, attributeFilter: ['class', 'data-fonts-ready'] });
    var pages = document.getElementById('pages');
    if (pages) observer.observe(pages, { childList: true, subtree: true });
    check();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch, { once: true });
  else watch();
})();
