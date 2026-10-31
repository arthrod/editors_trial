/**
 * A DOM realm for Plate's DOCX engine, in Node.
 *
 * Plate's import path calls `captureDocxDomRealm()`, which requires
 * globalThis.DOMParser, globalThis.XMLSerializer, globalThis.DOMException,
 * globalThis.HTMLElement and globalThis.Node.TEXT_NODE - it throws
 * "DOCX import requires a complete browser DOM realm." without them.
 *
 * happy-dom supplies the DOM, but its GlobalRegistrator also REPLACES the
 * global WritableStream and Blob with implementations that are not spec
 * compliant: happy-dom's Blob.stream() has no getWriter(), and its
 * WritableStream class has no getWriter() at all. @zip.js/zip.js - which
 * Plate uses to read the package - calls writable.getWriter() and dies with
 * "writable.getWriter is not a function".
 *
 * So: take happy-dom's DOM classes, and put Node's native stream and Blob
 * classes back.
 */
import { GlobalRegistrator } from '@happy-dom/global-registrator';
import { Blob as NodeBlob, File as NodeFile } from 'node:buffer';
import {
  ReadableStream as NodeReadableStream,
  WritableStream as NodeWritableStream,
  TransformStream as NodeTransformStream,
} from 'node:stream/web';

GlobalRegistrator.register();

const g = globalThis as any;

// happy-dom's DOM stays: DOMParser, XMLSerializer, HTMLElement, Node, Document
// Node's native streams and Blob come back: @zip.js/zip.js needs spec
// compliant ones.
g.WritableStream = NodeWritableStream;
g.ReadableStream = NodeReadableStream;
g.TransformStream = NodeTransformStream;
g.Blob = NodeBlob;
if (NodeFile) g.File = NodeFile;

export const domReady = {
  DOMParser: typeof g.DOMParser,
  XMLSerializer: typeof g.XMLSerializer,
  DOMException: typeof g.DOMException,
  HTMLElement: typeof g.HTMLElement,
  TEXT_NODE: g.Node?.TEXT_NODE,
  WritableStream: g.WritableStream?.name,
  Blob: g.Blob?.name,
};
