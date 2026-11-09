"""Search test set against the database search function (server search).

    SUPABASE_DB_URL=... uv run --project pipeline python tests/search_eval_db.py uwb-stem

Same queries and metrics as tests/search_eval.mjs (curated research areas,
hit@10 and MRR), with the curated lists excluded from the index.
"""

import json
import os
import sys
from pathlib import Path

import psycopg

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "pipeline" / "src"))
from research_map import db, model  # noqa: E402

slug = sys.argv[1] if len(sys.argv) > 1 else "uwb-stem"
areas = json.loads((root / "rosters" / f"{slug}-areas.json").read_text())
with psycopg.connect(db.connection_string()) as conn:
    conn.execute(f"set search_path = {db.SCHEMA}, extensions")
    ids = {r[0] for r in conn.execute("select id from people where unit_slug = %s", (slug,))}
    queries = [(q, set(i for i in v if i in ids)) for q, v in areas.items()]
    queries = [(q, rel) for q, rel in queries if len(rel) >= 2]
    emb = model.Embedder(db.SERVER_SEARCH_MODEL, cache_dir=root / "data" / slug)
    qvecs = dict(zip([q for q, _ in queries], emb.encode([q for q, _ in queries])))

    def run(alpha, use_vec):
        hit = rr = 0.0
        for q, rel in queries:
            vec = db.vector_literal(qvecs[q]) if use_vec else None
            ranked = [r[0] for r in conn.execute(
                "select person_id from search_people(%s::text, %s::text, %s::vector, %s::real, 50, false)", (slug, q, vec, alpha))]
            hit += len([p for p in ranked[:10] if p in rel]) / min(10, len(rel))
            first = next((k for k, p in enumerate(ranked) if p in rel), None)
            rr += 0 if first is None else 1 / (first + 1)
        return hit / len(queries), rr / len(queries)

    print(f"{len(queries)} queries (curated areas), server search")
    for name, alpha, use_vec in [("keyword only", 0.5, False), ("hybrid 50/50", 0.5, True), ("meaning only", 1.0, True)]:
        h, m = run(alpha, use_vec)
        print(f"  {name:14s} hit@10 {h:.2f}  MRR {m:.2f}")
