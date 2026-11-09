# research-map

Interactive research maps of universities: each researcher is a point, and
nearby points work on similar topics.

- [PLAN.md](PLAN.md): plan and open questions
- [docs/survey.md](docs/survey.md): survey of other research-map styles
- [BRIEFING.md](BRIEFING.md): scope and decisions

## Maps

`site/index.html` lists the built maps:

| Map | Config | People |
|---|---|---|
| UW Bothell School of STEM | `config/uwb-stem.yaml` | 87 |
| UW Tacoma (whole campus) | `config/uwt.yaml` | 256 |
| UW College of Engineering | `config/uw-coe.yaml` | roster only so far (301) |
| Northwestern Engineering (McCormick) | `config/nu-mccormick.yaml` | roster only so far (288) |
| UC Santa Barbara College of Engineering | `config/ucsb-coe.yaml` | roster only so far (170) |

A new university needs a config and, unless an existing one fits, an
adapter in `pipeline/src/research_map/adapters.py` that lists people and
parses profile pages.

## Hosting

- **Netlify**: https://uw-research-maps.netlify.app serves `site/` (no build
  step; `netlify.toml`). Deploy after a build, from the repo root:

  ```bash
  env -u NETLIFY_SITE_ID npx netlify deploy --prod --dir site --site uw-research-maps --no-build
  ```

  (`env -u` matters where a `NETLIFY_SITE_ID` for another site is set.)
- **Supabase**: planned in the shared HintWise project (`arktxlrlyceffyozdwhq`),
  schema `app_research_map` only; not applied yet. Schema and search
  function: `supabase/migrations/`; search API:
  `supabase/functions/research-map-search/`. `research-map load CONFIG`
  writes a built map into that schema (`SUPABASE_DB_URL`, the session pooler
  URI; never commit it);
  `tests/search_eval_db.py` runs the search test set against it.
- **Pipeline**: runs on halflife for now; Render later.

## First map: UW Bothell School of STEM

`site/uwb-stem/index.html` is one self-contained file (about 2.3 MB) that
works offline: open it in a browser, or host it anywhere. It shows 87
full-time STEM faculty, placed by their publications (OpenAlex), venues,
profile text and courses; 2 more with no text are findable by search.

## Build

Needs [uv](https://docs.astral.sh/uv/). Embedding runs locally; the only key is a free OpenAlex key.

```bash
cd pipeline
uv sync
uv run research-map roster ../config/uwb-stem.yaml    # scrape directory + profiles (cached in data/)
uv run research-map openalex ../config/uwb-stem.yaml  # match people, fetch works since 2011 (cached)
uv run research-map build ../config/uwb-stem.yaml     # embed, lay out, write site/uwb-stem/index.html
```

`openalex` needs an OpenAlex API key (free, $1/day of calls). In the cloud
environment the network proxy adds it; locally set `OPENALEX_API_KEY`. It
stops at `--max-cost` (default $0.50) and caches every response. It writes
`rosters/<slug>-openalex-matches.csv` (who matched which author records, for
review) and, for people it could not match safely,
`rosters/<slug>-openalex-candidates.csv`. Confirm a candidate by adding a row
to `config/<slug>-openalex-overrides.csv` (`id,openalex_ids,note`; ids
separated by `|`, or `none` to skip a person). Works go to `data/` and are
refetched cheaply from the cache.

`roster` writes `rosters/<slug>.csv`, `rosters/<slug>-profiles.json` and
`rosters/<slug>-areas.json` (the department's own research-area lists). These
are committed, so `build` works on a fresh clone without scraping again. The
first `build` downloads the embedding model (about 470 MB) from Hugging Face.

`build` prints a check: how often each person's five nearest neighbours share
one of the department-curated research areas, against chance.

## Layout

| Path | What |
|---|---|
| `config/<slug>.yaml` | one map: directory pages, who is included, opt-out list |
| `pipeline/` | Python package `research_map` (roster, profiles, text, model, bundle, cli) |
| `web/` | page template, `map.js`, `search.js` (shared with the tests), `map.css`, vendored D3 v7.9.0 |
| `rosters/` | scraped roster, profile text, curated areas (public data) |
| `site/<slug>/index.html` | built map |
| `data/` | cache (pages, embeddings, payload); gitignored |

## Tests

```bash
npm install                                     # once: transformers.js 4.3.1, for the search test set only
cd pipeline && uv run pytest -q
node tests/search_unit.mjs                      # search module (web/search.js)
node tests/search_eval.mjs uwb-stem --detail    # search test set: hit@10 and MRR per query
node tests/smoke.mjs site/uwb-stem/index.html   # Playwright: offline load, search, advisors, card, phone width
node tests/semantic_online.mjs                  # needs network: turns on search by meaning in a real browser
```

Search by meaning is optional in the page: the build stores a vector for
every search record (`search_model` in the config, English
all-MiniLM-L6-v2 by default), and the page downloads the matching 23 MB
model only when someone clicks "Also search by meaning". Without it the
page searches by words, fully offline.

`build` also prints the search test set scores. The test queries are the
department-curated research areas; add hand-written ones in
`tests/<slug>-queries.json` as `[{"q": "...", "relevant": ["person-id", ...]}]`.
