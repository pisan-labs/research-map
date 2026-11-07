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

// Find a person: Yusuf Pisan on the UW Bothell map, otherwise the first mapped person.
const isUWB = file.includes("uwb-stem");
const who = isUWB ? { name: "Pisan", id: "yusuf-pisan" }
  : await page.evaluate(() => { const p = window.__rm.P.find((x) => !x.off && x.near.length); return { name: p.name.split(" ").slice(-1)[0], id: p.id }; });
await page.fill("#q", who.name);
await page.waitForTimeout(400);
const top = await page.evaluate(() => document.querySelector(".hits button b")?.textContent);
if (!top || !top.includes(who.name)) fail(`name search did not find ${who.name}: ` + top);
await page.evaluate((id) => window.__rm.select(window.__rm.P.findIndex((p) => p.id === id), true), who.id);
await page.waitForTimeout(700);
const card = await page.textContent("#panel");
if (!card.includes("Closest people")) fail("person card did not open");
const near = await page.$$eval(".near .who", (els) => els.map((e) => e.textContent));
if (near.length < 3) fail(`expected neighbours, got ${near.length}`);
console.log(`${who.name}'s neighbours:`, near.join(", "));
if (!page.url().includes(`#p=${who.id}`)) fail("URL hash not set: " + page.url());
if (shots) await page.screenshot({ path: `${shots}/person.png` });

// Keyword search (department checks only where the expected departments exist).
const KEYWORD_CHECKS = isUWB ? [["machine learning", "Computing & Software Systems"], ["ecology", "Biological Sciences"]] : [];
for (const [q, expect] of KEYWORD_CHECKS) {
  if (await page.$("#back")) await page.click("#back");
  await page.fill("#q", q);
  await page.waitForTimeout(400);
  // Department mix of the top 10 results (record search matches anyone with one relevant paper).
  const hits = await page.$$eval(".hits button", (els) => els.slice(0, 10).map((b) => window.__rm.P[Number(b.dataset.i)].department));
  const share = hits.filter((d) => d === expect).length / Math.max(hits.length, 1);
  console.log(`"${q}": top ${hits.length}, ${(share * 100).toFixed(0)}% in ${expect}`);
  if (!hits.length || share < 0.5) fail(`keyword search "${q}" looks wrong`);
}
if (!isUWB) { await page.fill("#q", "data"); await page.waitForTimeout(400); }
const ev = await page.$$eval(".hits .ev", (els) => els.length);
if (!ev) fail("search results show no evidence lines");
if (shots) await page.screenshot({ path: `${shots}/search.png` });

// Advisor finder: a project paragraph returns ten people with evidence.
await page.fill("#q", "");
await page.waitForTimeout(300);
if (await page.$("#back")) await page.click("#back");
await page.fill("#project", "Low-cost sensors and machine learning to monitor stream water quality and detect pollution events");
await page.click("#projectform button");
await page.waitForTimeout(600);
const adv = await page.$$eval(".hits li", (els) => els.length);
const head = await page.textContent("#panel h2");
console.log(`advisor finder: ${adv} people; first: ${await page.textContent(".hits li b")}`);
if (!head.includes("Possible advisors") || adv !== 10) fail(`advisor finder returned ${adv} (${head})`);
if (shots) await page.screenshot({ path: `${shots}/advisors.png` });
await page.click("#clearproject");

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
