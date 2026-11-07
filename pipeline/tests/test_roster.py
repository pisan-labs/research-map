from research_map.roster import (
    dedupe,
    id_from_url,
    parse_directory,
    parse_research_areas,
    split_name_title,
)

BASE = "https://www.uwb.edu/"

# Trimmed from the real division pages: program h2, category h3, person h4 or h3.
DIRECTORY = """
<main>
<h1>Department of Engineering &amp; Mathematics Faculty</h1>
<h2>Mathematics</h2>
<h3>Full-time faculty</h3>
<div><h4 class="wp-block-heading"><a href="https://www.uwb.edu/faculty/casey-mann/">Casey Mann, Professor</a></h4>
<p>UW2-123<br><a href="mailto:person@example.edu">person@example.edu</a></p>
<p><strong>Research</strong>: tilings, discrete geometry</p></div>
<div><h4><a href="/faculty/no-research/">Pat Doe, Assistant Teaching Professor</a></h4>
<p>UW2-1<br><a href="mailto:other@example.edu">other@example.edu</a></p></div>
<h3>Affiliated faculty</h3>
<div><h4><a href="/faculty/aff-person/">Aff Person, Affiliate Instructor</a></h4></div>
<h2>Physics</h2>
<h3>Full-time faculty</h3>
<div><h3 class="wp-block-heading"><a href="/faculty/jeffrey-jensen/">Jeff Jensen, Teaching Professor</a></h3>
<p><strong>Research:</strong> ecology,
  field biology</p></div>
<h2>Research areas</h2>
<h4><a href="/faculty/should-not-appear/">Not A Person, Professor</a></h4>
</main>
<div class="accordion">
 <button class="js-accordion-title">In this section</button>
 <div class="js-accordion-body"><ul><li><a href="/stem/about">About</a></li></ul></div>
 <button class="js-accordion-title">Discrete Mathematics</button>
 <div class="js-accordion-body"><ul><li><a href="https://www.uwb.edu/faculty/casey-mann/">Casey Mann</a></li></ul></div>
</div>
"""


def test_parse_directory_programs_categories_and_keywords():
    people = parse_directory(DIRECTORY, "Engineering & Mathematics", BASE)
    assert [p.id for p in people] == ["casey-mann", "no-research", "aff-person", "jeffrey-jensen"]
    mann, doe, aff, jensen = people
    assert (mann.program, mann.category, mann.title) == ("Mathematics", "Full-time faculty", "Professor")
    assert mann.keywords == "tilings, discrete geometry"
    assert doe.keywords == ""
    assert aff.category == "Affiliated faculty"
    assert (jensen.program, jensen.keywords) == ("Physics", "ecology, field biology")
    assert jensen.profile_url == "https://www.uwb.edu/faculty/jeffrey-jensen/"


def test_research_areas_skip_navigation():
    assert parse_research_areas(DIRECTORY, BASE) == {"Discrete Mathematics": ["casey-mann"]}


def test_ids_and_names():
    assert id_from_url("https://www.uwb.edu/faculty/jeffrey-jensen/", "Jeff Jensen") == "jeffrey-jensen"
    assert id_from_url("https://www.uwb.edu/faculty/?p=716", "Aaron Enten") == "aaron-enten"
    assert split_name_title("Yusuf Pisan, Teaching Professor") == ("Yusuf Pisan", "Teaching Professor")


def test_dedupe_keeps_first():
    people = parse_directory(DIRECTORY, "A", BASE) + parse_directory(DIRECTORY, "B", BASE)
    out = dedupe(people)
    assert len(out) == 4 and all(p.department == "A" for p in out)


def test_uwt_names():
    from research_map.adapters import split_uwt_department, uwt_name

    assert uwt_name("Abraham, Isaac") == "Isaac Abraham"
    assert uwt_name("Endo, PhD/SPHR , Rachel") == "Rachel Endo"
    assert uwt_name("Adams - Free Man of Color, Luther") == "Luther Adams"
    assert uwt_name("Barnes Jr, Gordon R.") == "Gordon R. Barnes Jr"
    assert split_uwt_department("Sciences and Mathematics, Department of School of Interdisciplinary Arts and Sciences") == (
        "School of Interdisciplinary Arts and Sciences", "Sciences and Mathematics")
    assert split_uwt_department("Engineering & Technology, School of") == (
        "School of Engineering & Technology", "School of Engineering & Technology")
