# Changes

2026-11-07 [doc] Surveyed research-map styles and tore down the GTU map; notes in docs/survey.md.

2026-11-07 [plan] Drafted PLAN.md: roster + OpenAlex, local embeddings, UMAP + Leiden, single-HTML output; vertical slice first.

2026-11-07 [note] OpenAlex needs a free API key since Feb 2026 (about $1/day budget); the container's shared no-key budget was already spent.

2026-11-07 [decision] Adopted the (rec) defaults for PLAN.md Q1-Q11 after 15 min without answers; OpenAlex API key (Q4) still open.

2026-11-07 [code] Phase 0 slice for UW Bothell STEM: roster/profile scraper, embed + UMAP + Leiden pipeline, single-file map page, tests.

2026-11-07 [decision] Model switched to paraphrase-multilingual-MiniLM-L12-v2: 48% top-5 share a curated area vs 40% for e5-small.

2026-11-07 [note] Slice uses directory and profile text; OpenAlex waits for an API key (Q4).

2026-11-07 [plan] PLAN.md revised from GTU build notes: record-level hybrid search, search test set, centred vectors, privacy scrub, advisor matching to Phase 1.

2026-11-07 [note] Centering person vectors: 48% -> 50% on curated-area check; adding courses w=0.15: 51%. Small, near noise at 87 people.

2026-11-07 [decision] Full-time faculty only (Q6 confirmed); user is getting the OpenAlex key; user reviewed 10 people's neighbours.

2026-11-07 [code] OpenAlex step: name matching within UW Bothell, works since 2011, candidates file for review; 59/89 matched, 2,306 works, ~$0.29.

2026-11-07 [decision] Person vector weights self .40 / works .30 / venues .15 / courses .15, centred: 52% neighbours share a curated area (was 48%).

2026-11-07 [code] Neighbour cut-off (90th percentile), e-mail/phone scrub with failing build check, off-map people searchable, publications on card.

2026-11-07 [code] OpenAlex matching: first+last search, UW-wide fallback, nickname table, strict UWB-only works for mixed records, topic check; 58/89, 2 wrong matches removed.

2026-11-07 [decision] Confirmed 7 OpenAlex matches by hand (overrides file); 65/89 matched. Phase 1 approved: record-level search, test set, advisor matching.

2026-11-07 [code] Record-level search (web/search.js), search test set (curated areas), advisor finder: hit@10 0.68 vs 0.38, MRR 0.83 vs 0.64.

2026-11-07 [code] Hand-written area and topic names (config/uwb-stem-labels.yaml), keyed by a member person; drafted by Claude for review.

2026-11-07 [code] Optional in-page search by meaning (transformers.js 4.3.1, all-MiniLM-L6-v2, 23 MB on request), blended 50/50: hit@10 0.76 vs 0.68.

2026-11-07 [decision] Search-by-meaning model is English (multilingual ONNX is 118 MB); map vectors stay multilingual. No hand-written test queries.
