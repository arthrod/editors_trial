import { applyTheme, type DocenDocument, registerComponents } from "@docen/editor";

const DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

const downloadButton = document.querySelector<HTMLButtonElement>("#download");
const statusOutput = document.querySelector<HTMLOutputElement>("#status");

if (!downloadButton || !statusOutput) {
  throw new Error("Docen demo controls are missing");
}

function showStatus(message: string): void {
  statusOutput.textContent = message;
  statusOutput.hidden = !message;
}

function mountDownloadButton(editor: DocenDocument): void {
  const titleBar = editor.shadowRoot?.querySelector("docen-title-bar");
  const endSlot = titleBar?.querySelector<HTMLElement>('[slot="end"]');
  if (!endSlot) return;

  // Integrate with the editor's own title bar rather than covering its
  // search/file controls on narrow screens.
  downloadButton.style.cssText = [
    "position:static",
    "min-height:28px",
    "padding:3px 10px",
    "border:1px solid #d1d1d1",
    "border-radius:4px",
    "background:#ffffff",
    "color:#242424",
    "font:600 12px/18px 'Segoe UI',system-ui,sans-serif",
    "cursor:pointer",
  ].join(";");
  endSlot.prepend(downloadButton);
}

async function downloadDocx(editor: DocenDocument): Promise<void> {
  downloadButton.disabled = true;
  showStatus("");

  try {
    // Use the editor's public export path. It delegates to @docen/docx's
    // generateDOCX(), the same exporter measured by the trial harness.
    const bytes = await editor.saveDOCX();
    const buffer = bytes.slice().buffer as ArrayBuffer;
    const blob = new Blob([buffer], { type: DOCX_MIME });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");

    anchor.href = url;
    anchor.download = "document.docx";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  } catch (error) {
    showStatus(`Could not export the document: ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    downloadButton.disabled = false;
  }
}

async function start(): Promise<void> {
  await registerComponents();
  applyTheme("light");

  const editor = document.createElement("docen-document") as DocenDocument;
  editor.className = "demo-editor";
  editor.setAttribute("filename", "document.docx");
  // Seed a valid empty document so the component's initial Tiptap mount has a
  // node type. The requested fixture replaces it through openDOCX() below.
  editor.setAttribute(
    "content",
    JSON.stringify({ type: "doc", content: [{ type: "paragraph" }] }),
  );
  // The editor opens at 100%, wider than a phone; fit a Letter page (816 px) to a narrow screen.
  if (window.innerWidth < 860) {
    editor.setAttribute("zoom", String(Math.floor(((window.innerWidth - 32) / 816) * 100)));
  }
  document.body.prepend(editor);

  const demo = {
    editor,
    error: undefined as unknown,
    ready: undefined as Promise<void> | undefined,
  };
  Object.defineProperty(window, "__docenDemo", {
    configurable: true,
    value: demo,
  });

  downloadButton.addEventListener("click", () => {
    void downloadDocx(editor);
  });

  try {
    const response = await fetch("./document.docx");
    if (!response.ok) {
      throw new Error(`document.docx returned HTTP ${response.status}`);
    }

    // The editor's own format-specific loader delegates to @docen/docx's
    // parseDOCX(), the same import path measured by the trial harness.
    await editor.openDOCX(await response.arrayBuffer());
    mountDownloadButton(editor);
    demo.ready = Promise.resolve();
    document.body.dataset.demoReady = "true";
    downloadButton.disabled = false;
  } catch (error) {
    demo.error = error;
    showStatus(`Could not open the document: ${error instanceof Error ? error.message : String(error)}`);
    document.body.dataset.demoError = "true";
  }
}

void start();
