/**
 * Static host for the published `docxodus` package.
 *
 * Import path matches the trial harness (`harness/ui/docxodus/src/main.ts`):
 * `initialize` + `getWasmExports` + `DocxEditor.openAsync`.
 * Export path matches the editor's own `DocxEditor.save()` (WASM
 * `DocxSessionBridge.Save`), the same session save the trial round-trip uses.
 */
import {
  DocxEditor,
  TrackedChangeMode,
  getWasmExports,
  initialize,
} from 'docxodus';

const host = document.querySelector<HTMLElement>('#editor');
const download = document.querySelector<HTMLButtonElement>('#download');
const status = document.querySelector<HTMLElement>('#status');

if (!host || !download || !status) {
  throw new Error('Docxodus demo is missing its mount nodes.');
}

type DemoState = {
  ready: boolean;
  error: string | null;
  editor: DocxEditor | null;
  lastExport: Uint8Array | null;
};

const state: DemoState = {
  ready: false,
  error: null,
  editor: null,
  lastExport: null,
};

(window as unknown as { __docxodus: DemoState }).__docxodus = state;

function fail(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  state.error = message;
  status.hidden = false;
  status.textContent = message;
  console.error('[docxodus-demo]', error);
}

function downloadBytes(bytes: Uint8Array): void {
  const blob = new Blob([bytes], {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'document.docx';
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 4000);
}

async function boot(): Promise<void> {
  const wasmBase = new URL('./wasm/', document.baseURI).href;
  await initialize(wasmBase);

  const response = await fetch(new URL('./document.docx', document.baseURI).href);
  if (!response.ok) {
    throw new Error(`GET document.docx failed: HTTP ${response.status}`);
  }
  const bytes = new Uint8Array(await response.arrayBuffer());
  const editor = await DocxEditor.openAsync(host, bytes, getWasmExports(), {
    paginated: true,
    showRevisions: true,
    trackedChanges: TrackedChangeMode.RenderInline,
    fitToWidth: true,
    headerFooter: true,
  });

  state.editor = editor;
  state.ready = true;
  host.dataset.ready = 'true';
  download.disabled = false;
  download.addEventListener('click', () => {
    const saved = editor.save();
    state.lastExport = saved;
    downloadBytes(saved);
  });
}

boot().catch(fail);
