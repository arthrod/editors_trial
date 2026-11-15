/**
 * Executable await sites in runCriteriaSuite must carry @suite-phase on the same statement;
 * discovered phases must match RUN_CRITERIA_SUITE_PHASES and have injection coverage.
 */
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';

const repo = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const criteriaPath = `${repo}/perf/runner/criteria_input.mjs`;
const moduleUrl = pathToFileURL(criteriaPath).href;
const { RUN_CRITERIA_SUITE_PHASES } = await import(moduleUrl);

const INJECTION_PHASES = new Set([
  ...RUN_CRITERIA_SUITE_PHASES,
  'alive_c04',
  'alive_boundary',
  'partial_c07',
  'after_c08',
]);

const SUITE_PHASE_RE = /\/\/\s*@suite-phase\s+(\w+)/;

function extractRunCriteriaSuiteSource(src) {
  const needle = 'export async function runCriteriaSuite';
  const start = src.indexOf(needle);
  if (start < 0) return null;
  const paramOpen = src.indexOf('(', start);
  if (paramOpen < 0) return null;
  let depth = 0;
  let paramClose = -1;
  for (let i = paramOpen; i < src.length; i += 1) {
    const ch = src[i];
    if (ch === '(') depth += 1;
    else if (ch === ')') {
      depth -= 1;
      if (depth === 0) {
        paramClose = i;
        break;
      }
    }
  }
  if (paramClose < 0) return null;
  const brace = src.indexOf('{', paramClose);
  if (brace < 0) return null;
  depth = 0;
  for (let i = brace; i < src.length; i += 1) {
    const ch = src[i];
    if (ch === '{') depth += 1;
    else if (ch === '}') {
      depth -= 1;
      if (depth === 0) return src.slice(brace + 1, i);
    }
  }
  return null;
}

function stripStringsAndComments(line) {
  let out = '';
  let i = 0;
  while (i < line.length) {
    const ch = line[i];
    const next = line[i + 1];
    if (ch === '/' && next === '/') break;
    if (ch === '/' && next === '*') {
      i += 2;
      while (i < line.length - 1 && !(line[i] === '*' && line[i + 1] === '/')) i += 1;
      i += 2;
      continue;
    }
    if (ch === "'" || ch === '"' || ch === '`') {
      const quote = ch;
      i += 1;
      while (i < line.length) {
        if (line[i] === '\\') {
          i += 2;
          continue;
        }
        if (line[i] === quote) {
          i += 1;
          break;
        }
        i += 1;
      }
      out += ' ';
      continue;
    }
    out += ch;
    i += 1;
  }
  return out;
}

/**
 * Walk runCriteriaSuite body lines; count awaits that are suite boundaries (not
 * nested helper bodies like paintAfter or safeCriterion's `return await run()`).
 */
