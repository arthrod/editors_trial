/**
 * Browser stand-in for the server's prom-client metrics registry.
 *
 * The conversion domain increments one counter when an export image is dropped.
 * The browser demo keeps the same call surface and records the drops on
 * `window.__docsPlusDemo` so the page can report them without a network call.
 */
interface Counter {
  inc: (labels?: Record<string, string | number>) => void
  reset: () => void
}

const createCounter = (name: string): Counter => {
  const counters = new Map<string, number>()
  const bump = (labels?: Record<string, string | number>): void => {
    const key = labels ? JSON.stringify(labels) : ''
    counters.set(key, (counters.get(key) ?? 0) + 1)
    const globalScope = globalThis as unknown as {
      __docsPlusDemo?: { metrics?: Record<string, unknown> }
    }
    const scope = (globalScope.__docsPlusDemo ??= {})
    const metrics = (scope.metrics ??= {})
    metrics[name] = Object.fromEntries(counters)
  }
  return {
    inc: bump,
    reset: () => counters.clear()
  }
}

export const documentExportImagesDroppedTotal = createCounter('document_export_images_dropped_total')
export const documentExportImagesInlinedTotal = createCounter('document_export_images_inlined_total')
export const documentImportImagesTotal = createCounter('document_import_images_total')
export const buildInfo = createCounter('docsplus_build_info')
export const httpRequestsTotal = createCounter('http_requests_total')
export const httpRequestDuration = createCounter('http_request_duration_seconds')
export const register = { metrics: () => '' }
