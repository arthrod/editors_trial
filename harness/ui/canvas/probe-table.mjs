/**
 * Probe: dumps the table model that the DOCX importer hands to the editor,
 * captured before the editor's layout pass runs, plus the imported document
 * skeleton. Everything the simulation needs is preserved verbatim.
 */
export async function probe(page) {
  return await page.evaluate(() => {
    const data = window.__SET_VALUE_DATA__
    if (!data) {
      return {
        error: 'no __SET_VALUE_DATA__ captured',
        docxError: window.__DOCX_ERROR__ || null
      }
    }
    const tables = []
    const walk = (list, depth, path) => {
      let i = 0
      for (const el of list || []) {
        if (el && el.type === 'table') {
          tables.push({
            depth,
            path,
            colgroup: (el.colgroup || []).map(c => ({ width: c.width })),
            trList: (el.trList || []).map((tr, ri) => ({
              ri,
              height: tr.height,
              tdList: (tr.tdList || []).map((td, di) => ({
                di,
                colIndex: td.colIndex === undefined ? null : td.colIndex,
                colspan: td.colspan,
                rowspan: td.rowspan,
                text: (td.value || [])
                  .map(v => (typeof v.value === 'string' ? v.value : ''))
                  .join('')
                  .slice(0, 30),
                childTables: (td.value || [])
                  .filter(v => v && v.type === 'table')
                  .length
              }))
            }))
          })
          for (const tr of el.trList || []) {
            for (const td of tr.tdList || []) walk(td.value, depth + 1, `${path}/${td.di}`)
          }
        }
        i++
      }
    }
    walk(data.main, 0, 'main')

    // Skeleton of the imported document (element types + text) so we can see
    // how much of the corpus made it into the editor model at all.
    const skeleton = []
    const skel = (list, depth) => {
      for (const el of list || []) {
        skeleton.push({
          depth,
          type: el.type,
          text:
            typeof el.value === 'string'
              ? el.value.slice(0, 40)
              : Array.isArray(el.value)
                ? ''
                : ''
        })
        if (el.type === 'table') {
          for (const tr of el.trList || []) {
            for (const td of tr.tdList || []) skel(td.value, depth + 1)
          }
        }
      }
    }
    skel(data.main, 0)

    return {
      imported: !!window.__DOCX_IMPORTED__,
      pageSize: window.__PAGE_SIZE__ ?? null,
      docxError: window.__DOCX_ERROR__ || null,
      counts: {
        mainLen: (data.main || []).length,
        headerLen: (data.header || []).length,
        footerLen: (data.footer || []).length
      },
      tables,
      skeleton
    }
  })
}
