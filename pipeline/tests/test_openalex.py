from research_map.openalex import abstract_text, name_matches, norm_name


def test_name_matching():
    assert name_matches("Jeff Jensen", "Jeffrey S. Jensen")
    assert name_matches("Zachary (Zak) Rubin", "Zak Rubin")
    assert name_matches("Pierre Mourad", "Pierre D. Mourad")
    assert name_matches("Eric Salathé Jr.", "Eric P. Salathé")
    assert not name_matches("Zhao (Joanna) Wang", "Lei Wang")
    assert not name_matches("Zhao (Joanna) Wang", "Z. Wang")
    assert not name_matches("Jeffrey D. Kim", "Jeffrey J. Kim")
    assert not name_matches("Guy Hamilton", "Tim Hamilton")
    assert norm_name("Zhao (Joanna) Wang") == ["zhao", "wang"]


def test_abstract_from_inverted_index():
    assert abstract_text({"world": [1], "hello": [0], "again": [2]}) == "hello world again"
    assert abstract_text(None) == ""


def test_nicknames_not_prefixes():
    assert name_matches("Zhao (Joanna) Wang", "Zhao Wang")
    assert not name_matches("Zhao (Joanna) Wang", "Zhaoming Wang")
    assert name_matches("Rick McLaughlin", "Richard McLaughlin")
    assert name_matches("Bill Anderson", "William Anderson")


def test_search_queries_drop_middle_initials():
    from research_map.openalex import search_queries

    assert search_queries("Erika F. Parsons") == ["erika parsons"]
    assert search_queries("Zachary (Zak) Rubin")[:2] == ["zachary rubin", "zak rubin"]


def test_listed_at_checks_this_authors_institution():
    from research_map.openalex import _listed_at

    w = {"authorships": [
        {"author": {"id": "https://openalex.org/A1"}, "institutions": [{"id": "https://openalex.org/I9"}]},
        {"author": {"id": "https://openalex.org/A2"}, "institutions": [{"id": "https://openalex.org/I4210138624"}]},
    ]}
    assert _listed_at(w, {"A2"}, "I4210138624")
    assert not _listed_at(w, {"A1"}, "I4210138624")


def test_search_queries_keep_hyphenated_surnames():
    from research_map.openalex import search_queries

    assert "eyhab al-masri" in search_queries("Eyhab Al-Masri")


def test_search_queries_keep_apostrophe_surnames():
    from research_map.openalex import search_queries

    assert "eleanor o'rourke" in search_queries("Eleanor O'Rourke")


def test_family_name_must_end_candidate_name_and_short_forms_searched():
    from research_map.openalex import search_queries

    from research_map.openalex import _name_hits, name_match_kind

    assert name_match_kind("Simon Peter", "Simon Peter Horslen") == "loose"
    assert name_match_kind("Yan Chen", "Chen Yan") == "exact"
    hits = _name_hits("Simon Peter", [{"display_name": "Simon Peter Horslen"}, {"display_name": "Simon Peter"}])
    assert [h["display_name"] for h in hits] == ["Simon Peter"]
    assert _name_hits("Pedram Khalili", [{"display_name": "Pedram Khalili Amiri"}])
    assert "dan grossman" in search_queries("Daniel Grossman")


def test_works_by_record():
    from research_map.openalex import works_by_record
    works = [{"id": "W1", "authors": ["A1", "X"]}, {"id": "W2", "authors": ["A2"]}, {"id": "W3", "authors": ["A1"]}]
    split = works_by_record(works, ["A1", "A2", "A3"])
    assert [w["id"] for w in split["A1"]] == ["W1", "W3"]
    assert [w["id"] for w in split["A2"]] == ["W2"]
    assert split["A3"] == []


def test_pick_records_drops_namesake_record():
    from research_map.openalex import pick_records
    counts = {"cs": 40, "med": 30, "tiny": 1}
    # The medicine record disagrees with a CS profile; the tiny one is not judged.
    kept, dropped = pick_records({"cs": 0.45, "med": 0.12, "tiny": 0.0}, counts, 0.10, 0.20)
    assert dropped == ["med"] and kept == ["cs", "tiny"]
    # Two records in the same field: both kept.
    kept, dropped = pick_records({"cs": 0.45, "cs2": 0.38}, {"cs": 40, "cs2": 20}, 0.10, 0.20)
    assert dropped == [] and kept == ["cs", "cs2"]
    # Below the absolute floor even if close to the best.
    kept, dropped = pick_records({"a": 0.12, "b": 0.05}, {"a": 10, "b": 10}, 0.10, 0.20)
    assert dropped == ["b"]
    # Only one judgeable record: nothing to compare, keep all.
    kept, dropped = pick_records({"a": 0.05, "b": None}, {"a": 10, "b": 0}, 0.10, 0.20)
    assert dropped == [] and kept == ["a", "b"]


def test_budget_429_stops_without_retrying(tmp_path):
    import httpx
    import pytest
    from research_map.openalex import BudgetExceeded, OpenAlexClient

    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(429, headers={"retry-after": "40577", "x-ratelimit-remaining-usd": "0.0003"},
                              json={"message": "Insufficient budget. Resets at midnight UTC."})

    c = OpenAlexClient(tmp_path, delay=0)
    c.http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(BudgetExceeded, match="daily budget"):
        c.get("/authors", {"search": "x"})
    assert len(calls) == 1


def test_names_with_letters_nfkd_drops():
    from research_map.openalex import name_match_kind, norm_name

    assert norm_name("Magdalena Bałazińska") == ["magdalena", "balazinska"]
    assert name_match_kind("Magdalena Balazinska", "Magdalena Bałazińska") == "exact"
    assert name_match_kind("Thomas Rothvoss", "Thomas Rothvoß") == "exact"
    assert name_match_kind("Su-In Lee", "Su‐In Lee") == "exact"  # U+2010 hyphen


def test_short_roster_names_also_search_full_forms():
    from research_map.openalex import name_match_kind, search_queries

    assert "michael averkiou" in search_queries("Mike Averkiou")
    assert "kimberly ingraham" in search_queries("Kim Ingraham")
    assert name_match_kind("Kim Ingraham", "Kimberly Ingraham") == "exact"


def test_curly_apostrophe_surname():
    from research_map.openalex import name_match_kind

    assert name_match_kind("Michelle O'Malley", "Michelle O’Malley") == "exact"
