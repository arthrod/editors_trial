// The Fidus Writer document library on the editors trial's fixture, in the browser.
//
// The same path the trial measured (harness/fidus/roundtrip.mts in arthrod/editors_trial):
//   ./document.docx -> DocxConvert (import) -> Fidus document -> DOCXExporter (export)
// with the Fidus document shown in between as an editable ProseMirror view on the library's
// own docSchema. Download exports whatever the view holds now, so edits go into the file.
// As in the scored run, the opened .docx is the export template.
import JSZip from "jszip"
import {CSL, createCSL} from "citeproc-plus"
import {EditorState} from "prosemirror-state"
import {EditorView} from "prosemirror-view"
import {history, undo, redo} from "prosemirror-history"
import {keymap} from "prosemirror-keymap"
import {baseKeymap} from "prosemirror-commands"

import {DocxConvert} from "../../dist/importer/docx/convert.js"
import {DOCXExporter} from "../../dist/exporter/docx/index.js"
import {docSchema} from "../../dist/schema/document/index.js"

const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
const status = document.getElementById("status")!
const button = document.getElementById("download") as HTMLButtonElement
const show = (text: string, state = "") => {
    status.textContent = text
    status.dataset.state = state
}

// The import template the Fidus Writer CLI uses by default (as in the trial's harness).
const part = (attrs: Record<string, unknown>) => ({
    locking: false, optional: false, help: "", deleted: false, hidden: false, language: "", ...attrs
})
const IMPORT_TEMPLATE = {
    content: {
        type: "doc",
        attrs: {
            import_id: "benchmarks-law-demo", template: "Default", papersize: "A4", papersizes: ["A4"],
            citationstyle: "apa", citationstyles: ["apa"], documentstyle: "default",
            language: "en-US", languages: ["en-US"], footnote_marks: [], footnote_elements: [],
            bibliography_header: {type: "text", content: [{type: "text", text: "Bibliography"}]},
            metadata: {}
        },
        content: [
            {type: "title"},
            {type: "contributors_part", attrs: part({id: "authors", metadata: "authors", title: "Authors"})},
            {
                type: "richtext_part",
                attrs: part({id: "body", title: "Body", initial: [{type: "paragraph"}], elements: ["paragraph"]}),
                content: [{type: "paragraph"}]
            },
            {type: "tags_part", attrs: part({metadata: "keywords", title: "Keywords"})}
        ]
    }
}

class BrowserDocxExporter extends DOCXExporter {
    download(blob: Blob): Promise<void> {
        const url = URL.createObjectURL(new Blob([blob], {type: DOCX}))
        const a = Object.assign(document.createElement("a"), {href: url, download: "document.docx"})
        document.body.append(a)
        a.click()
        a.remove()
        setTimeout(() => URL.revokeObjectURL(url), 10_000)
        return Promise.resolve()
    }
}

async function main() {
    const res = await fetch("./document.docx")
    if (!res.ok) throw new Error(`document.docx returned HTTP ${res.status}`)
    const bytes = await res.arrayBuffer()
    const importer = new DocxConvert(await JSZip.loadAsync(bytes), "benchmarks-law-demo", IMPORT_TEMPLATE as never, {})
    const imported = await importer.init()

    // The Fidus app resolves figures through docSchema.cached.imageDB (image id -> URL); hand it the
    // importer's own image blobs, or every figure renders as an empty <img>.
    const shown: Record<string, unknown> = {}
    for (const [id, entry] of Object.entries(importer.images ?? {})) {
        const e = entry as {file?: Blob, file_type?: string}
        if (e.file) shown[id] = {...e, image: URL.createObjectURL(e.file), file_type: e.file.type || e.file_type}
    }
    ;(docSchema as unknown as {cached: Record<string, unknown>}).cached.imageDB = {db: shown}

    const view = new EditorView(document.getElementById("editor")!, {
        state: EditorState.create({
            doc: docSchema.nodeFromJSON(imported.content),
            plugins: [history(), keymap({"Mod-z": undo, "Mod-y": redo, "Mod-Shift-z": redo}), keymap(baseKeymap)]
        })
    })
    ;(window as unknown as {fidusView: EditorView}).fidusView = view
    show("document.docx imported by @fiduswriter/document")
    button.disabled = false

    // Images: the importer keeps the binary in `file`; the exporter wants it as `image`.
    const imageDB = {db: {} as Record<string, unknown>}
    for (const [id, entry] of Object.entries(importer.images ?? {})) {
        const e = entry as {file?: Blob, image?: unknown, file_type?: string}
        imageDB.db[String(id)] = {...e, image: e.file ?? e.image, file_type: e.file?.type ?? e.file_type}
    }

    button.addEventListener("click", async () => {
        button.disabled = true
        try {
            const catalog = new CSL()
            const styles = await catalog.getStyles()
            const name = styles["apa"] ? "apa" : Object.keys(styles)[0]
            const csl = createCSL({[name]: await catalog.getStyle(name)})
            const content = view.state.doc.toJSON()
            const doc = {
                id: 1, path: "", content, settings: imported.settings, comments: imported.comments,
                title: content.content?.[0]?.content?.[0]?.text ?? "document"
            }
            const exporter = new BrowserDocxExporter(
                doc as never, "", {db: {}} as never, imageDB as never, csl as never, new Blob([bytes], {type: DOCX})
            )
            await exporter.init()
            show("Exported with DOCXExporter")
        } catch (error) {
            show(`Export failed: ${error instanceof Error ? error.message : String(error)}`, "error")
            console.error(error)
        } finally {
            button.disabled = false
        }
    })
}

main().catch(error => {
    show(`Could not open the document: ${error instanceof Error ? error.message : String(error)}`, "error")
    console.error(error)
})
