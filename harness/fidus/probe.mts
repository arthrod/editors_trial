// Probe: can we load the Fidus document library modules in plain Node?
const results: Record<string, string> = {}

try {
    const fw = await import("fwtoolkit")
    results["fwtoolkit"] = "OK exports=" + Object.keys(fw).length
} catch (e: any) {
    results["fwtoolkit"] = "FAIL: " + e.message
}

try {
    const dj = await import("downloadjs")
    results["downloadjs"] = "OK default=" + typeof dj.default
} catch (e: any) {
    results["downloadjs"] = "FAIL: " + e.message
}

try {
    const {DocxConvert} = await import(
        "/Users/arthrod/temp/T/editors_trial/repos/fiduswriter-document-ts/src/importer/docx/convert.js"
    )
    results["importer/convert"] = "OK " + typeof DocxConvert
} catch (e: any) {
    results["importer/convert"] = "FAIL: " + e.message
}

try {
    const {DOCXExporter} = await import(
        "/Users/arthrod/temp/T/editors_trial/repos/fiduswriter-document-ts/src/exporter/docx/index.js"
    )
    results["exporter/docx"] = "OK " + typeof DOCXExporter
} catch (e: any) {
    results["exporter/docx"] = "FAIL: " + e.message
}

try {
    const t = await import(
        "/Users/arthrod/temp/T/editors_trial/repos/fiduswriter-document-ts/src/exporter/template/docx.js"
    )
    results["exporter/template/docx"] = "OK " + typeof t.generateDocxTemplate
} catch (e: any) {
    results["exporter/template/docx"] = "FAIL: " + e.message
}

console.log(JSON.stringify(results, null, 2))
