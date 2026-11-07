# Plan: university research map

Status: **defaults adopted, 2026-11-07.** No answers to the questions at the
end arrived within 15 minutes, so each "(rec)" default is now the working
decision. To reverse one, answer that question by number and the plan will be
updated. Still open: the OpenAlex API key (Q4), which needs your yes.

Background and examples: [docs/survey.md](docs/survey.md).

## Goal

A reusable generator: given a university (or one unit) and its faculty
roster, build an interactive research map in the spirit of the GTU map. Each
point is a researcher; nearby points work on similar things. Output is one
self-contained HTML file that works offline and can be hosted anywhere.

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
| Embed | Local `sentence-transformers`, title + abstract per work. Person vector = recency-weighted mean (GTU weights: 1.0 / 0.6 / 0.35) | No paid API. Model choice below |
| Layout | UMAP, cosine | Choice below |
| Areas | Leiden on a k-nearest-neighbour graph, two resolutions: broad areas and fine topics | Gives labels that change with zoom |
| Labels | Distinctive terms (c-TF-IDF) plus the most common OpenAlex topic names; optional naming pass with the local `claude` CLI; `labels.yaml` to override by hand | Never the Anthropic API with a key |
| Extras | 10 nearest people per person (with shared terms), co-author pairs within the roster | Precomputed, so the page needs no vectors |
| Bundle | Inline JSON, JS, CSS into one HTML; size budget about 5 MB per 1,000 people | GTU is 16 MB for 800 people because it ships every title and vector |

Front end: vanilla JS, D3 v7 for zoom and scales, Canvas 2D for drawing
(SVG slows past a few thousand points). No build step. Python pipeline
managed with `uv`, tests with `pytest`, page smoke test with Playwright.

### Technical choices

**Text model**

| Option | Strength | Weakness |
|---|---|---|
| `intfloat/multilingual-e5-small` (rec) | Multilingual, small (CPU-friendly), close to what GTU used | Not tuned for science |
| `intfloat/multilingual-e5-base` / `BAAI/bge-m3` | Better quality, multilingual | 2–5× slower on CPU |
| SPECTER2 | Trained on scientific papers (title + abstract) | English only |
| OpenAlex topic vectors only | No ML, consistent across universities | Coarse (about 4,500 topics); misses specifics |

Recommendation: e5-small for the slice; compare with SPECTER2 on the same
people and keep whichever gives neighbours you judge better.

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
| In-page keyword search over titles, abstracts, topics (rec for V1) | Works offline, instant | Misses synonyms |
| In-page semantic search (transformers.js, same model) | Finds "machine learning" for "deep nets"; still offline | 30–120 MB download on first search |
| Small search server (GTU live site) | Best quality | A server to run and secure |

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

### Phase 1: generalise

- Config per university: OpenAlex institution ID, roster path, colours, name.
- Run on a second, different university (for example GTU's public data, or a
  non-US one) to shake out assumptions.
- Department × area matrix (GTU's lower panel).
- Shareable URL state (selected person, filters, zoom).

### Phase 2: views GTU does not have

Pick from these after Phase 1; each is independent.

- Co-author links drawn on the semantic map; list "close but never
  co-authored" pairs as collaboration candidates.
- Year-range filter; colour by "new in the last 3 years".
- Department footprints (density contours).
- "Paste a call for proposals" search returning people with evidence titles.
- In-page semantic search (transformers.js).
- Topics-over-time streamgraph.
- Collaboration world map from the same co-author data.
- Shared base map so different universities can be compared.

### Phase 3: refresh

- Scheduled rebuild on halflife; new people placed into the existing layout
  (UMAP transform or alignment to the previous map) so the map does not
  reshuffle each time.

## Risks

| Risk | Mitigation |
|---|---|
| OpenAlex merges or splits people, so someone gets the wrong papers | ORCID first; overrides file; unmatched report; "report an error" note on the page |
| Missing abstracts for some publishers | Fall back to titles (GTU uses titles only and works) |
| Teaching-focused and new faculty have few papers | Hollow markers; optionally add course titles from the catalogue, as GTU does |
| Weak OpenAlex coverage in arts, humanities, books | Flag those people; allow roster-supplied keywords |
| Free OpenAlex budget | Cache everything; fetch incrementally; ID lookups are free |
| Privacy | Public data only; faculty only by default; opt-out list in config |
| Use of university names and logos | Generic look by default; logo only with permission |

## Open questions

Answer by number. Every "(rec)" default below was adopted on 2026-11-07;
answering a question overrides its default. Q4's API key is still open.

1. First target for the slice? (rec: UW Bothell School of STEM)
2. One map, or a tool you will run for many universities? (rec: a tool, grown from the slice)
3. Main audience: public and prospective students, faculty looking for collaborators, research office and leadership, or industry partners? (rec: faculty and research office)
4. Data: OpenAlex plus a roster CSV? (rec: yes). OpenAlex needs a free key tied to an email address. Create one yourself, or say yes and I request one for pisan@uw.edu (OpenAlex emails you a confirmation link).
5. Do you have rosters with departments (and ORCIDs), or should I scrape public directories? (rec: scrape for the slice)
6. Who goes on the map: faculty only, or also postdocs, research staff, graduate students? (rec: faculty, with an opt-out list)
7. Points: people, papers, or both with a toggle? (rec: people; papers later)
8. Which extra views matter most from Phase 2? (rec: department × area matrix, then co-author links on the map)
9. Search: keyword only, in-page semantic, or a server? (rec: keyword for V1, in-page semantic in Phase 2)
10. Hosting and refresh: single HTML file, where hosted, one-off or scheduled? (rec: single HTML, local or GitHub Pages, one-off first)
11. Language and branding: English UI only or bilingual like GTU; generic look or per-university colours? (rec: English UI, multilingual model, generic look with configurable colours)
