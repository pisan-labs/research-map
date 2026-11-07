"""Command line: `research-map roster CONFIG` then `research-map build CONFIG`."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

from . import bundle, model, roster
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


def cmd_build(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    root = repo_root(args.config)
    data = root / "data" / cfg["slug"]
    people = roster.read_csv(root / "rosters" / f"{cfg['slug']}.csv")
    prof_path = root / "rosters" / f"{cfg['slug']}-profiles.json"
    profiles = json.loads(prof_path.read_text()) if prof_path.exists() else {}
    areas_path = root / "rosters" / f"{cfg['slug']}-areas.json"
    listed_areas = json.loads(areas_path.read_text()) if areas_path.exists() else {}

    docs = [build_doc(p.id, p.keywords, profiles.get(p.id)) for p in people]
    empty = [p for p, d in zip(people, docs) if not d.weighted]
    if empty:
        print(f"no text at all, left off: {', '.join(p.id for p in empty)}", file=sys.stderr)
        keep = [i for i, d in enumerate(docs) if d.weighted]
        people = [people[i] for i in keep]
        docs = [docs[i] for i in keep]

    embedder = model.Embedder(args.model, cache_dir=data)
    vecs = model.person_vectors(docs, embedder)
    xy = model.layout(vecs, seed=args.seed)
    sim = model.similarity(vecs)
    broad = model.leiden_areas(sim, k=8, resolution=args.broad, seed=args.seed)
    fine = model.leiden_areas(sim, k=6, resolution=args.fine, seed=args.seed)
    names = [p.name for p in people]
    terms = model.person_terms(docs, names=names)
    nbrs = model.nearest(sim, 10)
    broad_labels = model.cluster_labels(docs, broad, names=names)
    fine_labels = model.cluster_labels(docs, fine, names=names)
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
        left_off=[p.name for p in empty],
        as_of=dt.date.today().isoformat(),
    )
    out = root / "site" / cfg["slug"] / "index.html"
    size = bundle.write_html(payload, root / "web", out)
    (data / "payload.json").write_text(json.dumps(payload, indent=1))
    print(f"wrote {out.relative_to(root)} ({size / 1024:.0f} KB)", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="research-map")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("roster", help="scrape the directory and profiles into rosters/<slug>.csv")
    r.add_argument("config", type=Path)
    r.add_argument("--refresh", action="store_true", help="refetch pages instead of using the cache")
    r.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    r.set_defaults(func=cmd_roster)

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
