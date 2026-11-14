# Handoff: research-map (2026-11-14 13:15 Lisbon)

Read this, then `BRIEFING.md` (scope, decisions), `PLAN.md` (plan) and the last 30
lines of `CHANGES.md`. Replaces `HANDOVER.md` (renamed; history in git).

## 1. Goal

From `BRIEFING.md`: "Build interactive research maps of universities: each researcher
is a point, and nearby points work on similar topics." One self-contained HTML page per
unit, plus a Supabase search API. User requests this session, verbatim:
"apply these changes to the shared project arktxlrlyceffyozdwhq";
"I also want to create a map for UC Santa Barbara"; "Can we expand UWB STEM to all of
UWB?" (then "keep both"); "switch off the per-record check".

## 2. Status

Done (live at https://research-map.hintwise.org, all loaded into Supabase):
- [x] Supabase: schema `app_research_map` in the shared HintWise project, exposed; Edge
      Function `research-map-search` (verify_jwt off). 2026-11-10.
- [x] uwb (whole UW Bothell, 231 people, adapter `uwb-campus`), live 2026-11-14.
- [x] uwb-stem (89), uwt (268), uw-coe (300), nu-mccormick (288), ucsb-coe (170).
- [x] Every area and topic on all six maps has a hand-written name (0 computed in
      Supabase, checked 2026-11-14).
- [x] OpenAlex: name fixes (letters NFKD drops, Unicode dashes, curly apostrophes,
      short given names search full forms); daily-budget 429 stops cleanly.
- [x] Namesakes: field scan of every multi-record match, pins in
      `config/<slug>-openalex-overrides.csv`. Per-record check off by default.
- [x] `load` builds the pooler URI from `SUPABASE_DB_PASSWORD`.

Remaining (none started):
- [ ] User review of the uwb-stem and uwt names (Claude drafts of 7 Nov; never reviewed).
- [ ] Page size: uw-coe 4.6 MB, nu-mccormick 3.9 MB (slow on phones).
- [ ] Unmatched: 18 uw-coe, 71 uwb (many artists, clinical teaching faculty). User: leave for now.
- [ ] uw-coe main records missing for `jenq-neng-hwang`, `peter-mackenzie-helnwein` (noted 8 Nov, not rechecked).

## 3. Current state

- Repo `pisan-labs/research-map`, branch `main` (the only branch), last commit: the
  `handoff:` commit that adds this file (parent `b7ddce4`).
- Tests on 2026-11-14 13:09 Lisbon: `pytest` 41 passed; `node tests/search_unit.mjs`
  passed; `node tests/smoke.mjs` passed for `site/uwb` (231) and `site/ucsb-coe` (170).
- Known broken: none.

## 4. Next step

`git fetch`, then ask the user which Remaining item to take (recommended: page size).

## 5. Decisions and why

- Hosting: Netlify static pages + Supabase. Supabase is the shared HintWise project
  (free plan allows 2 projects), schema `app_research_map` only (user approved 2026-11-09).
- Full-time faculty only (title rules in each config; `uwb` filters profile roles).
- `uwb` sits beside `uwb-stem` (user, 2026-11-13): STEM pages have curated areas for checks.
- Labels are keyed by a member person, so renumbered clusters keep their names.
- Per-record namesake check off (user, 2026-11-14): 3 of 6 drops checked were the
  person's own records. Opt in with `--record-check`.
- OpenAlex and all `load`/deploy runs happen on the user's Mac (key, DB password, Netlify
  login live there). User declined putting tokens in cloud environment secrets.
- McCormick stays live (user, 2026-11-11). UC San Diego dropped for UCSB.
- Model choices and search blend: see `BRIEFING.md`. No hand-written search test queries.

## 6. Tried and rejected

- Supabase CLI: rejects the token format; use the management API with curl.
- Scheduled cloud OpenAlex runs: the key never reached cloud sessions; both disabled.
- Per-record check (see 5). Prefix rule for given names ("Zhao" ~ "Zhaoming"): matched
  different people; only the NICKNAMES table counts.
