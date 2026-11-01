import { copyFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const appDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repoDir = resolve(appDir, '../src');
const distDir = resolve(appDir, '../dist');

copyFileSync(resolve(repoDir, 'LICENSE'), resolve(distDir, 'LICENSE'));
copyFileSync(
  resolve(repoDir, 'packages/core/THIRD_PARTY_NOTICES.md'),
  resolve(distDir, 'THIRD_PARTY_NOTICES-core.md')
);
copyFileSync(
  resolve(repoDir, 'packages/react/THIRD_PARTY_NOTICES.md'),
  resolve(distDir, 'THIRD_PARTY_NOTICES-react.md')
);

mkdirSync(resolve(distDir, 'licenses'), { recursive: true });
copyFileSync(
  resolve(repoDir, 'packages/core/licenses/HarfBuzz-COPYING.txt'),
  resolve(distDir, 'licenses/HarfBuzz-COPYING.txt')
);
copyFileSync(
  resolve(repoDir, 'packages/core/licenses/ECMA-376.md'),
  resolve(distDir, 'licenses/ECMA-376.md')
);

writeFileSync(
  resolve(distDir, 'SOURCE.txt'),
  'Repository: https://github.com/eigenpal/docx-editor.git\nCommit: c6f8f0f\n'
);
