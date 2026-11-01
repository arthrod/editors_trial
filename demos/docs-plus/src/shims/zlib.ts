/**
 * Browser stand-in for `node:zlib`.
 *
 * The conversion domain's ZIP writer (`zipWriter.ts`) and its zip-bomb guard
 * (`zipInflateSize.ts`) use `crc32`, `deflateRawSync` and `inflateRawSync`.
 * fflate provides the deflate/inflate primitives in the browser; the CRC-32
 * (the ZIP polynomial, identical to Node's `zlib.crc32`) is implemented here
 * because fflate does not export one.
 *
 * Node's `zlib.inflateRawSync` stops at `maxOutputLength` while it inflates.
 * fflate's synchronous inflate allocates the whole result, so the guard is
 * implemented with fflate's streaming `Inflate`: the running total is checked
 * on every chunk and the call throws as soon as the budget is passed — the
 * same "measured inflate, not declared size" contract the domain relies on.
 */
import { deflateSync, Inflate } from 'fflate'

type Bytes = Uint8Array

const CRC_TABLE = (() => {
  const table = new Uint32Array(256)
  for (let index = 0; index < 256; index += 1) {
    let value = index
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1
    }
    table[index] = value >>> 0
  }
  return table
})()

export const crc32 = (bytes: Bytes): number => {
  let crc = 0xffffffff
  for (let index = 0; index < bytes.length; index += 1) {
    crc = CRC_TABLE[(crc ^ bytes[index]) & 0xff] ^ (crc >>> 8)
  }
  return (crc ^ 0xffffffff) >>> 0
}

export const deflateRawSync = (bytes: Bytes): Uint8Array => deflateSync(bytes)

/** fflate's stream chunks are views into a reused buffer: copy before keeping one. */
const inflateChunks = (bytes: Bytes, max: number | undefined): Uint8Array => {
  const chunks: Uint8Array[] = []
  let total = 0
  const inflate = new Inflate((chunk: Uint8Array) => {
    const copy = chunk.slice()
    total += copy.length
    if (max !== undefined && total > max) {
      throw new Error('maxOutputLength exceeded')
    }
    chunks.push(copy)
  })
  inflate.push(bytes, true)
  const out = new Uint8Array(total)
  let at = 0
  for (const chunk of chunks) {
    out.set(chunk, at)
    at += chunk.length
  }
  return out
}

export const inflateRawSync = (
  bytes: Bytes,
  options?: { maxOutputLength?: number }
): Uint8Array => inflateChunks(bytes, options?.maxOutputLength)
