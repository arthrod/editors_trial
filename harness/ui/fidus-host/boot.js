/**
 * Injected by harness/ui/fidus-host/proxy.mjs into every HTML page of the
 * Django app. It turns "one page load" into "a rendered, editable document",
 * using only the application's own paths (Report C §2.11):
 *
 *   /                        log in through the app's own form
 *   /documents/overview/     the app's own "Import document" dialog: fetch the
 *                            corpus from /corpus.docx (the perf harness's
 *                            corpus_route), hand it to #doc-uploader, press
 *                            Import, follow the new row into the editor
 *   /document/<id>/          wait for the body ProseMirror to hold the text,
 *                            lift the never-cleared wait cover, mark ready
 *
 * The cover: the adjust-doc-to-template worker throws on this corpus
 * (RangeError: Invalid content for node title), its onerror only logs, so the
 * "Updating document. Please wait…" overlay is never lifted. Report C §2.11
 * discloses that the probe lifts it — this is the same intervention
 * (`deactivateWait()`), applied on every document load instead of once.
 *
 * Ready signal: `html[data-fidus-host-ready="1"]`, set only after the body
 * editor contains the imported text AND the cover is gone. It is not
 * `.ProseMirror` because that element exists before the document arrives.
 */
(() => {
  'use strict';
  const TAG = '[fidus-host]';
  const say = (...a) => console.log(TAG, ...a);

  const CORPUS_PATH = '/corpus.docx';
  const CORPUS_NAME = 'complex.docx';
  const DOCX_MIME =
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  const BODY_SELECTOR = '#document-editable .ProseMirror';
  const MIN_BODY_TEXT = 80; // the corpus body is ~865 chars; 80 rules out an empty mount
  const S = window.sessionStorage;

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const bump = (k) => S.setItem(k, String(Number(S.getItem(k) || 0) + 1));

  async function until(label, fn, timeoutMs = 60000, everyMs = 200) {
    const t0 = Date.now();
    for (;;) {
      try {
        const v = fn();
        if (v) return v;
      } catch {
        /* element mid-render; keep polling */
      }
      if (Date.now() - t0 > timeoutMs) throw new Error(`timeout: ${label}`);
      await sleep(everyMs);
    }
  }

  function byText(selector, re) {
    return [...document.querySelectorAll(selector)].find((el) => re.test(el.textContent || ''));
  }

  function fail(stage, err) {
    const msg = `${stage}: ${err && err.message ? err.message : err}`;
    say('FAILED ' + msg);
    document.documentElement.setAttribute('data-fidus-host-error', msg);
  }

  // The host's own boot page (proxy.mjs) and Django's setup page both reload
  // themselves; neither is the application, and polling them for 45 s only
  // writes a false "no login form" error into the page the probe is watching.
  function isStartingPage() {
    if (document.documentElement.hasAttribute('data-fidus-host-booting')) return true;
    const body = document.body ? document.body.textContent || '' : '';
    return body.includes('Fidus Writer is currently being updated');
  }

  // ---- the wait cover -------------------------------------------------------
  function liftWait() {
    let lifted = 0;
    for (const el of document.querySelectorAll('#wait')) {
      if (!el.classList || !el.classList.contains('active')) continue;
      el.classList.remove('active');
      el.classList.remove('full');
      el.style.pointerEvents = 'none';
      const msg = el.querySelector('span.message');
      if (msg && msg.parentElement) msg.parentElement.removeChild(msg);
      lifted++;
    }
    return lifted;
  }

  function keepWaitLifted(ms = 20000) {
    // Observe only the cover itself: a tree-wide observer would run during the
    // measured keystrokes and pollute input-to-next-paint.
    const wait = document.querySelector('#wait');
    liftWait();
    if (!wait) return;
    const mo = new MutationObserver(() => liftWait());
    mo.observe(wait, { attributes: true, attributeFilter: ['class'] });
    setTimeout(() => mo.disconnect(), ms);
  }

  // ---- stages ---------------------------------------------------------------

  async function loginStage() {
    const input = document.querySelector('#id-login');
    if (Number(S.getItem('loginAttempts') || 0) >= 3) {
      throw new Error('still signed out after 3 attempts (bad credentials?)');
    }
    bump('loginAttempts');
    const form = input.form || input.closest('form');
    const user = form.querySelector('#id-login');
    const pass = form.querySelector('#id-password');
    user.value = S.getItem('fidusHostUser') || 'corpus';
    pass.value = S.getItem('fidusHostPass') || 'corpus-pass-2026';
    for (const el of [user, pass]) {
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
    say('logging in as ' + user.value);
    // The app's login submits POST /api/user/login/ and re-initialises itself
    // in place (user/static/js/modules/login/index.js: afterLogin -> app.init).
    // That in-place overview keeps the login page's settings, which carry no
    // document_templates: the importer would then post an empty import_id and
    // /api/document/get_template/ answers 500. So wait for the sign-in to take
    // effect and load the real overview page, which has the full settings.
    const submit = form.querySelector('button[type=submit], input[type=submit]');
    if (submit) submit.click();
    else form.requestSubmit();
    await until('sign-in to take effect', () => !document.querySelector('#id-login'), 30000);
    say('signed in -> /documents/overview/');
    location.assign('/documents/overview/');
  }

  function overviewImportButton() {
    return byText('button.fw-text-menu', /import document/i);
  }

  async function importStage() {
    // A reload mid-import loses the dialog but the new document usually exists.
    if (S.getItem('importing') === '1' && S.getItem('importedHref')) {
      say('import already finished in this tab -> ' + S.getItem('importedHref'));
      location.assign(S.getItem('importedHref'));
      return;
    }
    S.setItem('importing', '1');

    const menuBtn = await until(
      'overview "Import document" menu button',
      () => overviewImportButton(),
      60000,
    );
    menuBtn.click();
    const uploader = await until('#doc-uploader', () => document.getElementById('doc-uploader'), 30000);
    say('import dialog open');

    const res = await fetch(CORPUS_PATH, { cache: 'no-store' });
    if (!res.ok) throw new Error(`GET ${CORPUS_PATH} -> ${res.status}`);
    const blob = await res.blob();
    const file = new File([blob], CORPUS_NAME, { type: DOCX_MIME });
    const dt = new DataTransfer();
    dt.items.add(file);
    uploader.files = dt.files;
    uploader.dispatchEvent(new Event('change', { bubbles: true }));
    say(`corpus attached: ${file.name} ${file.size} bytes`);

    const before = new Set(
      [...document.querySelectorAll('a.fw-data-table-title:not(.parentdir)')].map((a) => a.getAttribute('href')),
    );
    const newRow = () =>
      [...document.querySelectorAll('a.fw-data-table-title:not(.parentdir)')].find(
        (a) => !before.has(a.getAttribute('href')),
      );
    const importBtn =
      byText('.ui-dialog-buttonset button', /^\s*import\s*$/i) || byText('.fw-button', /^\s*import\s*$/i);
    if (!importBtn) throw new Error('no "Import" button in the dialog');
    importBtn.click();
    say('import pressed');

    // The app's importer throws into the page rather than rejecting: a DOCX
    // without the optional docProps/core.xml dies inside
    // DocxConvert.extractAuthors (`zip.file(...).query(...)` on null) and the
    // dialog simply stays open. Waiting out the row budget turns that into a
    // 120 s probe timeout that names nothing, so the throw is caught here and
    // reported as the failure it is.
    const thrown = [];
    const describe = (e) => {
      const err = e && (e.error || e.reason);
      if (err && err.message) return String(err.message);
      if (typeof err === 'string' && err) return err;
      if (e && typeof e.message === 'string' && e.message) return e.message;
      return 'uncaught error in the import path';
    };
    const onError = (e) => thrown.push(describe(e));
    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onError);
    let settled = false;
    let row;
    try {
      row = await Promise.race([
        until('imported document row', newRow, 60000, 500),
        (async () => {
          for (;;) {
            if (settled) return null;
            if (thrown.length) {
              // One last look: a just-created row beats a stray error.
              await sleep(1000);
              const late = newRow();
              if (late) return late;
              throw new Error(`the app's DOCX import threw: ${thrown[0]}`);
            }
            await sleep(250);
          }
        })(),
      ]);
    } finally {
      settled = true;
      window.removeEventListener('error', onError);
      window.removeEventListener('unhandledrejection', onError);
    }
    const href = row.getAttribute('href');
    say('imported -> ' + href);
    S.setItem('importedHref', href);
    location.assign(href);
  }

  async function documentStage() {
    const pm = await until(
      'body ProseMirror with text',
      () => {
        const el = document.querySelector(BODY_SELECTOR);
        return el && (el.innerText || '').trim().length >= MIN_BODY_TEXT ? el : null;
      },
      120000,
    );
    const lifted = liftWait();
    say(`document rendered (${(pm.innerText || '').length} chars), cover lifted: ${lifted}`);
    keepWaitLifted(20000);
    window.__fidusHostReady = true;
    document.documentElement.setAttribute('data-fidus-host-ready', '1');
    say('READY');
  }

  // ---- dispatch -------------------------------------------------------------
  // Decided by what the page holds, not by its path: the app renders the
  // documents overview at "/" after an in-place login.
  async function main() {
    if (isStartingPage()) {
      say('host/upstream still starting; the page reloads itself');
      return;
    }
    if (location.pathname.startsWith('/document/')) return documentStage();
    const kind = await until(
      'login form or documents overview',
      () => {
        if (document.querySelector('#id-login')) return 'login';
        if (overviewImportButton()) return 'overview';
        return null;
      },
      45000,
    );
    say('page ' + location.pathname + ' is the ' + kind + ' page');
    if (kind === 'login') {
      // loginStage ends by loading the overview; never fall through into an
      // import on the page that is on its way out.
      await loginStage();
      return;
    }
    return importStage();
  }

  main().catch((e) => fail(location.pathname, e));
})();
