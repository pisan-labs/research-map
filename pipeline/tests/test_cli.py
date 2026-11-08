from research_map import cli, roster
from research_map.roster import Person


def test_read_people_applies_opt_out(tmp_path):
    (tmp_path / "rosters").mkdir()
    people = [Person("a-b", "A B", "Professor", "D", "D", "", "", ""), Person("c-d", "C D", "Professor", "D", "D", "", "", "")]
    roster.write_csv(people, tmp_path / "rosters" / "x.csv")
    cfg = {"slug": "x", "opt_out": ["c-d"]}
    assert [p.id for p in cli.read_people(tmp_path, cfg)] == ["a-b"]
