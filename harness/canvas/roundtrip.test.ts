import { describe, it, expect, vi } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const TRIAL_ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '../..')

// The real WorkerManager spins up `?worker&inline` web workers, which need a
// working Blob/Worker/URL.createObjectURL stack that jsdom does not provide.
// Mirror the repo's own tests/factories/editor.ts mock (path must be a literal
// because vi.mock is hoisted above const declarations; it is relative to this
// test file so it resolves on any host, not only the CI agent's checkout).
vi.mock(
  '../../repos/canvas-editor/src/editor/core/worker/WorkerManager.ts',
  () => {
    class MockWorkerManager {
      private draw: any
      constructor(draw: any) {
        this.draw = draw
      }
      getWordCount(): Promise<number> {
        return Promise.resolve(0)
      }
      getCatalog(): Promise<null> {
        return Promise.resolve(null)
      }
      getGroupIds(): Promise<string[]> {
        return Promise.resolve([])
      }
      getValue(options?: any): Promise<any> {
        const data = this.draw.getOriginValue
          ? this.draw.getOriginValue(options)
          : { main: [] }
        return Promise.resolve({
          version: '0.9.132',
          data,
          options: {}
        })
      }
      destroy(): void {}
    }
    return { WorkerManager: MockWorkerManager }
  }
)

import Editor from '@hufe921/canvas-editor'
import docxPlugin from '@hufe921/canvas-editor-plugin-docx'
import { TableParticle } from '@/editor/core/draw/particle/table/TableParticle'

const FIXTURE = process.env.VITEST_DOCX_INPUT
  || process.env.IN_DOCX
  || path.join(TRIAL_ROOT, 'fixture/complex.docx')
const OUT_DIR = process.env.OUT_DIR
  || path.join(TRIAL_ROOT, 'out/canvas')
const OUT_DOCX = process.env.VITEST_DOCX_OUTPUT
  ? path.resolve(process.env.VITEST_DOCX_OUTPUT)
  : path.join(OUT_DIR, 'complex.docx')
const PERF_ONLY = process.env.PERF_ONLY === '1'

// ---------------------------------------------------------------------------
// Harness instrumentation (NOT a repo change): wrap the editor's table layout
// routine so we can record exactly which imported table blows up, and so a
// grid/render inconsistency does not abort the round trip.
// ---------------------------------------------------------------------------
const tableFindings: unknown[] = []
const originalComputeRowColInfo =
  TableParticle.prototype.computeRowColInfo.bind(TableParticle.prototype)
;(TableParticle.prototype as any).computeRowColInfo = function (
  element: any
) {
  try {
    return originalComputeRowColInfo(element)
  } catch (e) {
    const colgroup = element?.colgroup || []
    const trList = element?.trList || []
    tableFindings.push({
      error: (e as Error).message,
      colgroupLength: colgroup.length,
      colgroupWidths: colgroup.map((c: any) => c?.width),
      rows: trList.map((tr: any) => ({
        height: tr?.height,
        tds: (tr?.tdList || []).map((td: any) => ({
          colspan: td?.colspan,
          rowspan: td?.rowspan,
          colIndex: td?.colIndex,
          rowIndex: td?.rowIndex
        }))
      }))
    })
    throw e
  }
}

function toArrayBuffer(buf: Buffer): ArrayBuffer {
  // JSZip is evaluated inside the same (jsdom) realm as this test file and
  // dispatches on `input instanceof ArrayBuffer`. A Buffer's underlying
  // ArrayBuffer belongs to the Node realm, so `instanceof` fails there.
  // Copy the bytes into a fresh Uint8Array of THIS realm and hand back its
  // (same-realm) ArrayBuffer.
  const u8 = new Uint8Array(buf.byteLength)
  u8.set(buf)
  return u8.buffer
}

// crude visible-text probe over the editor's in-memory element list
function modelText(elements: any[]): string {
  if (!Array.isArray(elements)) return ''
  let out = ''
  const walk = (list: any[]) => {
    for (const el of list) {
      if (!el) continue
      if (typeof el.value === 'string') out += el.value
      if (Array.isArray(el.trList)) {
        for (const tr of el.trList) {
          if (Array.isArray(tr.tdList)) for (const td of tr.tdList) walk(td.value || [])
        }
      }
      if (Array.isArray(el.children)) walk(el.children)
    }
  }
  walk(elements)
  return out
}

