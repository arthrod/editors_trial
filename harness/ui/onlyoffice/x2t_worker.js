// OnlyOffice's converter (cryptpad/onlyoffice-x2t-wasm) in a Worker.
//
// CryptPad calls x2t on the page itself. The trial's host calls it the same way
// (same files, same params.xml, same `main1` entry) but from a Worker, for one
// reason: a conversion that never returns would freeze the page, and a frozen
// page cannot be photographed or even report that it is frozen. From here the
// page can say "x2t did not return" and the capture records it.
/* global importScripts, Module */
const W = '/working/';
let ready;

function start(base) {
  ready ??= (async () => {
    // x2t.js looks for its .wasm next to the script that runs it, which in a
    // Worker is this file; the module is handed over instead (emscripten's
    // documented `Module.wasmBinary`).
    const wasmBinary = await (await fetch(`${base}x2t/x2t.wasm`)).arrayBuffer();
    self.Module = { wasmBinary };
    importScripts(`${base}x2t/x2t.js`);
    await new Promise((resolve) => {
      // Set in the task the script ran in, as CryptPad does: the wasm cannot have started yet.
      Module.onRuntimeInitialized = resolve;
    });
    for (const dir of ['/working', '/working/media', '/working/fonts', '/working/themes']) {
      try { Module.FS.mkdir(dir); } catch { /* exists */ }
    }
    return Module;
  })();
  return ready;
}

self.onmessage = async (e) => {
  const { base, name, bytes, to } = e.data;
  try {
    const m = await start(base);
    self.postMessage({ step: 'converting' });
    const out = `${W}${name}.${to}`;
    m.FS.writeFile(W + name, bytes);
    // x2t infers both formats from the file extensions, as CryptPad calls it.
    m.FS.writeFile(`${W}params.xml`,
      '<?xml version="1.0" encoding="utf-8"?><TaskQueueDataConvert xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
      + `<m_sFileFrom>${W}${name}</m_sFileFrom><m_sThemeDir>${W}themes</m_sThemeDir><m_sFileTo>${out}</m_sFileTo>`
      + '<m_bIsNoBase64>false</m_bIsNoBase64></TaskQueueDataConvert>');
    const code = m.ccall('main1', 'number', ['string'], [`${W}params.xml`]);
    let result;
    try { result = m.FS.readFile(out); } catch { throw new Error(`x2t wrote no ${to} for ${name} (exit ${code})`); }
    const media = {};
    for (const f of m.FS.readdir(`${W}media`)) if (!f.startsWith('.')) media[f] = m.FS.readFile(`${W}media/${f}`);
    self.postMessage({ step: 'done', code, result, media });
  } catch (err) {
    self.postMessage({ step: 'failed', error: String(err && err.message || err) });
  }
};
