import { GlobalRegistrator } from '@happy-dom/global-registrator';

GlobalRegistrator.register();

console.log('DOMParser:', typeof globalThis.DOMParser);
console.log('XMLSerializer:', typeof globalThis.XMLSerializer);
console.log('DOMException:', typeof globalThis.DOMException);
console.log('HTMLElement:', typeof globalThis.HTMLElement);
console.log('Node.TEXT_NODE:', globalThis.Node?.TEXT_NODE);

const PLATE = '/Users/arthrod/temp/T/editors_trial/repos/plate/packages/platejs/src';
for (const p of ['docx/import/index.ts', 'docx/export/index.ts']) {
  console.log(`--- importing ${p} ---`);
  try {
    const mod = await import(`${PLATE}/${p}`);
    console.log('OK, exports:', Object.keys(mod).join(', '));
  } catch (e: any) {
    console.log('FAIL:', e?.message ?? String(e));
    console.log((e?.stack ?? '').split('\n').slice(0, 6).join('\n'));
  }
}
