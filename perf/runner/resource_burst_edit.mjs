/**
 * B8 resource lane edit burst: real keyboard input and the same witness families
 * as the B4 input and B9 typing lanes (DOM text, canvas model, paint ink).
 */
import { clockSkew, witnessFrame } from './witness.mjs';

export function countToken(text, token) {
  const source = String(text || '');
  if (!token) return 0;
  let count = 0;
  let start = 0;
  while (true) {
    const at = source.indexOf(token, start);
    if (at < 0) return count;
    count += 1;
    start = at + token.length;
  }
}

const READ_DOM_TEXT = (selector) => {
  const el = document.querySelector(selector);
  if (!el) return '';
  const tag = String(el.tagName || '').toUpperCase();
  if ((tag === 'INPUT' || tag === 'TEXTAREA') && 'value' in el) return String(el.value || '');
  return String(el.innerText || el.textContent || '');
};

const READ_CANVAS_MODEL_TEXT = () => {
  const inst = window.__CANVAS_EDITOR_INSTANCE__;
  const cmd = inst && inst.command;
  if (!cmd || typeof cmd.getValue !== 'function') return null;
  const out = [];
  const walk = (node) => {
    if (Array.isArray(node)) return node.forEach(walk);
    if (!node || typeof node !== 'object') return;
    if (typeof node.value === 'string') out.push(node.value);
    for (const key of ['valueList', 'trList', 'tdList']) {
      if (node[key]) walk(node[key]);
    }
  };
  const data = cmd.getValue().data;
  if (!data || typeof data !== 'object') return '';
  for (const zone of ['header', 'main', 'footer']) walk(data[zone]);
  return out.join('').replace(/\n/g, ' ');
};

async function readWitnessText(page, witness, selector) {
  if (witness?.mode === 'canvas_model') {
    const text = await page.evaluate(READ_CANVAS_MODEL_TEXT);
    return text == null ? '' : String(text);
  }
  if (!selector) return '';
  return page.evaluate(READ_DOM_TEXT, selector);
}

async function armTrustedKeyCounter(page) {
  await page.evaluate(() => {
    window.__b8burst = { keys: 0 };
    const onKey = (event) => {
      if (event.isTrusted && event.key && event.key.length === 1) {
        window.__b8burst.keys += 1;
      }
    };
    window.__b8burst.stop = () => document.removeEventListener('keydown', onKey, true);
    document.addEventListener('keydown', onKey, true);
  });
}

async function trustedKeyCount(page) {
  return page.evaluate(() => {
    try {
      window.__b8burst?.stop?.();
    } catch {
      /* the page may already have navigated away */
    }
    return Number(window.__b8burst?.keys || 0);
  });
}

async function applyPaintInkBurst(page, cdp, { selector, text, repetitions }) {
  await page.locator(selector).first().click({ timeout: 30000 });
  const clock = await clockSkew(page, cdp, { settleMs: 0, samples: 5 });
  await armTrustedKeyCounter(page);
  const witness = await witnessFrame(page, cdp, {
    region: { selector },
    clockCheck: clock,
    settleMs: 100,
    windowMs: 3000,
    arm: async () => {
      for (let i = 0; i < repetitions; i++) {
        await page.keyboard.type(text, { delay: 0 });
      }
      return page.evaluate(() => performance.now());
    },
  });
  const keys = await trustedKeyCount(page);
  const minKeys = String(text || '').length * Math.max(0, repetitions);
  const applied =
    witness.outcome === 'witnessed'
    && witness.document_scoped !== false
    && keys >= minKeys;
  return {
    applied,
    kind: 'keyboard.type',
    text,
    repetitions,
    witness: 'paint_ink',
    trusted_keys: keys,
    paint_witness: witness.outcome,
    paint_refusal: witness.refusal_reason || null,
  };
}

/**
 * @param {import('playwright').Page} page
 * @param {import('playwright').CDPSession} cdp
 * @param {{ selector: string, text: string, repetitions: number, witness?: { mode: string } }} params
 */
export async function applyResourceBurst(page, cdp, params) {
  const repetitions = Math.max(0, Number(params.repetitions || 0));
  const text = params.text || '';
  const selector = params.selector || '';
  const witness = params.witness || { mode: 'dom_text' };
  void cdp;

  if (witness.mode === 'paint_ink') {
    return applyPaintInkBurst(page, cdp, { selector, text, repetitions });
  }

  if (selector) {
    await page.locator(selector).first().click({ timeout: 30000 });
  }

  let beforeText = await readWitnessText(page, witness, selector);
  await armTrustedKeyCounter(page);

  for (let i = 0; i < repetitions; i++) {
    await page.keyboard.type(text, { delay: 0 });
  }

  let applied = false;
  let afterText = beforeText;
  const witnessDetail = witness.mode;

  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => resolve(null))));
  afterText = await readWitnessText(page, witness, selector);
  const keys = await trustedKeyCount(page);
  const minKeys = text.length * repetitions;
  const delta = countToken(afterText, text) - countToken(beforeText, text);
  applied = repetitions > 0 && text.length > 0 && delta === repetitions && keys >= minKeys;

  return {
    applied,
    editorText: afterText,
    beforeText,
    kind: 'keyboard.type',
    text,
    repetitions,
    witness: witnessDetail,
    trusted_keys: keys,
    text_delta: delta,
  };
}
