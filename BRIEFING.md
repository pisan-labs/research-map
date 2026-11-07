# Briefing

## Scope

Build interactive research maps of universities: each researcher is a point,
and nearby points work on similar topics. Inspired by the GTU Research Map
(<https://tanitim.gtu.edu.tr/arastirma-haritasi/?lang=en>). Intended for use
across many universities.

Plan: [PLAN.md](PLAN.md). Survey of other map styles: [docs/survey.md](docs/survey.md).

## Decisions

Draft as of 2026-11-07, pending answers to the open questions in PLAN.md.

- Output is one self-contained HTML file per map; no server needed.
- Data: university roster CSV plus OpenAlex works.
- Python pipeline (uv, pytest); front end is vanilla JS with D3 and Canvas, no build step.
- Local open embedding models only; any LLM step uses the local `claude` CLI, never an API key.
- Build a vertical slice on one unit before generalising.

## Non-goals (for now)

- A hosted server or login system.
- Paid data sources (Scopus, SciVal, Dimensions).
- Ranking or evaluating researchers.
