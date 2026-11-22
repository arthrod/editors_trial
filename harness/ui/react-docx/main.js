// Editors-trial host for react-docx (@extend-ai/react-docx, the `/vanilla` entry).
//
// The package's own quick start ("Open a document from a URL"), with these changes
// so the page can be measured:
//   - the document is the trial's fixture, served by the driver at /sample.docx
//     (or ?doc=<url>);
//   - mode "edit": the trial measures editors, and the package defaults to read-only;
//   - ?review=1 passes the package's own `showTrackedChanges` and `showComments`
//     options, both off by default, to photograph its review marks;
//   - window.__host exposes the viewer and a promise that settles when the
//     document is shown, for build/capture_ui.sh.
// The package ships no toolbar; nothing of ours is drawn over the page.
import { createDocxViewer } from '@extend-ai/react-docx/vanilla';

const params = new URLSearchParams(location.search);
const review = params.get('review') === '1';

const viewer = createDocxViewer(document.getElementById('viewer'), {
  src: params.get('doc') || '/sample.docx',
  mode: 'edit',
  ...(review ? { showTrackedChanges: true, showComments: true } : {}),
});

const loaded = new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error('no document after 90 s')), 90000);
  viewer.subscribe((c) => {
    if (c.error) { clearTimeout(timer); reject(new Error(String(c.error.message || c.error))); }
    else if (c.hasDocument && !c.isLoading) { clearTimeout(timer); resolve({ fileName: c.fileName }); }
  });
});
loaded.catch(() => {});
window.__host = { viewer, loaded, review, ready: false, error: null };
// A flag the browser speed lanes (Report E2) can poll: set when `loaded` settles.
loaded.then(() => { window.__host.ready = true; }, (e) => { window.__host.error = String(e && e.message || e); });
