"""Command line: `research-map roster CONFIG` then `research-map build CONFIG`."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import yaml

from . import bundle, model, openalex, roster
from .fetch import CachedFetcher
from .profiles import parse_profile
from .text import build_doc


def repo_root(config_path: Path) -> Path:
    return config_path.resolve().parent.parent


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text())
    cfg.setdefault("include_categories", ["Full-time faculty"])
    cfg.setdefault("opt_out", [])
    cfg.setdefault("color_by", "program")
    return cfg


def cmd_roster(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    root = repo_root(args.config)
    data = root / "data" / cfg["slug"]
    fetcher = CachedFetcher(data / "html", delay=args.delay)

    people: list[roster.Person] = []
    areas: dict[str, list[str]] = {}
    for entry in cfg["directory"]:
        html = fetcher.get(entry["url"], refresh=args.refresh)
        found = roster.parse_directory(html, entry["department"], cfg["base_url"])
        print(f"{entry['department']}: {len(found)} listed", file=sys.stderr)
        people += found
        for name, ids in roster.parse_research_areas(html, cfg["base_url"]).items():
            areas.setdefault(name, [])
            areas[name] += [i for i in ids if i not in areas[name]]

    keep = set(cfg["include_categories"])
    people = [p for p in roster.dedupe(people) if p.category in keep and p.id not in set(cfg["opt_out"])]
    print(f"on the map: {len(people)}", file=sys.stderr)

    profiles = {}
    for i, p in enumerate(people, 1):
        try:
            prof = parse_profile(fetcher.get(p.profile_url, refresh=args.refresh))
        except Exception as e:  # a missing profile should not stop the roster
            print(f"  profile failed for {p.id}: {e}", file=sys.stderr)
            continue
        if prof.orcid and not p.orcid:
            p.orcid = prof.orcid
        profiles[p.id] = asdict(prof)
        if i % 20 == 0:
            print(f"  profiles {i}/{len(people)}", file=sys.stderr)

    roster.write_csv(people, root / "rosters" / f"{cfg['slug']}.csv")
    (root / "rosters" / f"{cfg['slug']}-profiles.json").write_text(json.dumps(profiles, indent=1) + "\n")
    ids = {p.id for p in people}
    areas = {k: [i for i in v if i in ids] for k, v in areas.items()}
    (root / "rosters" / f"{cfg['slug']}-areas.json").write_text(
        json.dumps({k: v for k, v in areas.items() if v}, indent=1) + "\n"
    )
    print(f"wrote rosters/{cfg['slug']}.csv ({len(people)} people, {len(profiles)} profiles)", file=sys.stderr)
    return 0


def cmd_openalex(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    root = repo_root(args.config)
    slug = cfg["slug"]
    inst = cfg.get("openalex_institution")
    if not inst:
        print("config has no openalex_institution", file=sys.stderr)
        return 1
    data = root / "data" / slug
    client = openalex.OpenAlexClient(data / "openalex", max_cost_usd=args.max_cost)
    overrides = openalex.read_overrides(root / "config" / f"{slug}-openalex-overrides.csv")
    people = roster.read_csv(root / "rosters" / f"{slug}.csv")

    matches, works = [], {}
    try:
        for p in people:
            m = openalex.match_person(client, p.id, p.name, p.orcid, inst, overrides,
                                      cfg.get("openalex_fallback_institutions", []))
            matches.append(m)
            if not args.match_only:
                works[p.id] = openalex.fetch_works(client, m.author_ids, args.since, m.strict_lineage)
    except openalex.BudgetExceeded as e:
        print(f"stopped: {e}. Rerun tomorrow; cached responses are reused.", file=sys.stderr)
        return 2
    finally:
        print(f"OpenAlex: {client.fresh_calls} fresh calls, ${client.spent:.4f}", file=sys.stderr)

    by_id = {p.id: p for p in people}
    agreement: dict[str, float] = {}
    if works:
        # Topic check: own description vs matched papers. UW-wide matches that
        # disagree are probably a namesake, so they go to review instead.
        profiles_path = root / "rosters" / f"{slug}-profiles.json"
        profiles = json.loads(profiles_path.read_text()) if profiles_path.exists() else {}
        embedder = model.Embedder(args.model, cache_dir=data)
        now = dt.date.today().year
        for m in matches:
            p = by_id[m.person_id]
            doc = build_doc(p.id, p.keywords, profiles.get(p.id), works.get(p.id))
            a = model.self_works_agreement(doc, embedder, now)
            if a is None:
                continue
            agreement[p.id] = a
            if m.how == "search-wider" and a < args.min_agreement:
                print(f"  rejected {p.name}: papers do not match their description "
                      f"(agreement {a:.2f} < {args.min_agreement}); see candidates", file=sys.stderr)
                m.how, m.author_ids = "rejected-topic", []
                works[p.id] = []
        low = [f"{by_id[k].name} {v:.2f}" for k, v in sorted(agreement.items(), key=lambda kv: kv[1])
               if v < args.min_agreement and dict((m.person_id, m.how) for m in matches)[k] != "rejected-topic"]
        if low:
            print("low agreement, kept (check by hand): " + ", ".join(low), file=sys.stderr)

    out = root / "rosters" / f"{slug}-openalex-matches.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "how", "openalex_ids", "openalex_names", "works_count", "works_since", "agreement"])
        for m in matches:
            a = agreement.get(m.person_id)
            w.writerow([m.person_id, by_id[m.person_id].name, m.how, "|".join(m.author_ids),
                        "|".join(m.names), m.works_count, len(works.get(m.person_id, [])),
                        "" if a is None else f"{a:.2f}"])
    unmatched = [by_id[m.person_id].name for m in matches if not m.author_ids]
    multi = [by_id[m.person_id].name for m in matches if len(m.author_ids) > 1]
    print(f"matched {len(matches) - len(unmatched)}/{len(matches)}; "
          f"{len(multi)} with several author records; wrote {out.relative_to(root)}", file=sys.stderr)
    if unmatched:
        print("unmatched: " + ", ".join(unmatched), file=sys.stderr)
        cand_path = root / "rosters" / f"{slug}-openalex-candidates.csv"
        try:
            with cand_path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id", "name", "candidate_id", "candidate_name", "works_count", "recent_affiliations"])
                for m in matches:
                    if m.author_ids or m.how == "none" and m.person_id in overrides:
                        continue
                    for c in openalex.candidates(client, by_id[m.person_id].name):
                        w.writerow([m.person_id, by_id[m.person_id].name, c["id"], c["name"], c["works"], c["affiliations"]])
            print(f"candidates for review: {cand_path.relative_to(root)} "
                  f"(confirm in config/{slug}-openalex-overrides.csv)", file=sys.stderr)
        except openalex.BudgetExceeded as e:
            print(f"candidates incomplete: {e}", file=sys.stderr)
    if works:
        (data / "works.json").write_text(json.dumps(works))
        n = sum(len(v) for v in works.values())
        print(f"works since {args.since}: {n} ({n / max(len(works), 1):.0f} per person)", file=sys.stderr)
    return 0


def read_openalex_ids(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {r["id"]: [x for x in r["openalex_ids"].split("|") if x] for r in csv.DictReader(f)}


def coauthor_pairs(works: dict[str, list[dict]], oa_ids: dict[str, list[str]]) -> dict[str, dict[str, int]]:
    """Papers shared by two people on the roster, counted once per paper."""
    owner = {a: pid for pid, ids in oa_ids.items() for a in ids}
    shared: dict[str, set[str]] = {}
    for ws in works.values():
        for w in ws:
            people = sorted({owner[a] for a in w.get("authors", []) if a in owner})
            for i, a in enumerate(people):
                for b in people[i + 1 :]:
                    shared.setdefault(f"{a}\t{b}", set()).add(w["id"])
    out: dict[str, dict[str, int]] = {}
    for key, ids in shared.items():
        a, b = key.split("\t")
        out.setdefault(a, {})[b] = len(ids)
        out.setdefault(b, {})[a] = len(ids)
    return out


def apply_label_overrides(path: Path, ids: list[str], levels: dict) -> None:
    """Replace computed labels with hand-written ones from config/<slug>-labels.yaml.

    Each entry names the cluster containing `member`, so cluster renumbering
    between builds does not misplace a label.
    """
    if not path.exists():
        return
    index = {pid: i for i, pid in enumerate(ids)}
    used: dict[tuple[str, int], str] = {}
    for e in yaml.safe_load(path.read_text()) or []:
        level, member, label = e.get("level"), e.get("member"), e.get("label")
        if level not in levels or not label:
            print(f"labels: skipped bad entry {e}", file=sys.stderr)
            continue
        if member not in index:
            print(f"labels: {member} is not on the map; '{label}' unused", file=sys.stderr)
            continue
        clusters, names = levels[level]
        c = clusters[index[member]]
        if (level, c) in used:
            print(f"labels: '{label}' and '{used[(level, c)]}' name the same {level}; keeping the first", file=sys.stderr)
            continue
        used[(level, c)] = label
        names[c] = [label]
    for level, (clusters, _) in levels.items():
        unnamed = sorted({c for c in clusters if (level, c) not in used and clusters.count(c) > 1})
        if unnamed:
            print(f"labels: {len(unnamed)} {level}(s) still use computed labels", file=sys.stderr)


def cmd_build(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    root = repo_root(args.config)
    data = root / "data" / cfg["slug"]
    people = roster.read_csv(root / "rosters" / f"{cfg['slug']}.csv")
    prof_path = root / "rosters" / f"{cfg['slug']}-profiles.json"
    profiles = json.loads(prof_path.read_text()) if prof_path.exists() else {}
    areas_path = root / "rosters" / f"{cfg['slug']}-areas.json"
    listed_areas = json.loads(areas_path.read_text()) if areas_path.exists() else {}

    works_path = data / "works.json"
    works = json.loads(works_path.read_text()) if works_path.exists() else {}
    if not works:
        print("no data/<slug>/works.json: building from profile text only (run `openalex` first)", file=sys.stderr)
    oa_ids = read_openalex_ids(root / "rosters" / f"{cfg['slug']}-openalex-matches.csv")

    now = dt.date.today().year
    docs = [build_doc(p.id, p.keywords, profiles.get(p.id), works.get(p.id)) for p in people]
    empty = [i for i, d in enumerate(docs) if not d.components(now)]
    left_off, left_off_docs = [people[i] for i in empty], [docs[i] for i in empty]
    if empty:
        print(f"no text at all, off the map (still searchable): {', '.join(p.id for p in left_off)}", file=sys.stderr)
        keep = [i for i in range(len(docs)) if i not in set(empty)]
        people = [people[i] for i in keep]
        docs = [docs[i] for i in keep]

    embedder = model.Embedder(args.model, cache_dir=data)
    vecs = model.person_vectors(docs, embedder, now=now)
    xy = model.layout(vecs, seed=args.seed)
    sim = model.similarity(vecs)
    # Show a neighbour only if closer than 90% of all pairs (GTU hides weak matches too).
    pairs = sim[np.triu_indices_from(sim, k=1)]
    near_cutoff = float(np.quantile(pairs, 0.90))
    coauthors = coauthor_pairs(works, oa_ids)
    n_pairs = sum(len(v) for v in coauthors.values()) // 2
    print(f"co-author pairs within the roster: {n_pairs}", file=sys.stderr)
    broad = model.leiden_areas(sim, k=8, resolution=args.broad, seed=args.seed)
    fine = model.leiden_areas(sim, k=6, resolution=args.fine, seed=args.seed)
    names = [p.name for p in people]
    terms = model.person_terms(docs, names=names)
    nbrs = model.nearest(sim, 10)
    broad_labels = model.cluster_labels(docs, broad, names=names)
    fine_labels = model.cluster_labels(docs, fine, names=names)
    apply_label_overrides(root / "config" / f"{cfg['slug']}-labels.yaml", [p.id for p in people],
                          {"area": (broad, broad_labels), "topic": (fine, fine_labels)})
    print(f"areas: {len(set(broad))} broad, {len(set(fine))} fine", file=sys.stderr)
    check = model.listed_area_agreement([p.id for p in people], nbrs, listed_areas)
    print(
        "neighbours vs curated research areas: "
        f"{check['precision']:.0%} of top-5 share an area (chance {check['chance']:.0%}, "
        f"lift {check['lift']:.1f}x, {check['people']} people listed)",
        file=sys.stderr,
    )

    payload = bundle.payload(
        cfg=cfg,
        people=people,
        profiles=profiles,
        docs=docs,
        xy=xy,
        broad=broad,
        fine=fine,
        broad_labels=broad_labels,
        fine_labels=fine_labels,
        terms=terms,
        nbrs=nbrs,
        listed_areas=listed_areas,
        model_name=args.model,
        left_off=left_off,
        left_off_docs=left_off_docs,
        coauthors=coauthors,
        near_cutoff=near_cutoff,
        openalex_ids=oa_ids,
        as_of=dt.date.today().isoformat(),
    )
    out = root / "site" / cfg["slug"] / "index.html"
    size = bundle.write_html(payload, root / "web", out)
    (data / "payload.json").write_text(json.dumps(payload, indent=1))
    print(f"wrote {out.relative_to(root)} ({size / 1024:.0f} KB)", file=sys.stderr)
    run_search_eval(root, cfg["slug"])
    return 0


def run_search_eval(root: Path, slug: str) -> None:
    """Print the search test set scores (tests/search_eval.mjs) if node is available."""
    import shutil
    import subprocess

    script = root / "tests" / "search_eval.mjs"
    if not shutil.which("node") or not script.exists():
        print("search test set skipped (needs node)", file=sys.stderr)
        return
    res = subprocess.run(["node", str(script), slug, "--json"], capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        print(f"search test set failed: {res.stderr.strip()[:300]}", file=sys.stderr)
        return
    for name, m in json.loads(res.stdout).items():
        print(f"search test set, {name}: hit@10 {m['hit10']:.2f}, MRR {m['mrr']:.2f}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="research-map")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("roster", help="scrape the directory and profiles into rosters/<slug>.csv")
    r.add_argument("config", type=Path)
    r.add_argument("--refresh", action="store_true", help="refetch pages instead of using the cache")
    r.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    r.set_defaults(func=cmd_roster)

    o = sub.add_parser("openalex", help="match people to OpenAlex and fetch their works")
    o.add_argument("config", type=Path)
    o.add_argument("--since", default="2011-01-01", help="earliest publication date")
    o.add_argument("--max-cost", type=float, default=0.5, help="stop after this many USD of fresh calls")
    o.add_argument("--match-only", action="store_true")
    o.add_argument("--model", default=model.DEFAULT_MODEL, help="embedding model for the topic check")
    o.add_argument("--min-agreement", type=float, default=0.30,
                   help="UW-wide matches whose papers agree less than this with the profile go to review")
    o.set_defaults(func=cmd_openalex)

    b = sub.add_parser("build", help="embed, lay out and write site/<slug>/index.html")
    b.add_argument("config", type=Path)
    b.add_argument("--model", default=model.DEFAULT_MODEL)
    b.add_argument("--seed", type=int, default=42)
    b.add_argument("--broad", type=float, default=1.5, help="Leiden resolution for broad areas")
    b.add_argument("--fine", type=float, default=3.0, help="Leiden resolution for fine topics")
    b.set_defaults(func=cmd_build)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
