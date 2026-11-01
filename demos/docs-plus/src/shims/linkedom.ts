/**
 * Browser stand-in for linkedom.
 *
 * `documentHtml.ts` (the product's HTML <-> Tiptap bridge) parses and serializes
 * with linkedom, because the server has no DOM. In a browser the real DOM is
 * both available and stricter, so `parseHTML` is backed by the browser's own
 * `DOMParser`. The call signature is unchanged.
 */
export const parseHTML = (html: string): { document: Document } => {
  const document = new DOMParser().parseFromString(html, 'text/html')
  return { document }
}

export const serializeHTML = (document: Document): string =>
  new XMLSerializer().serializeToString(document)

export default { parseHTML, serializeHTML }
