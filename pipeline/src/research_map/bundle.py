"""Assemble the page data and inline everything into one HTML file."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from .roster import Person
from .text import Doc

SPARSE_WORDS = 25  # fewer words of research text than this -> hollow marker


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
    left_off: list[str] | None = None,
) -> dict:
    listed_by_person: dict[str, list[str]] = {}
    for area, ids in listed_areas.items():
        for i in ids:
            listed_by_person.setdefault(i, []).append(area)

    term_sets = [set(t) for t in terms]
    rows = []
    for i, (p, d) in enumerate(zip(people, docs)):
        prof = profiles.get(p.id, {})
        rows.append(
            {
                "id": p.id,
                "name": p.name,
                "title": p.title,
                "department": p.department,
                "program": p.program,
                "x": round(float(xy[i, 0]), 4),
                "y": round(float(xy[i, 1]), 4),
                "area": broad[i],
                "topic": fine[i],
                "keywords": d.fields.get("keywords", ""),
                "interests": d.fields.get("interests", ""),
                "bio": prof.get("bio", ""),
                "terms": terms[i][:8],
                "listed": listed_by_person.get(p.id, []),
                "url": p.profile_url,
                "links": [{"text": t, "href": h} for t, h in prof.get("links", [])],
                "orcid": p.orcid,
                "sparse": d.word_count < SPARSE_WORDS or not d.research_only,
                "near": [
                    {"i": j, "s": round(s, 3), "t": sorted(term_sets[i] & term_sets[j])[:4]}
                    for j, s in nbrs[i]
                ],
            }
        )

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
            "left_off": left_off or [],
            "method": (
                "Each point is a faculty member. Text from the public directory (research keywords) "
                "and profile pages (research interests, bio, dissertation title) is embedded with "
                f"{model_name}; a person's vector is a weighted mean of their fields. UMAP places "
                "people with similar vectors close together. Areas are Leiden communities on the "
                "nearest-neighbour graph, labelled with distinctive terms."
            ),
        },
        "people": rows,
        "areas": area_rows(broad, broad_labels),
        "topics": area_rows(fine, fine_labels),
    }


def write_html(data: dict, web_dir: Path, out: Path) -> int:
    template = (web_dir / "template.html").read_text(encoding="utf-8")
    css = (web_dir / "map.css").read_text(encoding="utf-8")
    js = (web_dir / "map.js").read_text(encoding="utf-8")
    d3 = (web_dir / "vendor" / "d3.v7.9.0.min.js").read_text(encoding="utf-8")
    # "</" inside inline JSON would end the script tag early.
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
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
