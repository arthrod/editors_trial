// Ensure Chromium delivers about:blank before navigation; expose the race
// without altering the document, detector, recorder, or frame timestamps.
import { loadPlaywright } from '../../runner/witness.mjs';
const { chromium } = await loadPlaywright();
const launch = chromium.launch.bind(chromium);
chromium.launch = async (...args) => {
  const browser = await launch(...args);
  const newContext = browser.newContext.bind(browser);
  browser.newContext = async (...args) => {
    const context = await newContext(...args);
    const newPage = context.newPage.bind(context);
    context.newPage = async (...args) => {
      const page = await newPage(...args);
      const goto = page.goto.bind(page);
      page.goto = async (...args) => {
        await page.waitForTimeout(150);
        return goto(...args);
      };
      return page;
    };
    return context;
  };
  return browser;
};
