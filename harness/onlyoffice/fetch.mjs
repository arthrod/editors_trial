// Fetch the pinned x2t release archive (pin.json), check its SHA-512 against
// the pin, and unpack the two runtime files into vendor/x2t/ (git-ignored).
//
//   node fetch.mjs
//
// CryptPad publishes x2t (OnlyOffice's converter, compiled to WebAssembly) as
// a GitHub release archive, not on npm, so the pin is the release tag plus the
// archive's hash. A second run with the files in place only re-checks the pin.
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const pin = JSON.parse(readFileSync(join(HERE, 'pin.json'), 'utf8')).x2t;
const dir = join(HERE, 'vendor', 'x2t');
const stamp = join(dir, 'PIN.txt');
const want = `${pin.repository} ${pin.tag} sha512 ${pin.sha512}`;

// x2t.js is a CommonJS script; this harness's package.json says "module".
mkdirSync(dir, { recursive: true });
writeFileSync(join(dir, 'package.json'), '{ "type": "commonjs" }\n');

if (existsSync(stamp) && readFileSync(stamp, 'utf8').trim() === want && pin.files.every((f) => existsSync(join(dir, f)))) {
  console.log(`x2t ${pin.tag}: in place`);
  process.exit(0);
}
const zip = join(dir, pin.asset);
console.log(`x2t ${pin.tag}: downloading ${pin.url}`);
const response = await fetch(pin.url, { headers: { 'user-agent': 'docx-benchmark-harness' } });
if (!response.ok) throw new Error(`download failed: ${response.status}`);
const bytes = Buffer.from(await response.arrayBuffer());
const got = createHash('sha512').update(bytes).digest('hex');
if (got !== pin.sha512) throw new Error(`SHA-512 mismatch for ${pin.asset}: pinned ${pin.sha512}, got ${got}`);
writeFileSync(zip, bytes);
execFileSync('unzip', ['-oq', zip, ...pin.files, '-d', dir], { stdio: 'inherit' });
writeFileSync(stamp, `${want}\n`);
console.log(`x2t ${pin.tag}: ${bytes.length} bytes, SHA-512 matches the pin, unpacked ${pin.files.join(' + ')}`);
