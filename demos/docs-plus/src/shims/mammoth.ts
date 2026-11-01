/**
 * Browser adapter for mammoth.
 *
 * docs.plus' importer (`docxImport.ts`) calls `mammoth.convertToHtml({ buffer }, ...)`
 * because it runs on Bun/Node. mammoth ships an official browser build whose
 * unzip entry point only accepts `{ arrayBuffer }`, so this adapter is the whole
 * difference between the two platforms: the product code stays untouched.
 *
 * The browser build is mammoth's own (mammoth.browser.min.js, shipped in the
 * npm package) and carries its own `Buffer` polyfill, so `image.readAsBuffer()`
 * keeps working for the injected `uploadImage` boundary.
 */
import mammoth from 'mammoth/mammoth.browser.min.js'

type MammothInput = { buffer?: unknown; arrayBuffer?: ArrayBuffer } & Record<string, unknown>

const toArrayBuffer = (value: unknown): ArrayBuffer => {
  const bytes =
    value instanceof ArrayBuffer
      ? new Uint8Array(value)
      : ArrayBuffer.isView(value)
        ? new Uint8Array(value.buffer, value.byteOffset, value.byteLength)
        : new Uint8Array(value as ArrayLike<number>)
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)
}

export const convertToHtml = (input: MammothInput, options?: unknown): Promise<unknown> => {
  if (input && !input.arrayBuffer && input.buffer !== undefined) {
    return mammoth.convertToHtml({ arrayBuffer: toArrayBuffer(input.buffer) }, options)
  }
  return mammoth.convertToHtml(input, options)
}

export const convertToMarkdown = mammoth.convertToMarkdown
export const images = mammoth.images
export const transformDocument = mammoth.transformDocument
export const underline = mammoth.underline
export const embedStyleMap = mammoth.embedStyleMap
export const readEmbeddedStyleMap = mammoth.readEmbeddedStyleMap

export default {
  convertToHtml,
  convertToMarkdown,
  images,
  transformDocument,
  underline,
  embedStyleMap,
  readEmbeddedStyleMap
}
