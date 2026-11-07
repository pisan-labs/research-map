# Briefing

## Scope

Build interactive research maps of universities: each researcher is a point,
and nearby points work on similar topics. Inspired by the GTU Research Map
(<https://tanitim.gtu.edu.tr/arastirma-haritasi/?lang=en>). Intended for use
across many universities.

Plan: [PLAN.md](PLAN.md). Survey of other map styles: [docs/survey.md](docs/survey.md).

## Decisions

Adopted 2026-11-07 as defaults, since the questions in PLAN.md went
unanswered for 15 minutes. Reverse any of them by answering that question.

- First target: UW Bothell School of STEM, faculty only, with an opt-out list.
- A reusable tool for many universities, aimed at faculty, the research office, and students looking for advisors.
- Points are people; papers may come later.
- Keyword search first, then record-level search (rank works, then people, show evidence titles), as GTU found person averages hide key papers; next views are the unit × area table, then co-author links.
- English UI, multilingual model, plain look with configurable colours.
- Output is one self-contained HTML file per map, kept local or on GitHub Pages, built one-off at first; no server needed.
- Data: university roster CSV plus OpenAlex works.
- Python pipeline (uv, pytest); front end is vanilla JS with D3 and Canvas, no build step.
- Local open embedding models only; any LLM step uses the local `claude` CLI, never an API key.
- Build a vertical slice on one unit before generalising.
- 2026-11-07: until OpenAlex has a key, people are placed by public directory
  and profile text (research keywords, interests, bio, dissertation title).
- 2026-11-07: text model is `paraphrase-multilingual-MiniLM-L12-v2` (best on
  the curated-area check among six local models, and multilingual).
- 2026-11-07: default colouring is by department with a shape per
  department; program and computed area are options.
- 2026-11-07: full-time faculty only (confirmed).
- 2026-11-07: more universities: UW Tacoma (whole campus), then one unit at
  a time at large universities, engineering colleges first (UW Seattle,
  Northwestern, UCSD), each from its own faculty directory.
- 2026-11-07: search ranks records then people, with evidence; optional
  in-page search by meaning uses an English model (23 MB, downloaded on
  request) because multilingual ones are 118 MB. The map vectors stay
  multilingual. Area names are written by hand in config/<slug>-labels.yaml.
- 2026-11-07: after GTU's build notes, every change is measured on two
  checks (curated-area neighbours, search test set); person vectors are
  centred; e-mails and phone numbers never reach the page.

## Non-goals (for now)

- A hosted server or login system.
- Paid data sources (Scopus, SciVal, Dimensions).
- Ranking or evaluating researchers.
