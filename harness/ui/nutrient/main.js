// Editors-trial host for Nutrient Web SDK (formerly PSPDFKit; commercial,
// closed source), a viewer: it converts the .docx to a PDF in the browser (a
// .NET/WebAssembly office engine) and shows the PDF.
//
// Loaded exactly as the sister site (editors.benchmarks.law) loads it: the
// pinned version from Nutrient's own public CDN, with NO license key, which
// Nutrient documents as trial mode (the pages carry its evaluation watermark).
// No account, no key and no accepted terms are involved, and none is to be
// added here. The viewer is opened with Nutrient's documented minimum
// (`container`, `document`, `baseUrl`): its own default toolbar and view.
// Changes for measuring:
//   - the document is the trial's fixture, served by the driver at /sample.docx
//     (or ?doc=<url>);
//   - window.__host exposes the instance and a promise that settles when the
//     converted document is shown, for build/capture_ui.sh.
const VERSION = '1.25.0'; // published 2026-11-02 (npm @nutrient-sdk/viewer); the CDN path is versioned
const BASE = `https://cdn.cloud.pspdfkit.com/pspdfkit-web@${VERSION}/`;
const params = new URLSearchParams(location.search);

const script = (src) => new Promise((resolve, reject) => {
  const s = document.createElement('script');
  s.src = src;
  s.onload = () => resolve();
  s.onerror = () => reject(new Error(`could not load ${src}`));
  document.head.append(s);
});

async function open() {
  await script(`${BASE}nutrient-viewer.js`);
  const NV = window.NutrientViewer;
  if (!NV) throw new Error('the Nutrient script did not define NutrientViewer');
  const bytes = await (await fetch(params.get('doc') || '/sample.docx')).arrayBuffer();
  const instance = await NV.load({ container: document.getElementById('viewer'), document: bytes, baseUrl: BASE });
  window.__host.instance = instance;
  return { pages: instance.totalPageCount, version: NV.version };
}

window.__host = { instance: null, loaded: null, version: VERSION };
window.__host.loaded = open();
window.__host.loaded.catch(() => {});
// A flag the browser speed lanes (Report E2) can poll: set when `loaded` settles.
window.__host.ready = false;
window.__host.error = null;
window.__host.loaded.then(() => { window.__host.ready = true; }, (e) => { window.__host.error = String((e && e.message) || e); });
