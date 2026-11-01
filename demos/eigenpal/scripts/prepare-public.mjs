import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const appDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const publicDir = resolve(appDir, 'public');
mkdirSync(publicDir, { recursive: true });
copyFileSync(resolve(appDir, '../document.docx'), resolve(publicDir, 'document.docx'));
