"""Turn a person's roster row and profile into weighted text fields.

Each field is embedded on its own and the person vector is a weighted mean,
so a long bio does not drown out a precise keyword line. Courses and teaching
interests are left out: they would pull everyone who teaches intro classes
together. OpenAlex works will join this list as further fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Weights per field. Keywords are the person's own short summary of their research.
WEIGHTS = {
    "keywords": 1.0,
    "interests": 1.0,
    "thesis": 0.5,
    "bio": 0.7,
    # Fallback only, for people with no research text at all.
    "teaching": 0.5,
}

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

    @property
    def weighted(self) -> list[tuple[str, float]]:
        return [(t, WEIGHTS[k]) for k, t in self.fields.items() if t]

    @property
    def all_text(self) -> str:
        return " . ".join(t for t in self.fields.values() if t)

    @property
    def topic_text(self) -> str:
        """Short self-descriptions only: used for area labels."""
        parts = [self.fields.get(k, "") for k in ("keywords", "interests", "teaching")]
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


def build_doc(person_id: str, keywords: str, profile: dict | None) -> Doc:
    profile = profile or {}
    sections = profile.get("sections", {})
    interests = next((v for k, v in sections.items() if k.lower().startswith("research")), "")
    fields = {
        "keywords": keywords.strip(),
        "interests": interests.strip(),
        "thesis": sections.get("_thesis", "").strip(),
        "bio": research_bio(profile.get("bio", "")).strip(),
    }
    if not any(fields.values()):
        # Teaching-focused faculty: place them by what they teach, drawn hollow.
        teaching = " . ".join(
            sections.get(k, "") for k in ("Teaching Interests", "Courses") if sections.get(k)
        )
        fields["teaching"] = re.sub(r"\b[A-Z]{2,5} \d{3}\b", "", teaching).strip()
    return Doc(person_id=person_id, fields=fields)
