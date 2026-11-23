// Editors-trial host for BetterOffice DOCX (@betteroffice/docx-react).
//
// The package's own usage (README, "Usage" and the fonts package's "Usage"):
// its stylesheet, its metric-compatible fonts configured once before the editor
// mounts, and <DocxEditor documentBuffer={bytes} /> with every option at its
// default (editing mode, its own toolbar, zoom control). Changes for measuring:
//   - the document is the trial's fixture, served by the driver at /sample.docx
//     (or ?doc=<url>);
//   - downloadOnSave={false}: nothing lands in a downloads folder;
//   - window.__host exposes the editor ref and a promise that settles when the
//     layout of the whole document is complete, for build/capture_ui.sh.
import { createElement, createRef } from 'react';
import { createRoot } from 'react-dom/client';
import { configureDefaultFonts } from '@betteroffice/docx/layout';
import * as fonts from '@betteroffice/fonts';
import { DocxEditor } from '@betteroffice/docx-react';
import '@betteroffice/docx-react/styles.css';

configureDefaultFonts({ fonts });

const params = new URLSearchParams(location.search);
const ref = createRef();
const errors = [];
let settle;
const loaded = new Promise((resolve, reject) => { settle = { resolve, reject }; });
loaded.catch(() => {});
window.__host = { ref, loaded, errors, ready: false, error: null };
// A flag the browser speed lanes (Report E2) can poll: set when `loaded` settles.
loaded.then(() => { window.__host.ready = true; }, (e) => { window.__host.error = String(e && e.message || e); });

// A document that cannot be fetched is said at once: without this the module stops here,
// `loaded` never settles, and the probe reports a two-minute timeout instead of the cause.
const bytes = await (async () => {
  const url = params.get('doc') || '/sample.docx';
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.arrayBuffer();
  } catch (e) {
    const err = new Error(`could not fetch ${url}: ${e && e.message || e}`);
    errors.push({ message: err.message, recoverable: false });
    settle.reject(err);
    throw err;
  }
})();
createRoot(document.getElementById('root')).render(createElement(DocxEditor, {
  ref,
  documentBuffer: bytes,
  downloadOnSave: false,
  onError: (e, info) => {
    errors.push({ message: String(e && e.message || e), recoverable: !!(info && info.recoverable) });
    if (!(info && info.recoverable)) settle.reject(e);
  },
}));

// The ref is attached when the editor chunk has loaded; the page count is final
// once whenLayoutComplete() resolves (README, "Loading and accessibility").
const t0 = performance.now();
(async function wait() {
  while (!ref.current) {
    if (performance.now() - t0 > 90000) return settle.reject(new Error('editor not mounted after 90 s'));
    await new Promise((r) => setTimeout(r, 50));
  }
  for (let attempt = 1; ; attempt++) {
    try {
      const pages = await ref.current.whenLayoutComplete({ timeoutMs: 90000 });
      return settle.resolve({ pages });
    } catch (e) {
      // The wait is rejected when the document's identity moves while it waits.
      if (attempt >= 4 || !/Document was replaced/.test(String(e && e.message || e))) return settle.reject(e);
      await new Promise((r) => setTimeout(r, 100));
    }
  }
})().catch((e) => settle.reject(e)); // nothing in the wait may fail unseen
