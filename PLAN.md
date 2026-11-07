# Plan: university research map

Status: **defaults adopted, 2026-11-07; revised the same day after GTU's
build notes** (see "Lessons from GTU's build notes"). Each "(rec)" default
is the working decision; answer a question by number to reverse it. Q4: you
are getting the OpenAlex key. Q6 confirmed: full-time faculty only. New
questions: Q12 and Q13.

Background and examples: [docs/survey.md](docs/survey.md).

**Progress, 2026-11-07:** Phase 0 vertical slice built for UW Bothell STEM
(`site/uwb-stem/index.html`, 87 faculty). OpenAlex is not wired in yet
because there is no API key (Q4); the slice uses directory keywords and
profile text instead. See "Phase 0 status" below.

## Goal

A reusable generator: given a university (or one unit) and its faculty
roster, build an interactive research map in the spirit of the GTU map. Each
point is a researcher; nearby points work on similar things. Output is one
self-contained HTML file that works offline and can be hosted anywhere.

## Lessons from GTU's build notes

Source: [How the Research Map was built](https://tanitim.gtu.edu.tr/arastirma-haritasi/nasil-yapildi.html)
(read 2026-11-07). The survey already covered their vectors, layout and page.
What the notes add, and what it changes here:

| GTU finding | Change to this plan |
|---|---|
| Averaging a person's work hides their few but important papers; search must rank **records** (titles), then people | Search moves from person text to record-level: each work is indexed, a person's score is their best 8 records with weights 1, 0.7, 0.49, …, and results show the matching titles as evidence (Phase 1) |
| Meaning + keyword (BM25) together beat either alone: top-10 hit rate 0.72 (keyword only) → 0.80 (hybrid) → 0.81 (+ LLM profiles). Keywords catch acronyms (GNSS, Li-ion); meaning catches phrase queries ("biosensors for disease diagnosis": 0.19 → 0.89) | In-page BM25 over records first (offline, no model), then add in-page semantic search and blend 50/50. A query that names several concepts is scored by how many it covers |
| "Don't tune without measuring": many improvements did nothing once measured | Two fixed checks run on every build: (a) neighbours vs the departments' curated areas (exists); (b) a search test set with top-10 hit rate and MRR. UW Bothell's curated area lists give (b) for free: the query is the area name, the relevant people are its listed members. Add 10–20 hand-written phrase queries |
| LLM-written profiles help ranking a little; never shown as evidence; grounded in titles, JSON schema, temperature 0, human review before anything is shown | Optional Phase 2 step, ranking only, with the same rules. Needs a decision on sending public titles to the local `claude` CLI (Q12) |
| Person vector has 5 parts: titles 0.45, venues 0.15, courses 0.15, supervised theses 0.15, projects 0.10 | Ours, once OpenAlex is in: works (title + abstract) 0.40, self-description (directory keywords, interests, bio) 0.20, venues 0.15, courses 0.15, grants 0.10, all re-tuned with check (a). Theses: no public source here. Grants: NSF and NIH award APIs, free, no key (Q13) |
| PCA to 96 dims, then remove the Turkish/English direction | Measured on our slice: subtracting the mean vector raises check (a) from 48% to 50% and makes similarity scores centre on 0; PCA adds nothing at 87 people. Adopt centering now. Language-direction removal only when a map mixes languages (second university, Phase 1) |
| Neighbours below cosine 0.45 are not shown | After centering, hide neighbours below a cut-off set from the score distribution, rather than always showing 10 |
| Fewer than 6 records: hollow marker. Too few records: off the map but still found by search | Same thresholds once records exist. People left off the map (2 now) must still be searchable; today they are not |
| No e-mails or phone numbers on the page; every release scanned for ID-like numbers | Scrub e-mails and phone numbers from bios before bundling (one bio now carries an e-mail address); release scan in the build |
| Main real use: students matched to industry project ideas by finding possible advisors | Promote "describe a project, get advisors with evidence titles" from Phase 2 to Phase 1; add students looking for advisors to the audience |
| Map page works alone; an optional campus search service adds better search, and the page falls back to built-in search when the service is down. Read-only public API, rate-limited | Keep the no-server default. If a service is ever added, use the same fallback design so the file still works offline |
| One-command update script backs up and rolls back the web server config | Phase 3 refresh script follows the same rule |
| Privacy-preserving visit counts: no IPs, a daily-rotated salted hash | Only if the map is hosted somewhere we control; not for GitHub Pages |
| 800 people, 40k titles: 16 MB page (7.5 MB compressed) | Keep the 5 MB per 1,000 people budget; ship titles, not vectors |

## Architecture

```
roster.csv ─┐
            ├─> fetch (OpenAlex, cached) ─> match people ─> embed works ─> person vectors
config.yaml ┘                                                                   │
                     single HTML <── bundle <── labels <── areas (Leiden) <── layout (UMAP)
                                                                   └── co-author edges, neighbours
```

| Stage | Default | Notes |
|---|---|---|
| Roster | CSV: name, department, unit, title, ORCID / OpenAlex ID (optional) | OpenAlex has no departments, and its "last known institution" includes students and alumni, so a roster defines who is on the map |
| Fetch | OpenAlex works per person, last 15 years, cached as JSONL under `data/` (gitignored) | Free API key needed. About 1,000 list calls a day on the free budget, enough for a few thousand people per day |
| Match | ORCID first, then name + institution search, then a manual `overrides.csv`; print an unmatched report | Disambiguation is the main data-quality risk |
| Embed | Local `sentence-transformers`, one vector per work (title + abstract), per venue, per course, per grant, plus the self-description fields. Person vector = weighted mean of components (weights above), works weighted by recency (last 10 years 1.0, the 10 before 0.6, older 0.35), then centred | No paid API. Model choice below |
| Layout | UMAP, cosine | Choice below |
| Areas | Leiden on a k-nearest-neighbour graph, two resolutions: broad areas and fine topics | Gives labels that change with zoom |
| Labels | Distinctive terms (c-TF-IDF) plus the most common OpenAlex topic names; optional naming pass with the local `claude` CLI; `labels.yaml` to override by hand | Never the Anthropic API with a key |
| Extras | Up to 10 nearest people per person (with shared terms), hidden below a similarity cut-off; co-author pairs within the roster | Precomputed, so the page needs no vectors |
| Search index | Records (work titles, courses, grants) with BM25 statistics, inlined; later a compact vector per record for semantic search | Person score from best 8 records; evidence titles shown |
| Checks | Neighbours vs curated areas; search test set (top-10 hit rate, MRR); privacy scan (e-mails, phone and ID-like numbers) | Printed on every build; the privacy scan fails the build |
| Bundle | Inline JSON, JS, CSS into one HTML; size budget about 10 MB per 1,000 people (revised 2026-11-07 for search vectors) | GTU is 16 MB for 800 people because it ships every title and vector |

Front end: vanilla JS, D3 v7 for zoom and scales, Canvas 2D for drawing
(SVG slows past a few thousand points). No build step. Python pipeline
managed with `uv`, tests with `pytest`, page smoke test with Playwright.

### Technical choices

**Text model**

| Option | Strength | Weakness |
|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2` (chosen) | Multilingual, small; 48% on check (a), tied best | General-purpose, not science-tuned |
| `intfloat/multilingual-e5-small` / `-base` (GTU used e5-base) | Multilingual | 40% on check (a) with our profile text |
| SPECTER2 | Trained on scientific papers (title + abstract) | English only; 45% on profile text, worth re-testing on OpenAlex abstracts |
| `BAAI/bge-m3` (GTU's search model) | Strong multilingual retrieval, long input | About 2 GB; slow on CPU. Candidate for record-level semantic search, not person vectors |
| OpenAlex topic vectors only | No ML, consistent across universities | Coarse (about 4,500 topics); misses specifics |

Re-run the comparison once OpenAlex works are in: profile text and paper
abstracts may favour different models.

**Layout**

| Option | Strength | Weakness |
|---|---|---|
| UMAP (rec) | Keeps more global structure; fast; can place new people into an existing map, which keeps refreshes stable | Has knobs that change the picture |
| t-SNE (GTU) | Clean local clusters | Distances between clusters mean little; refreshes reshuffle the map |
| Force layout on the neighbour graph (VOSviewer style) | Easy to explain ("linked = similar") | Slower; can tangle |

**Areas**

| Option | Strength | Weakness |
|---|---|---|
| Leiden on neighbour graph (rec) | Two resolutions give broad and fine areas; standard in bibliometrics | Resolution must be tuned |
| k-means (GTU) | Simple; fixed number of areas | One level only; forces round clusters |
| HDBSCAN on the 2-D map | Finds noise points | Depends on the projection, not the real similarity |

**Search**

| Option | Strength | Weakness |
|---|---|---|
| Keyword search over person text (V1, done) | Works offline, instant | Misses synonyms; ranks people, not evidence |
| Record-level BM25 in the page, person = best 8 records, evidence titles (rec for Phase 1) | Offline; finds people with one relevant paper; GTU's baseline | Misses synonyms and phrasing |
| + in-page semantic search blended 50/50 (rec for Phase 2) | GTU's measured gain (0.72 → 0.80 top-10); still offline | 30–120 MB model download on first search |
| Small search server (GTU live site), page falls back to built-in search | Larger models; API | A server to run and secure |

**Hosting**

| Option | Strength | Weakness |
|---|---|---|
| One self-contained HTML per map (rec) | Email it, put it on any web server or GitHub Pages, open offline | Size grows with people and works |
| Static folder (HTML + JSON) | Smaller first load, data fetched lazily | Needs a web server; no file:// |
| Server app | Live search, logins, updates | Hosting and maintenance |

## Phases

### Phase 0: vertical slice (the first working map)

Target: one unit of 100–200 faculty you know well, so you can judge whether
neighbours make sense. Suggested: UW Bothell School of STEM.

1. Skeleton: `pipeline/` (uv project, pytest), `web/` (template, JS, CSS),
   `config/<slug>.yaml`, `data/` (gitignored cache), `site/` (output).
2. Roster CSV for the unit (scrape the public directory or by hand).
3. Fetch and cache works; match people; print the unmatched report.
4. Embed, UMAP, Leiden, labels, neighbours, co-author pairs.
5. Page, first version:
   - map coloured by department or by area, labels by zoom level
   - hover tooltip; click for a person card: top works with links, OpenAlex
     topics, 10 nearest people with shared terms, ORCID/OpenAlex links
   - filters: department, title; find a person; keyword search
   - hollow markers for people with few records (GTU convention)
   - method and data-source note, "as of" date
6. Check: you review 10 people's neighbours; Playwright smoke test and a
   screenshot.

Done when `site/<slug>/index.html` opens offline, finds a person, shows
sensible neighbours, and keyword search returns the right people.

### Phase 0 status (2026-11-07)

Done:

- Roster scraped from the four STEM division pages: 89 full-time faculty, 87
  on the map (2 have no research or teaching text and are named on the page).
- Text per person: directory "Research:" line, profile research interests,
  dissertation title, research sentences of the bio. Teaching-only people are
  placed by teaching interests and drawn hollow.
- Model: `paraphrase-multilingual-MiniLM-L12-v2`, not e5-small. On the
  departments' own research-area lists, 48% of each person's top-5 neighbours
  share an area (chance 8%); e5-small scored 40%, e5-base 40%, bge-small 46%,
  SPECTER2 45%, all-mpnet 48%. It is multilingual and small.
- UMAP layout, Leiden areas (6 broad, 14 fine), c-TF-IDF labels from
  keyword text, 10 nearest people with shared terms.
- Page: colour by department (with shapes), program or area; labels change
  with zoom; tooltip; person card; department and rank filters; name and
  keyword search; hollow markers; method note; `#p=<id>` links; light and
  dark; phone layout. Playwright smoke test passes offline.

- Your review of 10 people's neighbours (done 2026-11-07).

- OpenAlex (2026-11-07): 58 of 89 matched. Search is by first + last name
  (and nickname + last) among authors with a UW Bothell affiliation, then
  across all 15 UW institutions if exactly one record matches. Given names
  match in full or via a nickname table, never by prefix ("Zhao" is not
  "Zhaoming"). Common names whose records mix people (Min Chen: 11 records)
  keep only works where that author is listed at UW Bothell. A topic check
  compares each person's own description with their matched papers: UW-wide
  matches below 0.30 go to review (this caught a chemist matched to
  Zhengquan Li and a geochemist to Zhao Wang). 2,168 works since 2011.
  25 people have no UW-affiliated record; candidates are in
  `rosters/uwb-stem-openalex-candidates.csv`. OpenAlex cost so far: about
  $0.48 of the free $1/day.
- Person vector = self-description .40, works .30, venues .15, courses .15,
  centred. Neighbours sharing a curated area: 51% (was 48%). Works alone
  score 40%, but the curated lists come from self-descriptions, so this
  check favours self text; re-tune on the search test set in Phase 1. Same
  ranking of blends on MiniLM, all-mpnet and SPECTER2 (49%); MiniLM kept.
- Neighbours shown only above the 90th percentile of all pair similarities.
- E-mails and phone numbers scrubbed; the build fails if any remain.
- People off the map (2) are searchable; search also covers work titles.
- Person card: recent publications with links, OpenAlex topics, co-authors
  on the map (19 pairs).
- Labels from self text plus OpenAlex topic names (raw titles were noisy).

Still to do in Phase 0:

- Overrides confirmed 2026-11-07 for 7 people (Retik, Martensen, Khemani,
  Price, Lewis, Gliboff, Champion): 65 of 89 matched, 2,195 works. Other
  candidates remain in `rosters/uwb-stem-openalex-candidates.csv`.
- Done 2026-11-07: `config/uwb-stem-labels.yaml` names all 6 areas and 11
  of 12 topics by hand, keyed by a member so renumbering does not misplace
  them; drafted from members' research text, for you to edit.

### Phase 1: generalise

**Status 2026-11-07:** record-level search, the search test set and the
advisor finder are built. On the 28 curated-area queries (the curated lists
are kept out of the index while testing), record-level BM25 finds 68% of the
listed people in the top 10 (MRR 0.83), against 38% (MRR 0.64) for the
earlier person-level keyword search. Weight, decay and coverage variants all
moved the result by 0.03 or less, so the defaults stay. The advisor finder
is lexical: it ranks "air-quality sensor" papers well for a water-quality
project but also matches "protein quality". In-page semantic search
(Phase 2) is the fix GTU measured. Hand-written phrase queries for the test
set still need someone who knows the faculty (Q14).

- Record-level search: BM25 over work titles, courses and grants in the
  page; person score from best 8 records (1, 0.7, 0.49, …); evidence titles.
- Search test set: curated-area queries plus 10–20 hand-written phrase
  queries; top-10 hit rate and MRR printed on every build.
- "Describe a project, get advisors" (GTU's main real use): a text box that
  runs the same record-level search on a paragraph and lists people with
  their matching titles.
- Person-vector components: venues, courses, grants (Q13); re-tune weights
  and re-compare models on check (a).
- Config per university: OpenAlex institution ID, roster path, colours, name.
- Run on a second, different university (for example GTU's public data, or a
  non-US one) to shake out assumptions. If its records mix languages, remove
  the language direction from the vectors, as GTU does.
- Department × area matrix (GTU's lower panel).
- Shareable URL state (selected person, filters, zoom).

### Phase 2 status (2026-11-07)

In-page search by meaning is built. Each search record carries an 8-bit
vector from `all-MiniLM-L6-v2` (2,829 records, about 1.4 MB of the 2.3 MB
page). On request the page loads transformers.js 4.3.1 from jsDelivr and
the 23 MB model from Hugging Face (3.7 s in testing), embeds the query, and
blends meaning and keyword scores 50/50 per record. On the curated-area test
set: hit@10 0.76 (keyword only 0.68), MRR 0.83 (unchanged). Meaning alone
scores 0.72; 30/70 and 70/30 blends are within 0.03; bge-small-en-v1.5
scores 0.73 / 0.87 at 34 MB, so the smaller model stays. The search model is
English: the multilingual ONNX models are 118 MB. A non-English university
should set a multilingual `search_model` or consider a server. The test set
has only short topic names (no hand-written phrase queries), so the gain on
project descriptions is not measured.

### More universities (started 2026-11-07)

Order: UW Tacoma and UW Seattle, then Northwestern and UC San Diego.

Scope (default adopted after 15 minutes without an answer; change by
saying which units): large universities are mapped one unit at a time from
that unit's own faculty directory, starting with the engineering college at
each (UW College of Engineering, Northwestern McCormick, UCSD Jacobs).
Whole-campus rosters taken from OpenAlex were rejected: OpenAlex cannot tell
faculty from students, postdocs and clinical staff, has no departments, and
UW alone would be tens of thousands of people.

Each site gets a small adapter in `pipeline/src/research_map/adapters.py`;
who is kept is a title rule in the config.

| Map | Status | Notes |
|---|---|---|
| UW Bothell STEM (`uwb-stem`) | built | 87 people; neighbour check 52%; search hit@10 0.75 |
| UW Tacoma (`uwt`) | built | whole campus, 268 full-time faculty, 256 mapped; 195 matched in OpenAlex, 6,180 works; no curated areas, so no checks; areas named by hand |
| UW College of Engineering (`uw-coe`) | roster done | 301 full-time faculty from the Faculty Finder, with research areas (also a test set: 68 areas with 2+ people); OpenAlex waits for the daily budget |
| Northwestern McCormick (`nu-mccormick`) | roster done | 288 core faculty from the directory's XML feed; 170+ with research-area text |
| UCSD Jacobs (`ucsd-jacobs`) | roster done | 288 faculty from the profiles list, 284 with research text; needs the InCommon intermediate certificate (in `config/certs/`) |

OpenAlex costs about $0.30–0.45 per unit of 300 people (name searches are
$0.001 each), so two units fit in one free daily budget ($1, resets at
midnight UTC).

Lessons so far: some university servers omit an intermediate certificate
(fixed by shipping it, not by turning verification off); degree text must
keep only fields, not institutions; search vectors are shrunk to 64 PCA
dimensions (no measurable loss, page about half the size). Page budget
revised: about 10 MB per 1,000 people with search vectors (GTU: 16 MB for
800).

### Phase 2: views GTU does not have

Pick from these after Phase 1; each is independent.

- Co-author links drawn on the semantic map; list "close but never
  co-authored" pairs as collaboration candidates.
- Year-range filter; colour by "new in the last 3 years".
- Department footprints (density contours).
- In-page semantic search (transformers.js), blended 50/50 with BM25 (done 2026-11-07).
- LLM research profiles for ranking only (Q12): grounded in titles, JSON
  schema, temperature 0, never shown without human review.
- Topics-over-time streamgraph.
- Collaboration world map from the same co-author data.
- Shared base map so different universities can be compared.

### Phase 3: refresh

- Scheduled rebuild on halflife; new people placed into the existing layout
  (UMAP transform or alignment to the previous map) so the map does not
  reshuffle each time.
- One-command publish that backs up whatever it changes and rolls back on
  failure (GTU's lesson from a shared web server).
- Visit counts only if hosted on a server we control: no IPs, daily-rotated
  salted hash, bots excluded.

## Risks

| Risk | Mitigation |
|---|---|
| OpenAlex merges or splits people, so someone gets the wrong papers | ORCID first; overrides file; unmatched report; "report an error" note on the page |
| Missing abstracts for some publishers | Fall back to titles (GTU uses titles only and works) |
| Teaching-focused and new faculty have few papers | Hollow markers; optionally add course titles from the catalogue, as GTU does |
| Weak OpenAlex coverage in arts, humanities, books | Flag those people; allow roster-supplied keywords |
| Free OpenAlex budget | Cache everything; fetch incrementally; ID lookups are free |
| Privacy | Public data only; faculty only by default; opt-out list in config; e-mails and phone numbers scrubbed; build fails on ID-like numbers |
| Model-written text taken as fact | LLM profiles used for ranking only; users always see real titles (GTU rule) |
| Search quality claims without evidence | Search test set and curated-area check on every build |
| Use of university names and logos | Generic look by default; logo only with permission |

## Open questions

Answer by number. Every "(rec)" default below was adopted on 2026-11-07;
answering a question overrides its default. Q4: you are getting the key.
Q6: confirmed. Q12 and Q13 are new and open.

1. First target for the slice? (rec: UW Bothell School of STEM)
2. One map, or a tool you will run for many universities? (rec: a tool, grown from the slice)
3. Main audience: public and prospective students, faculty looking for collaborators, research office and leadership, or industry partners? (rec: faculty and research office, plus students looking for advisors, which was GTU's main real use)
4. Data: OpenAlex plus a roster CSV? (rec: yes). OpenAlex needs a free key tied to an email address. Create one yourself, or say yes and I request one for pisan@uw.edu (OpenAlex emails you a confirmation link).
5. Do you have rosters with departments (and ORCIDs), or should I scrape public directories? (rec: scrape for the slice)
6. Who goes on the map: faculty only, or also postdocs, research staff, graduate students? (rec: faculty, with an opt-out list)
7. Points: people, papers, or both with a toggle? (rec: people; papers later)
8. Which extra views matter most from Phase 2? (rec: department × area matrix, then co-author links on the map)
9. Search: keyword only, in-page semantic, or a server? (done: record-level BM25 plus optional in-page search by meaning, no server)
10. Hosting and refresh: single HTML file, where hosted, one-off or scheduled? (rec: single HTML, local or GitHub Pages, one-off first)
11. Language and branding: English UI only or bilingual like GTU; generic look or per-university colours? (rec: English UI, multilingual model, generic look with configurable colours)
12. LLM research profiles (ranking only, never shown): run them with the local `claude` CLI, which sends public titles to Anthropic under your subscription, or skip them? GTU kept everything on campus with an open-weight model; their measured gain was small (0.80 → 0.81 top-10). (rec: skip until record-level search is measured; then decide)
13. Add grants as a component from the NSF and NIH award APIs (public, free, no key)? (rec: yes, in Phase 1)
14. Hand-written test queries: declined 2026-11-07. The curated areas remain the only search test set; `tests/<slug>-queries.json` is supported if someone writes them later.
15. Units for UW Seattle, Northwestern and UC San Diego: engineering colleges first? (default adopted 2026-11-07; name other units to change)
