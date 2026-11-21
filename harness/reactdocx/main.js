// Editors-trial host for react-docx (@extend-ai/react-docx).
//
// The package's own framework-free entry, as its README's "Vanilla JavaScript"
// quick start mounts it:
//   createDocxViewer(element, { file, mode: 'edit' })
//   viewer.subscribe(controller => ...)      loading, error, hasDocument
//   viewer.getController().getDocxBytes()    the bytes its Export writes
//
// Nothing of ours is between the document and the editor: the driver serves
// the trial's fixture at /sample.docx (or ?doc=<url>) and this page hands the
// bytes to the viewer. window.__reactdocx exposes the viewer and a promise
// that settles when the document has loaded (or failed), for roundtrip.mjs.
import { createDocxViewer } from '@extend-ai/react-docx/vanilla';

const params = new URLSearchParams(location.search);
const doc = params.get('doc') || '/sample.docx';

let markLoaded;
let markFailed;
const loaded = new Promise((resolve, reject) => { markLoaded = resolve; markFailed = reject; });
window.__reactdocx = { viewer: null, loaded, doc, errors: [] };

const describe = (e) => (e instanceof Error ? e.message : String(e));

try {
  const response = await fetch(doc);
  if (!response.ok) throw new Error(`could not fetch ${doc}: ${response.status}`);
  const file = await response.arrayBuffer();
  const t0 = performance.now();
  const viewer = createDocxViewer(document.getElementById('viewer'), {
    file,
    fileName: 'complex.docx',
    mode: 'edit',
  });
  window.__reactdocx.viewer = viewer;
  // "Loaded" is the controller's own state: a document, and no load running.
  // The controller starts with neither, so a load must have been seen first.
  let sawLoading = false;
  let settled = false;
  const check = (controller) => {
    if (settled || !controller) return;
    if (controller.error) {
      settled = true;
      window.__reactdocx.errors.push(describe(controller.error));
      markFailed(new Error(describe(controller.error)));
      return;
    }
    if (controller.isLoading || !controller.hasDocument) sawLoading = true;
    if (controller.hasDocument && !controller.isLoading) {
      settled = true;
      markLoaded({
        fileName: controller.fileName,
        pages: controller.totalPages,
        sawLoading,
        model_ready_ms: performance.now() - t0,
      });
    }
  };
  viewer.subscribe(check);
  check(viewer.getController());
} catch (e) {
  window.__reactdocx.errors.push(describe(e));
  markFailed(e);
}
