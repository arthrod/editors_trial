// Editors-trial host for OnlyOffice's document editor with no document server,
// the way CryptPad runs it (AGPL-3.0; both parts served unmodified from their
// release archives, see fetch.py):
//   - cryptpad/onlyoffice-x2t-wasm: OnlyOffice's converter (x2t) in WebAssembly
//     turns the .docx into the editor's own binary format, in this page;
//   - cryptpad/onlyoffice-editor: the editor (web-apps + sdkjs), built so that
//     the co-editing socket is replaced by messages to the embedding page
//     (`connectMockServer`).
// The editor is OnlyOffice's whole application in its own frame, opened with
// OnlyOffice's documented config (document, documentType, editorConfig.mode
// "edit") and an empty `customization`: its own header, toolbar, side panels and
// theme, as shipped. Changes for measuring:
//   - the document is the trial's fixture, served by the driver at /sample.docx
//     (or ?doc=<url>);
//   - window.__host exposes a promise that settles when the editor has laid
//     the document out to its last page, and api() for build/capture_ui.sh;
//   - window.__host.ready turns true when OnlyOffice reports the document ready
//     for editing (its documented onDocumentReady event), and
//     window.__host.error holds the reason the document did not open: flags
//     the browser speed lanes (Report E2) can poll synchronously.
const BASE = `${location.origin}/vendor/`;
const params = new URLSearchParams(location.search);

const script = (src) => new Promise((resolve, reject) => {
  const s = document.createElement('script');
  s.src = src; // absolute: x2t.js reads its own address from document.currentScript
  s.onload = () => resolve();
  s.onerror = () => reject(new Error(`could not load ${src}`));
  document.head.append(s);
});

/**
 * .docx → the editor's binary, by x2t in a Worker (x2t_worker.js says why a
 * Worker). A conversion that has not returned after CONVERT_MS is given up on.
 */
const CONVERT_MS = Number(params.get('convert-ms') || 120000);
function convert(bytes) {
  return new Promise((resolve, reject) => {
    const worker = new Worker('/x2t_worker.js');
    const t0 = performance.now();
    let step = 'starting x2t';
    const timer = setTimeout(() => {
      worker.terminate();
      reject(new Error(`x2t did not return within ${CONVERT_MS / 1000} s (${step})`));
    }, CONVERT_MS);
    worker.onerror = (e) => { clearTimeout(timer); reject(new Error(`x2t worker: ${e.message}`)); };
    worker.onmessage = (e) => {
      if (e.data.step === 'converting') { step = 'converting the document'; return; }
      clearTimeout(timer);
      worker.terminate();
      if (e.data.step === 'failed') reject(new Error(e.data.error));
      else resolve({ bin: e.data.result, media: e.data.media, code: e.data.code, ms: Math.round(performance.now() - t0) });
    };
    worker.postMessage({ base: BASE, name: 'doc.docx', bytes, to: 'bin' });
  });
}

const api = () => {
  const frame = document.querySelector('#root iframe');
  return frame && frame.contentWindow && frame.contentWindow.editor;
};

/**
 * Resolves when the editor has laid the document out to its last page.
 * `onDocumentReady` comes with the first page; the editor then paginates on a
 * timer whose id is on its logic document (`FullRecalc.Id`), null when nothing
 * is left to lay out. Four readings 50 ms apart with no timer and the same
 * page count end the wait.
 */
async function paginated(timeoutMs = 180000) {
  const pending = () => {
    const recalc = api()?.WordControl?.m_oLogicDocument?.FullRecalc;
    return recalc ? recalc.Id != null : undefined;
  };
  const count = () => api()?.getCountPages?.() ?? 0;
  const start = performance.now();
  let idle = 0;
  let pages = count();
  while (pending() !== undefined) {
    const busy = pending();
    const now = count();
    idle = busy || now !== pages ? 0 : idle + 1;
    pages = now;
    if (idle >= 4) break;
    if (performance.now() - start > timeoutMs) throw new Error('still paginating after 180 s');
    await new Promise((res) => setTimeout(res, 50));
  }
  return count();
}

async function open() {
  await script(`${BASE}editor/web-apps/apps/api/documents/api.js`);
  if (!window.DocsAPI) throw new Error("OnlyOffice's API script did not load");
  const bytes = new Uint8Array(await (await fetch(params.get('doc') || '/sample.docx')).arrayBuffer());
  const converted = await convert(bytes);
  window.__host.convertMs = converted.ms;
  const bin = converted.bin;
  const media = {};
  for (const [f, data] of Object.entries(converted.media)) media[f] = URL.createObjectURL(new Blob([data]));
  window.APP ??= {}; // sdkjs reads parent.APP
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('no document after 180 s')), 180000);
    const done = (err) => { clearTimeout(timer); err ? reject(err) : resolve(); };
    const ed = new window.DocsAPI.DocEditor('oo-holder', {
      document: { fileType: 'docx', key: 'fresh', title: 'complex.docx', url: URL.createObjectURL(new Blob([bin.slice()])) },
      documentType: 'word',
      width: '100%',
      height: '100%',
      // CryptPad's build reads `customization.font` unguarded, so the object is given, empty.
      editorConfig: { mode: 'edit', lang: 'en', user: { id: '1', name: 'Trial' }, customization: {} },
      events: {
        onDocumentReady: () => done(),
        onError: (e) => { window.__host.errors.push(e && e.data); done(new Error(`OnlyOffice: ${e?.data?.errorDescription ?? JSON.stringify(e?.data)}`)); },
      },
    });
    let saves = 0;
    const send = (message) => ed.sendMessageToOO(message);
    // The replies CryptPad's own page gives, with nobody else in the document.
    ed.connectMockServer({
      getParticipants: () => ({
        index: 1,
        list: [{ id: '11', idOriginal: '1', username: 'Trial', indexUser: 1, connectionId: 'c', isCloseCoAuthoring: false, view: false }],
      }),
      getInitialChanges: () => [],
      getImageURL: (name) => Promise.resolve(media[name] ?? media[name.replace(/^media\//, '')] ?? ''),
      onMessage(msg) {
        if (msg.type === 'isSaveLock') send({ type: 'saveLock', saveLock: false });
        else if (msg.type === 'saveChanges') send({ type: 'unSaveLock', index: saves++, time: Date.now() });
        else if (msg.type === 'getLock') send({ type: 'getLock', locks: {} });
        else if (msg.type === 'getMessages') send({ type: 'message' });
      },
    });
  });
  window.__host.ready = true;
  return { pages: await paginated(), media: Object.keys(media) };
}

window.__host = { api, errors: [], loaded: null, convertMs: null, ready: false, error: null };
window.__host.loaded = open();
// An error before the document is ready is the document not opening; a later
// one (pagination still running after 180 s) is kept apart from it.
window.__host.loaded.catch((e) => {
  const reason = String((e && e.message) || e);
  if (window.__host.ready) window.__host.paginateError = reason;
  else window.__host.error = reason;
});
