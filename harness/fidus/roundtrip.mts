/**
 * Fidus Writer document library round-trip harness.
 *
 *   input.docx -> DocxConvert (import) -> Fidus doc model -> DOCXExporter (export) -> output.docx
 *
 * Run from the repo dir so workspace resolution works:
 *   cd repos/fiduswriter-document-ts && ./node_modules/.bin/tsx --no-cache \
 *       /Users/arthrod/temp/T/editors_trial/harness/fidus/roundtrip.mts
 *
 * Env:
 *   IN_DOCX   input path
 *   OUT_DOCX  output path
 *   TEMPLATE  "generated" (library default template) | "original" (input docx as export template)
 */
import {readFile, writeFile} from "node:fs/promises"

import JSZip from "jszip"
import {CSL, createCSL} from "citeproc-plus"

const REPO = "/Users/arthrod/temp/T/editors_trial/repos/fiduswriter-document-ts"

const {DocxConvert} = await import(`${REPO}/src/importer/docx/convert.js`)
const {DOCXExporter} = await import(`${REPO}/src/exporter/docx/index.js`)
const {generateDocxTemplate} = await import(`${REPO}/src/exporter/template/docx.js`)

const IN_DOCX = process.env.IN_DOCX ?? "/Users/arthrod/temp/T/editors_trial/fixture/complex.docx"
const OUT_DOCX = process.env.OUT_DOCX ?? "/Users/arthrod/temp/T/editors_trial/out/fidus/complex.docx"
const TEMPLATE_MODE = process.env.TEMPLATE ?? "generated"

/** Fidus document template used for the import (mirrors the CLI default template). */
const IMPORT_TEMPLATE = {
    content: {
        type: "doc",
        attrs: {
            import_id: "fidus-trial",
            template: "Default",
            papersize: "A4",
            papersizes: ["A4"],
            citationstyle: "apa",
            citationstyles: ["apa"],
            documentstyle: "default",
            language: "en-US",
            languages: ["en-US"],
            footnote_marks: [],
            footnote_elements: [],
            bibliography_header: {
                type: "text",
                content: [{type: "text", text: "Bibliography"}]
            },
            metadata: {}
        },
        content: [
            {type: "title"},
            {
                type: "contributors_part",
                attrs: {
                    id: "authors",
                    metadata: "authors",
                    title: "Authors",
                    locking: false,
                    optional: false,
                    help: "",
                    deleted: false,
                    hidden: false,
                    language: ""
                }
            },
            {
                type: "richtext_part",
                attrs: {
                    id: "body",
                    title: "Body",
                    locking: false,
                    optional: false,
                    help: "",
                    deleted: false,
                    hidden: false,
                    language: "",
                    initial: [{type: "paragraph"}],
                    elements: ["paragraph"]
                },
                content: [{type: "paragraph"}]
            },
            {
                type: "tags_part",
                attrs: {
                    metadata: "keywords",
                    title: "Keywords",
                    locking: false,
                    optional: false,
                    help: "",
                    deleted: false,
                    hidden: false,
                    language: ""
                }
            }
        ]
    }
}

/** Captures the exported blob instead of triggering a browser download. */
class CapturingDocxExporter extends DOCXExporter {
    captured: Blob | null = null
    download(blob: Blob): Promise<void> {
        this.captured = blob
        return Promise.resolve()
    }
}

function nodeStats(node: any, acc: Record<string, number> = {}): Record<string, number> {
    acc[node.type] = (acc[node.type] ?? 0) + 1
    ;(node.content ?? []).forEach((child: any) => nodeStats(child, acc))
    return acc
}

const inputBuffer = await readFile(IN_DOCX)

// ---------------------------------------------------------------- import ----
const inputZip = await JSZip.loadAsync(inputBuffer)
const importer = new DocxConvert(inputZip, "fidus-trial", IMPORT_TEMPLATE as any, {})
const t0 = performance.now()
const imported = await importer.init()
const t1 = performance.now()
console.log(`PERF model_ready_ms=${(t1 - t0).toFixed(6)}`)
console.log(
    "IMPORT OK: doc nodes:",
    imported.content.content?.length,
    "node types:",
    JSON.stringify(nodeStats(imported.content))
)
console.log("IMPORT settings:", JSON.stringify(imported.settings))
console.log("IMPORT comments:", Object.keys(imported.comments ?? {}).length)
console.log("IMPORT comments data:", JSON.stringify(imported.comments))

if (process.env.DUMP) {
    await writeFile(
        process.env.DUMP,
        JSON.stringify(
            {
                content: imported.content,
                settings: imported.settings,
                comments: imported.comments,
                imageIds: Object.keys(importer.images ?? {})
            },
            null,
            2
        )
    )
    console.log("dumped imported model ->", process.env.DUMP)
}

// ---------------------------------------------------------------- export ----
// Images: the importer keeps the binary in `file` and the bare filename in
// `image`; the exporter wants `image` to be a Blob, so hand it over directly.
const imageDB = {db: {}}
for (const [id, entry] of Object.entries(importer.images ?? {})) {
    const blob = (entry as any).file as Blob | undefined
    imageDB.db[String(id)] = {
        ...entry,
        image: blob ?? (entry as any).image,
        file_type: blob?.type ?? (entry as any).file_type
    }
}
console.log("EXPORT images in db:", Object.keys(imageDB.db).length)

const bibDB = {db: {}} as any

const catalog = new CSL()
const styles = await catalog.getStyles()
const styleName = styles["apa"] ? "apa" : Object.keys(styles)[0]
const style = await catalog.getStyle(styleName)
const csl = createCSL({[styleName]: style}) as any

const title =
    (imported.content.content?.[0] as any)?.content?.[0]?.text ?? "Untitled"

const doc = {
    id: 1,
    title,
    path: "",
    content: imported.content,
    settings: imported.settings,
    comments: imported.comments
}

let templateBlob: Blob
if (TEMPLATE_MODE === "original") {
    templateBlob = new Blob([inputBuffer], {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    })
    console.log("EXPORT template: ORIGINAL input docx")
} else {
    templateBlob = await generateDocxTemplate(doc.content as any)
    console.log("EXPORT template: library generated (generateDocxTemplate)")
}

const exporter = new CapturingDocxExporter(doc, "", bibDB, imageDB, csl, templateBlob)
await exporter.init()

if (!exporter.captured) {
    throw new Error("export produced no blob")
}
const outBytes = Buffer.from(await exporter.captured.arrayBuffer())
await writeFile(OUT_DOCX, outBytes)
console.log(`EXPORT OK bytes: ${outBytes.length} -> ${OUT_DOCX}`)
