"""Turn a person's roster row and profile into weighted text fields.

Each field is embedded on its own and the person vector is a weighted mean,
so a long bio does not drown out a precise keyword line. Courses and teaching
interests are left out: they would pull everyone who teaches intro classes
together. OpenAlex works will join this list as further fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Weights per field. Keywords are the person's own short summary of their research.
WEIGHTS = {
    "keywords": 1.0,
    "interests": 1.0,
    "thesis": 0.5,
    "bio": 0.7,
    # Fallback only, for people with no research text at all.
    "teaching": 0.5,
}

# Weights of the parts of a person vector (after GTU: titles 0.45, venues 0.15,
# courses 0.15, theses 0.15, projects 0.10). Missing parts are skipped and the
# rest renormalised, so people without OpenAlex works keep their profile text.
# Measured 2026-11-07 on UW Bothell STEM (neighbours sharing a curated area):
# self .4 / works .3 / venues .15 / courses .15 -> 52%; GTU-like works .45 -> 49%;
# works alone 40%; self alone 50%. The curated lists come from self-descriptions,
# so this check favours "self"; re-tune with the search test set (Phase 1).
COMPONENT_WEIGHTS = {
    "self": 0.40,
    "works": 0.30,
    "venues": 0.15,
    "courses": 0.15,
}


def recency_weight(year: int | None, now: int) -> float:
    """GTU's weights: last 10 years 1.0, the 10 before 0.6, older 0.35."""
    if not year:
        return 0.6
    age = now - year
    return 1.0 if age < 10 else 0.6 if age < 20 else 0.35


# Bio sentences about career history say little about research topics.
BIO_SKIP = re.compile(
    r"\b(joined|received (his|her|their)|earned|ph\.?d\.? (from|in)|before (moving|joining)|"
    r"lived in|grew up|hobbies|in (his|her|their) (free|spare) time|prior to)\b",
    re.I,
)

# Words that appear in many bios but carry no topic.
STOP_WORDS = {
    "research", "researcher", "researchers", "university", "washington", "bothell", "uw",
    "professor", "assistant", "associate", "teaching", "faculty", "department", "school",
    "stem", "interests", "interest", "include", "includes", "including", "work", "works",
    "working", "focus", "focuses", "area", "areas", "student", "students", "dr", "phd",
    "ph", "degree", "currently", "courses", "course", "lab", "laboratory", "also", "using",
    "use", "new", "various", "field", "fields", "study", "studies", "studying", "years",
    "year", "currently", "previously", "member", "program", "programs", "college",
    "science", "sciences", "applications", "application", "based", "related", "topics",
    "systems", "methods", "approaches", "teaches", "taught", "classes", "class",
}


@dataclass
class Doc:
    person_id: str
    fields: dict[str, str]
    works: list[dict] = field(default_factory=list)
    courses: str = ""

    def components(self, now: int) -> dict[str, list[tuple[str, float]]]:
        """Each part of the person vector as (text, weight) pairs."""
        out: dict[str, list[tuple[str, float]]] = {}
        if self.weighted:
            out["self"] = self.weighted
        if self.works:
            out["works"] = [
                ((w["title"] + ". " + w.get("abstract", "")).strip(), recency_weight(w.get("year"), now))
                for w in self.works
            ]
            venues: dict[str, float] = {}
            for w in self.works:
                if w.get("venue"):
                    venues[w["venue"]] = venues.get(w["venue"], 0.0) + recency_weight(w.get("year"), now)
            if venues:
                out["venues"] = list(venues.items())
        if self.courses:
            out["courses"] = [(self.courses, 1.0)]
        return out

    @property
    def n_works(self) -> int:
        return len(self.works)

    @property
    def weighted(self) -> list[tuple[str, float]]:
        return [(t, WEIGHTS[k]) for k, t in self.fields.items() if t]

    @property
    def all_text(self) -> str:
        return " . ".join(t for t in self.fields.values() if t)

    @property
    def topic_text(self) -> str:
        """Short self-descriptions plus OpenAlex topic names: used for labels and terms.

        Raw titles made noisy labels ("discoveries · velocity" from large
        physics collaborations); OpenAlex topic names are a curated vocabulary.
        """
        parts = [self.fields.get(k, "") for k in ("keywords", "interests", "teaching")]
        parts += [w["topics"][0] for w in self.works if w.get("topics")]
        return " . ".join(t for t in parts if t)

    @property
    def research_only(self) -> bool:
        return not self.fields.get("teaching")

    @property
    def word_count(self) -> int:
        return len(self.all_text.split())


def research_bio(bio: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", bio)
    return " ".join(s for s in sentences if s and not BIO_SKIP.search(s))


DEGREE_RE = re.compile(
    r"\b(Ph\.?\s?D\.?|Ed\.?\s?D\.?|D\.?\s?N\.?\s?P\.?|J\.?\s?D\.?|M\.?\s?F\.?\s?A\.?|M\.?\s?B\.?\s?A\.?|"
    r"M\.?\s?S\.?\s?W\.?|M\.?\s?S\.?|M\.?\s?A\.?|B\.?\s?S\.?|B\.?\s?A\.?|MPH|MPA|MEd|M\.Ed\.?)\s+"
)
INSTITUTION_RE = re.compile(r"\b(University|College|Institute|School|Universidad|Universit[éeà]|Academy|Polytechnic)\b")


def degree_fields(text: str) -> str:
    """'Ph.D. Chemistry University of Washington Seattle 2015 M.S. Chemistry ...' -> 'Ph.D. Chemistry'.

    Only the fields: institution names would group people by where they
    studied, not what they study.
    """
    out = []
    parts = DEGREE_RE.split(text or "")
    # split keeps the captured degree: [pre, deg, rest, deg, rest, ...]
    for deg, rest in zip(parts[1::2], parts[2::2]):
        field = INSTITUTION_RE.split(rest)[0]
        field = re.sub(r"\b(19|20)\d\d\b|[,;]", " ", field).strip()
        if field and f"{deg.strip()} {field}" not in out:
            out.append(f"{deg.strip()} {field}")
    return " . ".join(out)


def courses_text(profile: dict | None) -> str:
    sections = (profile or {}).get("sections", {})
    text = " . ".join(sections.get(k, "") for k in ("Courses", "Teaching Interests") if sections.get(k))
    return re.sub(r"\b[A-Z]{2,5} \d{3}\b", "", text).strip()


def build_doc(person_id: str, keywords: str, profile: dict | None, works: list[dict] | None = None,
              with_courses: bool = True) -> Doc:
    profile = profile or {}
    sections = profile.get("sections", {})
    interests = next((v for k, v in sections.items() if k.lower().startswith("research")), "")
    fields = {
        "keywords": keywords.strip(),
        "interests": interests.strip(),
        "thesis": sections.get("_thesis", "").strip(),
        "bio": research_bio(profile.get("bio", "")).strip(),
    }
    if not any(fields.values()) and not works:
        # Teaching-focused faculty: place them by what they teach, drawn hollow.
        # Degrees (e.g. "Ph.D. Sociology") are the last resort: at least the discipline.
        teaching = " . ".join(
            sections.get(k, "") for k in ("Teaching Interests", "Courses") if sections.get(k)
        )
        if not teaching:
            teaching = degree_fields(sections.get("Degrees", ""))
        fields["teaching"] = re.sub(r"\b[A-Z]{2,5} \d{3}\b", "", teaching).strip()
    return Doc(
        person_id=person_id,
        fields=fields,
        works=list(works or []),
        courses=courses_text(profile) if with_courses and not fields.get("teaching") else "",
    )
