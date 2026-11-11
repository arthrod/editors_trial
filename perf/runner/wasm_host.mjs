/**
 * C24 WASM-boundary probe (Playwright).
 *
 * Loads the editor's own browser host, waits for its own ready signal, reaches the
 * editor's already-initialized WASM instance in that page, and runs the C24
 * operations warm in-process (`in_process_iteration`) after one compile.
 *
 *   node perf/runner/wasm_host.mjs --spec <spec.json>
 *
 * The spec (written by `perf/runner/wasm_boundary.py`) names the editor, the URL to
 * open, the ready signal, the served module to re-instantiate, and one entry per
 * operation. The probe never invents a sample: every timed repetition carries a
 * correctness assertion, and an operation whose call does not return the expected
 * value is reported with `ok: false` plus the observed value instead of samples.
 *
 * Output (stdout): one JSON object, `schema: "c24-wasm-host/1"`.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { startChromeTrace, stopChromeTrace } from './chrome_trace.mjs';
import { loadTimeoutMs } from './load_timeout.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '../..');
const uiRoot = path.join(repoRoot, 'harness', 'ui');

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) continue;
    const key = a.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith('--')) {
      out[key] = true;
    } else {
      out[key] = next;
      i++;
    }
  }
  return out;
}

const opt = parseArgs(process.argv.slice(2));
if (!opt.spec) {
  console.error('wasm_host: --spec is required');
  process.exit(2);
}
const spec = JSON.parse(fs.readFileSync(String(opt.spec), 'utf8'));
if (!spec.url || !Array.isArray(spec.ops) || spec.ops.length === 0) {
  console.error('wasm_host: spec needs url and a non-empty ops list');
  process.exit(2);
}

/**
 * Installed before any page script: records every WebAssembly compile/instantiate the
 * editor itself performs, so the probe can re-instantiate the page's own module with
 * the page's own import object, and captures the exports WordCraft publishes on its
 * Trunk boot event. Measurement only — it wraps the standard API, nothing else.
 */
function installHooks() {
  const cap = { compiles: [], instantiations: [], last: null };
  window.__C24__ = cap;
  window.__C24_TRUNK__ = null;
  window.addEventListener('TrunkApplicationStarted', (event) => {
    const detail = event && event.detail ? event.detail : null;
    if (detail && detail.wasm && typeof detail.wasm === 'object') {
      window.__C24_TRUNK__ = detail.wasm;
    }
  });
  const W = WebAssembly;
  const origCompile = W.compile.bind(W);
  const origCompileStreaming = W.compileStreaming.bind(W);
  const origInstantiate = W.instantiate.bind(W);
  const origInstantiateStreaming = W.instantiateStreaming.bind(W);

  W.compile = async function (bytes) {
    const t0 = performance.now();
    const module = await origCompile(bytes);
    const info = { kind: 'compile', url: '', ms: performance.now() - t0, source: 'bytes' };
    cap.compiles.push(info);
    return module;
  };
  W.compileStreaming = async function (source) {
    const url = (source && source.url) || '';
    const t0 = performance.now();
    const module = await origCompileStreaming(source);
    cap.compiles.push({ kind: 'compileStreaming', url, ms: performance.now() - t0, source: 'stream' });
    return module;
  };
  W.instantiateStreaming = async function (source, imports) {
    const url = (source && source.url) || '';
    const t0 = performance.now();
    const result = await origInstantiateStreaming(source, imports);
    cap.instantiations.push({ kind: 'instantiateStreaming', url, ms: performance.now() - t0 });
    cap.last = { module: result.module, imports, instance: result.instance, url };
    return result;
  };
  W.instantiate = async function (source, imports) {
    const t0 = performance.now();
    const result = await origInstantiate(source, imports);
    const instance = result instanceof WebAssembly.Instance ? result : result.instance;
    const module = result instanceof WebAssembly.Instance ? source : result.module;
    const url = cap.compiles.length ? cap.compiles[cap.compiles.length - 1].url : '';
    cap.instantiations.push({
      kind: 'instantiate',
      url,
      ms: performance.now() - t0,
      from: source instanceof WebAssembly.Module ? 'module' : 'bytes',
    });
    cap.last = { module, imports, instance, url };
    return result;
  };
}