function discoverTaggedAwaits(body, lineOffset) {
  const lines = body.split('\n');
  let depth = 0;
  let skipDepth = null;
  let inSafeCriterion = false;
  let safeCriterionDepth = null;
  const untagged = [];
  const phases = [];

  const phaseOnStatement = (stmtLines) => {
    for (const raw of stmtLines) {
      const m = raw.match(SUITE_PHASE_RE);
      if (m) return m[1];
    }
    return null;
  };

  const statementSlice = (idx) => {
    const chunk = [];
    for (let j = idx; j >= 0; j -= 1) {
      chunk.unshift(lines[j]);
      const stripped = stripStringsAndComments(lines[j]);
      if (j < idx && (/;\s*$/.test(stripped) || /^\s*}\s*else\b/.test(lines[j]))) break;
      if (j < idx && /^\s*(if|for|while|try|else)\b/.test(stripped) && !/^\s*}\s*else\b/.test(lines[j])) {
        break;
      }
    }
    return chunk;
  };

  for (let idx = 0; idx < lines.length; idx += 1) {
    const raw = lines[idx];
    const stripped = stripStringsAndComments(raw);

    for (const ch of stripped) {
      if (ch === '{') depth += 1;
      else if (ch === '}') depth -= 1;
    }

    if (/^\s*async function safeCriterion\b/.test(stripped)) {
      inSafeCriterion = true;
      safeCriterionDepth = depth;
    }
    if (skipDepth !== null && depth < skipDepth) skipDepth = null;
    if (inSafeCriterion && safeCriterionDepth !== null && depth < safeCriterionDepth) {
      inSafeCriterion = false;
      safeCriterionDepth = null;
    }
    if (/\basync\s+paintAfter\s*\(/.test(stripped)) {
      skipDepth = depth;
    }

    if (skipDepth !== null && depth >= skipDepth) continue;

    if (!/\bawait\b/.test(stripped)) continue;
    if (/return\s+await\s+run\s*\(/.test(stripped)) continue;
    if (inSafeCriterion && !/\bcatch\b/.test(stripped) && !/@suite-phase\s+classify_criterion/.test(raw)) {
      const prev = idx > 0 ? lines[idx - 1] : '';
      if (!/@suite-phase\s+classify_criterion/.test(prev)) continue;
    }

    const stmt = statementSlice(idx);
    const phase = phaseOnStatement(stmt);
    const code = stmt.map(stripStringsAndComments).join(' ').trim();
    if (!phase) {
      untagged.push({ line: lineOffset + idx + 1, code: code.slice(0, 120) });
      continue;
    }
    phases.push(phase);
  }

  return { phases, untagged };
}

function extractNamedFunctionBody(src, name) {
  const needle = `async function ${name}`;
  const start = src.indexOf(needle);
  if (start < 0) return null;
  const brace = src.indexOf('{', start);
  if (brace < 0) return null;
  let depth = 0;
  for (let i = brace; i < src.length; i += 1) {
    const ch = src[i];
    if (ch === '{') depth += 1;
    else if (ch === '}') {
      depth -= 1;
      if (depth === 0) return { body: src.slice(brace + 1, i), line: src.slice(0, start).split('\n').length };
    }
  }
  return null;
}

const src = fs.readFileSync(criteriaPath, 'utf8');
const suite = extractRunCriteriaSuiteSource(src);
if (!suite) {
  console.log(JSON.stringify({ ok: false, error: 'runCriteriaSuite body not found' }));
  process.exit(1);
}

const fnLine = src.slice(0, src.indexOf('export async function runCriteriaSuite')).split('\n').length;
const suiteScan = discoverTaggedAwaits(suite, fnLine);
const classifyFn = extractNamedFunctionBody(src, 'classifySuiteError');
const classifyScan = classifyFn
  ? discoverTaggedAwaits(classifyFn.body, classifyFn.line)
  : { phases: [], untagged: [] };
const discovered = [...suiteScan.phases, ...classifyScan.phases];
const untagged = [...suiteScan.untagged, ...classifyScan.untagged];

const discoveredSet = new Set(discovered);
const exported = [...RUN_CRITERIA_SUITE_PHASES];
const exportSet = new Set(exported);
const missingTags = [...discoveredSet].filter((p) => !exportSet.has(p));
const extraExport = exported.filter((p) => !discoveredSet.has(p));
const missingInjection = [...discoveredSet].filter((p) => !INJECTION_PHASES.has(p));

const ok =
  untagged.length === 0 &&
  missingTags.length === 0 &&
  extraExport.length === 0 &&
  missingInjection.length === 0 &&
  discovered.length === exported.length;

const report = {
  ok,
  discovered,
  exported,
  untagged_awaits: untagged,
  missing_export: missingTags,
  extra_export: extraExport,
  missing_injection: missingInjection,
  // Back-compat for older tests
  tagged: discovered,
  missing_tags: extraExport,
  extra_tags: missingTags,
};

console.log(JSON.stringify(report));
process.exit(ok ? 0 : 1);
