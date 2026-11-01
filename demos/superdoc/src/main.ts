/**
 * benchmarks.law static demo for SuperDoc.
 *
 * Everything here goes through SuperDoc's own public browser surface:
 *   - import:  `new SuperDoc({ document: { data: bytes, ... } })`
 *               SuperDoc normalises the bytes and hands them to the DOCX
 *               engine's importer (`@superdoc/docx-engine`) - the very same
 *               import path the trial's SDK lane exercised through
 *               `client.open({ doc })`.
 *   - export:  `superdoc.export({ exportType: ['docx'] })`
 *               SuperDoc's own DOCX exporter, not a hand-rolled serializer.
 *
 * No network calls outside this folder: telemetry is disabled and no CDN,
 * font host, analytics or licence-check endpoint is contacted.
 */
import { SuperDoc } from 'superdoc';
import 'superdoc/style.css';
import { superdocFonts } from '@superdoc/fonts';

const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

type MaybePromise<T> = T | Promise<T>;

declare global {
  interface Window {
    /** Exposed so the benchmark harness can read the loaded text / state. */
    superdocDemo?: {
      instance: SuperDoc;
      getText: () => Promise<string>;
      isReady: () => boolean;
    };
  }
}

const statusEl = document.getElementById('status');
const downloadButton = document.getElementById('download-docx') as HTMLButtonElement | null;

function setStatus(text: string): void {
  if (statusEl) statusEl.textContent = text;
}

export async function mountDemo(bytes: ArrayBuffer): Promise<void> {
  const superdoc = new SuperDoc({
    selector: '#editor',
    // SuperDoc's own document source: raw bytes + the DOCX type. This is the
    // editor's import path - no third-party parser is involved.
    document: {
      data: bytes,
      type: DOCX_MIME,
      name: 'document.docx',
    },
    title: 'document',
    // SuperDoc's own toolbar, and its fit-width zoom so a phone sees the whole page (never above 100%).
    // On a phone the comments and track-changes sidebar would take the page's width, so it stays off there.
    ui: { toolbar: { container: '#toolbar' }, comments: window.innerWidth >= 760 },
    zoom: { mode: 'fit-width', fitWidth: { max: 100, padding: 16 } },
    // The reviewed metric-compatible font pack ships with this build, so the
    // document's Calibri / Calibri Light faces resolve to local .woff2 assets
    // instead of a CDN and instead of an Arial fallback.
    fonts: superdocFonts,
    // Never phone home from a static benchmark demo.
    telemetry: { enabled: false },
    licenseKey: null,
    onReady: () => {
      setStatus('ready');
      if (downloadButton) downloadButton.disabled = false;
    },
    onContentError: ({ error }) => {
      setStatus('content error');
      console.error('[superdoc-demo] SuperDoc could not open the document.', error);
    },
    onException: ({ error }) => {
      console.error('[superdoc-demo] SuperDoc exception.', error);
    },
  });

  window.superdocDemo = {
    instance: superdoc,
    isReady: () => Boolean(superdoc.activeEditor),
    getText: async () => {
      const api = superdoc.getDocumentApi() as any;
      if (!api || typeof api.getText !== 'function') return '';
      const text = await api.getText({});
      return typeof text === 'string' ? text : String(text ?? '');
    },
  };

  if (downloadButton) {
    downloadButton.addEventListener('click', async () => {
      downloadButton.disabled = true;
      setStatus('exporting…');
      try {
        // SuperDoc's own export path. `triggerDownload` defaults to true, so
        // SuperDoc creates the <a download> and clicks it for us.
        await superdoc.export({ exportType: ['docx'], exportedName: 'document' });
        setStatus('exported');
      } catch (error) {
        setStatus('export failed');
        console.error('[superdoc-demo] SuperDoc could not export the document.', error);
      } finally {
        downloadButton.disabled = false;
      }
    });
  }
}
