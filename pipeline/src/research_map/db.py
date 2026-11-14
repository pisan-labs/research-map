"""Load a built map into Postgres (Supabase): `research-map load CONFIG`.

Reads data/<slug>/payload.json (written by `build`) and replaces that unit's
rows in one transaction. Search records get gte-small vectors so the search
Edge Function can embed queries with Supabase's built-in gte-small model.
The connection string comes from SUPABASE_DB_URL (or DATABASE_URL).
"""

from __future__ import annotations

import json
import os
from urllib.parse import quote
import re
from pathlib import Path

from . import model

SCHEMA = "app_research_map"  # see supabase/migrations
SERVER_SEARCH_MODEL = "thenlper/gte-small"  # matches Supabase.ai Session("gte-small")


# Session pooler of the shared HintWise project (the direct host is IPv6-only).
POOLER_USER = "postgres.arktxlrlyceffyozdwhq"
POOLER_HOST = "aws-1-us-east-1.pooler.supabase.com"


def connection_string() -> str:
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL") or ""
    if url:
        return url
    pw = os.environ.get("SUPABASE_DB_PASSWORD", "")
    if pw:  # quoted, so a password with @ : / does not break the URI
        return f"postgresql://{POOLER_USER}:{quote(pw, safe='')}@{POOLER_HOST}:5432/postgres"
    raise SystemExit("set SUPABASE_DB_PASSWORD (or SUPABASE_DB_URL, the session pooler URI from the\n"
                     "dashboard's Connect dialog; the direct host is IPv6-only). Never commit either.")


def search_record_rows(payload: dict) -> list[tuple]:
    """The same records web/search.js builds, in the same order."""
    rows = []
    for p in payload["people"]:
        for t, y, v, u in p.get("pubs", []):
            rows.append((p["id"], "title", t, y, v, u))
        if p.get("keywords"):
            rows.append((p["id"], "keywords", p["keywords"], None, None, None))
        if p.get("interests") and p["interests"] != p.get("keywords"):
            rows.append((p["id"], "interests", p["interests"], None, None, None))
        if p.get("bio"):
            rows.append((p["id"], "bio", p["bio"], None, None, None))
        for t in p.get("oa_topics", []):
            rows.append((p["id"], "topic", t, None, None, None))
        for a in p.get("listed", []):
            rows.append((p["id"], "listed", a, None, None, None))
    return rows


def vector_literal(v) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def load(cfg: dict, root: Path, embed: bool = True) -> dict:
    import psycopg

    slug = cfg["slug"]
    data = root / "data" / slug
    payload = json.loads((data / "payload.json").read_text())
    meta = payload["meta"]
    people = payload["people"]
    records = search_record_rows(payload)
    vecs = None
    if embed:
        emb = model.Embedder(SERVER_SEARCH_MODEL, cache_dir=data)
        vecs = emb.encode([r[2] for r in records])

    works: dict[str, tuple] = {}
    links: list[tuple] = []
    for p in people:
        for t, y, v, u in p.get("pubs", []):
            wid = re.sub(r"\W+", "-", u.rsplit("/", 1)[-1]) if u else re.sub(r"\W+", "-", t.lower())[:80]
            works.setdefault(wid, (wid, t, y, v, u))
            links.append((slug, p["id"], wid))

    with psycopg.connect(connection_string()) as conn, conn.cursor() as cur:
        # The shared HintWise project: this app's tables live in their own schema.
        cur.execute(f"set search_path = {SCHEMA}, extensions")
        cur.execute("delete from units where slug = %s", (slug,))  # cascades to the unit's rows
        cur.execute(
            "insert into units (slug, name, university, openalex_institution, as_of, people_count, works_count, meta)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s)",
            (slug, cfg["name"], cfg.get("university", ""), cfg.get("openalex_institution"), meta["as_of"],
             sum(1 for p in people if not p.get("off")), len(works),
             json.dumps({k: meta.get(k) for k in ("method", "sources", "left_off", "near_cutoff", "model")})),
        )
        cur.executemany(
            "insert into people (unit_slug, id, name, title, department, program, keywords, interests, bio,"
            " profile_url, orcid, openalex_ids, x, y, area, topic, sparse, off_map, terms)"
            " values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [(slug, p["id"], p["name"], p["title"], p["department"], p["program"], p["keywords"], p["interests"],
              p["bio"], p["url"], p.get("orcid") or None, p.get("openalex", []), p.get("x"), p.get("y"),
              p.get("area"), p.get("topic"), bool(p.get("sparse")), bool(p.get("off")), p.get("terms", []))
             for p in people],
        )
        cur.executemany(
            "insert into works (id, title, year, venue, url) values (%s,%s,%s,%s,%s)"
            " on conflict (id) do update set title = excluded.title, year = excluded.year,"
            " venue = excluded.venue, url = excluded.url",
            list(works.values()),
        )
        cur.executemany("insert into person_works values (%s,%s,%s) on conflict do nothing", links)
        cur.executemany(
            "insert into areas (unit_slug, level, cluster, label, x, y, n) values (%s,%s,%s,%s,%s,%s,%s)",
            [(slug, level[:-1] if level == "areas" else "topic", a["id"], a["label"] or "", a["x"], a["y"], a["n"])
             for level in ("areas", "topics") for a in payload[level]],
        )
        ids = [p["id"] for p in people]
        cur.executemany(
            "insert into neighbours (unit_slug, person_id, other_id, rank, score, shared) values (%s,%s,%s,%s,%s,%s)",
            [(slug, p["id"], ids[n["i"]], k + 1, n["s"], n["t"])
             for p in people for k, n in enumerate(p.get("near", []))],
        )
        cur.executemany(
            "insert into search_records (unit_slug, person_id, kind, text, year, venue, url, embedding)"
            " values (%s,%s,%s,%s,%s,%s,%s,%s::vector)",
            [(slug, pid, kind, text, y, v, u, vector_literal(vecs[i]) if vecs is not None else None)
             for i, (pid, kind, text, y, v, u) in enumerate(records)],
        )
    return {"people": len(people), "works": len(works), "records": len(records)}