async function waitForReady(page, spec) {
  const timeout = Number(spec.ready_timeout_ms || 180000);
  if (spec.ready_js) {
    await page.waitForFunction(
      (expr) => {
        try {
          // eslint-disable-next-line no-eval
          return Boolean(eval(expr));
        } catch {
          return false;
        }
      },
      spec.ready_js,
      { timeout },
    );
  }
  if (spec.ready_selector) {
    await page.waitForSelector(spec.ready_selector, { timeout, state: 'attached' });
  }
  if (spec.wait_after_ready_ms) {
    await page.waitForTimeout(Number(spec.wait_after_ready_ms));
  }
}

/**
 * Runs inside the page. Everything it needs is in `cfg`; it returns plain JSON.
 * Any thrown error is reported per operation, never as a sample.
 */
async function runOps(cfg) {
  const cap = window.__C24__ || { compiles: [], instantiations: [], last: null };
  const result = { ops: {}, errors: [], module: null, live_surface: null, clock: null };
  const now = () => performance.now();

  // Clock floor: Chromium quantises performance.now() on a non-isolated page, so a
  // cheap operation's sample can sit on the quantum. Recorded so a reader can tell
  // "0.1 ms" apart from "below the resolution of this clock".
  (function measureClock() {
    let quantum = null;
    let previous = performance.now();
    for (let i = 0; i < 5000; i++) {
      const value = performance.now();
      const delta = value - previous;
      if (delta > 0 && (quantum === null || delta < quantum)) quantum = delta;
      previous = value;
    }
    result.clock = { source: 'performance.now()', quantum_ms: quantum, probes: 5000 };
  })();

  const hex = (bytes) =>
    Array.from(bytes)
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');

  async function sha256(bytes) {
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return hex(new Uint8Array(digest));
  }

  function resourceUrls(regex) {
    const re = new RegExp(regex);
    const urls = [];
    for (const entry of performance.getEntriesByType('resource')) {
      if (re.test(entry.name)) urls.push(entry.name);
    }
    for (const compile of cap.compiles || []) {
      if (compile.url && re.test(compile.url)) urls.push(compile.url);
    }
    return Array.from(new Set(urls));
  }

  async function fetchModuleBytes() {
    const urls = resourceUrls(cfg.module_url_regex || '\\.wasm$');
    if (urls.length === 0) throw new Error('no served .wasm resource matched ' + cfg.module_url_regex);
    let lastError = null;
    for (const candidate of urls) {
      const tries = candidate.endsWith('.br') ? [candidate.slice(0, -3), candidate] : [candidate];
      for (const url of tries) {
        try {
          const response = await fetch(url);
          if (!response.ok) {
            lastError = new Error('GET ' + url + ' -> HTTP ' + response.status);
            continue;
          }
          const bytes = new Uint8Array(await response.arrayBuffer());
          return { url, bytes, requested: candidate, transport: url === candidate ? 'served' : 'served-uncompressed' };
        } catch (error) {
          lastError = error;
        }
      }
    }
    throw lastError || new Error('module bytes unreachable');
  }

  function stubImports(module) {
    const groups = {};
    let expected = 0;
    for (const entry of WebAssembly.Module.imports(module)) {
      expected++;
      groups[entry.module] = groups[entry.module] || {};
      groups[entry.module][entry.name] = () => {
        throw new Error('C24 stub import called: ' + entry.module + '.' + entry.name);
      };
    }
    return { imports: groups, count: expected, source: 'stub' };
  }

  function sameModuleUrl(a, b) {
    const norm = (value) => String(value || '').split('?')[0].replace(/\.br$/, '');
    if (!a || !b) return true;
    return norm(a) === norm(b);
  }

  function capturedImports(url) {
    const last = cap.last;
    if (!last || !last.imports) return null;
    if (!sameModuleUrl(url, last.url)) return null;
    return { imports: last.imports, source: 'captured' };
  }

  function liveExports() {
    if (cfg.surface !== 'exports') return null;
    const trunk = window.__C24_TRUNK__;
    if (trunk && typeof trunk[cfg.require_export] === 'function') {
      return { exports: trunk, source: 'TrunkApplicationStarted detail.wasm' };
    }
    const last = cap.last;
    if (last && last.instance && typeof last.instance.exports[cfg.require_export] === 'function') {
      return { exports: last.instance.exports, source: 'WebAssembly instantiate hook' };
    }
    return null;
  }

  async function resolveBridge() {
    const urls = resourceUrls(cfg.bridge_url_regex || 'docxodus/(dist|.*)core\\.js');
    for (const url of urls) {
      try {
        const mod = await import(url);
        if (mod && typeof mod.getWasmExports === 'function') {
          if (typeof mod.isInitialized === 'function' && !mod.isInitialized()) continue;
          return { mod, url, bridge: mod.getWasmExports() };
        }
      } catch (error) {
        result.errors.push({ stage: 'bridge-import', url, error: String(error) });
      }
    }
    return null;
  }

  function callPath(root, dotted) {
    return dotted.split('.').reduce((node, key) => (node == null ? node : node[key]), root);
  }

  let surface = null;
  if (cfg.surface === 'exports') {
    surface = liveExports();
    if (!surface) {
      result.live_surface = null;
      return result;
    }
    result.live_surface = {
      source: surface.source,
      exports: Object.keys(surface.exports).length,
    };
  } else if (cfg.surface === 'bridge') {
    const resolved = await resolveBridge();
    if (!resolved) {
      result.live_surface = null;
      return result;
    }
    surface = { bridge: resolved.bridge, mod: resolved.mod, url: resolved.url };
    result.live_surface = {
      source: 'getWasmExports() on the page\'s own initialized module',
      url: resolved.url,
      groups: Object.keys(resolved.bridge),
    };
  }

  // --- measurement ----------------------------------------------------------

  /**
   * A timed region runs `calls` identical calls; the clock on a non-isolated page is
   * quantised (recorded as `clock.quantum_ms`), so a region is calibrated to span at
   * least 2 ms and a cheap operation's sample is its amortised per-call cost.
   * `sample_basis` says which reading a sample is; `calls_per_sample` says how many
   * calls produced it.
   */
  function measure(op, region) {
    const basis = op.basis || 'amortized_per_call';
    const samples = Math.max(1, Number(op.samples ?? cfg.samples ?? 5));
    const warmup = Math.max(0, Number(op.warmup ?? cfg.warmup ?? 2));
    const maxCalls = Math.max(1, Number(op.max_calls || 65536));
    let calls = basis === 'single_call' ? Math.max(1, Number(op.calls || 1)) : null;

    const runRegion = (k) => {
      const t0 = now();
      const check = region(k);
      return { ms: now() - t0, check };
    };

    // One untimed call first: a first-call one-time cost (lazy .NET init, JIT warmup)
    // must not be mistaken for the region size the calibration is looking for.
    {
      const check = region(1);
      if (check && check.ok === false) {
        return { error: 'first call failed its correctness assertion: ' + JSON.stringify(check), samples: [], correctness: check };
      }
    }

    if (calls === null) {
      let probeCalls = 8;
      for (let round = 0; round < 10; round++) {
        const { ms, check } = runRegion(probeCalls);
        if (check && check.ok === false) {
          return { error: 'calibration call returned a wrong value: ' + JSON.stringify(check), samples: [], correctness: check };
        }
        if (ms >= 2.0) {
          calls = probeCalls;
          break;
        }
        if (probeCalls >= maxCalls) {
          calls = maxCalls;
          break;
        }
        probeCalls = Math.min(probeCalls * 4, maxCalls);
      }
      if (calls === null) calls = maxCalls;
    }

    for (let i = 0; i < warmup; i++) {
      const { check } = runRegion(calls);
      if (check && check.ok === false) {
        return { error: 'warmup call failed its correctness assertion: ' + JSON.stringify(check), samples: [], correctness: check };
      }
    }

    const values = [];
    let first = null;
    for (let i = 0; i < samples; i++) {
      const { ms, check } = runRegion(calls);
      if (check && check.ok === false) {
        return { error: 'call returned a wrong value: ' + JSON.stringify(check), samples: [], correctness: check };
      }
      values.push(basis === 'amortized_per_call' ? ms / calls : ms);
      if (first === null) first = check;
    }
    return {
      samples_ms: values,
      calls_per_sample: calls,
      sample_basis: basis,
      correctness: {
        ok: true,
        expected: first ? first.expected : null,
        observed: first ? first.observed : null,
        calls_per_sample: calls,
        sample_basis: basis,
      },
    };
  }

  // --- operations -----------------------------------------------------------

  let moduleBytes = null;
  async function ensureModule() {
    if (!moduleBytes) {
      const fetched = await fetchModuleBytes();
      moduleBytes = {
        ...fetched,
        sha256: await sha256(fetched.bytes),
        byte_length: fetched.bytes.byteLength,
      };
      result.module = {
        url: fetched.url,
        requested: fetched.requested,
        transport: fetched.transport,
        byte_length: fetched.bytes.byteLength,
        sha256: moduleBytes.sha256,
      };
    }
    return moduleBytes;
  }

  async function compileInstantiate(op) {
    const mod = await ensureModule();
    const firstCompile = await WebAssembly.compile(mod.bytes);
    const captured = capturedImports(mod.url);
    const provided = captured || stubImports(firstCompile);
    const importCount = WebAssembly.Module.imports(firstCompile).length;
    const expectedExports = WebAssembly.Module.exports(firstCompile).filter((e) => e.kind === 'function').length;
    const liveMemoryBytes = surface && surface.exports && surface.exports.memory
      ? surface.exports.memory.buffer.byteLength
      : null;
    result.module.imports = importCount;
    result.module.import_paths = provided.source === 'stub' ? Object.keys(provided.imports).length : null;
    result.module.imports_source = provided.source;
    result.module.function_exports = expectedExports;

    let stubCalls = 0;
    if (provided.source === 'stub') {
      for (const group of Object.values(provided.imports)) {
        for (const key of Object.keys(group)) {
          group[key] = () => {
            stubCalls++;
            return 0;
          };
        }
      }
    }

    const warmup = Math.max(0, Number(op.warmup ?? 1));
    for (let i = 0; i < warmup; i++) {
      const module = await WebAssembly.compile(mod.bytes);
      await WebAssembly.instantiate(module, provided.imports);
    }
    const samples = [];
    let baselineMemory = null;
    let first = null;
    for (let i = 0; i < Number(op.samples ?? cfg.compile_samples ?? 5); i++) {
      const t0 = now();
      const module = await WebAssembly.compile(mod.bytes);
      const instance = await WebAssembly.instantiate(module, provided.imports);
      const ms = now() - t0;
      const funcs = WebAssembly.Module.exports(module).filter((e) => e.kind === 'function').length;
      const memory = instance.exports.memory;
      if (memory && baselineMemory === null) baselineMemory = memory.buffer.byteLength;
      const check = {
        ok:
          funcs === expectedExports &&
          Boolean(memory) &&
          memory.buffer.byteLength === baselineMemory &&
          stubCalls === 0,
        expected: { function_exports: expectedExports, stub_import_calls: 0, deterministic_memory: true },
        observed: {
          function_exports: funcs,
          has_memory: Boolean(memory),
          memory_bytes: memory ? memory.buffer.byteLength : null,
          live_memory_bytes: liveMemoryBytes,
          stub_import_calls: stubCalls,
        },
      };
      if (!check.ok) {
        return { error: 're-instantiated module does not match itself across samples: ' + JSON.stringify(check), samples: [], correctness: check };
      }
      samples.push(ms);
      if (first === null) first = check;
    }
    return {
      samples_ms: samples,
      calls_per_sample: 1,
      sample_basis: 'single_call',
      correctness: { ok: true, ...first, samples: samples.length },
    };
  }

  function requireExports() {
    if (!surface || !surface.exports) throw new Error('no live exports on the page');
    return surface.exports;
  }

  function exportRegion(op) {
    return (calls) => {
      const exportsObj = requireExports();
      const fn = exportsObj[op.export];
      if (typeof fn !== 'function') throw new Error('export ' + op.export + ' is not a function on the live instance');
      const memory = exportsObj.memory;
      const before = memory ? memory.buffer.byteLength : null;
      let ok = true;
      for (let i = 0; i < calls; i++) {
        if (fn(...(op.args || [])) !== undefined) ok = false;
      }
      if (memory) ok = ok && memory.buffer.byteLength === before;
      return {
        ok,
        expected: { returned: 'undefined', memory_unchanged: true },
        observed: { returned: 'undefined', calls, memory_bytes: memory ? memory.buffer.byteLength : null },
      };
    };
  }

  function mallocRegion(op) {
    return (calls) => {
      const exportsObj = requireExports();
      const malloc = exportsObj[op.malloc];
      const free = exportsObj[op.free];
      if (typeof malloc !== 'function' || typeof free !== 'function') {
        throw new Error('allocator exports missing: ' + op.malloc + '/' + op.free);
      }
      const size = Number(op.size || 64);
      const align = Number(op.align || 8);
      const pointers = [];
      let ok = true;
      for (let i = 0; i < calls; i++) {
        const ptr = malloc(size, align);
        if (!(typeof ptr === 'number' && ptr > 0 && ptr % align === 0)) ok = false;
        pointers.push(ptr);
      }
      for (const ptr of pointers) {
        if (typeof ptr === 'number' && ptr > 0) free(ptr, size, align);
      }
      return {
        ok: ok && pointers.length === calls,
        expected: { allocations: calls, size, alignment: align, freed: true },
        observed: { allocations: pointers.length, first_pointer: pointers[0], last_pointer: pointers[pointers.length - 1] },
      };
    };
  }

  function stringRegion(op) {
    const enc = new TextEncoder();
    const dec = new TextDecoder();
    return (calls) => {
      const exportsObj = requireExports();
      const malloc = exportsObj[op.malloc];
      const free = exportsObj[op.free];
      const bytes = enc.encode(op.text);
      let ok = true;
      let observed = null;
      for (let i = 0; i < calls; i++) {
        const ptr = malloc(bytes.length, 1);
        new Uint8Array(exportsObj.memory.buffer, ptr, bytes.length).set(bytes);
        const back = new Uint8Array(exportsObj.memory.buffer, ptr, bytes.length).slice();
        free(ptr, bytes.length, 1);
        const decoded = dec.decode(back);
        if (decoded !== op.text) ok = false;
        observed = decoded;
      }
      return {
        ok,
        expected: op.text,
        observed,
        bytes: bytes.length,
      };
    };
  }

  function f64Region(op) {
    return (calls) => {
      const exportsObj = requireExports();
      const malloc = exportsObj[op.malloc];
      const free = exportsObj[op.free];
      const values = op.values;
      const source = new Float64Array(values);
      const sourceBytes = new Uint8Array(source.buffer, source.byteOffset, source.byteLength);
      let ok = true;
      let observed = null;
      for (let i = 0; i < calls; i++) {
        const ptr = malloc(source.byteLength, 8);
        new Uint8Array(exportsObj.memory.buffer, ptr, source.byteLength).set(sourceBytes);
        const back = new Float64Array(exportsObj.memory.buffer, ptr, values.length).slice();
        free(ptr, source.byteLength, 8);
        observed = Array.from(back);
        if (!values.every((value, index) => Object.is(value, back[index]))) ok = false;
      }
      return {
        ok,
        expected: values,
        observed,
        bytes: source.byteLength,
      };
    };
  }

  function batchRegion(op) {
    return (calls) => {
      const exportsObj = requireExports();
      const malloc = exportsObj[op.malloc];
      const free = exportsObj[op.free];
      const size = Number(op.size || 64);
      const align = Number(op.align || 8);
      const pattern = [0xa5, 0x5a, 1, 2, 3, 4, 5, 6];
      let ok = true;
      let lastPointer = 0;
      for (let i = 0; i < calls; i++) {
        const ptr = malloc(size, align);
        if (!(typeof ptr === 'number' && ptr > 0 && ptr % align === 0)) {
          ok = false;
          break;
        }
        const view = new Uint8Array(exportsObj.memory.buffer, ptr, pattern.length);
        view.set(pattern.map((byte, index) => (index === 0 ? (i + byte) & 0xff : byte)));
        const echo = Array.from(view);
        if (echo.join(',') !== pattern.map((byte, index) => (index === 0 ? (i + byte) & 0xff : byte)).join(',')) ok = false;
        free(ptr, size, align);
        lastPointer = ptr;
      }
      return {
        ok,
        expected: { calls, size, alignment: align, roundtrip: 'byte pattern' },
        observed: { calls, last_pointer: lastPointer },
      };
    };
  }

  function memoryGrowRegion(op) {
    return (calls) => {
      const exportsObj = requireExports();
      const memory = exportsObj.memory;
      const pages = Number(op.pages || 1);
      let ok = true;
      let observed = null;
      for (let i = 0; i < calls; i++) {
        const before = memory.buffer.byteLength;
        const previous = memory.grow(pages);
        const after = memory.buffer.byteLength;
        observed = { previous_pages: previous, delta_bytes: after - before };
        if (!(typeof previous === 'number' && previous === before / 65536 && after - before === pages * 65536)) ok = false;
      }
      return {
        ok,
        expected: { delta_bytes: calls * pages * 65536 },
        observed,
      };
    };
  }

  let bridgeCache = null;
  async function bridgeRoot() {
    if (cfg.surface !== 'bridge') throw new Error('bridge operation on a non-bridge surface');
    if (bridgeCache) return bridgeCache;
    const resolved = await resolveBridge();
    if (!resolved) throw new Error('the page is not running an initialized module that exports getWasmExports()');
    bridgeCache = resolved.bridge;
    return bridgeCache;
  }

  async function bridgeFunction(op) {
    const root = await bridgeRoot();
    const fn = callPath(root, op.call);
    if (typeof fn !== 'function') throw new Error('bridge method ' + op.call + ' is missing');
    return fn;
  }

  function bridgeNullaryRegion(fn, op) {
    return (calls) => {
      let ok = true;
      let value = null;
      for (let i = 0; i < calls; i++) {
        value = fn();
        if (op.expect !== undefined ? value !== op.expect : !(typeof value === 'string' && value.length > 0)) ok = false;
      }
      return { ok, expected: op.expect ?? 'non-empty string', observed: String(value).slice(0, 200) };
    };
  }

  function bridgeJsonRegion(fn, op) {
    return (calls) => {
      let ok = true;
      let parsed = null;
      for (let i = 0; i < calls; i++) {
        const value = fn();
        if (typeof value !== 'string') {
          ok = false;
          continue;
        }
        try {
          parsed = JSON.parse(value);
        } catch {
          ok = false;
          continue;
        }
        if (Array.isArray(op.require_keys)) {
          for (const key of op.require_keys) {
            if (parsed[key] === undefined || parsed[key] === null || parsed[key] === '') ok = false;
          }
        }
        if (op.expect_library) {
          ok = ok && (parsed.Library === op.expect_library || parsed.library === op.expect_library);
        }
      }
      return {
        ok,
        expected: { json_keys: op.require_keys || [], library: op.expect_library || null },
        observed: parsed
          ? { Library: parsed.Library ?? parsed.library ?? null, DotnetVersion: parsed.DotnetVersion ?? parsed.dotnetVersion ?? null }
          : null,
      };
    };
  }

  function bridgeBatchRegion(fn, op) {
    return (calls) => {
      let ok = true;
      let sample = null;
      for (let i = 0; i < calls; i++) {
        const value = fn();
        if (typeof value !== 'string' || value.length === 0) ok = false;
        if (i === 0) sample = String(value).slice(0, 120);
      }
      return { ok, expected: { calls, every_call: 'non-empty string' }, observed: { calls, first: sample } };
    };
  }

  for (const op of cfg.ops) {
    try {
      let outcome;
      if (op.technique === 'compile_instantiate') {
        outcome = await compileInstantiate(op);
      } else if (op.technique === 'export_call_void') {
        outcome = measure(op, exportRegion(op));
      } else if (op.technique === 'malloc_scalar') {
        outcome = measure(op, mallocRegion(op));
      } else if (op.technique === 'string_alloc_roundtrip') {
        outcome = measure(op, stringRegion(op));
      } else if (op.technique === 'f64_roundtrip') {
        outcome = measure(op, f64Region(op));
      } else if (op.technique === 'batch_malloc') {
        outcome = measure(op, batchRegion(op));
      } else if (op.technique === 'memory_grow') {
        outcome = measure(op, memoryGrowRegion(op));
      } else if (op.technique === 'bridge_nullary') {
        outcome = measure(op, bridgeNullaryRegion(await bridgeFunction(op), op));
      } else if (op.technique === 'bridge_json') {
        outcome = measure(op, bridgeJsonRegion(await bridgeFunction(op), op));
      } else if (op.technique === 'bridge_batch') {
        outcome = measure(op, bridgeBatchRegion(await bridgeFunction(op), op));
      } else {
        outcome = { error: 'unknown technique ' + op.technique, samples: [], correctness: null };
      }
      result.ops[op.name] = {
        technique: op.technique,
        surface: cfg.surface,
        calls_per_sample: outcome.calls_per_sample ?? Number(op.calls || 1),
        sample_basis: outcome.sample_basis ?? 'single_call',
        samples_ms: outcome.samples_ms || [],
        correctness: outcome.correctness || null,
        error: outcome.error || null,
      };
    } catch (error) {
      result.ops[op.name] = {
        technique: op.technique,
        surface: cfg.surface,
        calls_per_sample: Number(op.calls || 1),
        sample_basis: 'unknown',
        samples_ms: [],
        correctness: null,
        error: String(error && error.message ? error.message : error),
      };
    }
  }

  return result;
}

