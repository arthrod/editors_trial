import assert from 'node:assert/strict';
import { test } from 'node:test';

const downloadModule = await import('./download.ts').catch(() => ({}));

test('the download helper creates a DOCX blob with the expected MIME type and bytes', async () => {
  assert.equal(typeof downloadModule.createDocxBlob, 'function');

  const bytes = new Uint8Array([80, 75, 3, 4, 0, 0]);
  const blob = downloadModule.createDocxBlob(bytes);

  assert.equal(
    blob.type,
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  );
  assert.equal(blob.size, bytes.byteLength);
  assert.deepEqual(new Uint8Array(await blob.arrayBuffer()), bytes);
});
