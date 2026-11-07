"""Parse a UW Bothell faculty profile page (uwb.edu/faculty/<slug>/).

The page has a bio paragraph under the role heading, then sections headed
`h3.faculty-main-content-heading` (Education, Courses, Teaching Interests,
Research and Scholarship Interests, ...), and sidebar website links.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

ORCID_RE = re.compile(r"orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", re.I)


@dataclass
class Profile:
    bio: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    links: list[tuple[str, str]] = field(default_factory=list)
    orcid: str = ""

    @property
    def research_interests(self) -> str:
        for k, v in self.sections.items():
            if k.lower().startswith("research"):
                return v
        return ""

    @property
    def thesis(self) -> str:
        """Titles in <em> under Education, usually the PhD dissertation."""
        return self.sections.get("_thesis", "")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_profile(html: str) -> Profile:
    soup = BeautifulSoup(html, "html.parser")
    prof = Profile()

    role = soup.find(class_="faculty-profile-role")
    if role is not None:
        box = role.find_next("div", class_="margin-b-sm")
        if box is not None and not box.find("h3"):
            prof.bio = _clean(" ".join(p.get_text(" ") for p in box.find_all("p")))

    for h in soup.find_all("h3", class_="faculty-main-content-heading"):
        body = h.find_next_sibling(class_="faculty-main-content")
        if body is None:
            continue
        name = _clean(h.get_text(" "))
        prof.sections[name] = _clean(body.get_text(" "))
        if name.lower() == "education":
            titles = [_clean(e.get_text(" ")) for e in body.find_all("em")]
            if titles:
                prof.sections["_thesis"] = "; ".join(titles)

    for a in soup.select(".faculty-sidebar-content a[href]"):
        href = a["href"].strip()
        if not href.startswith("http") or "uwb.edu" in href:
            continue
        prof.links.append((_clean(a.get_text(" ")) or href, href))

    for _, href in prof.links:
        m = ORCID_RE.search(href)
        if m:
            prof.orcid = m.group(1)
            break
    if not prof.orcid:
        m = ORCID_RE.search(html)
        if m:
            prof.orcid = m.group(1)
    return prof