- Shell-built DB URL with the raw password: breaks on `@ : /`; replaced by the loader.

## 7. Constraints and gotchas

- Env var names (never values): `SUPABASE_ACCESS_TOKEN` (management API),
  `OPENALEX_API_KEY`, `SUPABASE_DB_PASSWORD` (Mac), `SUPABASE_DB_URL` (overrides it; the
  Mac `.env` sets it), `DATABASE_URL` (used last). `.env` is gitignored; `.env.asc` is an
  encrypted copy. A cloud session's `.env` exists only in its container.
- `GET /v1/projects/arktxlrlyceffyozdwhq/postgrest` returns `jwt_secret`: print only
  `.db_schema`. Any PATCH must append to `db_schema`, never replace (live apps use `wcv`).
- Netlify: always `env -u NETLIFY_SITE_ID ... --site uw-research-maps`. A deploy of
  `site/` publishes every built map linked from `site/index.html`.
- OpenAlex: $1/day budget, resets 00:00 UTC; caches in `data/<slug>/openalex/` (not in
  git). A new slug can reuse another's cache by copying it (same URLs).
- Pins can reshuffle clusters: after a rebuild read the `labels:` lines and name new ones.
- `uwb` roster: a failed profile fetch drops that person (no role); rerun `roster`.
- tacoma.uw.edu needs the intermediate cert in `config/certs/`.
- User preferences: numbered questions with a recommendation; ask before publishing new
  maps, writing production data or spending money; commit and push before ending.

## 8. How to run and verify

From `pipeline/` (Mac for openalex/load/deploy):
```
uv run research-map roster ../config/<slug>.yaml
uv run research-map openalex ../config/<slug>.yaml --max-cost 0.45
uv run research-map build ../config/<slug>.yaml 2>&1 | grep -E '^labels|wrote'
uv run research-map load ../config/<slug>.yaml      # prints "db: using ..."
cd .. && env -u NETLIFY_SITE_ID npx netlify deploy --prod --dir site --site uw-research-maps --no-build
```
Tests: `cd pipeline && uv run pytest -q`; `node tests/search_unit.mjs`;
`node tests/smoke.mjs site/<slug>/index.html`; `tests/search_eval_db.py <slug>`.
Live checks: `https://research-map.hintwise.org/<slug>/meta.json`;
`https://arktxlrlyceffyozdwhq.supabase.co/functions/v1/research-map-search?unit=<slug>&q=robot`.

## 9. Key files

| Path | Why |
|---|---|
| `pipeline/src/research_map/adapters.py` | One adapter per site, incl. `uwb-campus` |
| `pipeline/src/research_map/openalex.py` | Name matching, strict mode, budget handling |
| `pipeline/src/research_map/cli.py` | `roster`, `openalex`, `build`, `load`; topic check |
| `pipeline/src/research_map/db.py` | Supabase load; connection from env vars |
| `config/<slug>.yaml`, `-labels.yaml`, `-openalex-overrides.csv` | Units, names, pins |
| `rosters/` | Committed rosters and match files |
| `supabase/` | Migrations and the `research-map-search` Edge Function |
| `web/` | Page code (`map.js`, `search.js`) |

## 10. Background jobs

None for this project (no routines aim at research-map; other projects' routines exist,
leave them alone).

## 11. Open questions

1. Are the uwb-stem and uwt names right? (Claude drafts, unreviewed.)
2. Page size: lower `page_pubs` for uw-coe and nu-mccormick, or another approach? Not decided.
3. Keep both `SUPABASE_DB_URL` (Mac `.env`) and `SUPABASE_DB_PASSWORD`, or only one? User's call.
4. Why the first `uwb-stem` load on 2026-11-14 failed with password authentication and
   the retry with the same variable worked: I don't know.
