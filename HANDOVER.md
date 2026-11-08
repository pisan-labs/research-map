# Handover: research-map (2026-11-08)

For the next session. Read this, then `BRIEFING.md` (scope and decisions),
`PLAN.md` (plan, status tables, open questions) and the last 30 lines of
`CHANGES.md`.

## What this is

Interactive research maps of university faculty: each person is a point,
nearby points work on similar topics (inspired by GTU's research map; their
build notes are summarised in PLAN.md). Output per unit is one
self-contained HTML page that works offline.

- Repo: `pisan-labs/research-map`, branch `claude/charming-euler-asr2d3`.
- Draft PR: https://github.com/pisan-labs/research-map/pull/1 (no CI, no
  review comments). Nothing is on `main` yet except the initial commit.
- Live site (Netlify): https://uw-research-maps.netlify.app

## State of each map

| Unit | Config | Roster | OpenAlex | Map built | Deployed |
|---|---|---|---|---|---|
| UW Bothell STEM | `config/uwb-stem.yaml` | 89 (87 mapped) | 65 matched, 2,195 works | yes | yes |
| UW Tacoma (whole campus) | `config/uwt.yaml` | 268 (256 mapped) | 195 matched, 6,180 works; candidates file incomplete | yes | yes |
| UW College of Engineering | `config/uw-coe.yaml` | 301 | 274 matched, 23,620 works (final rules) | **no** | no |
| Northwestern McCormick | `config/nu-mccormick.yaml` | 288 | 240 matched, 26,473 works (**before** the latest name rules) | yes, needs rematch + rebuild | no |
| UC Santa Barbara Engineering | `config/ucsb-coe.yaml` | 170 | **not run** | no | no |

UC San Diego was dropped by the user in favour of UC Santa Barbara.

## Next steps, in order

