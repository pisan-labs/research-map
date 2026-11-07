// Search test set: node tests/search_eval.mjs <slug> [--json]
//
// Queries are the department-curated research areas (rosters/<slug>-areas.json):
// the query is the area name, the relevant people are its listed members.
// The curated lists are kept out of the search index here, or the test would
// read its own answers. Extra hand-written queries can be added in
// tests/<slug>-queries.json as [{"q": "...", "relevant": ["person-id", ...]}].
//
// Metrics (as GTU reports them):
//   hit@10  share of relevant people found in the top 10 (out of min(10, relevant))
//   MRR     mean of 1 / rank of the first relevant person
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const S = require(path.join(root, "web/search.js"));

const slug = process.argv[2] || "uwb-stem";
const asJson = process.argv.includes("--json");
const payload = JSON.parse(fs.readFileSync(path.join(root, "data", slug, "payload.json"), "utf8"));
const P = payload.people;
const areas = JSON.parse(fs.readFileSync(path.join(root, "rosters", `${slug}-areas.json`), "utf8"));

const queries = Object.entries(areas)
  .map(([q, ids]) => ({ q, relevant: ids.filter((id) => P.some((p) => p.id === id)), source: "curated" }))
  .filter((x) => x.relevant.length >= 2);
const extra = path.join(root, "tests", `${slug}-queries.json`);
if (fs.existsSync(extra)) for (const x of JSON.parse(fs.readFileSync(extra, "utf8"))) queries.push({ ...x, source: "hand" });

// V1: the person-level keyword search the page used before record-level search.
function searchV1(q) {
  const norm = S.norm;
  const words = norm(q).split(/[\s,/]+/).filter((w) => w.length > 1);
  const phrase = norm(q).trim();
  const hits = [];
  for (const [i, p] of P.entries()) {
    const name = norm(p.name);
    const kw = norm([p.keywords, p.interests, (p.terms || []).join(" "), (p.oa_topics || []).join(" . ")].join(" . "));
    const bio = norm(p.bio);
    const titles = (p.pubs || []).map((w) => norm(w[0]));
    let score = 0, all = true;
    if (name.includes(phrase)) score += 10;
    if (phrase.includes(" ") && kw.includes(phrase)) score += 6;
    for (const w of words) {
      const a = name.includes(w), b = kw.includes(w), c = bio.includes(w);
      const n = titles.reduce((k, t) => k + t.includes(w), 0);
      if (!(a || b || c || n)) all = false;
      score += (a ? 3 : 0) + (b ? 2 : 0) + (c ? 1 : 0) + Math.min(n, 4) * 0.5;
    }
    if (all && score > 0) hits.push({ p: i, score });
  }
  hits.sort((a, b) => b.score - a.score);
  return hits;
}

const index = S.buildIndex(P, { useListed: false });
const engines = {
  "V1 person keyword": (q) => searchV1(q),
  "V2 record BM25": (q) => S.search(index, q),
};

// Search by meaning: embed each query with the same transformers.js model the
// page loads (skipped if the package or the vectors are missing).
const sm = payload.meta.search_model;
const qvecs = new Map();
if (sm && index.hasVectors) {
  try {
    const { pipeline, env } = await import("@huggingface/transformers");
    env.allowLocalModels = false;
    const embed = await pipeline("feature-extraction", sm.browser, { dtype: "q8" });
    for (const { q } of queries) {
      const out = await embed(q, { pooling: sm.pooling, normalize: true });
      qvecs.set(q, Float32Array.from(out.data));
    }
    engines["V3 hybrid 50/50"] = (q) => S.search(index, q, { qvec: qvecs.get(q) });
    if (process.argv.includes("--variants")) {
      engines["meaning only"] = (q) => S.search(index, q, { qvec: qvecs.get(q), alpha: 1 });
      engines["hybrid 30/70"] = (q) => S.search(index, q, { qvec: qvecs.get(q), alpha: 0.3 });
      engines["hybrid 70/30"] = (q) => S.search(index, q, { qvec: qvecs.get(q), alpha: 0.7 });
    }
  } catch (e) {
    console.error(`search by meaning skipped: ${e.message.split("\n")[0]}`);
  }
}

function evaluate(run) {
  const rows = queries.map(({ q, relevant, source }) => {
    const ranked = run(q).map((h) => P[h.p].id);
    const rel = new Set(relevant);
    const top = ranked.slice(0, 10);
    const hit = top.filter((id) => rel.has(id)).length / Math.min(10, rel.size);
    const first = ranked.findIndex((id) => rel.has(id));
    return { q, source, n: rel.size, hit, rr: first < 0 ? 0 : 1 / (first + 1) };
  });
  const mean = (xs) => xs.reduce((a, b) => a + b, 0) / Math.max(xs.length, 1);
  return { rows, hit10: mean(rows.map((r) => r.hit)), mrr: mean(rows.map((r) => r.rr)) };
}

const results = Object.fromEntries(Object.entries(engines).map(([k, f]) => [k, evaluate(f)]));
if (asJson) {
  console.log(JSON.stringify(Object.fromEntries(Object.entries(results).map(([k, v]) => [k, { hit10: v.hit10, mrr: v.mrr }]))));
} else {
  console.log(`${queries.length} queries (${queries.filter((x) => x.source === "curated").length} curated areas)`);
  for (const [k, v] of Object.entries(results)) console.log(`${k.padEnd(20)} hit@10 ${v.hit10.toFixed(2)}  MRR ${v.mrr.toFixed(2)}`);
  if (process.argv.includes("--detail")) {
    const names = Object.keys(results);
    console.log(`  ${"query".padEnd(48)}  n  ` + names.map((n) => n.split(" ")[0].padEnd(10)).join(" "));
    results[names[0]].rows.forEach((r, i) => console.log(`  ${r.q.slice(0, 48).padEnd(48)} ${String(r.n).padStart(2)}  ` +
      names.map((n) => `${results[n].rows[i].hit.toFixed(2)}/${results[n].rows[i].rr.toFixed(2)}`.padEnd(10)).join(" ")));
  }
}
