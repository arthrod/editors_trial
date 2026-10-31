/**
 * Debug: seed identity, open the panel, click "Choose file…", and report
 * exactly what the app did (sign-in dialog vs hidden file input).
 */
import { chromium } from 'playwright'

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.on('console', (m) => console.log(`[${m.type()}] ${m.text().slice(0, 200)}`))
page.on('pageerror', (e) => console.log('[pageerror]', String(e).slice(0, 300)))

await page.goto('http://127.0.0.1:5205/editor', { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => !!window._editor && !!window._authStore, { timeout: 90000 })

console.log(
  'before seed:',
  JSON.stringify(
    await page.evaluate(() => {
      const a = window._authStore.getState()
      return { loading: a.loading, profile: a.profile, session: a.session }
    })
  )
)

const seeded = await page.evaluate(() => {
  window._authStore.getState().setProfile({ id: 'harness-user', username: 'harness' })
  const a = window._authStore.getState()
  return {
    loading: a.loading,
    profileId: a.profile?.id ?? null,
    isVisitor: !a.loading && !(a.profile?.id ?? a.session?.id)
  }
})
console.log('after seed:', JSON.stringify(seeded))

await page.click('button[aria-label="Document settings"]')
await page.waitForTimeout(600)
await page.click('input[name="gear-accordion"][aria-label="Import & export"]')
await page.waitForTimeout(600)

const panel = await page.evaluate(() => {
  const el = Array.from(document.querySelectorAll('button')).find((b) =>
    (b.textContent || '').includes('Choose file')
  )
  const box = el?.getBoundingClientRect()
  return {
    found: !!el,
    visible: el ? !!(el.offsetWidth || el.offsetHeight) : false,
    rect: box ? { x: box.x, y: box.y, w: box.width, h: box.height } : null,
    disabled: el?.disabled ?? null,
    text: el?.textContent ?? null
  }
})
console.log('choose-file button:', JSON.stringify(panel))

await page.click('button:has-text("Choose file…")').catch((e) => console.log('click err', e.message.slice(0, 120)))
await page.waitForTimeout(1500)

const after = await page.evaluate(() => {
  const inputs = Array.from(document.querySelectorAll('input[type=file]')).map((i) => ({
    accept: i.getAttribute('accept'),
    inBody: i.parentElement === document.body,
    style: i.getAttribute('style')
  }))
  return {
    inputs,
    dialogs: Array.from(document.querySelectorAll('[role=dialog]')).map((d) =>
      (d.innerText || '').slice(0, 200)
    ),
    bodyHasSignIn: document.body.innerText.includes('Sign in')
  }
})
console.log('after click:', JSON.stringify(after, null, 1))
await browser.close()
