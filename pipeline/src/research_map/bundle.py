"""Assemble the page data and inline everything into one HTML file."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import numpy as np

from .roster import Person
from .text import Doc

SPARSE_WORDS = 25  # fewer words of profile text than this ...
SPARSE_WORKS = 6  # ... and fewer works than this -> hollow marker (GTU: < 6 records)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
# US-style phone numbers with one consistent separator: (425) 352-5000, 425-352-5000, 425.352.5000.
PHONE = re.compile(r"(?<![\d./-])(?:\+?1[ .-]?)?(?:\(\d{3}\) ?\d{3}-\d{4}|\d{3}([.-])\d{3}\1\d{4})(?![\d./-])")
ID_LIKE = re.compile(r"(?<![\d./-])\d{3}-\d{2}-\d{4}(?![\d./-])|(?<![\d./-])\d{11}(?![\d./-])")
URL = re.compile(r"https?://[^\"\s]+")


def scrub(text: str) -> str:
    """Remove e-mail addresses and phone numbers from free text."""
    return PHONE.sub("[phone removed]", EMAIL.sub("[e-mail removed]", text or ""))


def privacy_problems(blob: str) -> list[str]:
    """What the final page data must not contain (GTU checks every release too)."""
    text = URL.sub(" ", blob)  # DOIs and links hold digit runs that are not contact details
    found = [m.group(0) for rx in (EMAIL, PHONE, ID_LIKE) for m in rx.finditer(text)]
    return sorted(set(found))


def work_url(w: dict) -> str:
    return w.get("doi") or f"https://openalex.org/{w['id']}"


def _centroids(xy: np.ndarray, labels: list[int]) -> dict[int, tuple[float, float]]:
    lab = np.array(labels)
    out = {}
    for c in sorted(set(labels)):
        pts = xy[lab == c]
        # Median is steadier than mean when one member sits far away.
        out[c] = (float(np.median(pts[:, 0])), float(np.median(pts[:, 1])))
    return out


def payload(
    *,
    cfg: dict,
    people: list[Person],
    profiles: dict,
    docs: list[Doc],
    xy: np.ndarray,
    broad: list[int],
    fine: list[int],
    broad_labels: dict[int, list[str]],
    fine_labels: dict[int, list[str]],
    terms: list[list[str]],
    nbrs: list[list[tuple[int, float]]],
    listed_areas: dict[str, list[str]],
    model_name: str,
    as_of: str,
    left_off: list[Person] | None = None,
    left_off_docs: list[Doc] | None = None,
    coauthors: dict[str, dict[str, int]] | None = None,
    near_cutoff: float = -1.0,
    openalex_ids: dict[str, list[str]] | None = None,
    page_pubs: int = 60,
) -> dict:
    listed_by_person: dict[str, list[str]] = {}
    for area, ids in listed_areas.items():
        for i in ids:
            listed_by_person.setdefault(i, []).append(area)

    term_sets = [set(t) for t in terms]
    index = {p.id: i for i, p in enumerate(people)}
    coauthors = coauthors or {}
    openalex_ids = openalex_ids or {}

    def base_row(p: Person, d: Doc) -> dict:
        prof = profiles.get(p.id, {})
        topics = Counter(t for w in d.works for t in w.get("topics", [])[:1])
        return {
            "id": p.id,
            "name": p.name,
            "title": p.title,
            "department": p.department,
            "program": p.program,
            "keywords": scrub(d.fields.get("keywords", "")),
            "interests": scrub(d.fields.get("interests", "")),
            "bio": scrub(prof.get("bio", "")),
            "listed": listed_by_person.get(p.id, []),
            "url": p.profile_url,
            "links": [{"text": t, "href": h} for t, h in prof.get("links", [])],
            "orcid": p.orcid,
            "openalex": openalex_ids.get(p.id, []),
            "n_works": d.n_works,  # all works; "pubs" below may be capped for page size
            # Every publication as [title, year, venue, link]: search records
            # and the card's list (newest first).
            "pubs": [[w["title"], w.get("year"), w.get("venue", ""), work_url(w)] for w in d.works[:page_pubs]],
            "oa_topics": [t for t, _ in topics.most_common(6)],
        }

    rows = []
    for i, (p, d) in enumerate(zip(people, docs)):
        row = base_row(p, d)
        row.update(
            {
                "x": round(float(xy[i, 0]), 4),
                "y": round(float(xy[i, 1]), 4),
                "area": broad[i],
                "topic": fine[i],
                "terms": terms[i][:8],
                "sparse": (d.n_works < SPARSE_WORKS and d.word_count < SPARSE_WORDS) or not d.research_only,
                "near": [
                    {"i": j, "s": round(s, 3), "t": sorted(term_sets[i] & term_sets[j])[:4]}
                    for j, s in nbrs[i]
                    if s >= near_cutoff
                ],
                "coauthors": sorted(
                    ([index[q], n] for q, n in coauthors.get(p.id, {}).items() if q in index),
                    key=lambda x: -x[1],
                ),
            }
        )
        rows.append(row)
    for p, d in zip(left_off or [], left_off_docs or []):
        row = base_row(p, d)
        row.update({"off": True, "terms": [], "sparse": True, "near": [], "coauthors": []})
        rows.append(row)

    def area_rows(labels: list[int], names: dict[int, list[str]]) -> list[dict]:
        cent = _centroids(xy, labels)
        size = Counter(labels)
        return [
            {"id": c, "label": " · ".join(names.get(c, [])), "x": cent[c][0], "y": cent[c][1], "n": size[c]}
            for c in sorted(cent)
        ]

    return {
        "meta": {
            "name": cfg["name"],
            "university": cfg.get("university", ""),
            "as_of": as_of,
            "model": model_name,
            "color_by": cfg.get("color_by", "program"),
            "sources": [d["url"] for d in cfg["directory"]],
            "left_off": [p.name for p in left_off or []],
            "near_cutoff": round(near_cutoff, 3),
            "method": (
                "Each point is a faculty member. A person's vector combines their publications since "
                "2011 from OpenAlex (title and abstract, recent work weighted more), the venues they "
                "publish in, their own description on the public directory and profile pages "
                "(research keywords, interests, bio, dissertation title) and the courses they teach. "
                f"Text is embedded with {model_name}. UMAP places people with similar vectors close "
                "together. Areas are Leiden communities on the nearest-neighbour graph, named by hand from their members' "
                "research where a name has been written, otherwise by distinctive terms. Closest people are shown only when they are closer than 90% of "
                "all pairs."
            ),
        },
        "people": rows,
        "areas": area_rows(broad, broad_labels),
        "topics": area_rows(fine, fine_labels),
    }


def write_html(data: dict, web_dir: Path, out: Path) -> int:
    template = (web_dir / "template.html").read_text(encoding="utf-8")
    css = (web_dir / "map.css").read_text(encoding="utf-8")
    js = (web_dir / "search.js").read_text(encoding="utf-8") + "\n" + (web_dir / "map.js").read_text(encoding="utf-8")
    d3 = (web_dir / "vendor" / "d3.v7.9.0.min.js").read_text(encoding="utf-8")
    # "</" inside inline JSON would end the script tag early.
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    problems = privacy_problems(blob)
    if problems:
        raise ValueError(f"page data contains contact details or ID-like numbers: {problems[:5]}")
    html = (
        template.replace("/*__CSS__*/", css)
        .replace("/*__D3__*/", d3)
        .replace("/*__DATA__*/", blob)
        .replace("/*__JS__*/", js)
        .replace("__TITLE__", data["meta"]["name"] + " research map")
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return len(html.encode())


def write_site_index(site_dir: Path) -> None:
    """site/index.html: one row per built map, from each map's meta.json."""
    import html as h

    rows = []
    for meta_path in sorted(site_dir.glob("*/meta.json")):
        m = json.loads(meta_path.read_text())
        rows.append(
            f"<li><a href=\"{h.escape(meta_path.parent.name)}/index.html\">{h.escape(m['name'])}</a>"
            f"<span>{h.escape(m['university'])} · {m['people']} faculty · {m['works']:,} publications · "
            f"as of {h.escape(m['as_of'])}</span></li>"
        )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>University research maps</title>