const playwrightPath = path.join(uiRoot, 'node_modules', 'playwright', 'index.mjs');
const { chromium } = await import(pathToFileURL(playwrightPath).href);
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });

if (spec.corpus_path) {
  const corpusBytes = fs.readFileSync(spec.corpus_path);
  await context.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === (spec.corpus_route || '/corpus.docx')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: corpusBytes,
      });
      return;
    }
    await route.continue();
  });
}

const page = await context.newPage();
const traceHandle = await startChromeTrace(browser, page, 'C24');
const pageErrors = [];
page.on('pageerror', (error) => pageErrors.push(String(error).slice(0, 400)));
await page.addInitScript(installHooks);

let payload = null;
let failure = null;
try {
  const loadTimeout = Number(spec.nav_timeout_ms || loadTimeoutMs());
await page.goto(spec.url, { waitUntil: 'domcontentloaded', timeout: loadTimeout });
  await waitForReady(page, spec);
  payload = await page.evaluate(runOps, {
    surface: spec.surface,
    ops: spec.ops,
    warmup: spec.warmup,
    samples: spec.samples,
    compile_samples: spec.compile_samples,
    module_url_regex: spec.module_url_regex,
    bridge_url_regex: spec.bridge_url_regex,
    require_export: spec.require_export,
  });
} catch (error) {
  failure = String(error && error.message ? error.message : error);
}

await stopChromeTrace(browser, traceHandle);
await browser.close();

const out = {
  schema: 'c24-wasm-host/1',
  editor_id: spec.editor_id,
  url: spec.url,
  driver: 'playwright',
  spec_ops: spec.ops.map((op) => ({ name: op.name, technique: op.technique, calls_per_sample: Number(op.calls || 1) })),
  module: payload ? payload.module : null,
  live_surface: payload ? payload.live_surface : null,
  clock: payload ? payload.clock : null,
  ops: payload ? payload.ops : {},
  errors: (payload ? payload.errors : []).concat(pageErrors.map((error) => ({ stage: 'pageerror', error }))),
  nav_timeout_ms: loadTimeout,
  failure,
};
process.stdout.write(JSON.stringify(out));
