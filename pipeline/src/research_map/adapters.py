"""Site adapters: how to read one university's faculty directory and profiles.

An adapter lists people (with department, title and profile URL), optionally
returns department-curated research areas, and parses a profile page into a
Profile. Config chooses one with `adapter:`; who is kept is decided by
`include` rules, shared by all adapters.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from . import profiles as uwb_profiles
from . import roster
from .fetch import CachedFetcher
from .profiles import Profile
from .roster import Person


@dataclass
class Adapter:
    listing: Callable[[CachedFetcher, dict, bool], tuple[list[Person], dict[str, list[str]]]]
    # None: the listing already carries the research text; profile pages are not fetched.
    profile: Callable[[str], Profile] | None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# ---------------------------------------------------------------- UW Bothell STEM


def uwb_listing(fetcher: CachedFetcher, cfg: dict, refresh: bool):
    people: list[Person] = []
    areas: dict[str, list[str]] = {}
    for entry in cfg["directory"]:
        html = fetcher.get(entry["url"], refresh=refresh)
        found = roster.parse_directory(html, entry["department"], cfg["base_url"])
        print(f"  {entry['department']}: {len(found)} listed", file=sys.stderr)
        people += found
        for name, ids in roster.parse_research_areas(html, cfg["base_url"]).items():
            areas.setdefault(name, [])
            areas[name] += [i for i in ids if i not in areas[name]]
    return people, areas


# ---------------------------------------------------------------- UW Tacoma


def split_uwt_department(text: str) -> tuple[str, str]:
    """'Sciences and Mathematics, Department of School of Interdisciplinary Arts and Sciences'
    -> ('School of Interdisciplinary Arts and Sciences', 'Sciences and Mathematics');
    'Engineering & Technology, School of' -> ('School of Engineering & Technology', same)."""
    text = _clean(text)
    m = re.match(r"(.+?), Department of (School of .+)$", text)
    if m:
        return m.group(2), m.group(1)
    m = re.match(r"(.+?), School of$", text)
    if m:
        school = f"School of {m.group(1)}"
        return school, school
    m = re.match(r"(.+?), (Office|Center|Institute) of( the)?$", text)
    if m:
        name = f"{m.group(2)} of{m.group(3) or ''} {m.group(1)}"
        return name, name
    return text, text


CREDENTIAL_RE = re.compile(r"\b(Ph\.?D|Ed\.?D|SPHR|MD|MBA|MSW|DNP|RN|J\.?D)\b\.?", re.I)


def uwt_name(text: str) -> str:
    """'Abraham, Isaac' -> 'Isaac Abraham'. Drops credentials ('Endo, PhD/SPHR , Rachel')
    and descriptions after a dash ('Adams - Free Man of Color, Luther')."""
    parts = [p.strip() for p in _clean(text).split(",")]
    parts = [p for p in parts if p and not CREDENTIAL_RE.fullmatch(re.sub(r"[/\s]+", " ", p).strip().split(" ")[0] or "")
             and not all(CREDENTIAL_RE.fullmatch(x) for x in re.split(r"[/\s]+", p) if x)]
    if not parts:
        return ""
    last = re.split(r"\s+[-–]\s+", parts[0])[0]
    first = parts[-1] if len(parts) > 1 else ""
    return f"{first} {last}".strip()


def uwt_listing(fetcher: CachedFetcher, cfg: dict, refresh: bool):
    base = cfg["listing_url"]
    people: list[Person] = []
    for page in range(0, 50):
        html = fetcher.get(f"{base}?page={page}", refresh=refresh)
        rows = BeautifulSoup(html, "html.parser").select("tbody tr")
        if not rows:
            break
        for r in rows:
            cell = lambda name: r.select_one(f'[data-cell="{name}"]')  # noqa: E731
            link = cell("Name").find("a")
            name = uwt_name(cell("Name").get_text(" ", strip=True))
            dept, program = split_uwt_department(cell("Department").get_text(" ", strip=True))
            people.append(
                Person(
                    id=roster.slugify(name),
                    name=name,
                    title=_clean(cell("Title").get_text(" ", strip=True)),
                    department=dept,
                    program=program,
                    category="",
                    keywords="",
                    profile_url=urljoin(base, link["href"]) if link else "",
                )
            )
    print(f"  directory: {len(people)} listed", file=sys.stderr)
    return people, {}


def uwt_profile(html: str) -> Profile:
    """Directory employee page: h3 sections such as Introduction, Current Research, Teaching."""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("main") or soup
    prof = Profile()
    for h in root.find_all("h3"):
        name = _clean(h.get_text(" "))
        parts = []
        for sib in h.find_next_siblings():
            if sib.name in ("h2", "h3"):
                break
            parts.append(sib.get_text(" "))
        text = _clean(" ".join(parts))
        if not text:
            continue
        key = {"current research": "Research Interests", "introduction": "_intro"}.get(name.lower(), name)
        prof.sections[key] = text
    prof.bio = prof.sections.pop("_intro", "")
    if "Teaching" in prof.sections:
        prof.sections["Teaching Interests"] = prof.sections.pop("Teaching")
    for a in root.select("a[href]"):
        href = a["href"].strip()
        if href.startswith("http") and "uw.edu" not in href:
            prof.links.append((_clean(a.get_text(" ")) or href, href))
    m = uwb_profiles.ORCID_RE.search(html)
    if m:
        prof.orcid = m.group(1)
    return prof


# ---------------------------------------------------------------- UW College of Engineering (Seattle)

RANK_RE = re.compile(r"\b(professor|lecturer|instructor)\b", re.I)


def uwcoe_listing(fetcher: CachedFetcher, cfg: dict, refresh: bool):
    """engr.washington.edu/facultyfinder: a paged table of name, roles/department/rank, research areas."""
    base = cfg["listing_url"]
    departments = cfg.get("departments", [])
    people: list[Person] = []
    areas: dict[str, list[str]] = {}
    seen_pages: set[tuple[str, ...]] = set()
    for page in range(0, 200):
        html = fetcher.get(f"{base}?page={page}", refresh=refresh)
        rows = BeautifulSoup(html, "html.parser").select("table tbody tr")
        names = tuple(r.get_text(" ", strip=True)[:40] for r in rows)
        if not rows or names in seen_pages:
            break
        seen_pages.add(names)
        for r in rows:
            tds = r.find_all("td")
            if len(tds) < 4:
                continue
            bold = tds[1].find("b")
            link = next((a for a in tds[1].find_all("a", href=True) if not a["href"].startswith("mailto:")), None)
            raw = (bold or link).get_text(" ", strip=True) if (bold or link) else ""
            if not raw or "@" in raw:
                continue
            name = uwt_name(raw)
            lines = [x for x in tds[2].get_text("\n", strip=True).split("\n") if x.strip()]
            dept = next((d for d in departments if any(d == x.strip() or x.strip().endswith(", " + d) for x in lines)), "")
            if not dept:
                dept = next((x for x in lines if re.search(r"Engineering|Science|Bioengineering", x) and not RANK_RE.search(x)), "Other")
            rank = next((x for x in reversed(lines) if RANK_RE.search(x)), lines[-1] if lines else "")
            research = [_clean(li.get_text(" ")) for li in tds[3].find_all("li")]
            pid = roster.slugify(name)
            people.append(Person(id=pid, name=name, title=_clean(rank), department=dept, program=dept,
                                 category="", keywords="; ".join(research), profile_url=link["href"] if link else ""))
            for a in research:
                areas.setdefault(a, [])
                if pid not in areas[a]:
                    areas[a].append(pid)
    print(f"  faculty finder: {len(people)} listed over {len(seen_pages)} pages", file=sys.stderr)
    return people, areas


ADAPTERS = {
    "uwb-stem": Adapter(uwb_listing, uwb_profiles.parse_profile),
    "uwt-directory": Adapter(uwt_listing, uwt_profile),
    "uwcoe-facultyfinder": Adapter(uwcoe_listing, None),
}


# ---------------------------------------------------------------- who is kept


def included(p: Person, rules: dict) -> bool:
    """Shared filter. `categories`: directory categories to keep (UW Bothell).
    `title_pattern` / `exclude_title_pattern`: regexes on the job title."""
    cats = rules.get("categories")
    if cats and p.category not in cats:
        return False
    pat = rules.get("title_pattern")
    if pat and not re.search(pat, p.title, re.I):
        return False
    bad = rules.get("exclude_title_pattern")
    if bad and re.search(bad, p.title, re.I):
        return False
    return True
