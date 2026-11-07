from research_map.profiles import parse_profile
from research_map.text import build_doc, research_bio

PROFILE = """
<aside><h3 class="faculty-sidebar-heading">Websites</h3>
<div class="faculty-sidebar-content">
 <div><a href="/stem/about/departments/css">CSS</a></div>
 <div><a href="https://example.org/me/">Faculty website</a></div>
 <div><a href="https://orcid.org/0000-0002-1825-0097">ORCID</a></div>
</div></aside>
<h2 class="faculty-profile-role">Teaching Professor</h2></div></div>
<div><div class="margin-b-sm"><div><p>Dr. Doe studies computer games and education. She joined UW Bothell in 2017.</p></div></div>
<div class="margin-b-sm"><h3 class="faculty-main-content-heading">Education</h3>
<div class="faculty-main-content"><ul><li><strong>Northwestern</strong><ul><li>Ph.D. 1998, <em>An integrated architecture</em></li></ul></li></ul></div></div>
<div class="margin-b-sm"><h3 class="faculty-main-content-heading">Research and Scholarship Interests</h3>
<div class="faculty-main-content"><p>Computer Science Education, Computer Games</p></div></div>
"""


def test_parse_profile():
    p = parse_profile(PROFILE)
    assert p.bio.startswith("Dr. Doe studies computer games")
    assert p.research_interests == "Computer Science Education, Computer Games"
    assert p.thesis == "An integrated architecture"
    assert p.orcid == "0000-0002-1825-0097"
    assert ("Faculty website", "https://example.org/me/") in p.links
    assert all("uwb.edu" not in h and h.startswith("http") for _, h in p.links)


def test_research_bio_drops_career_sentences():
    assert research_bio(parse_profile(PROFILE).bio) == "Dr. Doe studies computer games and education."


def test_build_doc_fields():
    from dataclasses import asdict

    d = build_doc("doe", "games, education", asdict(parse_profile(PROFILE)))
    assert d.fields["keywords"] == "games, education"
    assert d.fields["interests"].startswith("Computer Science Education")
    assert d.fields["thesis"] == "An integrated architecture"
    assert [w for _, w in d.weighted] == [1.0, 1.0, 0.5, 0.7]
    assert build_doc("x", "", None).weighted == []
