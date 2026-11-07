// Unit checks for web/search.js: node tests/search_unit.mjs
import { createRequire } from "node:module";
import assert from "node:assert/strict";
const require = createRequire(import.meta.url);
const S = require("../web/search.js");

assert.deepEqual(S.tokens("the and of to with"), [], "stop words are dropped");
assert.deepEqual(S.tokens("Neural Networks, studies"), ["neural", "network"], "plurals stemmed, stop words dropped");
assert.equal(S.stem("learning"), "learn");
assert.equal(S.stem("analysis"), "analysis");

const people = [
  { name: "Ann Lee", keywords: "plant ecology", pubs: [["Soil microbes in prairies", 2020, "", ""]], oa_topics: [], listed: [] },
  { name: "Bo Kim", keywords: "machine learning", pubs: [["Deep networks for images", 2021, "", ""], ["Machine learning for soil", 2019, "", ""]], oa_topics: [], listed: [] },
];
const idx = S.buildIndex(people);
let r = S.search(idx, "machine learning");
assert.equal(people[r[0].p].name, "Bo Kim");
assert.ok(r[0].evidence.length >= 1 && r[0].evidence[0].text.toLowerCase().includes("machine learning"));
r = S.search(idx, "soil ecology");
assert.equal(people[r[0].p].name, "Ann Lee", "covering more of the query ranks higher");
r = S.search(idx, "ann lee");
assert.equal(people[r[0].p].name, "Ann Lee", "name match first");
console.log("search unit tests passed");
