// Univer (open-source documents preset): is there a .docx import or export in
// the packages? This is not a round trip. It reads the installed, pinned
// packages and prints what it finds, so "no .docx path" is a result of running
// something, not a sentence someone typed.
//
//   node probe.mjs [result.json]
//
// With a path, the result is also written there for build/facts.py (probe.univer.*).
//
// It walks every package @univerjs/presets and @univerjs/preset-docs-core
// install (node_modules/.pnpm), and for each one reports:
//   - its licence and any dependency that could unpack a .docx (a zip library),
//     or a zip signature in its own code (a bundled one);
//   - the names a .docx reader or writer cannot avoid: the main part
//     (word/document.xml), [Content_Types].xml, or the WordprocessingML namespace;
//   - facade or API names for docx import or export.
// Any of those is a HIT. The .docx MIME type alone is not: it is printed with
// the line it is on, so a reader can see what it is used for (in
// @univerjs/drawing it sorts an embedded attachment by type).
// Exit code: 0 no reader or writer found, 1 one was found (then a lane is owed).
import { mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const STORE = join(HERE, 'node_modules', '.pnpm');
const FORMAT = /word\/document\.xml|\[Content_Types\]\.xml|schemas\.openxmlformats\.org\/wordprocessingml|0x04034b50|67324752|PK\\x03\\x04|PK\\u0003\\u0004/gi;
const MIME = /application\/vnd\.openxmlformats-officedocument\.wordprocessingml\.document/;
const ZIP = /^(jszip|fflate|pako|yauzl|adm-zip|@zip\.js\/zip\.js|zip\.js|unzipper)$/;
const API = /\b(importDocx\w*|exportDocx\w*|importDOCX\w*|exportDOCX\w*|docxTo\w+|\w+ToDocx|saveAsDocx\w*|openDocx\w*)\b/g;

const walk = (dir, out = []) => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    const s = statSync(p);
    if (s.isDirectory()) walk(p, out);
    else if (/\.(m?js|cjs)$/.test(name)) out.push(p);
  }
  return out;
};

const seen = new Map();
for (const entry of readdirSync(STORE)) {
  const scope = join(STORE, entry, 'node_modules', '@univerjs');
  let names = [];
  try { names = readdirSync(scope); } catch { continue; }
  for (const name of names) {
    const dir = join(scope, name);
    let pkg;
    try { pkg = JSON.parse(readFileSync(join(dir, 'package.json'), 'utf8')); } catch { continue; }
    const id = `${pkg.name}@${pkg.version}`;
    if (seen.has(id)) continue;
    const files = walk(dir).filter((f) => !f.includes(`${dir}/node_modules/`));
    const format = new Map();
    const api = new Set();
    const mime = [];
    for (const f of files) {
      const text = readFileSync(f, 'utf8');
      if (!f.includes('/lib/es/')) { /* one build is enough for the quoted lines */ }
      else text.split('\n').forEach((line, i) => { if (MIME.test(line)) mime.push(`${f.slice(dir.length + 1)}:${i + 1}: ${line.trim().slice(0, 160)}`); });
      for (const m of text.matchAll(FORMAT)) format.set(m[0].toLowerCase(), (format.get(m[0].toLowerCase()) ?? 0) + 1);
      for (const m of text.matchAll(API)) api.add(m[1]);
    }
    seen.set(id, {
      licence: pkg.license ?? '(none stated)',
      zip: Object.keys({ ...pkg.dependencies, ...pkg.peerDependencies }).filter((d) => ZIP.test(d)),
      files: files.length,
      format: Object.fromEntries(format),
      api: [...api],
      mime,
    });
  }
}

let found = 0;
console.log(`Univer packages installed by the pinned presets: ${seen.size}`);
for (const [id, r] of [...seen].sort()) {
  const hit = r.zip.length || Object.keys(r.format).length || r.api.length;
  if (hit) found++;
  console.log(`${hit ? 'HIT ' : 'none'}  ${id}  licence ${r.licence}  ${r.files} code files` +
    (hit ? `  zip deps ${JSON.stringify(r.zip)}  format names ${JSON.stringify(r.format)}  api ${JSON.stringify(r.api)}` : ''));
  for (const line of r.mime) console.log(`        MIME type only  ${line}`);
}
console.log(found
  ? `RESULT: ${found} package(s) name the .docx format; read them, a lane may be owed`
  : 'RESULT: no .docx reader or writer in these packages (no zip library or zip signature, no WordprocessingML part name or namespace, no docx import/export API)');
if (process.argv[2]) {
  const out = resolve(process.argv[2]);
  mkdirSync(dirname(out), { recursive: true });
  const packages = Object.fromEntries([...seen].sort().map(([id, r]) => [id, {
    licence: r.licence, files: r.files, zip: r.zip, format: r.format, api: r.api, mime_only: r.mime.length,
  }]));
  writeFileSync(out, `${JSON.stringify({ docx_path: found ? 'found' : 'none', packages_read: seen.size, hits: found, packages }, null, 1)}\n`);
}
process.exit(found ? 1 : 0);
