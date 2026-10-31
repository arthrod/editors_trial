/**
 * Why does Plate reject the corpus? readBoundedDocxPackage wraps every
 * non-DocxPackageError into "DOCX package structure is invalid.", so call the
 * inner reader directly and print the raw failure.
 */
import './setup_dom';

import { readFileSync } from 'node:fs';

const PLATE = '/Users/arthrod/temp/T/editors_trial/repos/plate/packages/platejs/src';

const { readBoundedDocxPackage } = await import(
  `${PLATE}/docx/internal/docxPackage.ts`
);

const bytes = readFileSync(process.argv[2]);
const blob = new Blob([bytes], {
  type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
});

try {
  const pkg = await readBoundedDocxPackage(blob, {
    limits: {},
  } as any);
  console.log('OK, entries:', pkg.entries.size);
  for (const name of pkg.entries.keys()) console.log('  ', name);
} catch (e: any) {
  console.log('RAW ERROR:', e?.constructor?.name);
  console.log('code:', e?.code);
  console.log('message:', e?.message);
  console.log('stack:');
  console.log((e?.stack ?? '').split('\n').slice(0, 12).join('\n'));
}
