/**
 * Perf host front door for docs.plus.
 *
 * The editor is the product's own webapp (Next.js dev server, started by
 * start.sh on an internal port). The app has no "open this DOCX" URL, so the
 * host puts one script tag into the /editor HTML — nothing else about the app
 * is touched, and nothing under repos/ is modified:
 *
 *   GET /editor  ->  proxied from Next, with
 *                    <script type="module" src="/__perf/bridge.js"> appended
 *   GET /__perf/bridge.js     ->  bridge.js from this directory
 *   GET /corpus.docx          ->  the fixture on disk (the perf probe fulfils
 *                                 this route itself; this is for manual runs)
 *   GET /__perf/healthz       ->  200 once this process is listening
 *
 * WebSocket upgrades (Next HMR) are piped through unchanged.
 *
 * Env: PORT (5215), UPSTREAM_PORT (5216), CORPUS_FILE, CORPUS_ROUTE (/corpus.docx)
 */
import fs from 'node:fs'
import http from 'node:http'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const PORT = Number(process.env.PORT || 5215)
const UPSTREAM_PORT = Number(process.env.UPSTREAM_PORT || 5216)
const UPSTREAM_HOST = '127.0.0.1'
const CORPUS_ROUTE = process.env.CORPUS_ROUTE || '/corpus.docx'
const CORPUS_FILE =
  process.env.CORPUS_FILE || path.resolve(here, '../../../../fixture/complex.docx')
const BRIDGE_FILE = path.join(here, 'bridge.js')

const REST_URL = process.env.REST_URL || 'http://127.0.0.1:4210/api'
const INJECT =
  `<script>window.__PERF_HOST__ = ${JSON.stringify({
    rest: REST_URL,
    corpusRoute: CORPUS_ROUTE,
  })};</script>` + '<script type="module" src="/__perf/bridge.js"></script>'

const log = (...args) => console.log('[host]', ...args)

const sendError = (res, status, message) => {
  res.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8' })
  res.end(message)
}

const injectBridge = (html) => {
  const at = html.lastIndexOf('</body>')
  if (at === -1) return html + INJECT
  return `${html.slice(0, at)}${INJECT}${html.slice(at)}`
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url ?? '/', `http://${req.headers.host ?? '127.0.0.1'}`)

  if (url.pathname === '/__perf/healthz') {
    res.writeHead(200, { 'Content-Type': 'text/plain' })
    res.end('ok')
    return
  }

  if (url.pathname === '/__perf/bridge.js') {
    fs.readFile(BRIDGE_FILE, (error, bytes) => {
      if (error) return sendError(res, 500, `bridge.js: ${error.message}`)
      res.writeHead(200, {
        'Content-Type': 'text/javascript; charset=utf-8',
        'Content-Length': bytes.length,
        'Cache-Control': 'no-store'
      })
      res.end(bytes)
    })
    return
  }

  if (url.pathname === CORPUS_ROUTE) {
    fs.readFile(CORPUS_FILE, (error, bytes) => {
      if (error) return sendError(res, 404, `corpus not found: ${CORPUS_FILE}`)
      res.writeHead(200, {
        'Content-Type':
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'Content-Length': bytes.length,
        'Cache-Control': 'no-store'
      })
      res.end(bytes)
    })
    return
  }

  const headers = { ...req.headers, host: `${UPSTREAM_HOST}:${UPSTREAM_PORT}` }
  // Ask for the identity encoding so HTML can be edited in place.
  delete headers['accept-encoding']
  delete headers.connection

  const upstream = http.request(
    { host: UPSTREAM_HOST, port: UPSTREAM_PORT, method: req.method, path: req.url, headers },
    (up) => {
      const type = String(up.headers['content-type'] || '')
      if (!type.includes('text/html')) {
        res.writeHead(up.statusCode ?? 502, up.headers)
        up.pipe(res)
        return
      }
      const chunks = []
      up.on('data', (c) => chunks.push(c))
      up.on('end', () => {
        const body = Buffer.from(injectBridge(Buffer.concat(chunks).toString('utf8')), 'utf8')
        const outHeaders = { ...up.headers }
        delete outHeaders['content-length']
        delete outHeaders['content-encoding']
        outHeaders['content-length'] = String(body.length)
        outHeaders['cache-control'] = 'no-store'
        res.writeHead(up.statusCode ?? 502, outHeaders)
        res.end(body)
      })
    }
  )
  upstream.on('error', (error) => {
    if (!res.headersSent) sendError(res, 503, `upstream not ready: ${error.message}`)
    else res.end()
  })
  req.pipe(upstream)
})

// Next's dev client opens a WebSocket for HMR; break it and the page still
// works but floods the console, so pipe upgrades through.
server.on('upgrade', (req, socket, head) => {
  const upstream = net.connect(UPSTREAM_PORT, UPSTREAM_HOST, () => {
    const lines = [`${req.method} ${req.url} HTTP/1.1`]
    for (let i = 0; i < req.rawHeaders.length; i += 2) {
      lines.push(`${req.rawHeaders[i]}: ${req.rawHeaders[i + 1]}`)
    }
    upstream.write(`${lines.join('\r\n')}\r\n\r\n`)
    if (head?.length) upstream.write(head)
    socket.pipe(upstream)
    upstream.pipe(socket)
  })
  upstream.on('error', () => socket.destroy())
  socket.on('error', () => upstream.destroy())
})

server.listen(PORT, '127.0.0.1', () => {
  log(`docs.plus host on http://127.0.0.1:${PORT}/editor (upstream :${UPSTREAM_PORT})`)
  log(`corpus route ${CORPUS_ROUTE} -> ${CORPUS_FILE}`)
})
