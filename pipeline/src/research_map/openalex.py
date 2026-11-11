"""OpenAlex: match roster people to author records and fetch their works.

The API key is not handled here. In the cloud environment a network proxy
adds it to every request to api.openalex.org; locally, set OPENALEX_API_KEY
and it is sent as a Bearer token.

Every response is cached under data/<slug>/openalex/ keyed by URL, so reruns
cost nothing. Fresh requests add up the `cost_usd` OpenAlex reports and stop
when a spending cap is reached.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

import httpx

API = "https://api.openalex.org"
WORK_FIELDS = (
    "id,doi,title,publication_year,type,abstract_inverted_index,primary_location,"
    "topics,authorships,awards,is_retracted,is_paratext"
)


class BudgetExceeded(RuntimeError):
    pass


def _out_of_budget(resp: httpx.Response) -> bool:
    """A 429 that means the daily budget is spent (not a short burst limit)."""
    try:
        retry = int(resp.headers.get("retry-after", "0"))
    except ValueError:
        retry = 0
    return retry > 300 or "insufficient budget" in resp.text.lower()


class OpenAlexClient:
    def __init__(self, cache_dir: Path, max_cost_usd: float = 0.5, delay: float = 0.15):
        self.cache_dir = cache_dir
        self.max_cost = max_cost_usd
        self.spent = 0.0
        self.fresh_calls = 0
        self.delay = delay
        headers = {"User-Agent": "research-map/0.1 (+https://github.com/pisan-labs/research-map)"}
        key = os.environ.get("OPENALEX_API_KEY", "")
        if key and key != "proxy-injected":
            headers["Authorization"] = f"Bearer {key}"
        self.http = httpx.Client(headers=headers, timeout=60, follow_redirects=True)

    def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{API}{path}" + (f"?{urlencode(params, safe=':,|*')}" if params else "")
        cache = self.cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()[:20]}.json"
        if cache.exists():
            return json.loads(cache.read_text())
        if self.spent >= self.max_cost:
            raise BudgetExceeded(f"spent ${self.spent:.4f}, cap ${self.max_cost}")
        for attempt in range(5):
            try:
                resp = self.http.get(url)
            except httpx.TransportError:  # connection reset, timeout: retry with backoff
                if attempt == 4:
                    raise
                time.sleep(2**attempt)
                continue
            if resp.status_code == 429 and _out_of_budget(resp):
                # The key's daily budget is spent: retrying cannot help until it resets.
                raise BudgetExceeded(
                    f"OpenAlex daily budget used up (remaining "
                    f"${resp.headers.get('x-ratelimit-remaining-usd', '?')}, resets at midnight UTC, "
                    f"in {int(resp.headers.get('retry-after', '0') or 0) // 60} min)")
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2**attempt)
                continue
            break
        resp.raise_for_status()
        data = resp.json()
        self.fresh_calls += 1
        self.spent += float((data.get("meta") or {}).get("cost_usd") or 0)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data))
        time.sleep(self.delay)
        return data


# ---------------------------------------------------------------- names


# Letters NFKD does not decompose: dropping them broke names ("Bałazińska" ->
# "baazinska", "Rothvoß" -> "rothvo"). Unicode dashes ("Su‐In") would glue tokens.
_TRANSLIT = str.maketrans({
    "ł": "l", "Ł": "L", "ß": "ss", "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE",
    "đ": "d", "Đ": "D", "ð": "d", "Ð": "D", "þ": "th", "Þ": "Th", "ı": "i", "ħ": "h", "Ħ": "H",
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    "‘": "'", "’": "'", "ʼ": "'",  # curly apostrophes: "O’Malley" became "omalley"
})


def norm_name(name: str) -> list[str]:
    """Lowercase ASCII tokens; drops bracketed nicknames and degree suffixes."""
    name = re.sub(r"\([^)]*\)", " ", name).translate(_TRANSLIT)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    toks = re.findall(r"[a-z]+", name.lower())
    return [t for t in toks if t not in {"dr", "phd", "jr", "sr", "ii", "iii", "md", "pe"}]


def nicknames(name: str) -> list[str]:
    return [t.lower() for t in re.findall(r"\(([^)]+)\)", name)]


# Common English short forms. A prefix rule ("Zhao" ~ "Zhaoming") matched
# different people, so only these pairs count as the same given name.
NICKNAMES = {
    "jeff": {"jeffrey", "jeffery", "geoffrey"}, "bill": {"william"}, "will": {"william"},
    "rick": {"richard", "ricardo", "eric", "frederick"}, "rich": {"richard"}, "dick": {"richard"},
    "bob": {"robert"}, "rob": {"robert"}, "zak": {"zachary"}, "zach": {"zachary"},
    "alex": {"alexander", "alexandre", "alexandra", "alexandria"}, "mike": {"michael"},
    "jim": {"james"}, "tom": {"thomas"}, "dan": {"daniel"}, "dave": {"david"}, "steve": {"steven", "stephen"},
    "chris": {"christopher", "christine", "christina"}, "kate": {"katherine", "kathryn", "katharine"},
    "liz": {"elizabeth"}, "beth": {"elizabeth"}, "andy": {"andrew"}, "matt": {"matthew"},
    "tony": {"anthony"}, "joe": {"joseph"}, "ben": {"benjamin"}, "sam": {"samuel", "samantha"},
    "nick": {"nicholas"}, "pat": {"patrick", "patricia"}, "sue": {"susan"}, "jen": {"jennifer"},
    "jenny": {"jennifer"}, "ed": {"edward"}, "ted": {"edward", "theodore"}, "greg": {"gregory"},
    "ken": {"kenneth"}, "larry": {"lawrence"}, "tim": {"timothy"}, "wolf": {"wolfgang", "bjong"},
    "joey": {"joanna", "josephine"}, "jong": {"jong"}, "kim": {"kimberly"},
}


def same_given_name(a: str, b: str) -> bool:
    if a == b:
        return True
    return b in NICKNAMES.get(a, ()) or a in NICKNAMES.get(b, ())


def _given_ok(roster_name: str, given: list[str]) -> bool:
    r = norm_name(roster_name)
    firsts = [r[0]] + [n for nick in nicknames(roster_name) for n in norm_name(nick)]
    if not given or not any(same_given_name(f, given[0]) for f in firsts):
        return False
    r_mid, c_mid = r[1:-1], given[1:]
    return not (r_mid and c_mid and r_mid[0][0] != c_mid[0][0])


def name_match_kind(roster_name: str, candidate: str) -> str:
    """'exact' (family name last, or a reversed 'Family Given' record), 'loose' (family name
    elsewhere: 'Pedram Khalili Amiri', 'Jarrod Call LCSW'), or '' (no match).

    Given names match in full, by a bracketed nickname ("Zachary (Zak)"), or through the
    NICKNAMES table (Jeff / Jeffrey); initials alone never do. Middle initials must agree.
    """
    r, c = norm_name(roster_name), norm_name(candidate)
    if len(r) < 2 or len(c) < 2:
        return ""
    last = r[-1]
    if c[-1] == last and _given_ok(roster_name, c[:-1]):
        return "exact"
    if c[0] == last and _given_ok(roster_name, c[1:]):
        return "exact"  # reversed: "Chen Yan" for Yan Chen
    if last in c[1:-1]:
        i = c.index(last, 1)
        if _given_ok(roster_name, c[:i]):
            return "loose"
    return ""


def name_matches(roster_name: str, candidate: str) -> bool:
    return bool(name_match_kind(roster_name, candidate))


# ---------------------------------------------------------------- matching


@dataclass
class Match:
    person_id: str
    author_ids: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    works_count: int = 0
    how: str = ""  # orcid | search | search-wider | strict | override | none | ambiguous
    # For common names with several records: keep only works where this
    # author is listed with an institution in `strict_lineage`.
    strict_lineage: str = ""


def short_id(url_or_id: str) -> str:
    return url_or_id.rstrip("/").split("/")[-1]


def read_overrides(path: Path) -> dict[str, list[str]]:
    """CSV: id,openalex_ids,note. openalex_ids is 'A1|A2', or 'none' to skip a person."""
    if not path.exists():
        return {}
    out = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ids = row.get("openalex_ids", "").strip()
            out[row["id"].strip()] = [] if ids.lower() == "none" else [short_id(x) for x in ids.split("|") if x.strip()]
    return out


def search_queries(name: str) -> list[str]:
    """First + last name, and nickname + last: middle initials hide records."""
    toks = norm_name(name)
    if len(toks) < 2:
        return [" ".join(toks)]
    qs = [f"{toks[0]} {toks[-1]}"] + [f"{n} {toks[-1]}" for nick in nicknames(name) for n in norm_name(nick)[:1]]
    # Short forms people publish under ("Daniel Grossman" publishes as "Dan Grossman").
    qs += [f"{short} {toks[-1]}" for short, full in NICKNAMES.items() if toks[0] in full and short != toks[0]]
    # And the reverse: the roster says "Mike Averkiou", the record is "Michael Averkiou".
    qs += [f"{full} {toks[-1]}" for full in sorted(NICKNAMES.get(toks[0], ())) if full != toks[0]]
    # Hyphenated or apostrophe surnames as written ("Al-Masri", "O'Rourke"): "eyhab masri" can miss them.
    words = re.sub(r"\([^)]*\)", " ", name).split()
    if len(words) >= 2 and re.search(r"[-'’]", words[-1]):
        qs.append(f"{toks[0]} {words[-1].lower()}")
    return list(dict.fromkeys(qs))


def _search(client: OpenAlexClient, name: str, filt: str | None) -> list[dict]:
    seen: dict[str, dict] = {}
    for q in search_queries(name):
        params = {
            "search": q,
            "select": "id,display_name,display_name_alternatives,works_count,affiliations",
            "per_page": 25,
        }
        if filt:
            params["filter"] = filt
        for a in client.get("/authors", params).get("results", []):
            seen.setdefault(a["id"], a)
    return list(seen.values())


def _name_hits(name: str, results: list[dict]) -> list[dict]:
    """Exact name matches if there are any; otherwise the loose ones.

    "Simon Peter" has an exact record, so "Simon Peter Horslen" is dropped;
    "Pedram Khalili" has only "Pedram Khalili Amiri", which is kept.
    """
    kinds = [(a, name_match_kind(name, a["display_name"])) for a in results]
    exact = [a for a, k in kinds if k == "exact"]
    return exact or [a for a, k in kinds if k == "loose"]


MAX_RECORDS = 3  # more author records than this for one name: likely several people
MAX_WORKS = 500  # more works than this in total: likely merged people


def candidates(client: OpenAlexClient, name: str) -> list[dict]:
    """Name matches anywhere, for a person to confirm by hand (overrides file)."""
    out = []
    for a in _name_hits(name, _search(client, name, None))[:6]:
        affs = sorted(
            ((x["institution"]["display_name"], min(x.get("years") or [0]), max(x.get("years") or [0]))
             for x in (a.get("affiliations") or [])),
            key=lambda t: -t[2],
        )[:3]
        out.append({"id": short_id(a["id"]), "name": a["display_name"], "works": a.get("works_count", 0),
                    "affiliations": "; ".join(f"{n} {lo}-{hi}" for n, lo, hi in affs)})
    return out


def match_person(client: OpenAlexClient, pid: str, name: str, orcid: str, institution: str,
                 overrides: dict[str, list[str]], fallback_institutions: list[str] = ()) -> Match:
    if pid in overrides:
        ids = overrides[pid]
        return Match(pid, ids, how="override" if ids else "none")
    if orcid:
        data = client.get(f"/authors/orcid:{orcid}", {"select": "id,display_name,works_count"})
        if data.get("id"):
            return Match(pid, [short_id(data["id"])], [data["display_name"]], data.get("works_count", 0), "orcid")
    m = Match(pid, how="search")
    hits = _name_hits(name, _search(client, name, f"affiliations.institution.id:{institution}"))
    if not hits and fallback_institutions:
        filt = "affiliations.institution.lineage:" + "|".join(fallback_institutions)
        wider = _name_hits(name, _search(client, name, filt))
        if len(wider) == 1:  # wider net: only an unambiguous single record
            hits, m.how = wider, "search-wider"
        elif wider:
            m.how = "ambiguous"
            m.names = [a["display_name"] for a in wider]
            return m
    total = sum(a.get("works_count", 0) for a in hits)
    if len(hits) > MAX_RECORDS or total > MAX_WORKS:
        # Several records or merged people: take them all, but only the works
        # where this author is listed at the institution (fetch_works checks).
        m.how = "strict"
        m.strict_lineage = institution
        m.names = [a["display_name"] for a in hits]
        m.works_count = total
        m.author_ids = [short_id(a["id"]) for a in hits]
        return m
    for a in hits:
        m.author_ids.append(short_id(a["id"]))
        m.names.append(a["display_name"])
        m.works_count += a.get("works_count", 0)
    if not m.author_ids and m.how != "ambiguous":
        m.how = "none"
    return m


# ---------------------------------------------------------------- works


def abstract_text(inverted: dict | None) -> str:
    if not inverted:
        return ""
    pos: list[tuple[int, str]] = []
    for word, idxs in inverted.items():
        pos += [(i, word) for i in idxs]
    return " ".join(w for _, w in sorted(pos))


def _listed_at(w: dict, author_ids: set[str], institution: str) -> bool:
    """True if one of these authors is listed with this institution on the work."""
    for a in w.get("authorships", []):
        if short_id((a.get("author") or {}).get("id") or "") in author_ids:
            for inst in a.get("institutions", []):
                ids = {short_id(inst.get("id") or "")} | {short_id(x) for x in inst.get("lineage") or []}
                if institution in ids:
                    return True
    return False


def fetch_works(client: OpenAlexClient, author_ids: list[str], since: str, strict_institution: str = "") -> list[dict]:
    """All works by any of these author records, newest first, slimmed down.

    With strict_institution, only works where one of these authors is listed
    at that institution (for common names whose records mix people).
    """
    if not author_ids:
        return []
    ids = set(author_ids)
    filt = f"author.id:{'|'.join(author_ids)},from_publication_date:{since}"
    if strict_institution:
        filt += f",institutions.id:{strict_institution}"
    out, cursor = [], "*"
    while cursor:
        data = client.get(
            "/works",
            {
                "filter": filt,
                "select": WORK_FIELDS,
                "per_page": 200,
                "cursor": cursor,
                "sort": "publication_date:desc",
            },
        )
        for w in data.get("results", []):
            if w.get("is_retracted") or w.get("is_paratext") or not w.get("title"):
                continue
            if strict_institution and not _listed_at(w, ids, strict_institution):
                continue
            src = ((w.get("primary_location") or {}).get("source") or {})
            out.append(
                {
                    "id": short_id(w["id"]),
                    "doi": w.get("doi") or "",
                    "title": re.sub(r"<[^>]+>", "", w["title"]).strip(),
                    "year": w.get("publication_year"),
                    "type": w.get("type", ""),
                    "venue": src.get("display_name") or "",
                    "abstract": abstract_text(w.get("abstract_inverted_index"))[:1500],
                    "topics": [t["display_name"] for t in (w.get("topics") or [])[:3]],
                    "authors": [short_id(a["author"]["id"]) for a in w.get("authorships", [])
                                if (a.get("author") or {}).get("id")],
                    "awards": [
                        {"funder": a.get("funder_display_name", ""), "award": a.get("funder_award_id", "")}
                        for a in (w.get("awards") or [])
                    ],
                }
            )
        cursor = (data.get("meta") or {}).get("next_cursor")
        if not data.get("results"):
            break
    seen, uniq = set(), []
    for w in out:
        key = re.sub(r"\W+", " ", w["title"].lower()).strip()
        if key in seen:
            continue  # preprint and published version of the same paper
        seen.add(key)
        uniq.append(w)
    return uniq


# ---------------------------------------------------------------- per-record check

MIN_RECORD_WORKS = 3  # fewer works than this: too little to judge a record


def works_by_record(works: list[dict], author_ids: list[str]) -> dict[str, list[dict]]:
    """Split a strict match's works by which of its author records wrote them."""
    out: dict[str, list[dict]] = {a: [] for a in author_ids}
    for w in works:
        for a in author_ids:
            if a in w.get("authors", []):
                out[a].append(w)
    return out


def pick_records(scores: dict[str, float | None], counts: dict[str, int],
                 min_abs: float, margin: float) -> tuple[list[str], list[str]]:
    """Which author records of a strict match to keep, from per-record agreement.

    A strict match merges every same-name record with a home affiliation, so
    a namesake in another field can leak in. A record is dropped when its
    papers agree with the person's own description below `min_abs`, or more
    than `margin` below the best-agreeing record. Records with too few works
    (or no score) are kept: there is too little to judge. Returns (kept, dropped).
    """
    judged = {a: s for a, s in scores.items() if s is not None and counts.get(a, 0) >= MIN_RECORD_WORKS}
    if len(judged) < 2:
        return list(scores), []  # one record or none to compare: the person-level check covers it
    best = max(judged.values())
    dropped = [a for a, s in judged.items() if s < min_abs or s < best - margin]
    return [a for a in scores if a not in dropped], dropped
