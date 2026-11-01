/**
 * The mermaid extension loads its renderer on demand (`import('pele/lazy')`).
 * The static demo ships no wasm renderer, so the module resolves to a stub
 * that reports "renderer unavailable" instead of pulling a multi-megabyte
 * dependency into the bundle. The demo document has no mermaid block, so the
 * stub is never reached in practice.
 */
const unavailable = (): never => {
  throw new Error('The diagram renderer is not bundled in this static demo')
}

export const detectType = unavailable
export const load = unavailable
export const mount = unavailable
export const update = unavailable
export const destroy = unavailable

export default { detectType, load, mount, update, destroy }
