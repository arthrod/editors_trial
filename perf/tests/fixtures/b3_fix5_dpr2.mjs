import { loadPlaywright } from '../../runner/witness.mjs';
const { chromium } = await loadPlaywright();
const launch = chromium.launch.bind(chromium);
chromium.launch = async (...args) => {
 const browser = await launch(...args);
 const newContext = browser.newContext.bind(browser);
 browser.newContext = async (opts) => newContext({...opts, deviceScaleFactor: 2});
 return browser;
};
