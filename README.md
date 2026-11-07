# research-map

Interactive research maps of universities: each researcher is a point, and
nearby points work on similar topics.

- [PLAN.md](PLAN.md): plan and open questions
- [docs/survey.md](docs/survey.md): survey of other research-map styles
- [BRIEFING.md](BRIEFING.md): scope and decisions

## First map: UW Bothell School of STEM

`site/uwb-stem/index.html` is one self-contained file (about 450 KB) that
works offline: open it in a browser, or host it anywhere. It shows the 87
full-time STEM faculty who have research or teaching text on their public
directory or profile pages.

## Build

Needs [uv](https://docs.astral.sh/uv/). Everything runs locally; no API keys.

```bash
cd pipeline
uv sync
uv run research-map roster ../config/uwb-stem.yaml   # scrape directory + profiles (cached in data/)
uv run research-map build ../config/uwb-stem.yaml    # embed, lay out, write site/uwb-stem/index.html
```

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
| `web/` | page template, `map.js`, `map.css`, vendored D3 v7.9.0 |
| `rosters/` | scraped roster, profile text, curated areas (public data) |
| `site/<slug>/index.html` | built map |
| `data/` | cache (pages, embeddings, payload); gitignored |

## Tests

```bash
cd pipeline && uv run pytest -q
node tests/smoke.mjs site/uwb-stem/index.html   # Playwright: offline load, search, person card, phone width
```
