import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {injectCaretMask, CARET_MASK_CSS} from '../runner/witness.mjs';

test('repeated and concurrent masking installs one stylesheet per document', async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage();
    await page.setContent('<div contenteditable="true">text</div>');
    const records = await Promise.all(Array.from({length:4}, () => injectCaretMask(page)));
    assert.ok(records.every(record => record.caret_masked));
    const count = () => page.locator('style').count();
    assert.equal(await count(), 1);
    assert.equal(await page.locator('style').textContent(), CARET_MASK_CSS);
    await page.setContent('<div contenteditable="true">new document</div>');
    assert.equal((await injectCaretMask(page)).caret_masked, true);
    assert.equal(await count(), 1);
  } finally { await browser.close(); }
});

test('a closed page reports failed masking rather than a cached success', async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage();
    await injectCaretMask(page);
    await page.close();
    const result = await injectCaretMask(page);
    assert.equal(result.caret_masked, false);
    assert.ok(result.caret_mask_error);
  } finally { await browser.close(); }
});