function modelSummary(elements: any[]): Record<string, number> {
  const s: Record<string, number> = {
    total: 0,
    text: 0,
    table: 0,
    image: 0,
    hyperlink: 0,
    control: 0,
    list: 0,
    checkbox: 0,
    withStyle: 0
  }
  const walk = (list: any[]) => {
    for (const el of list) {
      if (!el) continue
      s.total++
      if (el.type === 'table') s.table++
      if (el.type === 'image') s.image++
      if (el.type === 'hyperlink') s.hyperlink++
      if (el.type === 'control') s.control++
      if (el.type === 'checkbox') s.checkbox++
      if (el.listType) s.list++
      if (el.style || el.bold || el.italic || el.size) s.withStyle++
      if (typeof el.value === 'string' && el.value.trim()) s.text++
      if (Array.isArray(el.trList)) {
        for (const tr of el.trList) {
          if (Array.isArray(tr.tdList))
            for (const td of tr.tdList) walk(td.value || [])
        }
      }
      if (Array.isArray(el.children)) walk(el.children)
    }
  }
  walk(elements)
  return s
}

describe('canvas-editor docx plugin round trip', () => {
  it('imports complex.docx and exports it back to .docx', async () => {
    fs.mkdirSync(path.dirname(OUT_DOCX), { recursive: true })
    if (!PERF_ONLY) fs.mkdirSync(OUT_DIR, { recursive: true })

    const fixtureBytes = fs.readFileSync(FIXTURE)
    const arrayBuffer = toArrayBuffer(fixtureBytes)

    // --- create the editor (repo recipe: tests/factories/editor.ts) ---
    const container = document.createElement('div')
    container.style.width = '794px'
    container.style.height = '1123px'
    document.body.appendChild(container)

    const editor = new Editor(
      container,
      { header: [], main: [{ value: '\n' }], footer: [] } as any,
      {
        width: 794,
        height: 1123,
        margins: [100, 120, 100, 120]
      } as any
    )

    // --- register the docx plugin ---
    docxPlugin(editor)
    const cmd = editor.command as any
    expect(typeof cmd.executeImportDocx).toBe('function')
    expect(typeof cmd.executeExportDocx).toBe('function')

    // --- IMPORT ---
    let importError: unknown = null
    try {
      const t0 = performance.now()
      await cmd.executeImportDocx({ arrayBuffer })
      const t1 = performance.now()
      const line = `PERF model_ready_ms=${(t1 - t0).toFixed(6)}\n`
      if (PERF_ONLY) process.stdout.write(line)
      else console.log(line.trimEnd())
      if (process.env.PERF_MARK_PATH) {
        fs.appendFileSync(process.env.PERF_MARK_PATH, line, 'utf8')
      }
    } catch (e) {
      importError = e
    }
    if (importError) {
      // capture the exact failure and still dump whatever the editor holds
      if (!PERF_ONLY) fs.writeFileSync(
        path.join(OUT_DIR, 'import_error.txt'),
        ((importError as Error).stack || String(importError)) +
          '\n\n--- table findings ---\n' +
          JSON.stringify(tableFindings, null, 2)
      )
      // The plugin README's path is import, then export. A thrown import is
      // the editor refusing the file. Writing the blank starter document
      // afterwards would be this harness, not canvas-editor. A speed sample
      // (PERF_ONLY) fails here too: no save time for a half-loaded editor.
      if (process.env.EDITOR_CONFIG === 'suggested' || PERF_ONLY) {
        throw importError
      }
    }

    // give the editor a chance to flush its async render pipeline
    await new Promise(r => setTimeout(r, 500))

    const imported = PERF_ONLY ? undefined : cmd.getValue()
    const main = imported?.data?.main || []
    const summary = PERF_ONLY ? undefined : modelSummary(main)
    const text = PERF_ONLY ? '' : modelText(main)

    // --- EXPORT (download:false -> return the Blob, never touch document.body) ---
    const tSave0 = performance.now()
    const blob: Blob = await cmd.executeExportDocx({
      fileName: 'complex',
      download: false
    })
    const tSave1 = performance.now()
    const saveLine = `PERF save_ms=${(tSave1 - tSave0).toFixed(6)}\n`
    if (PERF_ONLY) process.stdout.write(saveLine)
    else console.log(saveLine.trimEnd())
    if (process.env.PERF_MARK_PATH) {
      fs.appendFileSync(process.env.PERF_MARK_PATH, saveLine, 'utf8')
    }
    const outBuf = Buffer.from(await blob.arrayBuffer())
    fs.writeFileSync(OUT_DOCX, outBuf)

    if (!PERF_ONLY) {
      // --- evidence dumps ---
      fs.writeFileSync(
        path.join(OUT_DIR, 'model_summary.json'),
        JSON.stringify(
          {
            fixtureBytes: fixtureBytes.length,
            outputBytes: outBuf.length,
            model: summary,
            modelTextLength: text.length,
            modelTextHead: text.slice(0, 2000),
            importError: importError
              ? (importError as Error).stack || String(importError)
              : null,
            tableFindings,
            editorOptions: imported?.options
          },
          null,
          2
        )
      )
      fs.writeFileSync(
        path.join(OUT_DIR, 'model.json'),
        JSON.stringify(imported?.data ?? null, null, 2)
      )
    }

    expect(outBuf.length).toBeGreaterThan(0)
  }, 170000)
})
