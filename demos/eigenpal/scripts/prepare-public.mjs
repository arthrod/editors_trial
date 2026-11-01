import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const appDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const publicDir = resolve(appDir, 'public');
mkdirSync(publicDir, { recursive: true });
// Optional: benchmarks.law's sync:demos writes document.docx itself; DEMO_DOCX previews the build on its own.
if (process.env.DEMO_DOCX) copyFileSync(process.env.DEMO_DOCX, resolve(publicDir, 'document.docx'));
