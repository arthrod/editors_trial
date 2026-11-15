/**
 * Warm/cold browser host for docen (@docen/editor).
 *
 * The repo's own demo page (packages/editor/document.html) opens a DOCX only
 * through the component's hidden file input — an interactive picker no probe
 * can drive. This host keeps everything else the demo does (same source-served
 * module graph, same theme/registration) and feeds the editor from an HTTP
 * route instead:
 *
 *   GET /corpus.docx  ->  el.openDOCX(new File([bytes], "corpus.docx"))
 *
 * perf/runner/warm_cold_browser.mjs fulfils /corpus.docx at the browser
 * context level, so the bytes come from --corpus, not from the dev server.
 *
 * Ready signal
 *   window.__DOCEN_READY__ === true   (and #host[data-ready="1"])
 * set only after the DOCX parse returned AND page 1 has a painted canvas —
 * not merely after <docen-document> attached.
 *
 * Edit surface
 *   docen-document .canvas-pages > div:first-child — page 1's frame. Its
 *   ancestor stage host (.docen-canvas) owns the bridge's mousedown handler
 *   (edit-bridge.ts takeFocus): the click parks and focuses the invisible
 *   textarea that carries keyboard input, and typing reaches the document
 *   through beforeinput. The stage host itself is not a usable click target:
 *   its box is the whole page stack (6368px tall on fixture/complex.docx), so
 *   its centre is far below the viewport.
 */
import { applyTheme, DocenDocument, registerComponents } from "@docen/editor";

const CORPUS = new URLSearchParams(window.location.search).get("src") || "/corpus.docx";
const FILENAME = CORPUS.split("/").pop() || "corpus.docx";

const host = document.querySelector<HTMLDivElement>("#host")!;
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function nextFrames(count = 2): Promise<void> {
  return new Promise((resolve) => {
    let seen = 0;
    const tick = (): void => {
      seen += 1;
      if (seen >= count) resolve();
      else requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

interface PaintState {
  pageFrames: number;
  canvas: { width: number; height: number } | null;
}

/** Wire the invisible light-DOM scroll proxy (#scroll-proxy) to the component's
 *  real scroller. perf/runner/adversarial_c10_scroll.mjs looks for the largest
 *  overflow:auto|scroll box under `document`, and `docen-document-area` is
 *  inside the shadow root — out of its reach. The proxy reports the same
 *  scrollHeight and its scrollTop is copied into the real scroller (and back),
 *  so the probe's scroll drives the same repaint a user scroll does. */
function mirrorScroll(el: DocenDocument): void {
  const proxy = document.querySelector<HTMLDivElement>("#scroll-proxy");
  const spacer = document.querySelector<HTMLDivElement>("#scroll-proxy-spacer");
  const area = el.shadowRoot?.querySelector<HTMLElement>("docen-document-area");
  const pages = el.shadowRoot?.querySelector<HTMLElement>(".canvas-pages");
  if (!proxy || !spacer || !area) return;

  const sync = (): void => {
    spacer.style.height = `${area.scrollHeight}px`;
    // Same clientHeight as the real scroller => same scroll range, so a probe
    // that scrolls to 50% lands exactly where a user's 50% scroll would.
    proxy.style.height = `${area.clientHeight}px`;
  };
  sync();
  if (pages) new ResizeObserver(sync).observe(pages);
  new ResizeObserver(sync).observe(area);
  // Content changes (typing, reflow) move scrollHeight without resizing the
  // pages element — re-read it whenever either side scrolls as well.
  proxy.addEventListener("scroll", () => {
    area.scrollTop = proxy.scrollTop;
    sync();
  });
  area.addEventListener("scroll", () => {
    proxy.scrollTop = area.scrollTop;
    sync();
  });
  Reflect.set(window, "__DOCEN_SCROLL__", { proxy: () => proxy.scrollTop, area: () => area.scrollTop });
}

/** Page 1 laid out and painted — the first canvas the stage creates has a
 *  non-zero bitmap and a non-zero box. Later pages are windowed (painted when
 *  they scroll into view), so only page 1 is a readiness gate. */
async function waitForFirstPage(el: DocenDocument, timeoutMs = 120_000): Promise<PaintState> {
  const started = performance.now();
  let last: PaintState = { pageFrames: 0, canvas: null };
  while (performance.now() - started < timeoutMs) {
    const root = el.shadowRoot;
    const frames = root ? [...root.querySelectorAll<HTMLElement>(".canvas-pages > div")] : [];
    const canvas = frames[0]?.querySelector("canvas") ?? null;
    last = {
      pageFrames: frames.length,
      canvas: canvas ? { width: canvas.width, height: canvas.height } : null
    };
    if (
      canvas &&
      canvas.width > 0 &&
      canvas.height > 0 &&
      (frames[0]?.getBoundingClientRect().height ?? 0) > 0
    ) {
      return last;
    }
    await sleep(50);
  }
  throw new Error(
    `page 1 did not paint within ${timeoutMs}ms (frames=${last.pageFrames}, canvas=${JSON.stringify(last.canvas)})`
  );
}

async function boot(): Promise<void> {
  await registerComponents();
  applyTheme("light");

  const el = document.createElement("docen-document") as DocenDocument;
  // No `show-marks`: formatting marks off is the default and the closest match
  // to what Word paints; the measurement does not depend on it either way.
  host.append(el);
  // The stage needs a measurable box before the document is laid out.
  await nextFrames(1);

  const response = await fetch(CORPUS);
  if (!response.ok) throw new Error(`fetch ${CORPUS} -> HTTP ${response.status}`);
  const bytes = await response.arrayBuffer();
  const file = new File([bytes], FILENAME, {
    type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  });
  console.log("[host] fetched", CORPUS, bytes.byteLength, "bytes");

  await el.openDOCX(file);
  const paint = await waitForFirstPage(el);
  // Two frames for the caret/selection overlay that follows the first paint,
  // then the ready flag — nothing below this point re-renders page 1.
  await nextFrames(2);
  mirrorScroll(el);

  Reflect.set(window, "__DOCEN__", el);
  Reflect.set(window, "__DOCEN_PAINT__", paint);
  Reflect.set(window, "__PERF_MODEL_TEXT__", () => {
    const editor = el.editor;
    if (!editor) return "";
    return editor.state.doc.textBetween(0, editor.state.doc.content.size, " ");
  });
  Reflect.set(window, "__DOCEN_READY__", true);
  host.dataset.ready = "1";
  console.log("[host] ready:", JSON.stringify(paint), "filename=", el.getAttribute("filename"));
}

boot().catch((error: unknown) => {
  const message = error instanceof Error ? (error.stack ?? error.message) : String(error);
  Reflect.set(window, "__DOCEN_ERROR__", message);
  host.dataset.error = message.slice(0, 500);
  console.error("[host] boot failed:", message);
});
