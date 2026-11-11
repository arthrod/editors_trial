/*
 * B5's fake hosts read the corpus .docx in the browser.
 *
 * The corpus is the same prose-50kw document the production lane measures: a
 * real DOCX package, served at /corpus.docx. The fake host unpacks it (the
 * ZIP central directory, then `DecompressionStream('deflate-raw')` for the
 * deflated entries) and renders the paragraphs of `word/document.xml`, so the
 * page really is as tall as the document the lane claims to measure.
 *
 * Nothing here is measured: the fake hosts exist so the probe's *contract*
 * (a container is found, the scroll moves, a shadow root is searched) can be
 * checked without an editor.
 */
window.__b5 = (function () {
  'use strict';

  function u16(view, offset) {
    return view.getUint16(offset, true);
  }

  function u32(view, offset) {
    return view.getUint32(offset, true);
  }

  async function inflate(bytes, method) {
    if (method === 0) return bytes;
    if (method !== 8) throw new Error('unsupported zip compression method ' + method);
    const stream = new Blob([bytes])
      .stream()
      .pipeThrough(new DecompressionStream('deflate-raw'));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }

  async function unzip(buffer) {
    const bytes = new Uint8Array(buffer);
    const view = new DataView(buffer);
    let eocd = -1;
    const floor = Math.max(0, bytes.length - 22 - 65536);
    for (let at = bytes.length - 22; at >= floor; at--) {
      if (u32(view, at) === 0x06054b50) {
        eocd = at;
        break;
      }
    }
    if (eocd < 0) throw new Error('not a zip file: no end of central directory');
    const count = u16(view, eocd + 10);
    let offset = u32(view, eocd + 16);
    const decoder = new TextDecoder();
    const files = {};
    for (let index = 0; index < count; index++) {
      if (u32(view, offset) !== 0x02014b50) throw new Error('bad central directory');
      const method = u16(view, offset + 10);
      const compressedSize = u32(view, offset + 20);
      const nameLength = u16(view, offset + 28);
      const extraLength = u16(view, offset + 30);
      const commentLength = u16(view, offset + 32);
      const localOffset = u32(view, offset + 42);
      const name = decoder.decode(bytes.subarray(offset + 46, offset + 46 + nameLength));
      const localNameLength = u16(view, localOffset + 26);
      const localExtraLength = u16(view, localOffset + 28);
      const start = localOffset + 30 + localNameLength + localExtraLength;
      files[name] = await inflate(bytes.subarray(start, start + compressedSize), method);
      offset += 46 + nameLength + extraLength + commentLength;
    }
    return files;
  }

  /** The paragraphs of the corpus document, in document order. */
  async function paragraphs(route) {
    const response = await fetch(route || '/corpus.docx');
    if (!response.ok) throw new Error('the corpus route answered ' + response.status);
    const files = await unzip(await response.arrayBuffer());
    const xml = files['word/document.xml'];
    if (!xml) throw new Error('the corpus has no word/document.xml');
    const doc = new DOMParser().parseFromString(new TextDecoder().decode(xml), 'application/xml');
    const out = [];
    const nodes = doc.getElementsByTagName('w:p');
    for (let index = 0; index < nodes.length; index++) {
      const texts = nodes[index].getElementsByTagName('w:t');
      let text = '';
      for (let at = 0; at < texts.length; at++) text += texts[at].textContent;
      if (text.trim()) out.push(text);
    }
    return out;
  }

  /** Render the paragraphs into a container and say the page is ready. */
  async function render(container, limit) {
    const all = await paragraphs();
    const list = typeof limit === 'number' ? all.slice(0, limit) : all;
    container.textContent = '';
    for (const text of list) {
      const paragraph = document.createElement('p');
      paragraph.textContent = text;
      container.appendChild(paragraph);
    }
    window.__docxParagraphs = list.length;
    window.__docxReady = true;
    return list.length;
  }

  return { paragraphs, render, unzip };
})();
