/**
 * docs.plus REST API stub — serves the DOCX import endpoint the webapp calls.
 *
 * The webapp posts to ${NEXT_PUBLIC_RESTAPI_URL}/documents/:documentId/import
 * (NEXT_PUBLIC_RESTAPI_URL is baked into the running dev server as
 * http://localhost:4000/api), so this server listens on 4000.
 *
 * The conversion itself is NOT re-implemented: it calls the product's own
 * domain function from the read-only repo,
 *   apps/hocuspocus.server/src/modules/document-conversion/domain/docxImport.ts
 * which is the exact function the real controller calls
 * (document-conversion/http/controller.ts -> importDocx(buffer, {...})).
 *
 * The only thing stubbed is the object-storage boundary the domain deliberately
 * does not own: `uploadImage` is injected by the caller. Here it parks the real
 * bytes in memory and serves them back from /media/<name>, so the picture
 * genuinely travels import -> rehost -> URL -> <img> instead of being dropped.
 *
 * Response shape mirrors the house envelope (apps/hocuspocus.server/src/http/envelope.ts):
 *   { success: true, data: { content, title, warnings } }
 */
import { createServer } from 'node:http'
import { Buffer } from 'node:buffer'

import { importDocx } from '/Users/arthrod/temp/T/editors_trial/repos/docs-plus/apps/hocuspocus.server/src/modules/document-conversion/domain/docxImport.ts'

const PORT = Number(process.env.STUB_PORT || 4000)
const HOST = process.env.STUB_HOST || '127.0.0.1'
const ORIGIN = `http://${HOST}:${PORT}`

/** The pad's object storage, stood in for by this process. */
const media = new Map<string, { bytes: Buffer; type: string }>()
let seq = 0

const EXT: Record<string, string> = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/jpg': 'jpg',
  'image/gif': 'gif',
  'image/webp': 'webp',
  'image/svg+xml': 'svg',
  'image/bmp': 'bmp'
}

const uploadImage = async (data: Buffer, contentType: string): Promise<string> => {
  const type = contentType || 'image/png'
  const name = `media/${++seq}.${EXT[type] || 'png'}`
  media.set(`/${name}`, { bytes: data, type })
  console.log(`[stub] uploadImage -> ${ORIGIN}/${name} (${data.length}B ${type})`)
  return `${ORIGIN}/${name}`
}

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  'Access-Control-Allow-Headers': 'token,content-type,authorization'
}

const json = (res: import('node:http').ServerResponse, status: number, body: unknown) => {
  const payload = JSON.stringify(body)
  res.writeHead(status, {
    ...CORS,
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload)
  })
  res.end(payload)
}

const readBody = (req: import('node:http').IncomingMessage): Promise<Buffer> =>
  new Promise((resolve, reject) => {
    const chunks: Buffer[] = []
    req.on('data', (c: Buffer) => chunks.push(c))
    req.on('end', () => resolve(Buffer.concat(chunks)))
    req.on('error', reject)
  })

const server = createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', ORIGIN)
  console.log(`[stub] ${req.method} ${url.pathname}`)

  if (req.method === 'OPTIONS') {
    res.writeHead(204, CORS)
    res.end()
    return
  }

  // media passthrough for the rehosted images
  if (req.method === 'GET' && url.pathname.startsWith('/media/')) {
    const hit = media.get(url.pathname)
    if (!hit) {
      res.writeHead(404, { 'Content-Type': 'text/plain' })
      res.end('not found')
      return
    }
    res.writeHead(200, {
      ...CORS,
      'Content-Type': hit.type,
      'Content-Length': hit.bytes.length,
      'Cache-Control': 'no-store'
    })
    res.end(hit.bytes)
    return
  }

  // POST /api/documents/:documentId/import
  if (req.method === 'POST' && /\/documents\/[^/]+\/import$/.test(url.pathname)) {
    try {
      const raw = await readBody(req)
      const form = await new Request('http://stub.local/', {
        method: 'POST',
        headers: { 'content-type': req.headers['content-type'] ?? '' },
        body: raw
      }).formData()

      const upload = form.get('documentFile')
      if (!(upload instanceof File)) {
        json(res, 400, { success: false, error: { message: 'missing documentFile', code: 'VALIDATION_ERROR' } })
        return
      }

      const buffer = Buffer.from(await upload.arrayBuffer())
      console.log(`[stub] import ${upload.name} (${buffer.length}B)`)

      const result = await importDocx(buffer, {
        fallbackTitle: 'Complex Fixture',
        uploadImage
      })

      console.log(
        `[stub] title=${JSON.stringify(result.title)} warnings=${result.warnings.length} ` +
          `nodes=${JSON.stringify(result.content).length}B`
      )
      json(res, 200, { success: true, data: result })
    } catch (error) {
      console.error('[stub] import failed', error)
      json(res, 422, {
        success: false,
        error: { message: error instanceof Error ? error.message : String(error), code: 'UNPROCESSABLE_ENTITY' }
      })
    }
    return
  }

  json(res, 404, { success: false, error: { message: 'no route', code: 'NOT_FOUND' } })
})

server.listen(PORT, HOST, () => {
  console.log(`[stub] docs.plus REST stub listening on ${ORIGIN}`)
  console.log(`[stub] import route: POST ${ORIGIN}/api/documents/:documentId/import`)
})
