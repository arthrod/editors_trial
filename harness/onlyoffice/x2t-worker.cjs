// Runs OnlyOffice's x2t (CryptPad's WebAssembly build) in a worker thread, so
// that roundtrip.mjs can stop a conversion that never returns: main1 is a
// synchronous call into WebAssembly and cannot be interrupted from its own thread.
//
// The calls are the ones CryptPad's own page makes (cryptpad www/common/outer/x2t.js):
// write the file and a params.xml into the module's in-memory /working, call
// main1(params.xml), read the result. x2t infers both formats from the file
// extensions. x2t.js is loaded through its own Node branch (it sets
// module.exports = Module and finds x2t.wasm next to itself).
const { parentPort, workerData } = require('node:worker_threads');
const path = require('node:path');

const W = '/working/';
const m = require(path.join(workerData.dir, 'x2t.js'));
// Set in the same task the script ran in, as CryptPad does: the wasm cannot have started yet.
m.onRuntimeInitialized = () => {
  try {
    for (const d of ['/working', '/working/media', '/working/fonts', '/working/themes']) {
      try { m.FS.mkdir(d); } catch { /* exists */ }
    }
    parentPort.postMessage({ type: 'ready' });
    const convert = (name, data, to) => {
      const out = `${W}${name}.${to}`;
      m.FS.writeFile(W + name, data);
      m.FS.writeFile(
        `${W}params.xml`,
        '<?xml version="1.0" encoding="utf-8"?><TaskQueueDataConvert xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">' +
          `<m_sFileFrom>${W}${name}</m_sFileFrom><m_sThemeDir>${W}themes</m_sThemeDir><m_sFileTo>${out}</m_sFileTo>` +
          '<m_bIsNoBase64>false</m_bIsNoBase64></TaskQueueDataConvert>',
      );
      parentPort.postMessage({ type: 'step', step: `${name} -> ${to}` });
      const t0 = performance.now();
      const rc = m.ccall('main1', 'number', ['string'], [`${W}params.xml`]);
      const ms = performance.now() - t0;
      let bytes;
      try {
        bytes = m.FS.readFile(out);
      } catch {
        throw new Error(`x2t could not convert ${name} to ${to} (main1 returned ${rc}, no output file)`);
      }
      return { bytes, ms, rc };
    };
    const first = convert('doc.docx', workerData.input, 'bin');
    const media = m.FS.readdir(`${W}media`).filter((f) => !f.startsWith('.'));
    parentPort.postMessage({ type: 'imported', ms: first.ms, rc: first.rc, binBytes: first.bytes.length, media });
    const second = convert('out.bin', first.bytes, 'docx');
    parentPort.postMessage({ type: 'done', ms: second.ms, rc: second.rc, bytes: second.bytes });
  } catch (e) {
    parentPort.postMessage({ type: 'error', message: e instanceof Error ? e.message : String(e) });
  }
};
