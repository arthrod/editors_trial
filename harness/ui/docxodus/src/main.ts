/**
 * Docxodus rendering-study host.
 *
 * Everything below is Docxodus (JSv4/Docxodus, v14.2.0) doing the work:
 *   - the published WebAssembly build of the .NET OOXML engine,
 *   - `convertDocxToPaginatedHtml()` — the materializer the `docxodus` CLI
 *     and `@docxodus/export` drive, so the page tree is the product's own,
 *   - `DocxEditor` — the in-browser block editor,
 *   - `DocxSession` — the package reader/writer.
 *
 * The host contributes no rendering logic. It fetches the corpus, calls the
 * product's own entry points, and puts their output on the page.
 *
 * The corpus is fetched from /corpus.docx; the Playwright driver intercepts
 * that request and answers with the fixture bytes.
 */
import {
  initialize,
  setWasmBasePath,
  getWasmExports,
  openDocxSession,
  generatePackageManifest,
  getDocumentMetadata,
  DocxEditor,
} from 'docxodus';
import { convertDocxToPaginatedHtml } from 'docxodus/export-browser';

const WASM_BASE = '/wasm/';

const state: any = {
  wasmReady: false,
  rendered: false,
  error: null,
  pageCount: 0,
  warnings: [],
  renderReport: null,
  pageMap: null,
  manifest: null,
  metadata: null,
  unsupported: null,
  savedDocxBase64: null,
  mode: 'render',
};

function log(...a: any[]) {
  console.log('[docxodus-host]', ...a);
}

function setStatus(text: string, isError = false) {
  const el = document.getElementById('status')!;
  el.textContent = text;
  el.classList.toggle('err', isError);
}

async function loadBytes(): Promise<Uint8Array> {
  const input = document.getElementById('file') as HTMLInputElement;
  if (input.files && input.files.length > 0) {
    const buf = await input.files[0].arrayBuffer();
    return new Uint8Array(buf);
  }
  const res = await fetch('/corpus.docx');
  if (!res.ok) throw new Error(`GET /corpus.docx -> HTTP ${res.status}`);
  return new Uint8Array(await res.arrayBuffer());
}

function toBase64(bytes: Uint8Array): string {
  let s = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    s += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(s);
}

async function render(bytes: Uint8Array) {
  const t0 = performance.now();
  const result = await convertDocxToPaginatedHtml(bytes, {
    // Word's own export of the corpus is in Print Markup mode with the
    // comment balloon panel visible, so the closest matching profile is
    // used here: markup review, Word-style presentation, balloons in the
    // margin.
    reviewProfile: 'markup',
    markupPresentation: 'word',
    commentProfile: 'margin',
    commentColumnPlacement: 'balloons',
    wasmBasePath: WASM_BASE,
    timeoutMs: 180000,
  });

  const host = document.getElementById('pages')!;
  host.innerHTML = result.html;

  state.pageCount = result.pageCount;
  state.warnings = result.warnings ?? [];
  state.renderReport = result.renderReport ?? null;
  state.pageMap = result.pageMap ?? null;
  state.rendererFingerprint = result.rendererFingerprint ?? null;
  state.renderMs = Math.round(performance.now() - t0);
  state.rendered = true;
  performance.mark('docxodus-first-usable');

  const doc = document.getElementById('docLabel')!;
  doc.textContent = `Docxodus ${state.metadata?.version ?? ''} — ${result.pageCount} pages, ${state.warnings.length} warning(s)`;
  setStatus(`rendered ${result.pageCount} page(s) in ${state.renderMs} ms`);
  log('rendered', result.pageCount, 'pages', state.warnings.length, 'warnings');
}

/** Open the product's own package reader and read the corpus back out. */
async function inspectPackage(bytes: Uint8Array) {
  state.manifest = await generatePackageManifest(bytes);
  state.metadata = await getDocumentMetadata(bytes);

  const session = openDocxSession(bytes);
  try {
    state.manifest = session.getPackageManifest();
  } catch (e) {
    log('session manifest failed', e);
  }
  // A save with no edits is the round trip Reports A and A2 measure.
  const saved = session.save();
  state.savedDocxBase64 = toBase64(saved);
  state.savedBytes = saved.length;
  session.close();
}

async function mountEditor(bytes: Uint8Array) {
  const host = document.getElementById('editorHost')!;
  host.innerHTML = '';
  host.classList.remove('hidden');
  document.getElementById('pages')!.classList.add('hidden');
  const exports = getWasmExports();
  const editor = await DocxEditor.openAsync(host, bytes, exports, {
    paginated: true,
    showRevisions: true,
    trackedChanges: 'RenderInline',
    fitToWidth: true,
    headerFooter: true,
  });
  state.editor = true;
  setStatus('block editor mounted');
  log('editor mounted');
}

async function boot() {
  try {
    setWasmBasePath(WASM_BASE);
    await initialize(WASM_BASE);
    performance.mark('docxodus-model-ready');
    state.wasmReady = true;
    log('wasm runtime ready');

    const bytes = await loadBytes();
    state.sourceBytes = bytes.length;
    await inspectPackage(bytes);
    await render(bytes);
    (window as any).__docxodus = state;
  } catch (e: any) {
    state.error = String(e && e.stack ? e.stack : e);
    (window as any).__docxodus = state;
    setStatus(`failed: ${e && e.message ? e.message : e}`, true);
    console.error('[docxodus-host] fatal', e);
  }
}

document.getElementById('file')!.addEventListener('change', async (ev: any) => {
  try {
    const bytes = await loadBytes();
    await inspectPackage(bytes);
    await render(bytes);
  } catch (e: any) {
    setStatus(`failed: ${e && e.message ? e.message : e}`, true);
    console.error('[docxodus-host] reload failed', e);
  }
});

document.getElementById('modeEditor')!.addEventListener('click', async () => {
  try {
    const bytes = await loadBytes();
    await mountEditor(bytes);
    state.mode = 'editor';
  } catch (e: any) {
    setStatus(`editor failed: ${e && e.message ? e.message : e}`, true);
  }
});

document.getElementById('modeRender')!.addEventListener('click', () => {
  document.getElementById('pages')!.classList.remove('hidden');
  document.getElementById('editorHost')!.classList.add('hidden');
  state.mode = 'render';
  setStatus(`rendered ${state.pageCount} page(s)`);
});

boot();
