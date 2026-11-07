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
