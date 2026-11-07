import pytest

from research_map.bundle import privacy_problems, scrub
from research_map.cli import coauthor_pairs
from research_map.text import Doc, recency_weight


def test_scrub_removes_contacts():
    text = "Write to jane.doe@example.edu or call (425) 352-5000 about tilings."
    out = scrub(text)
    assert "@" not in out and "352" not in out and "tilings" in out


def test_privacy_scan_flags_ids_but_not_years_or_dois():
    assert privacy_problems('{"t":"Paper 2019","u":"https://doi.org/10.1145/3287324.3287440"}') == []
    assert privacy_problems('{"x":"123-45-6789"}') == ["123-45-6789"]
    assert privacy_problems('{"x":"a@b.org"}') == ["a@b.org"]


def test_write_html_refuses_contact_details(tmp_path):
    from research_map.bundle import write_html

    web = tmp_path / "web"
    (web / "vendor").mkdir(parents=True)
    for name in ("template.html", "map.css", "map.js", "search.js", "vendor/d3.v7.9.0.min.js"):
        (web / name).write_text("/*__DATA__*/" if name == "template.html" else "")
    with pytest.raises(ValueError):
        write_html({"meta": {"name": "x"}, "bio": "mail me@x.org"}, web, tmp_path / "out.html")


def test_coauthor_pairs_count_shared_papers_once():
    works = {
        "ann": [{"id": "W1", "authors": ["A1", "A2"]}, {"id": "W2", "authors": ["A1", "A2", "A9"]}],
        "bob": [{"id": "W1", "authors": ["A1", "A2"]}],
    }
    pairs = coauthor_pairs(works, {"ann": ["A1"], "bob": ["A2"]})
    assert pairs == {"ann": {"bob": 2}, "bob": {"ann": 2}}


def test_components_and_recency():
    assert recency_weight(2024, 2026) == 1.0 and recency_weight(2012, 2026) == 0.6 and recency_weight(1990, 2026) == 0.35
    d = Doc("x", {"keywords": "tilings"}, works=[{"title": "T", "abstract": "A", "year": 2025, "venue": "V"}],
            courses="Discrete math")
    c = d.components(2026)
    assert set(c) == {"self", "works", "venues", "courses"}
    assert c["works"] == [("T. A", 1.0)] and c["venues"] == [("V", 1.0)]
    assert Doc("y", {}).components(2026) == {}


def test_privacy_scan_ignores_links_and_page_ranges():
    blob = '{"u":"https://doi.org/10.1007/978-981-97-4581-2_3","t":"Proc. 383-390.4492 x"}'
    assert privacy_problems(blob) == []
    assert privacy_problems('{"b":"call 425.352.5000"}') == ["425.352.5000"]
    assert privacy_problems('{"b":"call (425) 352-5000"}') == ["(425) 352-5000"]


def test_label_overrides_follow_members(tmp_path):
    from research_map.cli import apply_label_overrides

    f = tmp_path / "labels.yaml"
    f.write_text("- {level: area, member: bob, label: Robotics}\n- {level: area, member: cy, label: Dup}\n- {level: area, member: zed, label: Gone}\n")
    clusters, names = [0, 1, 1], {0: ["a"], 1: ["b"]}
    apply_label_overrides(f, ["ann", "bob", "cy"], {"area": (clusters, names)})
    assert names == {0: ["a"], 1: ["Robotics"]}
