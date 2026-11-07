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
    assert search_queries("Zachary (Zak) Rubin") == ["zachary rubin", "zak rubin"]


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