1. **OpenAlex (needs the daily budget; $1/day, resets 00:00 UTC; about
   $0.30-0.45 per 300-person unit).** Check first:
   `curl -s https://api.openalex.org/rate-limit`.
   - `research-map openalex ../config/ucsb-coe.yaml --max-cost 0.45`
   - `research-map openalex ../config/nu-mccormick.yaml --max-cost 0.3`
     (rematch: short given names, apostrophe surnames, exact-name rule;
     should pick up Eleanor O'Rourke)
   - `research-map openalex ../config/uwt.yaml --max-cost 0.3` (finishes
     the candidates file; Eyhab Al-Masri should now match)
   - `research-map openalex ../config/uw-coe.yaml --max-cost 0.45`: the
     works cache was in the previous container, so UW CoE must be fetched
     again before it can be built; it also applies the new overrides.
     All four runs together exceed $1, so spread them over two days.
2. **Check by hand** the low-agreement matches each run prints.
   UW CoE was checked on 2026-11-08 (free single-record lookups, no key):
   `config/uw-coe-openalex-overrides.csv` pins 17 people. Strict mode had
   merged every same-name record with any UW affiliation, so namesakes'
   UW papers leaked in (Daniel Grossman, James Lee, Kevin Lin, Michael
   Taylor, Joshua Smith, Xu Chen and others); Andrew Davidson set to none.
   Still to check, with paper titles (needs the key):
   - `abhishek-gupta`: two ~170-work CS records, both UW 2023-2026, plus
     dentistry namesakes; pin the right ones.
   - `sheng-wang` (A5100371324 pharmacology, A5100371286 medicine) and
     `ying-zheng` (A5089319540 medicine, A5101482643 chemistry): possible
     namesakes.
   - `jenq-neng-hwang`: only small records found (15 works since 2011);
     the main record is missing. `peter-mackenzie-helnwein`: one stray
     work (agreement 0.11); main record missing.
   - `jose-lopez` (Mechanical Engineering): every record is José A. López,
     hematology (UW Medicine). Probably an adjunct listed as "Professor";
     ask the user whether to keep him.
   Checked and kept: `jorge-marchand` (0.13), `hal-perkins` (0.25),
   `soraya-bailey` (0.29), and strict matches whose records all share
   one field. Idea: in strict mode, check each record's topics against
   the person's profile, not just the person's overall agreement, which
   would catch this automatically; measure it on UW CoE.
3. **Build** `uw-coe`, `nu-mccormick`, `ucsb-coe`, `uwt`
   (`research-map build ../config/<slug>.yaml`; about 2-10 min each on CPU).
4. **Name areas by hand**: `config/<slug>-labels.yaml` (see the UWB and UWT
   files; entries are keyed by a member person, and the build warns about
   conflicts or unnamed clusters). Needed for uw-coe, nu-mccormick, ucsb-coe.
5. **Tests**: `cd pipeline && uv run pytest -q`; `node tests/search_unit.mjs`;
   `node tests/smoke.mjs site/<slug>/index.html`; the build prints the
   search test set for units with curated areas (uwb-stem, uw-coe, ucsb-coe).
6. **Page size**: McCormick is 3.9 MB for 264 people even with the 60-paper
   cap (budget about 10 MB per 1,000 people). Options: lower `page_pubs` in
   its config (measure the search test set on a unit that has one first).
7. **Redeploy Netlify** (user approved keeping this site updated):
   `env -u NETLIFY_SITE_ID npx netlify deploy --prod --dir site --site uw-research-maps --no-build`
8. **Supabase** is blocked on the user (open question below). When a
   project exists: apply `supabase/migrations/*.sql`, run
   `research-map load ../config/<slug>.yaml` with `SUPABASE_DB_URL`, deploy
   `supabase/functions/search` (written, never run), test with
   `tests/search_eval_db.py`.

## Open questions for the user

- **Supabase project slot** (PLAN Q19): the free plan allows two active
  projects per owner across all orgs; `upvoteme` and `dsa` are active.
  Options: pause one (free, reversible), upgrade org YP to Pro (paid, needs
  a yes), or use a schema in an existing project. No recommendation given:
  depends on whether `upvoteme` is in use.
- Area names for UWB and UWT were drafted by Claude from members' research;
  the user has not reviewed them.

## Decisions already made (do not re-ask)

- Full-time faculty only; large universities one unit at a time from the
  unit's own directory, engineering colleges first.
- Hosting: Netlify (static pages) + Supabase (data, search Edge Function,
  auth for corrections). Pipeline runs on halflife for now, no Render yet.
- Netlify and Supabase CLIs installed (pinned in `package.json`); use them
  rather than the MCP connectors.
- Person vector: self-description .40, works .30, venues .15, courses .15,
  centred; map model `paraphrase-multilingual-MiniLM-L12-v2`.
- Search: record-level BM25 + optional in-page meaning search
  (all-MiniLM-L6-v2, 23 MB on request, 64-dim PCA vectors), 50/50 blend.
- No hand-written search test queries (user declined).

## How things work (key files)

| Path | What |
|---|---|
| `pipeline/src/research_map/adapters.py` | One adapter per site: `uwb-stem`, `uwt-directory`, `uwcoe-facultyfinder`, `nu-mccormick-xml`, `ucsb-coe` |
| `pipeline/src/research_map/openalex.py` | Matching: first+last (+ short given names, hyphen/apostrophe surnames) within the home institution; exact names preferred over loose; strict mode (only home-affiliated works) for >3 records or >500 works; UW-wide fallback only for a single record |
| `pipeline/src/research_map/cli.py` | `roster`, `openalex`, `build`, `load`; topic check (own text vs papers) sends doubtful matches to review |
| `pipeline/src/research_map/{text,model,bundle}.py` | Text fields, vectors/layout/areas/labels/neighbours, page data and privacy scan |
| `web/` | Page: `map.js`, `search.js` (shared with Node tests), `map.css`, vendored D3 |
| `rosters/` | Committed scraped data and OpenAlex match/candidate files (contact details scrubbed) |
| `config/` | Unit configs, `*-labels.yaml`, `*-openalex-overrides.csv`, `certs/` |
| `data/` | Caches (gitignored): pages, OpenAlex responses, embeddings, `works.json`, `payload.json` |
| `supabase/` | Migrations (schema, `search_people()`), Edge Function |

## Gotchas

- **OpenAlex key**: saved as a network secret on the cloud environment
  "EnvFull"; the proxy injects it for `api.openalex.org`. Only sessions
  started after the secret was added get it (the same holds for the
  Netlify and Supabase settings): a session from 2026-11-07 morning gets
  "Authentication required". Single-record lookups (`/authors/A...`)
  are free and work without a key. On halflife set
  `OPENALEX_API_KEY`. Responses are cached under `data/<slug>/openalex/`,
  but `data/` is not in git, so a fresh container refetches (costs budget).
- **Netlify**: this environment sets `NETLIFY_SITE_ID` for another site;
  always deploy with `env -u NETLIFY_SITE_ID` and `--site uw-research-maps`.
- **Supabase CLI** rejects the environment's `SUPABASE_ACCESS_TOKEN` format;
  the management API accepts it via curl.
- **TLS**: tacoma.uw.edu omits an intermediate certificate; it is shipped in
  `config/certs/` and added to the trust store (verification stays on).
- **Build time and size**: embeddings run on CPU; large units take minutes.
  `page_pubs` (default 60) caps papers in the page, not in the vectors.
- **Scheduled tasks**: all of this session's scheduled check-ins and the
  nightly OpenAlex runs were cancelled at handover, and the PR is no
  longer watched by this session. Re-create them in the new session if
  wanted (and subscribe to PR #1).
- User preferences apply (see the user's global instructions): ask before
  spending money or deploying to new places; questions numbered; commit
  and push before ending.
