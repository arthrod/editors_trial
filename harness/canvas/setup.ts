import 'vitest-canvas-mock'
import { afterEach, vi } from 'vitest'

// Re-implementation of /repos/canvas-editor/tests/setup.ts (read-only checkout,
// cannot be used as a setupFile from outside the repo root).

class StubResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
class StubIntersectionObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): unknown[] {
    return []
  }
  root: Element | null = null
  rootMargin = ''
  thresholds: ReadonlyArray<number> = []
}
;(globalThis as any).ResizeObserver ??= StubResizeObserver
;(globalThis as any).IntersectionObserver ??= StubIntersectionObserver
;(Element.prototype as any).scrollIntoView ??= () => {}
;(Element.prototype as any).scroll ??= () => {}
;(SVGElement.prototype as any).getBBox ??= () => ({
  x: 0,
  y: 0,
  width: 0,
  height: 0
})
;(window as any).matchMedia = (query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: () => {},
  removeListener: () => {},
  addEventListener: () => {},
  removeEventListener: () => {},
  dispatchEvent: () => false
})

class StubWorker {
  onmessage: ((this: Worker, ev: MessageEvent) => any) | null = null
  onerror: ((this: AbstractWorker, ev: ErrorEvent) => any) | null = null
  postMessage(): void {}
  terminate(): void {}
  addEventListener(): void {}
  removeEventListener(): void {}
  dispatchEvent(): boolean {
    return false
  }
}
;(globalThis as any).Worker ??= StubWorker

// jsdom does not implement URL.createObjectURL / revokeObjectURL.
// The plugin's utils.saveAs() uses them, and the `docx` package's Packer.toBlob()
// path is Blob-only, but the DOM shim keeps the environment faithful.
if (!(window.URL as any).createObjectURL) {
  ;(window.URL as any).createObjectURL = (blob: Blob) => {
    const buf = (blob as any)._buffer
    return `blob:mock/${String(buf && buf.length)}`
  }
  ;(window.URL as any).revokeObjectURL = () => {}
}

afterEach(() => {
  vi.useRealTimers()
})
