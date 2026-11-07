// Smoke test for a built map: node tests/smoke.mjs site/<slug>/index.html [screenshot-dir]
import { createRequire } from "node:module";
import path from "node:path";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const file = path.resolve(process.argv[2] || "site/uwb-stem/index.html");
const shots = process.argv[3];
const fail = (m) => { console.error("FAIL:", m); process.exitCode = 1; };

const browser = await chromium.launch();
const errors = [];
async function open(opts) {
  const page = await browser.newPage(opts);
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  // Offline: block every network request, the file must be self-contained.
  await page.route(/^https?:/, (r) => { errors.push("network: " + r.request().url()); r.abort(); });
  await page.goto("file://" + file);
  await page.waitForFunction(() => window.__rm);
  return page;
}

const page = await open({ viewport: { width: 1360, height: 860 }, deviceScaleFactor: 2 });
const n = await page.evaluate(() => window.__rm.P.length);
if (n < 50) fail(`only ${n} people`);
if (shots) await page.screenshot({ path: `${shots}/overview.png` });

// Find a person.
await page.fill("#q", "Pisan");
await page.waitForTimeout(400);
const top = await page.evaluate(() => document.querySelector(".hits button b")?.textContent);
if (!top || !top.includes("Pisan")) fail("name search did not find Yusuf Pisan: " + top);
await page.press("#q", "Enter");
await page.waitForTimeout(700);
const card = await page.textContent("#panel");
if (!card.includes("Closest people")) fail("person card did not open");
const near = await page.$$eval(".near .who", (els) => els.map((e) => e.textContent));
if (near.length !== 10) fail(`expected 10 neighbours, got ${near.length}`);
console.log("Pisan's neighbours:", near.join(", "));
if (!page.url().includes("#p=yusuf-pisan")) fail("URL hash not set: " + page.url());
if (shots) await page.screenshot({ path: `${shots}/person.png` });

// Keyword search.
for (const [q, expect] of [["machine learning", "Computing & Software Systems"], ["ecology", "Biological Sciences"]]) {
  if (await page.$("#back")) await page.click("#back");
  await page.fill("#q", q);
  await page.waitForTimeout(400);
  const hits = await page.evaluate(() => window.__rm.P.filter((p) => document.querySelector(`.hits [data-i="${p.i}"]`)).map((p) => p.department));
  const share = hits.filter((d) => d === expect).length / Math.max(hits.length, 1);
  console.log(`"${q}": ${hits.length} hits, ${(share * 100).toFixed(0)}% in ${expect}`);
  if (!hits.length || share < 0.5) fail(`keyword search "${q}" looks wrong`);
}
if (shots) await page.screenshot({ path: `${shots}/search.png` });

// Zoomed-in labels, then dark mode on a phone.
await page.fill("#q", "");
await page.waitForTimeout(300);
await page.click("#zin"); await page.click("#zin"); await page.click("#zin");
await page.waitForTimeout(500);
if (shots) await page.screenshot({ path: `${shots}/zoomed.png` });

const phone = await open({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, colorScheme: "dark" });
const overflow = await phone.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
if (overflow) fail("horizontal scroll on phone width");
if (shots) await phone.screenshot({ path: `${shots}/phone-dark.png`, fullPage: false });

if (errors.length) fail("console/page errors:\n  " + errors.join("\n  "));
await browser.close();
console.log(process.exitCode ? "smoke test FAILED" : `smoke test passed (${n} people)`);
