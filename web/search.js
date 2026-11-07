// Record-level search, shared by the page and tests/search_eval.mjs.
//
// Each person contributes records: every publication title, their directory
// keywords, profile interests, bio, and OpenAlex topics. A query is scored
// against every record with BM25, scaled by how much of the query the record
// covers. A person's score is their best 8 records with weights
// 1, 0.7, 0.49, ... (GTU's rule), so one strong paper counts and a long
// publication list alone does not win. Results carry the matching records
// as evidence.
(function (root) {
  "use strict";

  const STOP = new Set(("a an and are as at be by for from has have in into is it its of on or that the their this to " +
    "using use used via with within we our new based study studies research analysis approach approaches toward towards " +
    "how what when which who why can").split(" "));

  const KIND_WEIGHT = { title: 1.0, keywords: 1.3, interests: 1.2, topic: 0.8, bio: 0.5, listed: 1.0 };
  const DECAY = 0.7;
  const BEST = 8;
  const K1 = 1.2, B = 0.75;

  function norm(s) {
    return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  // Light stemming: plurals and common suffixes, enough for "networks" ~ "network".
  function stem(w) {
    if (w.length <= 3) return w;
    if (w.endsWith("ies") && w.length > 4) return w.slice(0, -3) + "y";
    if (w.endsWith("sses")) return w.slice(0, -2);
    if (w.endsWith("es") && /(ch|sh|x|z)es$/.test(w)) return w.slice(0, -2);
    if (w.endsWith("s") && !/(ss|us|is|ics)$/.test(w)) w = w.slice(0, -1);
    if (w.endsWith("ing") && w.length > 6) return w.slice(0, -3);
    if (w.endsWith("ed") && w.length > 5) return w.slice(0, -2);
    return w;
  }

  function tokens(text) {
    const out = [];
    for (const raw of norm(text).split(/[^a-z0-9+#]+/)) {
      if (!raw || STOP.has(raw)) continue;
      if (raw.length < 2 && !/\d/.test(raw)) continue;
      out.push(stem(raw));
    }
    return out;
  }

  // people: page rows. opts.useListed: include department-curated area names
  // as records (the page does; the evaluation must not, they are its answers).
  function buildIndex(people, opts = {}) {
    const recs = [];
    const add = (p, kind, text, extra) => {
      const toks = tokens(text);
      if (toks.length) recs.push({ p, kind, text, toks, ...extra });
    };
    people.forEach((person, p) => {
      for (const w of person.pubs || []) add(p, "title", w[0], { y: w[1], v: w[2], u: w[3] });
      if (person.keywords) add(p, "keywords", person.keywords);
      if (person.interests && person.interests !== person.keywords) add(p, "interests", person.interests);
      if (person.bio) add(p, "bio", person.bio);
      for (const t of person.oa_topics || []) add(p, "topic", t);
      if (opts.useListed) for (const a of person.listed || []) add(p, "listed", a);
    });
    const df = new Map();
    let total = 0;
    for (const r of recs) {
      total += r.toks.length;
      r.tf = new Map();
      for (const t of r.toks) r.tf.set(t, (r.tf.get(t) || 0) + 1);
      for (const t of r.tf.keys()) df.set(t, (df.get(t) || 0) + 1);
    }
    const names = people.map((x) => norm(x.name).replace(/\([^)]*\)/g, " ").replace(/\s+/g, " ").trim());
    return { people, recs, df, N: recs.length, avgdl: total / Math.max(recs.length, 1), names };
  }

  function idf(index, t) {
    const n = index.df.get(t) || 0;
    return Math.log(1 + (index.N - n + 0.5) / (n + 0.5));
  }

  // Returns [{p, score, evidence: [record, ...]}], best first.
  function search(index, query, opts = {}) {
    const q = norm(query).trim();
    const terms = [...new Set(tokens(query))];
    if (!terms.length) return [];
    const kindWeight = opts.kindWeight || KIND_WEIGHT;
    const best = opts.best || BEST;
    // Short queries must be covered closely; a pasted project description
    // (many terms) is scored by BM25 alone.
    const power = opts.power !== undefined ? opts.power : terms.length <= 3 ? 2 : terms.length <= 8 ? 1 : 0;
    const phrase = terms.length > 1 && terms.length <= 6 ? terms.join(" ") : "";
    const qidf = new Map(terms.map((t) => [t, idf(index, t)]));
    const per = new Map();
    for (const r of index.recs) {
      let s = 0, hit = 0;
      for (const t of terms) {
        const f = r.tf.get(t);
        if (!f) continue;
        hit += 1;
        s += qidf.get(t) * (f * (K1 + 1)) / (f + K1 * (1 - B + B * r.toks.length / index.avgdl));
      }
      if (!hit) continue;
      s *= Math.pow(hit / terms.length, power) * (kindWeight[r.kind] || 1);
      if (phrase && r.toks.join(" ").includes(phrase)) s *= 1.5;
      if (!per.has(r.p)) per.set(r.p, []);
      per.get(r.p).push({ r, s });
    }
    const out = [];
    for (const [p, list] of per) {
      list.sort((a, b) => b.s - a.s);
      let score = 0;
      list.slice(0, best).forEach((x, k) => { score += x.s * Math.pow(DECAY, k); });
      out.push({ p, score, evidence: list.slice(0, 3).map((x) => x.r) });
    }
    // A name match always comes first.
    if (q.length >= 3) {
      index.names.forEach((n, p) => {
        if (!n.includes(q)) return;
        const found = out.find((x) => x.p === p);
        if (found) found.score += 1e6;
        else out.push({ p, score: 1e6, evidence: [] });
      });
    }
    out.sort((a, b) => b.score - a.score || index.people[a.p].name.localeCompare(index.people[b.p].name));
    return opts.limit ? out.slice(0, opts.limit) : out;
  }

  const api = { norm, tokens, stem, buildIndex, search };
  root.RMSearch = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
