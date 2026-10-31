/**
 * Fidus Writer probe used by harness/ui/shot.mjs (`--probe`).
 *
 * Drives the whole "load the corpus into the editor" flow:
 *   1. log in
 *   2. documents overview -> "Import document" dialog
 *   3. set the DOCX on the hidden #doc-uploader input
 *   4. press the dialog's "Import" button
 *   5. open the freshly imported document in the ProseMirror editor
 *
 * Env vars:
 *   FIDUS_BASE   base url (default http://localhost:5209)
 *   FIDUS_FILE   corpus docx path
 *   FIDUS_SCROLL optional text to scroll into view before the screenshot
 *   FIDUS_USER   username (default corpus)
 *   FIDUS_PASS   password (default corpus-pass-2026)
 */
const BASE = process.env.FIDUS_BASE || 'http://localhost:5209';
const FILE = process.env.FIDUS_FILE || '/Users/arthrod/temp/T/editors_trial/fixture/complex.docx';
const SCROLL = process.env.FIDUS_SCROLL || '';
const USER = process.env.FIDUS_USER || 'corpus';
const PASS = process.env.FIDUS_PASS || 'corpus-pass-2026';

export async function probe(page) {
  const log = [];
  const note = (m) => { log.push(m); console.log('[probe]', m); };

  // ---- 1. login ----------------------------------------------------------
  // The login form is rendered client-side, so wait for it to appear.
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  try {
    await page.locator('#id-login').waitFor({ state: 'visible', timeout: 20000 });
    await page.fill('#id-login', USER);
    await page.fill('#id-password', PASS);
    await Promise.all([
      page.waitForNavigation({ timeout: 30000 }).catch(() => {}),
      page.click('button[type=submit], input[type=submit], .fw-button:has-text("LOG IN")'),
    ]);
    await page.waitForTimeout(2500);
    note('login submitted, url=' + page.url());
  } catch (e) {
    note('login form not present (' + e.message.split('\n')[0] + ')');
  }

  // ---- 2. documents overview --------------------------------------------
  await page.goto(BASE + '/documents/overview/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  note('overview url=' + page.url());

  // ---- 3. open the import dialog ----------------------------------------
  const importBtn = page.locator('button.fw-text-menu:has-text("Import document")');
  await importBtn.waitFor({ state: 'visible', timeout: 30000 });
  await importBtn.click();
  await page.waitForTimeout(2000);

  const uploader = page.locator('#doc-uploader');
  await uploader.waitFor({ state: 'attached', timeout: 20000 });
  note('import dialog open, #doc-uploader attached');

  // ---- 4. hand the corpus to the (hidden) file input ---------------------
  await page.setInputFiles('#doc-uploader', FILE);
  note('setInputFiles -> ' + FILE);
  await page.waitForTimeout(500);

  // ---- 5. press the dialog's Import button -------------------------------
  const beforeHrefs = await page.evaluate(() =>
    Array.from(document.querySelectorAll('a.fw-data-table-title:not(.parentdir)')).map((a) => a.getAttribute('href'))
  );
  await page.click('.ui-dialog-buttonset button:has-text("Import")');
  note('clicked Import');

  // wait for the imported document to show up in the overview table
  let titles = [];
  let newHref = null;
  for (let i = 0; i < 120; i++) {
    const rows = await page.evaluate(() =>
      Array.from(document.querySelectorAll('a.fw-data-table-title:not(.parentdir)'))
        .map((a) => ({ href: a.getAttribute('href'), text: a.innerText.trim() }))
    );
    titles = rows.map((r) => r.text);
    const fresh = rows.filter((r) => !beforeHrefs.includes(r.href));
    if (fresh.length) { newHref = fresh[0].href; break; }
    await page.waitForTimeout(1000);
  }
  note('overview titles: ' + JSON.stringify(titles));
  note('new document href: ' + newHref);

  const alerts = await page.evaluate(() =>
    Array.from(document.querySelectorAll('.fw-alert, .alert, .fw-dialog p'))
      .map((e) => (e.innerText || '').trim())
      .filter(Boolean)
      .slice(0, 10)
  );
  note('alerts: ' + JSON.stringify(alerts));

  // ---- 6. open the imported document in the editor ----------------------
  const docLink = page.locator('a.fw-data-table-title:not(.parentdir)').first();
  const href = newHref || (await docLink.getAttribute('href'));
  const linkText = (await docLink.innerText()).trim();
  note('opening ' + href + ' (' + linkText + ')');
  await page.goto(BASE + href, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(8000);

  const pm = await page.locator('.ProseMirror').count();
  note('ProseMirror containers: ' + pm);
  if (pm) {
    await page.locator('.ProseMirror').first().waitFor({ state: 'visible', timeout: 30000 });
    await page.waitForTimeout(4000);
  }

  // Fidus gets stuck on a permanent "Updating document. Please wait..." cover
  // when its adjust-doc-to-template worker throws (RangeError: Invalid content
  // for node title).  The document itself is already rendered underneath, so we
  // lift the cover (equivalent of deactivateWait()) to photograph the render.
  const stuck = await page.evaluate(() => {
    const w = document.getElementById('wait');
    if (!w || !w.classList.contains('active')) return false;
    w.classList.remove('active');
    w.classList.remove('full');
    const m = w.querySelector('span.message');
    if (m) m.parentElement.removeChild(m);
    return true;
  });
  note('stuck wait overlay dismissed: ' + stuck);
  await page.waitForTimeout(1500);

  // ---- 7. optional scroll ------------------------------------------------
  if (SCROLL) {
    const ok = await page.evaluate((t) => {
      const needle = t.toLowerCase();
      let best = null, bestLen = Infinity;
      for (const n of document.querySelectorAll('body *')) {
        const txt = (n.textContent || '').toLowerCase();
        if (!txt.includes(needle)) continue;
        if (txt.length < bestLen) { best = n; bestLen = txt.length; }
      }
      if (!best) return false;
      best.scrollIntoView({ block: 'center', inline: 'center' });
      return true;
    }, SCROLL);
    note('scroll-text "' + SCROLL + '" -> ' + (ok ? 'found' : 'NOT FOUND'));
    await page.waitForTimeout(2000);
  }

  // ---- 8. report what actually rendered ---------------------------------
  const summary = await page.evaluate(() => {
    const body = document.body;
    const q = (sel) => body.querySelectorAll(sel).length;
    const text = body.innerText || '';
    const pmInfo = Array.from(document.querySelectorAll('.ProseMirror')).map((p, i) => ({
      i,
      id: p.id,
      cls: String(p.className).slice(0, 40),
      parentCls: String(p.parentElement ? p.parentElement.className : '').slice(0, 40),
      textLen: (p.innerText || '').length,
      textHead: (p.innerText || '').slice(0, 200),
    }));
    const imgs = Array.from(body.querySelectorAll('img'));
    return {
      pmInfo,
      bodyTextLen: text.length,
      bodyText: text.slice(0, 8000),
      images: imgs.length,
      imageInfo: imgs.map((i) => ({
        src: (i.getAttribute('src') || '').slice(0, 160),
        natural: i.naturalWidth + 'x' + i.naturalHeight,
        rendered: Math.round(i.getBoundingClientRect().width) + 'x' + Math.round(i.getBoundingClientRect().height),
        cls: String(i.className).slice(0, 40),
      })),
      tables: q('table'),
      tableRows: q('table tr'),
      tableCells: q('table td, table th'),
      svg: q('svg'),
      canvas: q('canvas'),
      objects: q('object'),
      math: q('math, .katex, .MathJax, [class*=math]'),
      footnoteEls: Array.from(body.querySelectorAll('[class*=footnote]')).map((e) => e.className.slice(0, 60)),
      endnoteEls: Array.from(body.querySelectorAll('[class*=endnote]')).map((e) => e.className.slice(0, 60)),
      commentEls: Array.from(body.querySelectorAll('[class*=comment]')).map((e) => e.className.slice(0, 60)),
      trackEls: Array.from(body.querySelectorAll('[data-track], [class*=track]')).map((e) => e.className.slice(0, 60)),
      marginBoxes: q('.marginbox, [class*=marginbox]'),
      figures: q('figure'),
      textboxEls: q('[class*=textbox], [class*=text-box], [class*=text_box]'),
      figureInfo: Array.from(body.querySelectorAll('figure')).map((f) => ({
        cls: String(f.className).slice(0, 50),
        w: Math.round(f.getBoundingClientRect().width),
        h: Math.round(f.getBoundingClientRect().height),
      })),
    };
  });
  note('summary: ' + JSON.stringify(summary, null, 1));

  return { log, url: page.url(), summary };
}
