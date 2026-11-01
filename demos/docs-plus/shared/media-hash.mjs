/**
 * Byte hash shared by the build script (Node) and the runtime (browser).
 *
 * The imported images are re-hosted by the injected `uploadImage` boundary. A
 * static site cannot accept an upload, so the demo ships the document's media
 * next to it and hands back a same-folder URL. The bytes are matched to their
 * bundled file by this hash.
 */
export const hashBytes = (bytes) => {
  let hash = 0x811c9dc5
  for (let index = 0; index < bytes.length; index += 1) {
    hash ^= bytes[index]
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return `${(hash >>> 0).toString(16).padStart(8, '0')}-${bytes.length.toString(16)}`
}
