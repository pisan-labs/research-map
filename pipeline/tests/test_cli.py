from research_map import cli, roster
from research_map.roster import Person


def test_read_people_applies_opt_out(tmp_path):
    (tmp_path / "rosters").mkdir()
    people = [Person("a-b", "A B", "Professor", "D", "D", "", "", ""), Person("c-d", "C D", "Professor", "D", "D", "", "", "")]
    roster.write_csv(people, tmp_path / "rosters" / "x.csv")
    cfg = {"slug": "x", "opt_out": ["c-d"]}
    assert [p.id for p in cli.read_people(tmp_path, cfg)] == ["a-b"]


def test_check_strict_records_drops_namesake(capsys):
    import argparse

    import numpy as np

    from research_map.openalex import Match

    class FakeEmbedder:  # "robot" texts point one way, "tumour" texts another
        def encode(self, texts):
            return np.array([[1.0, 0.0] if "robot" in t.lower() else [0.0, 1.0] for t in texts], dtype=np.float32)

    p = Person("j-s", "J S", "Professor", "D", "D", "", "robot learning", "")
    m = Match("j-s", ["A1", "A2"], ["J. S", "J. S"], 0, "strict")
    works = {"j-s": [{"title": f"Robot grasping {i}", "year": 2024, "authors": ["A1"]} for i in range(4)]
             + [{"title": f"Tumour imaging {i}", "year": 2024, "authors": ["A2"]} for i in range(4)]}
    args = argparse.Namespace(min_agreement_home=0.10, record_margin=0.20)
    cli.check_strict_records(m, p, None, works, FakeEmbedder(), 2026, args)
    assert m.author_ids == ["A1"] and m.names == ["J. S"]
    assert all("Robot" in w["title"] for w in works["j-s"])
    assert "dropped record A2 from J S" in capsys.readouterr().err


def test_db_url_from_password(monkeypatch):
    from research_map import db

    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_DB_PASSWORD", "p@ss/w:rd")
    url = db.connection_string()
    assert url.startswith("postgresql://postgres.arktxlrlyceffyozdwhq:p%40ss%2Fw%3Ard@")
    assert url.endswith(":5432/postgres")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://x")
    assert db.connection_string() == "postgresql://x"
