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

2026-11-07 [decision] Large universities mapped one unit at a time from unit directories, engineering colleges first (default after 15 min).

2026-11-07 [code] Site adapters; UW Tacoma map (256 people, 6,180 works); UW CoE roster (293); 64-dim search vectors; degree-field fallback; site index.

2026-11-07 [code] Rosters for Northwestern McCormick (288, XML feed) and UCSD Jacobs (288); OpenAlex for UW CoE, McCormick, Jacobs waits for daily budget.

2026-11-07 [scope] UC Santa Barbara replaces UC San Diego; UCSB College of Engineering roster (170, research areas from profiles).

2026-11-07 [plan] Target hosting Netlify + Supabase + Render: migration order and service roles added to PLAN.md.

2026-11-07 [decision] Hosting: Netlify and Supabase now (new projects), pipeline on halflife, no Render yet. Netlify and Supabase CLIs installed via npm (pinned).

2026-11-07 [code] Netlify site uw-research-maps live. Supabase schema, loader, hybrid search SQL function and Edge Function written; tested on local Postgres.

2026-11-07 [note] Supabase project not created: free plan limit of 2 active projects per owner reached (upvoteme, dsa).

2026-11-08 [code] UW CoE OpenAlex: 274/301 matched, 23,620 works with the final name rules. McCormick map built (pre-fix matches; rematch pending).

2026-11-08 [doc] HANDOVER.md written for the next session; scheduled runs and PR watch cancelled at the user's request.

2026-11-08 [code] UW CoE matches checked by hand (free lookups): 17 overrides; strict mode had merged UW namesakes from other fields. 6 people still open (HANDOVER.md).

2026-11-08 [decision] Jose Lopez opted out of uw-coe (hematology; likely adjunct); default after 15 min. openalex and build now apply opt_out without a rescrape.

2026-11-09 [plan] OpenAlex key still missing in this session; user approved two one-shot fresh-session runs (day 1 UW CoE+UCSB 11-10 00:17 UTC, day 2 McCormick+UWT 11-11 00:17 UTC).

2026-11-09 [code] openalex: strict matches now drop author records whose papers disagree with the profile (per-record check; --record-margin, --no-record-check); unmeasured, day-1 run measures it on UW CoE.

2026-11-09 [decision] Supabase (Q19): Plabs session proposes schema app_research_map in the shared HintWise project; repo side done and tested locally; applying it waits for the user.

2026-11-09 [code] Migrations moved into schema app_research_map (pgvector in extensions, grants, fixed function search_path); Edge Function renamed research-map-search; loader and DB eval set search_path.

2026-11-09 [note] Session session_01JyJzMWrSwd6gUA3dgsLb31 (from 7 Nov) handed over on request; session_01JyJzMZ6ysgnDJhMkmezwAV continues. Corrected the OpenAlex key note: session age is not why the key is missing.

2026-11-09 [note] User approved applying app_research_map to the shared Supabase project; blocked: no Supabase management token reaches EnvFull sessions (helper session confirmed). Nothing applied.

2026-11-10 [code] Supabase: applied schema app_research_map to the shared HintWise project, exposed it, deployed research-map-search (approved by the user).

2026-11-10 [code] openalex: a 429 for a spent daily budget now stops cleanly (BudgetExceeded, exit 2) instead of 5 retries and a traceback. uwb-stem and uwt loaded into Supabase; nu-mccormick waits for the reset.

2026-11-10 [code] Supabase step d done: uwb-stem, uwt, nu-mccormick loaded; search answers for all three. Pages rebuilt with 2026-11-10 matches (small changes), committed and redeployed.

2026-11-10 [decision] Day-2 scheduled OpenAlex run disabled; OpenAlex runs move to the Mac (UW CoE, then UCSB, one per day). Tokens stay out of cloud environment secrets (user declined).

2026-11-10 [code] openalex names: transliterate letters NFKD drops (ł, ß, ø...) and Unicode dashes; roster short names (Mike) also search full forms (Michael). Recovers 10 of 28 unmatched UW CoE people.

2026-11-11 [decision] UW CoE: Noah Smith record drops accepted; Juming Tang pinned (all 3 records food engineering). The previous entry (name fix) is dated 2026-11-10 by mistake; it was 2026-11-11.

2026-11-11 [decision] McCormick stays on the live site (user); its area names are still computed and are queued for hand naming.

2026-11-11 [code] openalex names: curly apostrophes (O’Malley) normalised. Pins: UW CoE Jae-Hyun Chung, Jenny Robinson (check dropped her own record, kept a cardiologist); UCSB Xin (Eric) Wang (25 merged records), Palmstrøm, Klapperich, Chandrasekaran, Dey.

2026-11-11 [code] Field scan of 131 multi-record matches (free lookups): pinned 12 UW CoE and 16 UCSB people to drop namesake records (e.g. a cardiologist for Matt Reynolds); removed a duplicate Juming Tang pin (already pinned 2026-11-08).

2026-11-11 [doc] UCSB area and topic names drafted by Claude (config/ucsb-coe-labels.yaml, 10 areas, 17 topics) from departments, listed areas and OpenAlex topics; awaiting user review.
