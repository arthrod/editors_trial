/**
 * docs.plus import endpoint stub — the one server the webapp needs to convert a
 * DOCX into editor content.
 *
 * The webapp posts to `${NEXT_PUBLIC_RESTAPI_URL}/documents/:documentId/import`
 * (apps/webapp/src/api/documents/importDocument.ts). The real controller
 * (apps/hocuspocus.server/src/modules/document-conversion/http/controller.ts)
 * only reads the upload and calls the domain function, so this stub does the
 * same thing with the same domain function:
 *
 *   importDocx(buffer, { fallbackTitle, uploadImage })
 *
 * Nothing about the conversion is re-implemented. The only stub is the object
 * storage boundary the domain deliberately does not own (`uploadImage`): the
 * bytes are parked in memory and served back from /media/<name>, so pictures
 * travel import -> rehost -> URL -> <img> for real.
 *
 * Response envelope mirrors apps/hocuspocus.server/src/http/envelope.ts:
 *   { success: true, data: { content, title, warnings } }
 *
 * Run:  bun restapi.ts          (STUB_PORT defaults to 4210)
 */
import { Buffer } from 'node:buffer'
import { createServer } from 'node:http'

import { importDocx } from '../../../../repos/docs-plus/apps/hocuspocus.server/src/modules/document-conversion/domain/docxImport.ts'

const PORT = Number(process.env.STUB_PORT || 4210)
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
    const started = Date.now()
    try {
      const raw = await readBody(req)
      const form = await new Request('http://stub.local/', {
        method: 'POST',
        headers: { 'content-type': req.headers['content-type'] ?? '' },
        body: raw
      }).formData()

      const upload = form.get('documentFile')
      if (!(upload instanceof File)) {
        json(res, 400, {
          success: false,
          error: { message: 'missing documentFile', code: 'VALIDATION_ERROR' }
        })
        return
      }

      const buffer = Buffer.from(await upload.arrayBuffer())
      const result = await importDocx(buffer, {
        fallbackTitle: 'Harness Corpus',
        uploadImage
      })

      console.log(
        `[stub] import ${upload.name} ${buffer.length}B -> title=${JSON.stringify(result.title)} ` +
          `warnings=${result.warnings.length} in ${Date.now() - started}ms`
      )
      json(res, 200, { success: true, data: result })
    } catch (error) {
      console.error('[stub] import failed', error)
      json(res, 422, {
        success: false,
        error: {
          message: error instanceof Error ? error.message : String(error),
          code: 'UNPROCESSABLE_ENTITY'
        }
      })
    }
    return
  }

  json(res, 404, { success: false, error: { message: 'no route', code: 'NOT_FOUND' } })
})

server.listen(PORT, HOST, () => {
  console.log(`[stub] docs.plus import endpoint on ${ORIGIN}/api/documents/:id/import`)
})