<style>
:root {{ color-scheme: light; --bg: #f9f9f7; --ink: #0b0b0b; --muted: #6f6d68; --line: #e1e0d9; --accent: #2a78d6; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ color-scheme: dark; --bg: #0d0d0d; --ink: #f0efec; --muted: #9d9b94; --line: #2c2c2a; --accent: #3987e5; }} }}
:root[data-theme="dark"] {{ color-scheme: dark; --bg: #0d0d0d; --ink: #f0efec; --muted: #9d9b94; --line: #2c2c2a; --accent: #3987e5; }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 system-ui, sans-serif; }}
main {{ max-width: 720px; margin: 0 auto; padding: 32px 16px; }}
h1 {{ font-size: 22px; margin: 0 0 4px; }} p {{ color: var(--muted); margin: 0 0 20px; }}
ul {{ list-style: none; padding: 0; margin: 0; }} li {{ border-top: 1px solid var(--line); padding: 12px 0; }}
a {{ color: var(--accent); font-weight: 600; text-decoration: none; }} a:hover {{ text-decoration: underline; }}
li span {{ display: block; color: var(--muted); font-size: 13px; }}
</style></head><body><main>
<h1>University research maps</h1>
<p>Each map shows faculty as points; people who work on similar topics sit close together. Built from public directory pages and OpenAlex.</p>
<ul>{"".join(rows)}</ul>
</main></body></html>
"""
    (site_dir / "index.html").write_text(page, encoding="utf-8")
