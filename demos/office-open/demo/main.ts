// office-open live demo for benchmarks.law: the library's own import and export, nothing else.
//   parseDocument(bytes)       → DocumentOptions   (packages/docx/src/parse.ts, the path the trial measured)
//   generateDocument(options)  → .docx bytes       (packages/docx/src/generate.ts)
// office-open has no editor UI, so the page shows what the parser produced instead.
import { generateDocument, parseDocument } from "@office-open/docx";
import { renderJsonTree, renderOutline } from "./outline";
import "./style.css";

const status = document.getElementById("status") as HTMLElement;
const download = document.getElementById("download") as HTMLButtonElement;
const show = (text: string, state = "") => {
	status.textContent = text;
	status.dataset.state = state;
};

let parsed: Awaited<ReturnType<typeof parseDocument>> | null = null;

async function open() {
	try {
		const res = await fetch("./document.docx");
		if (!res.ok) throw new Error(`document.docx returned HTTP ${res.status}`);
		parsed = await parseDocument(new Uint8Array(await res.arrayBuffer()));
		renderOutline(parsed as unknown as Record<string, unknown>, document.getElementById("outline") as HTMLElement);
		renderJsonTree(parsed, document.getElementById("json") as HTMLElement);
		show(`Parsed ${parsed.sections?.length ?? 0} section(s)`, "loaded");
		download.disabled = false;
	} catch (error) {
		show(`Could not parse the document: ${error instanceof Error ? error.message : String(error)}`, "error");
	}
}

download.addEventListener("click", async () => {
	if (!parsed) return;
	download.disabled = true;
	try {
		const bytes = (await generateDocument(parsed, { type: "uint8array" })) as Uint8Array;
		const url = URL.createObjectURL(new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }));
		const a = Object.assign(document.createElement("a"), { href: url, download: "document.docx" });
		document.body.append(a);
		a.click();
		a.remove();
		setTimeout(() => URL.revokeObjectURL(url), 5000);
		show(`Generated ${bytes.byteLength} bytes`, "loaded");
	} catch (error) {
		show(`Could not generate the document: ${error instanceof Error ? error.message : String(error)}`, "error");
	} finally {
		download.disabled = false;
	}
});

void open();
