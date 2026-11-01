/**
 * Node globals the docs.plus server code expects.
 *
 * Imported first by `main.ts` so the globals exist before any module that
 * touches them is evaluated.
 */
import { Buffer } from 'buffer'

const scope = globalThis as unknown as Record<string, unknown>

if (!scope.Buffer) scope.Buffer = Buffer
// `@turbodocx/html-to-docx`'s browser build reads `global.Buffer`.
if (!scope.global) scope.global = scope

export {}
