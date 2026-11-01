// Editors-trial host for Apryse WebViewer's DOCX Editor (@pdftron/webviewer).
//
// Adapted from Apryse's own showcase (showcase-demos/office-editor/index.js),
// with three changes so the page can be measured:
//   - the document is the trial's fixture, served by the driver at /sample.docx
//     (or ?doc=<url>), not Apryse's sample files on S3;
//   - no alert(): a modal blocks every automated driver;
//   - window.__apryse exposes the instance and a promise that settles when
//     the document has loaded, for build/capture_ui.sh and roundtrip.mjs.
// The license key is read from the trial's .env (APRYSE_API_KEY) at serve time
// and is never committed.
import WebViewer from '@pdftron/webviewer';

const params = new URLSearchParams(location.search);
const doc = params.get('doc') || '/sample.docx';

let markLoaded;
let markFailed;
const loaded = new Promise((resolve, reject) => { markLoaded = resolve; markFailed = reject; });
window.__apryse = { instance: null, loaded, doc, errors: [] };

WebViewer(
  {
    path: '/lib',
    licenseKey: import.meta.env.APRYSE_API_KEY,
    initialDoc: doc,
    // The DOCX Editor: the document is opened for editing in the browser, by
    // Apryse's own office engine, not converted to PDF for viewing.
    enableOfficeEditing: true,
    enableFilePicker: true,
    extension: 'docx',
    filename: 'complex.docx',
  },
  document.getElementById('viewer'),
).then((instance) => {
  window.__apryse.instance = instance;
  const { documentViewer } = instance.Core;
  // "Loaded" means the document AND its comments: WebViewer imports a DOCX's
  // comments as annotations after documentLoaded, and an export taken in
  // between writes a different comments part (seen in v0.9.2: two round trips
  // of the same file differed in comments.xml at the same score).
  documentViewer.addEventListener('documentLoaded', async () => {
    const d = documentViewer.getDocument();
    await documentViewer.getAnnotationsLoadedPromise();
    markLoaded({ filename: d.getFilename(), type: d.getType(), pages: d.getPageCount(),
                 annotations: instance.Core.annotationManager.getAnnotationsList().length });
  });
  instance.UI.addEventListener(instance.UI.Events.LOAD_ERROR, (e) => {
    window.__apryse.errors.push(String(e.detail));
    markFailed(new Error(String(e.detail)));
  });
});
