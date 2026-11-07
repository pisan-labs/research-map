"""Roster: who is on the map.

A roster is a CSV with one row per person. For UW Bothell it is scraped from
the public STEM faculty directory pages, which list each person as a heading
"Name, Title" followed by an office/email paragraph and an optional
"Research: ..." paragraph. Headings above people give the program (h2, e.g.
"Mathematics") and the category (e.g. "Full-time faculty").
"""

from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

CATEGORY_WORDS = re.compile(r"faculty|lecturer|emerit|instructor|staff", re.I)
STOP_HEADINGS = re.compile(r"^research areas$", re.I)


@dataclass
class Person:
    id: str
    name: str
    title: str
    department: str
    program: str
    category: str
    keywords: str
    profile_url: str
    orcid: str = ""
    openalex_id: str = ""


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def id_from_url(url: str, name: str) -> str:
    """Profile slug ('/faculty/jeffrey-jensen/' -> 'jeffrey-jensen'), else the name slug."""
    parts = [x for x in urlparse(url).path.split("/") if x]
    if len(parts) >= 2 and parts[-2] == "faculty":
        return parts[-1]
    return slugify(name)


def is_profile_url(url: str) -> bool:
    parts = [x for x in urlparse(url).path.split("/") if x]
    return len(parts) == 2 and parts[0] == "faculty"


def split_name_title(text: str) -> tuple[str, str]:
    """'Yusuf Pisan, Teaching Professor' -> ('Yusuf Pisan', 'Teaching Professor').

    Degrees after the name ('Aaron Enten, Ph.D., MBA') stay with the name when
    no title follows, so we split on the first comma only.
    """
    name, _, title = text.partition(",")
    return name.strip(), title.strip()


def _person_heading(el: Tag) -> Tag | None:
    a = el.find("a")
    if a is None or "," not in el.get_text():
        return None
    return a


def _details(heading: Tag) -> tuple[str, str]:
    """Return (email, research keywords) from the paragraphs after a person heading."""
    email, keywords = "", ""
    for el in heading.find_all_next(["p", "h2", "h3", "h4"]):
        if el.name != "p":
            break
        text = el.get_text(" ", strip=True)
        m = re.match(r"Research\s*:\s*(.*)", text, re.S)
        if m:
            keywords = re.sub(r"\s+", " ", m.group(1)).strip()
        mail = el.find("a", href=re.compile(r"^mailto:"))
        if mail and not email:
            email = mail["href"].removeprefix("mailto:").strip()
    return email, keywords


def parse_directory(html: str, department: str, base_url: str) -> list[Person]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("main") or soup
    program, category = department, ""
    people: list[Person] = []
    for el in root.find_all(["h2", "h3", "h4"]):
        text = el.get_text(" ", strip=True)
        if STOP_HEADINGS.match(text):
            break
        link = _person_heading(el)
        if link is None:
            if CATEGORY_WORDS.search(text):
                category = text
            elif el.name == "h2":
                program, category = text, ""
            continue
        name, title = split_name_title(link.get_text(" ", strip=True))
        _, keywords = _details(el)
        url = urljoin(base_url, link.get("href", ""))
        people.append(
            Person(
                id=id_from_url(url, name),
                name=name,
                title=title,
                department=department,
                program=program,
                category=category,
                keywords=keywords,
                profile_url=url,
            )
        )
    return people


def parse_research_areas(html: str, base_url: str) -> dict[str, list[str]]:
    """The 'Research areas' accordion: area name -> person ids."""
    soup = BeautifulSoup(html, "html.parser")
    areas: dict[str, list[str]] = {}
    for title in soup.select(".js-accordion-title"):
        body = title.find_next_sibling(class_="js-accordion-body")
        if body is None:
            continue
        ids = []
        for a in body.find_all("a", href=True):
            url = urljoin(base_url, a["href"])
            if is_profile_url(url):
                ids.append(id_from_url(url, a.get_text(" ", strip=True)))
        if ids:
            areas[title.get_text(" ", strip=True)] = ids
    return areas


def write_csv(people: list[Person], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[x.name for x in fields(Person)])
        w.writeheader()
        for p in people:
            w.writerow(asdict(p))


def read_csv(path: Path) -> list[Person]:
    with path.open(newline="", encoding="utf-8") as f:
        return [Person(**row) for row in csv.DictReader(f)]


def dedupe(people: list[Person]) -> list[Person]:
    """Keep the first row per id; people listed in two departments appear once."""
    seen: dict[str, Person] = {}
    for p in people:
        seen.setdefault(p.id, p)
    return list(seen.values())
