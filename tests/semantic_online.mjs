// Online check of in-page search by meaning (needs network): node tests/semantic_online.mjs [page]
// Loads the page, turns search by meaning on (downloads transformers.js and the model),
// and checks that blended results appear for a keyword search and the advisor finder.
import { createRequire } from "node:module";
import path from "node:path";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const file = path.resolve(process.argv[2] || "site/uwb-stem/index.html");
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto("file://" + file);
await page.waitForFunction(() => window.__rm);
await page.fill("#q", "deep learning for medical images");
await page.waitForSelector("#semon");
const before = await page.$$eval(".hits li b", (els) => els.slice(0, 5).map((e) => e.textContent));
const t0 = Date.now();
await page.click("#semon");
await page.waitForFunction(() => window.__rm.sem.state === "on" || window.__rm.sem.state === "failed", null, { timeout: 180000 });
const state = await page.evaluate(() => [window.__rm.sem.state, window.__rm.sem.error]);
console.log(`model: ${state[0]} in ${((Date.now() - t0) / 1000).toFixed(1)}s ${state[1]}`);
await page.waitForTimeout(1500);
const after = await page.$$eval(".hits li b", (els) => els.slice(0, 5).map((e) => e.textContent));
const line = await page.textContent(".semline");
console.log("keyword top 5:", before.join(", "));
console.log("blended top 5:", after.join(", "));
await page.evaluate(() => window.__rm.runProject("Low-cost sensors and machine learning to monitor stream water quality and detect pollution events"));
await page.waitForTimeout(2500);
const adv = await page.$$eval(".hits li b", (els) => els.map((e) => e.textContent));
console.log("advisors (blended):", adv.join(", "));
await page.screenshot({ path: process.argv[3] || "/tmp/semantic.png" });
await browser.close();
if (state[0] !== "on" || !line.includes("is on") || errors.length) { console.error("FAIL", errors); process.exit(1); }
console.log("semantic online check passed");
